"""Bounded AI operations, source grounding and resumable essay writing."""
from __future__ import annotations
import asyncio
import json
import math
import os
import re
from google import genai
from google.genai import types

from app.essay.models import (QuestionSet, EssayPlan, EvidenceSet, ChapterPayload, EssayReview,
                               EvidenceExcerpt, identifier, now)
from app.essay.settings import stage_model
from app.essay.prompts import instructions, context, source_context, as_json
from app.essay.citations import evidence_index, validate_citations, content_hash, reference_checks
from app.essay.sources import acquire_url
from app.services.usage_service import metered_call, usage_summary
from app.persistence.sqlite_store import PROGRESS_FIELDS
from app.agent.narrative_memory import source_evidence


async def request(session, phase, prompt, schema=None, *, search=False):
    key = os.getenv("GOOGLE_API_KEY")
    if not key:
        raise ValueError("Configura GOOGLE_API_KEY nel file .env per usare la generazione.")
    model = stage_model(session.form_data, phase)
    output_limit = {"questions": 3072, "research": 4096, "evidence": 8192}.get(phase, 32768)
    config = {"system_instruction": instructions(session.form_data), "max_output_tokens": output_limit}
    if schema is not None:
        config.update(response_mime_type="application/json", response_schema=schema)
    if search:
        config["tools"] = [types.Tool(google_search=types.GoogleSearch())]
    client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=180000))
    try:
        last = None
        for attempt in range(2):
            try:
                from app.agent.session_store import get_session_store
                assert_budget(get_session_store(), session)
                result = await metered_call(lambda: client.aio.models.generate_content(
                    model=model, contents=prompt, config=types.GenerateContentConfig(**config)),
                    session_id=session.session_id, model=model, phase="essay-" + phase)
                if schema is None:
                    return result
                parsed = getattr(result, "parsed", None)
                return schema.model_validate(parsed) if parsed is not None else schema.model_validate_json(result.text)
            except Exception as exc:
                last = exc
                # Retry a transient server/transport failure or malformed model output once.
                code = getattr(exc, "code", None)
                if code in {400, 401, 403, 404}:
                    raise
                if attempt == 0:
                    await asyncio.sleep(1)
        raise last
    finally:
        await client.aio.aclose()
        client.close()


def assert_budget(store, session):
    if session.form_data.budget_eur is None:
        return
    summary = usage_summary(session, store.usage_events(session.session_id))
    if (summary["converted_cost_eur"] or 0) >= session.form_data.budget_eur:
        raise ValueError("Il limite di spesa impostato è stato raggiunto. Aumentalo nel progetto per continuare.")


def progress(store, sid, kind, **updates):
    session = store.get_session(sid)
    field = PROGRESS_FIELDS[kind]
    setattr(session, field, (getattr(session, field) or {}) | updates | {"updated_at": now()})
    store.save_session(session)
    return session


def validate_plan(plan, session):
    known = evidence_index(session.sources)
    if any(e not in known for c in plan.claims for e in c.evidence_ids):
        raise ValueError("Il piano contiene un'evidenza non registrata.")
    if session.form_data.profile == "academic" and not plan.method.strip():
        raise ValueError("Il piano accademico deve dichiarare il metodo.")
    # Allocate the author's requested extent, independent of the writing mode.
    total = sum(s.word_target for s in plan.sections)
    target = session.form_data.target_words
    if not 200 * len(plan.sections) <= target <= 8000 * len(plan.sections):
        raise ValueError("Il numero di capitoli non è adatto alla lunghezza scelta. Rigenera o modifica l'indice.")
    allocations = [max(200, min(8000, round(section.word_target * target / total))) for section in plan.sections]
    difference = target - sum(allocations)
    while difference:
        for index in range(len(allocations)):
            delta = 1 if difference > 0 else -1
            if 200 <= allocations[index] + delta <= 8000:
                allocations[index] += delta
                difference -= delta
                if not difference:
                    break
    for section, allocation in zip(plan.sections, allocations):
        section.word_target = allocation
    return plan


async def generate_questions(store, session):
    if session.generated_questions:
        return
    result = await request(session, "questions", as_json(context(session)) + """
Genera 3-5 domande brevi in italiano, utili al profilo scelto e al ruolo AI.
Non chiedere quanto è già specificato. Usa id Q1, Q2 ecc. Solo testo libero.""", QuestionSet)
    session = store.get_session(session.session_id)
    session.generated_questions = [q.model_dump() for q in result.questions]
    store.save_session(session)


async def generate_plan(store, session):
    previous_version = (session.draft_progress or {}).get("source_version", session.current_version)
    if session.plan and session.current_version > previous_version:
        return  # A result committed before a restart must not be purchased again.
    prompt = as_json(context(session)) + """
Produci un progetto editoriale completo per un libro italiano. Non scrivere ancora i capitoli.
Titolo e sottotitolo possono usare le preferenze del brief. La direction deve essere una tesi,
domanda interpretativa o domanda/ipotesi, coerente con il profilo e il ruolo AI.
In modalità support non proporre una tesi alternativa; in explore confronta posizioni nel piano.
Claims: identifica premesse e ragioni, tipo di affermazione, obiezione, risposta e lacuna.
Usa soltanto evidence_ids realmente presenti. Se mancano prove fattuali, dichiaralo in gap.
Sections: indice dall'introduzione alla conclusione, id unici C1, C2 ecc.; funzione, descrizione,
claim_ids e word_target. Distribuisci target_words tra le sezioni, con 400-4500 parole per capitolo
e abbastanza capitoli per la lunghezza richiesta. Se target_words è 1000, usa 2-4 sezioni di 250-500 parole. La bibliografia verrà generata separatamente.
Accademico: metodo e corpus veri, stato della questione, analisi, discussione, limiti;
non fingere raccolte di dati svolte. Divulgativo: spiega i concetti e non forzare una polemica.
Fornisci definitions e limits. Segnala le proposte all'autore, che approverà il piano."""
    plan = validate_plan(await request(session, "plan", prompt, EssayPlan), session)
    session = store.get_session(session.session_id)
    session.plan = plan.model_dump()
    session.current_version += 1
    session.validated = False
    session.review = None
    store.save_session(session)


async def analyze_sources(store, session):
    sources = [s for s in session.sources if s["status"] == "acquired"]
    for index, source in enumerate(sources):
        session = progress(store, session.session_id, "memory", current_step=index, total_steps=len(sources),
                           current_section_name=source["title"])
        assert_budget(store, session)
        result = await request(session, "evidence", as_json({"brief": session.form_data.model_dump(),
            "source_id": source["id"], "title": source["title"], "kind": source["kind"],
            "text": source["text"]}) + """
Trova fino a cinque estratti pertinenti. Copia quote letterali dal testo, non parafrasi,
tra 8 e 1000 caratteri. Classifica supports/contradicts/mixed/context rispetto alla domanda/tesi.
Non trattare appunti personali come riscontro esterno. explanation spiega ciò che l'estratto
sostiene e ciò che non permette di concludere. È lecito non trovare estratti pertinenti.""", EvidenceSet)
        excerpts = []
        for payload in result.excerpts:
            quote = source_evidence(payload.quote, source["text"])
            if quote is None:
                raise ValueError("L'analisi ha proposto una citazione assente dalla fonte: nessuna evidenza inventata è stata salvata.")
            start = source["text"].find(quote)
            prefix = source["text"][:start]
            import re
            pages = re.findall(r"\[Pagina (\d+)\]", prefix)
            locator = "Pagina " + pages[-1] if pages else "Caratteri " + str(start + 1) + "–" + str(start + len(quote))
            excerpts.append(EvidenceExcerpt(id=identifier("E"), source_id=source["id"], quote=quote,
                locator=locator, start=start, end=start+len(quote), stance=payload.stance,
                explanation=payload.explanation).model_dump())
        session = store.get_session(session.session_id)
        current = next(s for s in session.sources if s["id"] == source["id"])
        # Retain manually curated excerpts.
        current["evidence"] += excerpts
        current["status"] = "analyzed"
        session.validated = False
        session.review = None
        store.save_session(session)


def grounded_search_results(result):
    candidate = (getattr(result, "candidates", None) or [None])[0]
    metadata = getattr(candidate, "grounding_metadata", None)
    chunks = getattr(metadata, "grounding_chunks", None) or []
    seen, records = set(), []
    for chunk in chunks:
        web = getattr(chunk, "web", None)
        url = getattr(web, "uri", None)
        if url and url not in seen:
            seen.add(url)
            records.append({"url": url, "title": getattr(web, "title", "") or url})
    return records, list(getattr(metadata, "web_search_queries", None) or []), \
        getattr(getattr(metadata, "search_entry_point", None), "rendered_content", "") or ""


async def research(store, session):
    pending = session.research_request
    if not pending.get("discovered"):
        result = await request(session, "research", as_json({"topic": session.form_data.topic,
            "question": session.form_data.question, "thesis": session.form_data.thesis,
            "profile": session.form_data.profile, "criteria": session.form_data.source_criteria,
            "period": session.form_data.source_period, "query": pending["query"]}) + """
    Esegui una ricerca Google di fonti pertinenti, dirette quando disponibili. Cerca anche
    prove contrarie o interpretazioni concorrenti. Individua fino a sei documenti e cita i risultati.
    Non dichiarare di aver letto una fonte non accessibile.""", search=True)
        records, queries, suggestions = grounded_search_results(result)
        session = store.get_session(session.session_id)
        existing = {s.get("url") for s in session.sources}
        # Persist discovered references before fetching, so acquisition can resume.
        for record in records[:6]:
            if record["url"] not in existing:
                from app.essay.models import SourceRecord
                session.sources.append(SourceRecord(id=identifier("S"), title=record["title"], url=record["url"],
                    kind="web", selection_reason=pending["query"]).model_dump())
        session.research_log.append({"query": pending["query"], "provider_queries": queries,
            "at": now(), "found": len(records[:6]), "provider_results": len(records), "suggestions_html": suggestions,
            "summary": (getattr(result, "text", None) or "")[:12000]})
        # Tool charges can depend on account quota; never report them as measured token costs.
        events = store.usage_events(session.session_id)
        for event in reversed(events):
            if event["phase"] == "essay-research":
                event["tool_cost_unknown"] = True
                event["search_queries"] = queries
                store.record_usage(event)
                break
        session.validated = False
        session.review = None
        session.research_request["discovered"] = bool(records)
        store.save_session(session)
        if not records:
            raise ValueError("Il servizio non ha restituito fonti tracciabili. Prova una ricerca più specifica o importa un documento.")
    candidates = [s for s in session.sources if s["status"] == "proposed" and s["kind"] == "web"]
    for index, source in enumerate(candidates):
        session = progress(store, session.session_id, "memory", current_step=index, total_steps=len(candidates),
                           current_section_name=source["title"])
        try:
            acquired = await acquire_url(source["url"], source["title"])
            update = {"text": acquired["text"], "url": acquired["url"], "title": acquired["title"],
                "content_hash": content_hash(acquired["text"]), "status": "acquired", "acquired_at": now(), "error": "",
                "author": acquired.get("author", ""), "published": acquired.get("published", "")}
        except Exception as exc:
            update = {"status": "failed", "error": str(exc)[:1000]}
        session = store.get_session(session.session_id)
        next(s for s in session.sources if s["id"] == source["id"]).update(update)
        store.save_session(session)
    await analyze_sources(store, store.get_session(session.session_id))


def validate_review(review, chapters):
    by_id = {c.get("section_id"): c for c in chapters}
    for issue in review.issues:
        if issue.section_id and issue.section_id not in by_id:
            raise ValueError("La revisione richiama un capitolo inesistente.")
        if issue.quote:
            targets = [by_id[issue.section_id]] if issue.section_id else chapters
            matched = next((source_evidence(issue.quote, c["content"]) for c in targets
                            if source_evidence(issue.quote, c["content"])), None)
            if matched is None:
                raise ValueError("Il passaggio segnalato dalla revisione non compare nel manoscritto.")
            issue.quote = matched
    return review


async def review_chapters(session, chapters):
    return validate_review(await request(session, "review", as_json({
        "brief": session.form_data.model_dump(), "plan": session.plan,
        "evidence": source_context(session, priority_ids=list(re.findall(r"\[@([^\]]+)\]", " ".join(c["content"] for c in chapters)))), "chapters": chapters}) + """
Valuta soltanto il materiale fornito secondo il profilo. Nessun voto di verità.
Riporta problemi di logica, evidenza, obiezioni, metodo o stile.
Ogni issue indica section_id esistente e quote esatta quando riguarda un passaggio.
Per mancanze strutturali puoi lasciare quote vuota. Un'opinione dichiarata non è un fatto senza prova.
Non inventare difetti o fonti mancanti. In support migliora le ragioni senza suggerire una tesi alternativa.
Distingui blocking, important e suggestion. Un risultato accademico inconclusivo può essere corretto.
Non certificare l'accuratezza del mondo: esamina l'uso degli estratti acquisiti.""", EssayReview), chapters)


async def checked_chapter(session, phase, prompt, *, target_words=0):
    original = prompt
    for attempt in range(2):
        payload = await request(session, phase, prompt, ChapterPayload)
        try:
            validate_citations(payload.content, session.sources)
            if target_words and len(payload.content.split()) < max(50, round(target_words * .4)):
                raise ValueError("La parte è troppo breve rispetto alle parole richieste.")
            return payload
        except ValueError as error:
            if attempt:
                raise
            prompt = original + "\nLa risposta precedente non supera i controlli: " + str(error) + \
                "\nCorreggila. Ogni riferimento deve avere la forma singola [@IDENTIFICATIVO_ESATTO]. " + \
                "Per due evidenze scrivi due marcatori separati; non usare ellissi o elenchi dentro un marcatore. " + \
                "Mantieni la lunghezza richiesta e usa esclusivamente gli identificativi forniti.\nRisposta precedente:\n" + \
                as_json(payload.model_dump())


async def write_book(store, session):
    if not session.plan or not session.validated:
        raise ValueError("Approva il progetto editoriale prima di iniziare la scrittura.")
    sections = session.plan["sections"]
    total = len(sections)
    for index, section in enumerate(sections):
        session = store.get_session(session.session_id)
        existing = next((c for c in session.book_chapters if c["section_id"] == section["id"]), None)
        if existing and not existing.get("review_stale", False):
            continue
        if session.pause_requested:
            progress(store, session.session_id, "book", status="paused", error=None,
                     current_step=index, total_steps=total)
            return
        assert_budget(store, session)
        if existing is None:
            part_count = max(1, math.ceil(section["word_target"] / 1300))
            checkpoint = getattr(session, "part_checkpoint", None) or {}
            parts = checkpoint.get("parts", []) if checkpoint.get("section_id") == section["id"] else []
            for part in range(len(parts), part_count):
                session = progress(store, session.session_id, "book", current_step=index, total_steps=total,
                    current_section_name=section["title"], current_part=part + 1, total_parts=part_count)
                assert_budget(store, session)
                claims = [c for c in session.plan["claims"] if c["id"] in section["claim_ids"]]
                prompt = as_json({"brief": session.form_data.model_dump(), "approved_direction": session.plan["direction"],
                    "method": session.plan["method"], "definitions": session.plan["definitions"], "section": section,
                    "claims": claims, "evidence": source_context(session, priority_ids=[e for c in claims for e in c["evidence_ids"]]),
                    "previous_arguments": [{"title": c["title"], "summary": c.get("summary", "")} for c in session.book_chapters],
                    "current_parts": [p["content"] for p in parts], "part": part+1, "parts": part_count,
                    "target_words_this_part": round(section["word_target"] / part_count)}) + """
Scrivi la parte richiesta in italiano, come prosa saggistica sviluppata. Mantieni la direzione approvata.
Cita con un marcatore [@IDENTIFICATIVO_ESATTO] per ogni evidence_id. Due evidenze richiedono due marcatori separati. Usa soltanto evidence_id presenti e solo dove l'estratto è pertinente.
Non creare bibliografia o citazioni autore-data a mano: saranno composte dal registro.
Non attribuire agli estratti numeri, contesti o conclusioni assenti. Gli esempi ipotetici sono etichettati.
Non fingere esperienze dell'autore. Usa sottotitoli quando aiutano; non ripetere il titolo del capitolo.
Avanza l'argomentazione senza ripetere le parti precedenti; la conclusione della sezione appartiene
solo all'ultima parte. Segnala lacune in unresolved e qualificane le affermazioni nel testo.
summary sintetizza ragioni e conclusioni realmente sviluppate, non una lista di fatti inventati."""
                payload = await checked_chapter(session, "chapters", prompt,
                    target_words=round(section["word_target"] / part_count))
                parts.append(payload.model_dump())
                session = store.get_session(session.session_id)
                session.part_checkpoint = {"section_id": section["id"], "parts": parts}
                store.save_session(session)
            chapter = {"section_id": section["id"], "section_index": index, "title": section["title"],
                "content": "\n\n".join(p["content"] for p in parts), "summary": " ".join(p["summary"] for p in parts),
                "unresolved": [x for p in parts for x in p["unresolved"]], "review_stale": session.form_data.revision_mode == "reviewed"}
            session = store.get_session(session.session_id)
            session.book_chapters.append(chapter)
            session.part_checkpoint = None
            session.review = None
            store.save_session(session)  # Draft chapter and checkpoint committed together.
        session = store.get_session(session.session_id)
        chapter = next(c for c in session.book_chapters if c["section_id"] == section["id"])
        if session.form_data.revision_mode == "reviewed" and chapter.get("review_stale"):
            reviewed = await review_chapters(session, [chapter])
            if any(i.severity == "blocking" for i in reviewed.issues):
                revised = await checked_chapter(session, "revision", as_json({"brief": session.form_data.model_dump(),
                    "approved_direction": session.plan["direction"], "chapter": chapter,
                    "issues": reviewed.model_dump(), "evidence": source_context(session, priority_ids=list(re.findall(r"\[@([^\]]+)\]", chapter["content"])))}) + """
Correggi soltanto i problemi documentati. Mantieni direzione, voce e sviluppo.
Non cambiare la tesi, non inventare evidenze. Restituisci l'intero capitolo con riferimenti [@E...].
Puoi esplicitare un limite dove la prova non basta.""", target_words=section["word_target"])
                session = store.get_session(session.session_id)
                chapter = next(c for c in session.book_chapters if c["section_id"] == section["id"])
                chapter.update(content=revised.content, summary=revised.summary, unresolved=revised.unresolved)
                store.save_session(session)
                reviewed = await review_chapters(store.get_session(session.session_id), [chapter])
            session = store.get_session(session.session_id)
            chapter = next(c for c in session.book_chapters if c["section_id"] == section["id"])
            chapter["section_review"] = reviewed.model_dump()
            if any(i.severity == "blocking" for i in reviewed.issues):
                session.review = reviewed.model_dump() | {"stale": False, "at": now(), "partial": True}
                store.save_session(session)
                progress(store, session.session_id, "book", status="paused",
                    error="La revisione segnala problemi da risolvere. Modifica il capitolo e riprendi.",
                    current_step=index+1, total_steps=total)
                return
            chapter["review_stale"] = False
            store.save_session(session)
        progress(store, session.session_id, "book", current_step=index+1, total_steps=total)
    progress(store, session.session_id, "book", current_step=total, total_steps=total, manuscript_complete=True)


async def full_review(store, session):
    if not session.book_chapters:
        raise ValueError("Scrivi almeno un capitolo prima della revisione.")
    groups, current, chars = [], [], 0
    for chapter in session.book_chapters:
        if current and chars + len(chapter["content"]) > 90000:
            groups.append(current)
            current, chars = [], 0
        current.append(chapter)
        chars += len(chapter["content"])
    if current:
        groups.append(current)
    summaries, strengths, issues = [], [], []
    for index, chapters in enumerate(groups):
        session = progress(store, session.session_id, "review", current_step=index, total_steps=len(groups))
        assert_budget(store, session)
        result = await review_chapters(session, chapters)
        summaries.append(result.summary)
        strengths += result.strengths
        issues += [i.model_dump() for i in result.issues]
    session = store.get_session(session.session_id)
    checks = reference_checks(session)
    issues += checks["issues"]
    session.review = {"summary": "\n\n".join(summaries), "strengths": list(dict.fromkeys(strengths)),
        "issues": issues, "stale": False, "partial": len(session.book_chapters) < len(session.plan["sections"]),
        "at": now(), "checks": checks}
    store.save_session(session)


async def dispatch(job, store):
    sid, kind = job["session_id"], job["kind"]
    session = progress(store, sid, kind, status="running", error=None, started_at=now())
    try:
        if kind != "cover" or session.form_data.cover_style != "typographic":
            assert_budget(store, session)
        if kind == "questions":
            await generate_questions(store, session)
        elif kind == "draft":
            await generate_plan(store, session)
        elif kind == "memory":
            if getattr(session, "research_request", None):
                await research(store, session)
                session = store.get_session(sid)
                session.research_request = None
                store.save_session(session)
            else:
                await analyze_sources(store, session)
        elif kind == "book":
            await write_book(store, session)
            session = store.get_session(sid)
            if session.writing_progress.get("status") == "paused":
                return
        elif kind == "cover":
            from app.essay.cover import make_cover
            await make_cover(store, session)
        elif kind == "review":
            await full_review(store, session)
        else:
            raise ValueError("Operazione sconosciuta.")
        progress(store, sid, kind, status="completed", error=None, completed_at=now())
    except Exception as exc:
        progress(store, sid, kind, status="paused" if kind == "book" else "failed",
                 error=str(exc)[:1500], recoverable=True)

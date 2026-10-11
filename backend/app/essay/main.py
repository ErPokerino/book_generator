"""Standalone local SaggIA API, with isolated data and the existing durable worker."""
from __future__ import annotations
import asyncio
import math
from contextlib import asynccontextmanager, suppress
import os
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv
from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import Response, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from app.essay.models import (EssayBrief, BriefEdit, PublicationEdit, PlanEdit, SourceInput, SourceEdit, EvidenceInput, SearchInput,
    AnswersInput, ApprovalInput, RevisionInput, ChapterEdit, EvidenceExcerpt, identifier, now)
from app.essay.store import EssayStore
from app.essay.settings import settings
from app.essay.citations import content_hash, rendered_manuscript, reference_checks, evidence_index
from app.essay.sources import source_from_text, acquire_url, decode_document, MAX_BYTES
from app.essay.generation import dispatch, validate_plan
from app.services.durable_worker import DurableWorker
from app.persistence.sqlite_store import ConcurrentUpdateError, PROGRESS_FIELDS
from app.services.usage_service import usage_summary

root = Path(__file__).resolve().parents[3]
load_dotenv(os.getenv("SAGGIA_ENV_FILE") or root / ".env")


def invalidate(session, *, plan=False):
    session.review = None
    session.review_progress = None
    session.revision_request = None
    session.revision_progress = None
    if plan:
        session.validated = False
        if session.part_checkpoint:
            history = getattr(session, "checkpoint_history", [])
            history.append({"at": now(), "version": session.current_version, "checkpoint": session.part_checkpoint})
            session.checkpoint_history = history[-10:]
            session.part_checkpoint = None
    for chapter in session.book_chapters:
        chapter["review_stale"] = True


def create_app(store=None, *, run_worker=True, api_prefix="/api"):
    @asynccontextmanager
    async def lifespan(app):
        app.state.store = store or getattr(app.state, "store", None) or EssayStore()
        worker = asyncio.create_task(DurableWorker(app.state.store, handler=dispatch).run()) if run_worker else None
        try:
            yield
        finally:
            if worker:
                worker.cancel()
                with suppress(asyncio.CancelledError):
                    await worker

    app = FastAPI(title="SaggIA API", version="0.1.0", lifespan=lifespan)
    router = APIRouter(prefix=api_prefix)
    if store is not None:
        app.state.store = store
    app.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1:5174","http://localhost:5174"],
                       allow_methods=["*"], allow_headers=["*"], expose_headers=["Content-Disposition"])

    @app.exception_handler(ConcurrentUpdateError)
    async def conflict(request, error):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=409, content={"detail": str(error)})

    @app.exception_handler(ValueError)
    async def validation(request, error):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=422, content={"detail": str(error)})

    @app.exception_handler(KeyError)
    async def not_found(request, error):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"detail": str(error).strip("'")})

    def current(sid):
        session = app.state.store.get_session(sid)
        if session is None:
            raise HTTPException(404, "Saggio inesistente.")
        return session

    def measured_usage(session):
        summary = usage_summary(session, app.state.store.usage_events(session.session_id))
        if any(e.get("tool_cost_unknown") for e in summary["events"]):
            summary["coverage_complete"] = False
            summary["tool_cost_unknown"] = True
        return summary

    def visible(session):
        value = session.to_dict()
        value.pop("part_checkpoint", None)
        value.pop("research_request", None)
        checkpoint = value.pop("revision_request", None)
        hashes = {c["section_id"]: content_hash(c["content"]) for c in session.book_chapters}
        value["can_resume_revision"] = bool(checkpoint and checkpoint.get("stage") != "done"
            and checkpoint.get("source_version") == session.current_version
            and checkpoint.get("hashes") == hashes)
        value.pop("checkpoint_history", None)
        value["sources"] = [{k: v for k, v in s.items() if k != "text"} | {"text_length": len(s.get("text", ""))}
                            for s in session.sources]
        try:
            chapters, bibliography = rendered_manuscript(session, linked=True)
        except ValueError:
            chapters, bibliography = [c | {"display_content": c["content"]} for c in session.book_chapters], []
        value["book_chapters"] = [c | {"hash": content_hash(c["content"])} for c in chapters]
        value["bibliography"] = bibliography
        value["reference_checks"] = reference_checks(session)
        value["active"] = app.state.store.active(session.session_id)
        summary = measured_usage(session)
        value["usage"] = summary
        value["words"] = sum(len(c["content"].split()) for c in session.book_chapters)
        value["estimated_pages"] = math.ceil(value["words"] / 250)
        return value

    @router.get("/health")
    def health():
        return {"status": "ok", "product": "saggia"}

    @router.get("/essay-config")
    def config():
        return settings() | {"api_key_ready": bool(os.getenv("GOOGLE_API_KEY")),
            "adult_only": True, "pricing_source": "https://ai.google.dev/gemini-api/docs/pricing",
            "search_cost_note": "Il costo del servizio di ricerca dipende dal piano Google e può non essere incluso nel totale misurato."}

    @router.get("/essays")
    def library():
        sessions = app.state.store.get_all_sessions().values()
        items = []
        for session in sorted(sessions, key=lambda s: s.updated_at, reverse=True):
            words = sum(len(c["content"].split()) for c in session.book_chapters)
            usage = measured_usage(session)
            active = app.state.store.active(session.session_id)
            pdf_pages = None
            if session.book_chapters and session.plan and not active:
                from app.essay.exports import pdf_page_count
                try:
                    pdf_pages = pdf_page_count(session)
                except (ValueError, OSError):
                    pass  # Keep incomplete references/materials accessible in the library.
            items.append({"id": session.session_id,
                "title": session.form_data.title or (session.plan or {}).get("title") or session.form_data.topic,
                "topic": session.form_data.topic, "profile": session.form_data.profile, "ai_role": session.form_data.ai_role,
                "status": session.get_status(), "updated_at": session.updated_at, "words": words,
                "estimated_pages": math.ceil(words / 250), "pdf_pages": pdf_pages,
                "generation_cost_eur": usage["converted_cost_eur"],
                "cost_coverage_complete": usage["coverage_complete"], "generation_calls": usage["calls"],
                "active": active})
        return items

    @router.post("/essays", status_code=201)
    def create(brief: EssayBrief):
        return visible(app.state.store.create_session(identifier("P"), brief))

    @router.post("/essay-estimates")
    def estimates(brief: EssayBrief):
        from app.essay.estimates import essay_estimate
        return essay_estimate(brief, app.state.store)

    @router.get("/essays/{sid}")
    def project(sid: str):
        return visible(current(sid))

    @router.put("/essays/{sid}/brief")
    def update_brief(sid: str, change: BriefEdit):
        def mutate(session):
            if change.expected_version != session.current_version:
                raise ConcurrentUpdateError("Il progetto è cambiato. Ricarica prima di salvare.")
            resources = {"budget_eur", "llm_model", "model_overrides"}
            same_direction = session.form_data.model_dump(exclude=resources) == change.brief.model_dump(exclude=resources)
            session.form_data = change.brief
            session.current_version += 1
            if same_direction:
                if session.revision_request:
                    session.revision_request["source_version"] = session.current_version
            else:
                invalidate(session, plan=True)
                session.cover_image_path = None
        return visible(app.state.store.mutate(sid, mutate))

    @router.put("/essays/{sid}/publication")
    def update_publication(sid: str, change: PublicationEdit):
        def mutate(session):
            if change.expected_version != session.current_version:
                raise ConcurrentUpdateError("I dati del libro sono cambiati. Ricarica prima di salvare.")
            for field in ("author_name", "title", "subtitle", "back_cover_text"):
                setattr(session.form_data, field, getattr(change, field).strip())
            session.current_version += 1
            if session.revision_request:
                session.revision_request["source_version"] = session.current_version
            if session.plan:
                from app.essay.cover import compose_cover
                target = compose_cover(app.state.store, session)
                session.cover_image_path = str(target) if target else None
            # Publication metadata does not change the argument or review.
        return visible(app.state.store.mutate(sid, mutate))

    @router.post("/essays/{sid}/answers")
    def answers(sid: str, payload: AnswersInput):
        def mutate(session):
            valid = {q["id"] for q in session.generated_questions}
            if any(k not in valid for k in payload.answers):
                raise ValueError("Risposta associata a una domanda inesistente.")
            session.answers = payload.answers
            session.current_version += 1
            invalidate(session, plan=True)
        return visible(app.state.store.mutate(sid, mutate))

    @router.put("/essays/{sid}/plan")
    def update_plan(sid: str, payload: PlanEdit):
        def mutate(session):
            if payload.expected_version != session.current_version:
                raise ConcurrentUpdateError("Il piano è cambiato. Ricarica prima di salvarlo.")
            if session.book_chapters:
                old_ids = [s["id"] for s in session.plan["sections"]]
                if old_ids != [s.id for s in payload.plan.sections]:
                    raise ValueError("Con capitoli già scritti, conserva ordine e identificativi dell'indice.")
            session.plan = validate_plan(payload.plan, session).model_dump()
            titles = {section["id"]: section["title"] for section in session.plan["sections"]}
            for chapter in session.book_chapters:
                chapter["title"] = titles[chapter["section_id"]]
            session.current_version += 1
            session.outline_version += 1
            session.cover_image_path = None
            invalidate(session, plan=True)
        return visible(app.state.store.mutate(sid, mutate))

    @router.post("/essays/{sid}/approve")
    def approve(sid: str, payload: ApprovalInput):
        def mutate(session):
            if session.current_version != payload.expected_version:
                raise ConcurrentUpdateError("Il piano è cambiato. Leggi la versione attuale prima di approvarlo.")
            if not session.plan:
                raise ValueError("Prepara il progetto editoriale prima di approvarlo.")
            from app.essay.models import EssayPlan
            validate_plan(EssayPlan(**session.plan), session)
            session.validated = True
        return visible(app.state.store.mutate(sid, mutate))

    @router.post("/essays/{sid}/jobs/{kind}")
    def start(sid: str, kind: str):
        if kind not in {"questions","draft","memory","book","review","cover"}:
            raise HTTPException(404, "Operazione sconosciuta.")
        def prepare(session):
            if kind == "book" and (not session.plan or not session.validated):
                raise ValueError("Approva il progetto editoriale prima di scrivere.")
            if kind == "review" and not session.book_chapters:
                raise ValueError("Non ci sono ancora capitoli da revisionare.")
            if kind == "cover" and not session.plan:
                raise ValueError("Prepara titolo e progetto prima della copertina.")
            if kind == "book" and session.writing_progress and session.writing_progress.get("status") == "completed":
                raise ValueError("Il manoscritto è già completo. Puoi modificarlo nello studio.")
            if kind == "draft" and session.book_chapters:
                raise ValueError("Il manoscritto è già iniziato. Modifica il piano esistente senza rigenerare l'indice.")
            if kind == "book":
                session.pause_requested = False
            if kind == "draft":
                session.validated = False
            if kind == "review":
                session.revision_request = None
                session.revision_progress = None
            # memory resumes a persisted search if it was interrupted.
        app.state.store.enqueue(sid, kind, prepare)
        return visible(current(sid))

    @router.post("/essays/{sid}/revision")
    def delegate_revision(sid: str, payload: RevisionInput):
        def prepare(session):
            hashes = {c["section_id"]: content_hash(c["content"]) for c in session.book_chapters}
            if session.current_version != payload.expected_version or hashes != payload.expected_hashes:
                raise ConcurrentUpdateError("Il manoscritto è cambiato. Ricarica prima di delegare le correzioni.")
            if not session.plan or not session.book_chapters:
                raise ValueError("Prepara il piano e scrivi almeno un capitolo.")
            if payload.resume:
                checkpoint = session.revision_request
                if not checkpoint or checkpoint["stage"] == "done" or checkpoint["hashes"] != hashes or checkpoint["source_version"] != session.current_version:
                    raise ValueError("Il lavoro non è più riprendibile. Aggiorna la revisione e avvia nuove correzioni.")
                return
            review = session.review
            if not review or review.get("stale") or not review.get("issues"):
                raise ValueError("Genera una revisione aggiornata con interventi proposti prima di delegare.")
            if review.get("at") != payload.expected_review_at or (review.get("manuscript_hashes") and review["manuscript_hashes"] != hashes):
                raise ConcurrentUpdateError("Il rapporto di revisione è cambiato. Leggi quello aggiornato.")
            if any(i.get("section_id") and i["section_id"] not in hashes for i in review["issues"]):
                raise ValueError("Il rapporto richiama un capitolo inesistente. Aggiorna la revisione.")
            session.revision_request = {
                "source_version": session.current_version, "hashes": hashes, "original_review": review,
                "report": review, "pass": 1, "stage": "writing", "completed_ids": [],
                "updated_ids": [], "review_groups": [], "started_at": now(),
            }
        app.state.store.enqueue(sid, "revision", prepare)
        return visible(current(sid))

    @router.post("/essays/{sid}/pause")
    def pause(sid: str):
        session = current(sid)
        if not app.state.store.active(sid) or not session.writing_progress or session.writing_progress.get("status") not in {"pending","running"}:
            raise ValueError("Non c'è una scrittura attiva da mettere in pausa.")
        return visible(app.state.store.mutate(sid, lambda s: setattr(s, "pause_requested", True), allow_active=True))

    @router.post("/essays/{sid}/research")
    def search(sid: str, payload: SearchInput):
        def mutate(session):
            session.research_request = {"query": payload.query}
            session.validated = False
        app.state.store.enqueue(sid, "memory", mutate, idempotent=False)
        return visible(current(sid))

    @router.post("/essays/{sid}/sources")
    async def add_source(sid: str, payload: SourceInput):
        current(sid)
        if payload.url:
            acquired = await acquire_url(payload.url, payload.title)
            source = source_from_text(acquired["title"], acquired["text"], url=acquired["url"], kind="web",
                                      author=payload.author or acquired.get("author", ""), published=payload.published or acquired.get("published", ""))
        else:
            source = source_from_text(payload.title, payload.text, author=payload.author, published=payload.published, kind=payload.kind)
        def mutate(session):
            session.sources.append(source)
            session.current_version += 1
            invalidate(session, plan=True)
        return visible(app.state.store.mutate(sid, mutate))

    @router.post("/essays/{sid}/upload")
    async def upload(sid: str, file: UploadFile = File(...), author: str = Form(""), published: str = Form("")):
        current(sid)
        raw = await file.read(MAX_BYTES + 1)
        filename = (file.filename or "Documento").replace("\\", "/").split("/")[-1]
        text = await asyncio.to_thread(decode_document, raw, filename)
        source = source_from_text(filename, text, kind="document", filename=filename, author=author, published=published)
        def mutate(session):
            session.sources.append(source)
            session.current_version += 1
            invalidate(session, plan=True)
        session = app.state.store.mutate(sid, mutate)
        original = app.state.store.data_dir / "sources" / sid / (source["id"] + "." + filename.rsplit(".",1)[-1].lower())
        original.parent.mkdir(parents=True, exist_ok=True)
        original.write_bytes(raw)
        return visible(session)

    @router.get("/essays/{sid}/sources/{source_id}")
    def source_detail(sid: str, source_id: str):
        source = next((s for s in current(sid).sources if s["id"] == source_id), None)
        if source is None:
            raise HTTPException(404, "Fonte inesistente.")
        return source

    @router.put("/essays/{sid}/sources/{source_id}")
    def edit_source(sid: str, source_id: str, payload: SourceEdit):
        def mutate(session):
            source = next((s for s in session.sources if s["id"] == source_id), None)
            if source is None:
                raise KeyError("Fonte inesistente.")
            if payload.expected_version != source.get("version", 1):
                raise ConcurrentUpdateError("I dati della fonte sono cambiati. Riaprila prima di salvare.")
            source.update(title=payload.title, author=payload.author, published=payload.published,
                          version=source.get("version", 1)+1)
            session.current_version += 1
            invalidate(session, plan=True)
        return visible(app.state.store.mutate(sid, mutate))

    @router.post("/essays/{sid}/sources/{source_id}/retry")
    async def retry_source(sid: str, source_id: str):
        source = next((s for s in current(sid).sources if s["id"] == source_id), None)
        if source is None:
            raise HTTPException(404, "Fonte inesistente.")
        if source["status"] not in {"failed", "proposed"} or not source.get("url"):
            raise ValueError("Puoi ritentare l'acquisizione di una fonte web non ancora acquisita.")
        acquired = await acquire_url(source["url"], source["title"])
        def mutate(session):
            target = next(s for s in session.sources if s["id"] == source_id)
            target.update(text=acquired["text"], url=acquired["url"], title=acquired["title"],
                          content_hash=content_hash(acquired["text"]), status="acquired", acquired_at=now(), error="")
            session.current_version += 1
            invalidate(session, plan=True)
        return visible(app.state.store.mutate(sid, mutate))

    @router.post("/essays/{sid}/sources/{source_id}/evidence")
    def add_evidence(sid: str, source_id: str, payload: EvidenceInput):
        def mutate(session):
            source = next((s for s in session.sources if s["id"] == source_id), None)
            if source is None:
                raise KeyError("Fonte inesistente.")
            start = source["text"].find(payload.quote)
            if start < 0:
                raise ValueError("L'estratto deve coincidere con un passaggio del testo della fonte.")
            source["evidence"].append(EvidenceExcerpt(id=identifier("E"), source_id=source_id, quote=payload.quote,
                locator="Caratteri " + str(start + 1) + "–" + str(start + len(payload.quote)),
                start=start, end=start+len(payload.quote), stance=payload.stance, explanation=payload.explanation,
                reviewed=True).model_dump())
            source["status"] = "analyzed"
            session.current_version += 1
            invalidate(session, plan=True)
        return visible(app.state.store.mutate(sid, mutate))

    @router.post("/essays/{sid}/sources/{source_id}/exclude")
    def exclude(sid: str, source_id: str):
        def mutate(session):
            source = next((s for s in session.sources if s["id"] == source_id), None)
            if source is None:
                raise KeyError("Fonte inesistente.")
            if source["status"] == "excluded":
                source["status"] = "analyzed" if source.get("evidence") else ("acquired" if source.get("text") else "proposed")
            else:
                source["status"] = "excluded"
            session.current_version += 1
            invalidate(session, plan=True)
        return visible(app.state.store.mutate(sid, mutate))

    @router.put("/essays/{sid}/chapters/{index}")
    def edit_chapter(sid: str, index: int, payload: ChapterEdit):
        return visible(app.state.store.edit_chapter(sid, index, payload.content, payload.expected_hash))

    @router.get("/essays/{sid}/chapters/{index}/revisions")
    def revisions(sid: str, index: int):
        current(sid)
        return app.state.store.chapter_revisions(sid, index)

    @router.get("/essays/{sid}/cover")
    def cover(sid: str):
        session = current(sid)
        if not session.cover_image_path or not Path(session.cover_image_path).exists():
            raise HTTPException(404, "Copertina non disponibile.")
        return FileResponse(session.cover_image_path, media_type="image/png")

    @router.get("/essays/{sid}/export/{format}")
    async def export(sid: str, format: str):
        session = current(sid)
        if not session.book_chapters or not session.plan:
            raise ValueError("Scrivi almeno un capitolo prima dell'esportazione.")
        if format not in {"pdf","epub","docx"}:
            raise HTTPException(404, "Formato non supportato.")
        from app.essay.exports import export_book
        data, media = await asyncio.to_thread(export_book, session, format)
        title = session.form_data.title or session.plan["title"]
        name = title.replace("/", "-").replace("\\", "-")[:100] + "." + format
        return Response(data, media_type=media, headers={"Content-Disposition": "attachment; filename*=UTF-8''" + quote(name)})

    @router.delete("/essays/{sid}", status_code=204)
    def delete(sid: str):
        current(sid)
        app.state.store.delete_session(sid)
        # Originals and covers are owned exclusively by this project in the isolated data root.
        source_dir = app.state.store.data_dir / "sources" / sid
        if source_dir.exists():
            for file in source_dir.iterdir():
                if file.is_file():
                    file.unlink()
            source_dir.rmdir()
        (app.state.store.data_dir / "covers" / (sid + ".png")).unlink(missing_ok=True)
        (app.state.store.data_dir / "covers" / (sid + "-background.png")).unlink(missing_ok=True)
        return Response(status_code=204)

    static_root = root / "backend" / "static"
    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
        if path.startswith("api/") or path == "api":
            raise HTTPException(404, "Endpoint inesistente.")
        target = (static_root / path).resolve()
        if not target.is_relative_to(static_root.resolve()):
            raise HTTPException(404)
        if target.is_file():
            return FileResponse(target)
        index = static_root / "index.html"
        if index.exists():
            return FileResponse(index, headers={"Cache-Control": "no-cache"})
        raise HTTPException(404, "Frontend non compilato. Avvia Vite sulla porta 5174.")

    # API routes precede the standalone frontend fallback.
    app.router.routes[:0] = router.routes
    return app


app = create_app()

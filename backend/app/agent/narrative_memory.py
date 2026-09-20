"""Evidence-backed narrative facts, retrieval and bounded continuity review."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Literal
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, SystemMessage

from app.llm import build_google_chat_model, get_stage_model, invoke_chat_model, invoke_structured_chat_model


class Fact(BaseModel):
    subject: str = Field(min_length=1, max_length=120)
    predicate: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1, max_length=600)
    kind: Literal["identity", "knowledge", "location", "time", "state", "relationship", "thread"]
    certainty: Literal["explicit", "inferred"] = "explicit"
    evidence: str = Field(min_length=8, max_length=800)
    supersedes: list[str] = Field(default_factory=list, max_length=10)
    resolved: bool = False


class Contradiction(BaseModel):
    fact_id: str
    evidence: str = Field(min_length=8, max_length=800)
    explanation: str = Field(min_length=1, max_length=800)


class ChapterMemory(BaseModel):
    facts: list[Fact] = Field(default_factory=list, max_length=40)
    contradictions: list[Contradiction] = Field(default_factory=list, max_length=12)

    @classmethod
    def model_json_schema(cls, *args, **kwargs):
        # Gemini can reject nested bounded arrays/strings with INVALID_ARGUMENT.
        # Keep the wire grammar small; Pydantic still enforces every bound when
        # LangChain parses the response, before grounding checks or persistence.
        schema = super().model_json_schema(*args, **kwargs)

        def simplify(node):
            if isinstance(node, dict):
                return {key: simplify(value) for key, value in node.items()
                        if key not in {"minLength", "maxLength", "maxItems", "default"}}
            if isinstance(node, list):
                return [simplify(value) for value in node]
            return node

        return simplify(schema)


def content_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def relevant_facts(memory, query, before_index, limit=36):
    """Retrieve distant facts by entity relevance; always prioritize unresolved threads."""
    words = set(re.findall(r"\w{3,}", query.casefold()))
    candidates = [f for f in memory.get("facts", []) if f["section_index"] < before_index]
    superseded = {old for f in candidates for old in f.get("supersedes", [])}
    def score(f):
        entity = set(re.findall(r"\w{3,}", f["subject"].casefold()))
        terms = set(re.findall(r"\w{3,}", f'{f["predicate"]} {f["value"]}'.casefold()))
        return (8*len(words & entity) + len(words & terms)
                + (4 if f["kind"] == "thread" and not f.get("resolved") else 0)
                + (2 if f["kind"] == "identity" else 0), f["section_index"])
    active = [f for f in candidates if f["id"] not in superseded]
    return sorted(active, key=score, reverse=True)[:limit]


def source_evidence(quote, text):
    """Recover literal source offsets when the model drops Markdown/quote styling.

    Never fuzzy-match words: negations, case, numbers and sentence punctuation
    must still match. The persisted quote is always an actual source substring.
    """
    if quote in text:
        return quote

    def plain(source):
        characters, offsets = [], []
        for offset, character in enumerate(source):
            if character in '*_`«»“”"':
                continue
            character = "'" if character in '‘’' else character
            character = ' ' if character.isspace() else character
            if character == ' ' and characters and characters[-1] == ' ':
                continue
            characters.append(character)
            offsets.append(offset)
        return ''.join(characters), offsets

    normalized, offsets = plain(text)
    needle, _ = plain(quote)
    if not needle.strip():
        return None
    start = normalized.find(needle)
    return text[offsets[start]:offsets[start+len(needle)-1]+1] if start >= 0 else None


def grounded_payload(payload, text, prior_facts):
    """Reject invented quotes or references before persisting model assertions."""
    by_id = {fact["id"]: fact for fact in prior_facts}
    for fact in payload.facts:
        evidence = source_evidence(fact.evidence, text)
        if evidence is None:
            raise ValueError("La prova di un fatto non compare testualmente nel capitolo")
        fact.evidence = evidence
        if any(old not in by_id for old in fact.supersedes):
            raise ValueError("Il fatto sostituisce un riferimento inesistente")
    for conflict in payload.contradictions:
        evidence = source_evidence(conflict.evidence, text)
        if evidence is None or conflict.fact_id not in by_id:
            raise ValueError("Contraddizione priva di riscontro testuale")
        conflict.evidence = evidence
        if by_id[conflict.fact_id]["certainty"] != "explicit":
            raise ValueError("Una deduzione non può essere usata come contraddizione certa")
    return ChapterMemory.model_validate(payload.model_dump())


def merge_chapter_memory(memory, payload, chapter):
    index, text = chapter["section_index"], chapter["content"]
    # Editing a chapter invalidates all dependent facts, not just the edited card.
    facts = [f for f in memory.get("facts", []) if f["section_index"] < index]
    digest = content_hash(text)
    for offset, fact in enumerate(payload.facts):
        item = fact.model_dump()
        start = text.index(item["evidence"])
        item.update(id=f"{index}:{digest[:12]}:{offset}", section_index=index,
                    chapter_title=chapter["title"], source_hash=digest, start=start, end=start+len(item["evidence"]))
        facts.append(item)
    chapters = {k: v for k, v in memory.get("chapters", {}).items() if int(k) < index}
    chapters[str(index)] = digest
    checks = [c for c in memory.get("checks", []) if c["section_index"] < index]
    checks.append({"section_index": index, "source_hash": digest, "status": "conflict" if payload.contradictions else "checked",
                   "contradictions": [c.model_dump() for c in payload.contradictions]})
    return {"facts": facts, "chapters": chapters, "checks": checks}


async def extract_chapter_memory(session, chapter, prior, api_key=None):
    model = get_stage_model("memory", form_data=session.form_data)
    llm = build_google_chat_model(model_name=model, api_key=api_key, temperature=.2, max_output_tokens=8192)
    payload, _, _ = await invoke_structured_chat_model(
        llm=llm, schema=ChapterMemory, model_name=model, stage="narrative-memory", session_id=session.session_id,
        request_label=f"memory-{chapter['section_index']}",
        messages=[SystemMessage(content=(
            "Estrai solo fatti narrativi utili alla continuità: identità, conoscenze individuali, luoghi, tempo, "
            "stati, relazioni e fili aperti. Ogni fatto deve citare una frase ESATTA del capitolo, senza parafrasi. "
            "Distingui esplicito da inferito. Non trasformare il piano della trama in eventi avvenuti. "
            "Usa supersedes solo se il testo mostra un cambiamento rispetto a un fatto precedente; "
            "risoluzioni dei fili: kind thread, resolved true e supersedes con ID del filo. "
            "Segnala contraddizioni solo rispetto a fatti espliciti precedenti, citandone ID e prova nel nuovo testo. "
            "Spostamenti, nuove informazioni, flashback, menzogne e cambiamenti motivati non sono contraddizioni. "
            "Massimo 40 fatti e 12 contraddizioni. Subject e predicate: 1–120 caratteri; value: 1–600; "
            "evidence: 8–800; explanation: 1–800. Massimo 10 riferimenti in supersedes.")),
            HumanMessage(content=f"FATTI PRECEDENTI:\n{json.dumps(prior, ensure_ascii=False)}\nCAPITOLO:\n{chapter['content']}")],
        parsed_validator=lambda p: grounded_payload(p, chapter["content"], prior),
    )
    return payload


async def ensure_narrative_memory(store, session, api_key=None):
    """Checkpoint each analysis. Failed analysis never discards a generated chapter."""
    if not hasattr(store, "chapter_revisions"):
        return session  # In-memory test adapter; no implicit external requests.
    for chapter in list(session.book_chapters):
        index = chapter["section_index"]
        if session.narrative_memory.get("chapters", {}).get(str(index)) == content_hash(chapter["content"]):
            check = next((c for c in session.narrative_memory.get("checks", []) if c["section_index"] == index), {})
            if check.get("status") == "conflict":
                raise ValueError(f"Continuità da verificare nel capitolo {index+1}. Correggi il testo nello studio prima di riprendere.")
            continue
        prior = relevant_facts(session.narrative_memory, chapter["content"], index, limit=80)
        payload = await extract_chapter_memory(session, chapter, prior, api_key)
        if payload.contradictions:
            model = get_stage_model("chapters", form_data=session.form_data)
            llm = build_google_chat_model(model_name=model, api_key=api_key, temperature=.4, max_output_tokens=32768)
            corrected, _, = await invoke_chat_model(llm=llm, model_name=model, stage="continuity-revision",
                session_id=session.session_id, request_label=f"revise-{index}",
                messages=[SystemMessage(content="Correggi soltanto le contraddizioni documentate. Mantieni voce, scene e ampiezza. Restituisci il capitolo completo senza commenti."),
                    HumanMessage(content=json.dumps({"facts": prior, "contradictions": [c.model_dump() for c in payload.contradictions], "chapter": chapter["content"]}, ensure_ascii=False))])
            from app.agent.writer.common import validate_generated_chapter_text
            corrected = validate_generated_chapter_text(corrected, chapter["title"])
            chapter = chapter | {"content": corrected}
            payload = await extract_chapter_memory(session, chapter, prior, api_key)
        session = store.get_session(session.session_id)
        previous = next(c for c in session.book_chapters if c["section_index"] == index)
        if previous["content"] != chapter["content"]:
            session.pdf_path = session.pdf_filename = None
            session.literary_critique = session.critique_status = session.critique_error = None
            session.story_bible = None
        session.book_chapters = [chapter if c["section_index"] == index else c for c in session.book_chapters]
        session.narrative_memory = merge_chapter_memory(session.narrative_memory, payload, chapter)
        store.save_session(session)  # Chapter revision and grounded memory committed together.
        if payload.contradictions:
            raise ValueError(f"Contraddizione nel capitolo {index+1}: verifica le prove nello studio e correggi prima di riprendere.")
    return session

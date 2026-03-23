import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.models import QuestionAnswer, SubmissionRequest


DEFAULT_DRAFT_SUMMARY_MAX_CHARS = 1800
DEFAULT_CHAPTER_CARD_DESCRIPTION_MAX_CHARS = 320
DEFAULT_CONTINUITY_SUMMARY_MAX_CHARS = 420
DEFAULT_RECENT_DEVELOPMENTS_COUNT = 3
DEFAULT_RECENT_FULL_CHAPTERS = 2
DEFAULT_CONTINUITY_NOTES_WINDOW = 6
DEFAULT_CARD_CONTEXT_RADIUS_BEFORE = 1
DEFAULT_CARD_CONTEXT_RADIUS_AFTER = 2


def _normalize_whitespace(text: Optional[str]) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def _truncate_text(text: str, max_chars: int) -> str:
    normalized = _normalize_whitespace(text)
    if len(normalized) <= max_chars:
        return normalized

    truncated = normalized[: max_chars - 1].rstrip()
    last_space = truncated.rfind(" ")
    if last_space > int(max_chars * 0.6):
        truncated = truncated[:last_space].rstrip()
    return f"{truncated}..."


def summarize_for_story_bible(
    text: Optional[str],
    max_chars: int,
    max_sentences: int = 4,
) -> str:
    """Produce un riassunto deterministico e compatto senza chiamare il modello."""
    normalized = _normalize_whitespace(text)
    if not normalized:
        return ""

    sentences = re.split(r"(?<=[.!?])\s+", normalized)
    selected: list[str] = []
    current_length = 0

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        projected_length = current_length + len(sentence) + (1 if selected else 0)
        if selected and projected_length > max_chars:
            break
        selected.append(sentence)
        current_length = projected_length
        if len(selected) >= max_sentences:
            break

    candidate = " ".join(selected).strip()
    if candidate:
        return _truncate_text(candidate, max_chars)

    return _truncate_text(normalized, max_chars)


def _build_creative_brief(form_data: SubmissionRequest, draft_title: Optional[str]) -> list[str]:
    brief_fields = [
        ("Titolo", draft_title),
        ("Genere", form_data.genre),
        ("Sottogenere", form_data.subgenre),
        ("Target", form_data.target_audience),
        ("Tema", form_data.theme),
        ("Protagonista", form_data.protagonist),
        ("Archetipo", form_data.protagonist_archetype),
        ("Arco", form_data.character_arc),
        ("Punto di vista", form_data.point_of_view),
        ("Voce narrante", form_data.narrative_voice),
        ("Stile", form_data.style),
        ("Struttura temporale", form_data.temporal_structure),
        ("Ritmo", form_data.pace),
        ("Realismo", form_data.realism),
        ("Ambiguità", form_data.ambiguity),
        ("Intenzionalità", form_data.intentionality),
        ("Autore di riferimento", form_data.author),
    ]
    return [f"{label}: {value}" for label, value in brief_fields if value]


def _build_user_constraints(question_answers: list[QuestionAnswer]) -> list[str]:
    constraints: list[str] = []
    for qa in question_answers:
        if qa.answer and qa.answer.strip():
            constraints.append(f"{qa.question_id}: {qa.answer.strip()}")
    return constraints


def _build_chapter_cards(outline_sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    chapter_cards: list[dict[str, Any]] = []
    for fallback_index, section in enumerate(outline_sections):
        chapter_cards.append(
            {
                "section_index": int(section.get("section_index", fallback_index)),
                "title": section.get("title", "").strip(),
                "description": summarize_for_story_bible(
                    section.get("description", ""),
                    DEFAULT_CHAPTER_CARD_DESCRIPTION_MAX_CHARS,
                    max_sentences=3,
                ),
            }
        )
    return chapter_cards


def _build_continuity_notes(completed_chapters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []
    for fallback_index, chapter in enumerate(completed_chapters):
        content = chapter.get("content", "")
        summary = summarize_for_story_bible(
            content,
            DEFAULT_CONTINUITY_SUMMARY_MAX_CHARS,
            max_sentences=4,
        )
        if not summary:
            continue
        notes.append(
            {
                "section_index": int(chapter.get("section_index", fallback_index)),
                "title": chapter.get("title", f"Capitolo {fallback_index + 1}").strip(),
                "summary": summary,
            }
        )
    return notes[-DEFAULT_CONTINUITY_NOTES_WINDOW:]


def build_story_bible(
    form_data: SubmissionRequest,
    question_answers: list[QuestionAnswer],
    validated_draft: str,
    draft_title: Optional[str],
    outline_sections: list[dict[str, Any]],
    completed_chapters: Optional[list[dict[str, Any]]] = None,
    draft_version: int = 0,
    outline_version: int = 0,
    character_profiles: Optional[str] = None,
) -> dict[str, Any]:
    """Costruisce una story bible strutturata e persistibile partendo dai dati di sessione."""
    completed_chapters = completed_chapters or []
    continuity_notes = _build_continuity_notes(completed_chapters)
    recent_developments = [
        f"{note['title']}: {note['summary']}" for note in continuity_notes[-DEFAULT_RECENT_DEVELOPMENTS_COUNT:]
    ]

    bible: dict[str, Any] = {
        "title": draft_title or "Romanzo",
        "source_versions": {
            "draft_version": int(draft_version),
            "outline_version": int(outline_version),
        },
        "creative_brief": _build_creative_brief(form_data, draft_title),
        "user_constraints": _build_user_constraints(question_answers),
        "premise": _truncate_text(form_data.plot or "", 420),
        "draft_summary": summarize_for_story_bible(
            validated_draft,
            DEFAULT_DRAFT_SUMMARY_MAX_CHARS,
            max_sentences=6,
        ),
        "character_profiles": character_profiles or "",
        "chapter_cards": _build_chapter_cards(outline_sections),
        "continuity_notes": continuity_notes,
        "recent_developments": recent_developments,
        "updated_at": datetime.utcnow().isoformat(),
    }
    return bible


def is_story_bible_stale(
    story_bible: Optional[dict[str, Any]],
    draft_version: int,
    outline_version: int,
) -> bool:
    if not story_bible:
        return True

    versions = story_bible.get("source_versions", {})
    return (
        int(versions.get("draft_version", -1)) != int(draft_version)
        or int(versions.get("outline_version", -1)) != int(outline_version)
    )


def get_recent_full_chapters(
    previous_chapters: list[dict[str, Any]],
    max_recent_full_chapters: int = DEFAULT_RECENT_FULL_CHAPTERS,
) -> list[dict[str, Any]]:
    if max_recent_full_chapters <= 0:
        return []
    return previous_chapters[-max_recent_full_chapters:]


def get_relevant_continuity_notes(
    story_bible: Optional[dict[str, Any]],
    previous_chapters: list[dict[str, Any]],
    max_notes: int = DEFAULT_CONTINUITY_NOTES_WINDOW,
) -> list[dict[str, Any]]:
    if not story_bible:
        return []

    notes = story_bible.get("continuity_notes", [])
    if not isinstance(notes, list):
        return []

    recent_indices = {
        int(chapter.get("section_index", -1))
        for chapter in get_recent_full_chapters(previous_chapters)
    }
    filtered = [
        note for note in notes
        if int(note.get("section_index", -1)) not in recent_indices
    ]
    return filtered[-max_notes:]


def get_nearby_chapter_cards(
    story_bible: Optional[dict[str, Any]],
    current_section_index: Optional[int],
    before: int = DEFAULT_CARD_CONTEXT_RADIUS_BEFORE,
    after: int = DEFAULT_CARD_CONTEXT_RADIUS_AFTER,
) -> list[dict[str, Any]]:
    if not story_bible:
        return []

    chapter_cards = story_bible.get("chapter_cards", [])
    if not isinstance(chapter_cards, list) or current_section_index is None:
        return []

    nearby_cards: list[dict[str, Any]] = []
    for card in chapter_cards:
        section_index = int(card.get("section_index", -1))
        if current_section_index - before <= section_index <= current_section_index + after:
            nearby_cards.append(card)
    return nearby_cards

"""Primitive condivise per validation, story bible e token aggregation."""

from __future__ import annotations

import re
from typing import Any, Optional

from app.agent.session_store_helpers import save_session_async
from app.agent.story_bible import build_story_bible
from app.core.config import get_app_config
from app.core.logging import get_logger
from app.models import QuestionAnswer

DEFAULT_MIN_CHAPTER_LENGTH = 1200
DEFAULT_MIN_CHAPTER_WORDS = 180
DEFAULT_DISALLOWED_OUTPUT_MARKERS = ("[ERRORE:", "[ERROR:")

logger = get_logger("writer-common")


def _count_words(text: str) -> int:
    """Conta le parole in modo robusto anche con apostrofi e lettere accentate."""
    return len(re.findall(r"\b[\wÀ-ÖØ-öø-ÿ'-]+\b", text, flags=re.UNICODE))


def _get_chapter_validation_settings(
    app_config: Optional[dict[str, Any]] = None,
) -> tuple[int, int, list[str]]:
    """Restituisce le soglie di validazione per i capitoli."""
    if app_config is None:
        app_config = get_app_config()

    validation_config = app_config.get("validation", {})
    min_chars = int(validation_config.get("min_chapter_length", DEFAULT_MIN_CHAPTER_LENGTH))
    min_words = int(validation_config.get("min_chapter_words", DEFAULT_MIN_CHAPTER_WORDS))
    disallowed_markers = validation_config.get(
        "disallowed_output_markers",
        list(DEFAULT_DISALLOWED_OUTPUT_MARKERS),
    )
    if not isinstance(disallowed_markers, list):
        disallowed_markers = list(DEFAULT_DISALLOWED_OUTPUT_MARKERS)

    return min_chars, min_words, [str(marker) for marker in disallowed_markers if marker]


def _find_blocked_output_marker(text: str, disallowed_markers: list[str]) -> Optional[str]:
    """Cerca marker che indicano output tecnico o placeholder non narrativi."""
    text_lower = text.lower()
    for marker in disallowed_markers:
        if marker.lower() in text_lower:
            return marker
    return None


def validate_generated_chapter_text(
    chapter_text: str,
    current_section_title: str,
    app_config: Optional[dict[str, Any]] = None,
) -> str:
    """Valida che un capitolo abbia contenuto narrativo sufficiente e nessun placeholder tecnico."""
    if not chapter_text or not chapter_text.strip():
        raise ValueError(f"Capitolo vuoto per '{current_section_title}'")

    text = chapter_text.strip()
    min_chars, min_words, disallowed_markers = _get_chapter_validation_settings(app_config)
    blocked_marker = _find_blocked_output_marker(text, disallowed_markers)
    if blocked_marker:
        raise ValueError(
            f"Capitolo non valido per '{current_section_title}': contiene il marker non narrativo '{blocked_marker}'"
        )

    char_count = len(text)
    word_count = _count_words(text)
    alnum_count = len(re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9]", text))

    if alnum_count < 20:
        raise ValueError(
            f"Capitolo non valido per '{current_section_title}': contenuto non significativo ({alnum_count} caratteri alfanumerici)"
        )
    if char_count < min_chars:
        raise ValueError(
            f"Capitolo troppo corto per '{current_section_title}': {char_count} caratteri "
            f"(minimo richiesto: {min_chars})"
        )
    if word_count < min_words:
        raise ValueError(
            f"Capitolo troppo breve per '{current_section_title}': {word_count} parole "
            f"(minimo richiesto: {min_words})"
        )

    return text


def format_question_answers_for_writer(question_answers: list[QuestionAnswer]) -> Optional[str]:
    """Formatta le risposte alle domande preliminari come vincoli espliciti per lo scrittore."""
    if not question_answers:
        return None

    answered_lines = []
    for qa in question_answers:
        if qa.answer and qa.answer.strip():
            answered_lines.append(f"- {qa.question_id}: {qa.answer.strip()}")

    if not answered_lines:
        return None

    return "\n".join(answered_lines)


async def refresh_story_bible_for_session(
    session_store: Any,
    session: Any,
    outline_sections: list[dict[str, Any]],
) -> dict[str, Any]:
    """Rigenera e persiste la story bible della sessione usando outline e capitoli già completati."""
    session.story_bible = build_story_bible(
        form_data=session.form_data,
        question_answers=session.question_answers,
        validated_draft=session.current_draft or "",
        draft_title=session.current_title,
        outline_sections=outline_sections,
        completed_chapters=session.book_chapters or [],
        draft_version=session.current_version,
        outline_version=session.outline_version,
        character_profiles=getattr(session, "character_profiles", None),
    )
    await save_session_async(session_store, session)
    logger.info(
        "Story bible rigenerata",
        context={
            "session_id": getattr(session, "session_id", None),
            "outline_sections": len(outline_sections),
            "completed_chapters": len(session.book_chapters or []),
        },
    )
    return session.story_bible


def get_chapter_review_settings(app_config: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Restituisce la configurazione del review flow dei capitoli."""
    if app_config is None:
        app_config = get_app_config()

    review_config = app_config.get("review", {})
    chapters_config = review_config.get("chapters", {}) if isinstance(review_config, dict) else {}
    target_modes = chapters_config.get("target_modes", ["pro", "ultra"])
    if not isinstance(target_modes, list):
        target_modes = ["pro", "ultra"]

    return {
        "enabled": bool(chapters_config.get("enabled", True)),
        "target_modes": [str(mode) for mode in target_modes],
        "min_chapter_words": int(chapters_config.get("min_chapter_words", 220)),
        "max_issues": int(chapters_config.get("max_issues", 5)),
        "reviewer_max_output_tokens": int(chapters_config.get("reviewer_max_output_tokens", 2048)),
        "allow_fallback_to_original": bool(chapters_config.get("allow_fallback_to_original", True)),
    }


def combine_token_usage(*token_usages: dict[str, int]) -> dict[str, int]:
    """Somma il token usage di più chiamate LLM."""
    combined = {"input_tokens": 0, "output_tokens": 0, "model": None}
    for usage in token_usages:
        if not usage:
            continue
        combined["input_tokens"] += int(usage.get("input_tokens", 0) or 0)
        combined["output_tokens"] += int(usage.get("output_tokens", 0) or 0)
        if usage.get("model"):
            combined["model"] = usage.get("model")
    return combined

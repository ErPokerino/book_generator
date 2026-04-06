"""Review editoriale del capitolo e revisione non bloccante."""

from __future__ import annotations

from typing import Any, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from app.agent.story_bible import (
    get_nearby_chapter_cards,
    get_relevant_continuity_notes,
)
from app.agent.writer.common import (
    combine_token_usage,
    get_chapter_review_settings,
    validate_generated_chapter_text,
)
from app.agent.writer.prompts import load_chapter_reviewer_context
from app.core.config import get_app_config, get_temperature_for_agent
from app.core.logging import get_logger
from app.llm import (
    ChapterReviewPayload,
    LLMTraceRecorder,
    append_contract_instructions,
    build_google_chat_model,
    get_max_output_tokens,
    invoke_structured_chat_model,
    parse_json_model,
    resolve_generation_mode,
)
from app.models import SubmissionRequest

logger = get_logger("writer-review")


def should_run_chapter_review(
    form_data: SubmissionRequest,
    chapter_text: str,
    app_config: Optional[dict[str, Any]] = None,
) -> bool:
    """Determina se attivare il pass review->revise per il capitolo."""
    settings = get_chapter_review_settings(app_config)
    if not settings["enabled"]:
        return False
    mode = resolve_generation_mode(form_data.llm_model)
    if mode not in settings["target_modes"]:
        return False
    return len(chapter_text.split()) >= settings["min_chapter_words"]


def parse_chapter_review_response(response_text: str, max_issues: int = 5) -> dict[str, Any]:
    """Parsa l'output JSON del reviewer capitolo."""
    payload = parse_json_model(response_text, ChapterReviewPayload)
    return _normalize_chapter_review_payload(payload, max_issues=max_issues)


def _normalize_chapter_review_payload(
    payload: ChapterReviewPayload,
    *,
    max_issues: int,
) -> dict[str, Any]:
    """Normalizza il payload tipizzato del reviewer in un dizionario applicativo."""
    issues = payload.issues[:max_issues]
    preserve = payload.preserve[:max_issues]
    needs_revision = payload.needs_revision or bool(issues)
    if not issues:
        needs_revision = False
    return {
        "needs_revision": needs_revision,
        "issues": issues,
        "preserve": preserve,
    }


def format_chapter_review_context(
    form_data: SubmissionRequest,
    current_section: dict[str, Any],
    story_bible: Optional[dict[str, Any]],
    chapter_text: str,
) -> str:
    """Costruisce il contesto compatto per l'editor reviewer."""
    lines = [
        f"## Modalità: {resolve_generation_mode(form_data.llm_model)}",
        f"## Sezione corrente: {current_section.get('title', 'Sezione senza titolo')}",
        "### Descrizione della sezione",
        current_section.get("description", "Nessuna descrizione disponibile."),
    ]

    if story_bible:
        character_profiles = story_bible.get("character_profiles")
        if character_profiles:
            lines.append("\n### Profili personaggi")
            lines.append(character_profiles)

        creative_brief = story_bible.get("creative_brief", [])
        if creative_brief:
            lines.append("\n### Brief creativo")
            for item in creative_brief:
                lines.append(f"- {item}")

        user_constraints = story_bible.get("user_constraints", [])
        if user_constraints:
            lines.append("\n### Vincoli utente")
            for item in user_constraints:
                lines.append(f"- {item}")

        nearby_cards = get_nearby_chapter_cards(
            story_bible,
            current_section.get("section_index"),
        )
        if nearby_cards:
            lines.append("\n### Chapter cards rilevanti")
            for card in nearby_cards:
                lines.append(f"- {card.get('title', '')}: {card.get('description', '')}")

        continuity_notes = get_relevant_continuity_notes(story_bible, [])
        if continuity_notes:
            lines.append("\n### Continuità consolidata")
            for note in continuity_notes:
                lines.append(f"- {note.get('title', '')}: {note.get('summary', '')}")

        recent_developments = story_bible.get("recent_developments", [])
        if recent_developments:
            lines.append("\n### Ultimi sviluppi")
            for item in recent_developments:
                lines.append(f"- {item}")

    lines.append("\n## Capitolo da valutare")
    lines.append(chapter_text)
    return "\n".join(lines)


async def review_and_maybe_revise_chapter(
    *,
    agent_context: str,
    formatted_context: str,
    gemini_model: str,
    api_key: Optional[str] = None,
    form_data: SubmissionRequest,
    current_section: dict[str, Any],
    story_bible: Optional[dict[str, Any]],
    chapter_text: str,
) -> tuple[str, dict[str, int]]:
    """Esegue un pass review->revise non bloccante su un capitolo già valido."""
    app_config = get_app_config()
    if not should_run_chapter_review(form_data, chapter_text, app_config):
        return chapter_text, {"input_tokens": 0, "output_tokens": 0, "model": gemini_model}

    settings = get_chapter_review_settings(app_config)
    review_payload = format_chapter_review_context(
        form_data=form_data,
        current_section=current_section,
        story_bible=story_bible,
        chapter_text=chapter_text,
    )
    reviewer_context = append_contract_instructions(
        load_chapter_reviewer_context(),
        (
            "IMPORTANTE: il runtime applica uno schema strutturato nativo. "
            "Compila soltanto i campi `needs_revision`, `issues` e `preserve` senza wrapper o testo extra."
        ),
    )
    review_trace = LLMTraceRecorder(
        stage="chapter-review",
        request_id=current_section.get("title", "chapter-review"),
    )

    try:
        reviewer_llm = build_google_chat_model(
            model_name=gemini_model,
            api_key=api_key,
            temperature=get_temperature_for_agent("chapter_reviewer", gemini_model),
            max_output_tokens=min(
                get_max_output_tokens(gemini_model),
                settings["reviewer_max_output_tokens"],
            ),
        )
        review_payload_model, review_token_usage, _raw_output = await invoke_structured_chat_model(
            llm=reviewer_llm,
            schema=ChapterReviewPayload,
            messages=[
                SystemMessage(content=reviewer_context),
                HumanMessage(
                    content=(
                        "Valuta il capitolo seguente come editor tecnico. "
                        "Compila soltanto il payload editoriale richiesto.\n\n"
                        f"{review_payload}"
                    )
                ),
            ],
            model_name=gemini_model,
            stage="chapter-review",
            request_label=f"review {current_section['title']}",
            trace_recorder=review_trace,
        )
        review_result = _normalize_chapter_review_payload(
            review_payload_model,
            max_issues=settings["max_issues"],
        )
        review_trace.record(
            "review_decoded",
            needs_revision=review_result["needs_revision"],
            issues=review_result["issues"],
            preserve=review_result["preserve"],
        )

        if not review_result["needs_revision"]:
            return chapter_text, review_token_usage

        revision_prompt = f"""Rivedi il capitolo seguente mantenendo voce, continuità e materiale già efficace.

{formatted_context}

## CAPITOLO DA REVISIONARE
{chapter_text}

## PROBLEMI DA CORREGGERE
{chr(10).join(f"- {issue}" for issue in review_result["issues"])}
"""
        if review_result["preserve"]:
            revision_prompt += f"""
## ELEMENTI DA PRESERVARE
{chr(10).join(f"- {item}" for item in review_result["preserve"])}
"""
        revision_prompt += """
## ISTRUZIONI FINALI
- Correggi solo i problemi segnalati, senza cambiare inutilmente il resto.
- Mantieni coerenza con continuità, chapter cards e vincoli utente.
- Restituisci SOLO la versione finale del capitolo, senza note editoriali o spiegazioni.
"""

        revision_trace = LLMTraceRecorder(
            stage="chapter-revision",
            request_id=current_section.get("title", "chapter-revision"),
        )
        revision_llm = build_google_chat_model(
            model_name=gemini_model,
            api_key=api_key,
            temperature=get_temperature_for_agent("chapter_reviser", gemini_model),
            max_output_tokens=get_max_output_tokens(gemini_model),
        )
        revised_text, revision_token_usage = await invoke_chat_model(
            llm=revision_llm,
            messages=[
                SystemMessage(content=agent_context),
                HumanMessage(content=revision_prompt),
            ],
            model_name=gemini_model,
            stage="chapter-revision",
            request_label=f"revise {current_section['title']}",
            trace_recorder=revision_trace,
        )
        revised_text = validate_generated_chapter_text(
            revised_text,
            current_section["title"],
            app_config=app_config,
        )
        logger.info(
            "Capitolo rivisto dopo review",
            context={
                "section_title": current_section["title"],
                "issues_count": len(review_result["issues"]),
            },
        )
        return revised_text, combine_token_usage(review_token_usage, revision_token_usage)
    except Exception as exc:
        if settings["allow_fallback_to_original"]:
            logger.warning(
                "Review flow fallito, uso il capitolo originale",
                context={
                    "section_title": current_section.get("title"),
                    "error": str(exc),
                },
            )
            return chapter_text, {"input_tokens": 0, "output_tokens": 0, "model": gemini_model}
        raise

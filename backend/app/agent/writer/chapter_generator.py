"""Generazione dei singoli capitoli, inclusa la modalità long-form."""

from __future__ import annotations

from typing import Any, Optional

from app.agent.writer.common import combine_token_usage, validate_generated_chapter_text
from app.agent.writer.context_builder import format_writer_prefix, format_writer_turn
from app.agent.writer.context_cache import generate_chapter_with_prefix_cache
from app.agent.writer.prompts import load_writer_agent_context
from app.core.config import get_app_config
from app.core.logging import get_logger
from app.llm import LLMTraceRecorder, get_stage_model, get_writer_split_calls
from app.models import QuestionAnswer, SubmissionRequest

logger = get_logger("writer-chapter-generator")


def _validate_chapter_part(text: str, current_section_title: str) -> str:
    cleaned = text.strip()
    if len(cleaned) < 20:
        raise ValueError(
            f"Parte del capitolo generata vuota o troppo corta per '{current_section_title}'"
        )
    return cleaned


def _build_prefix_and_turn(
    *,
    form_data: SubmissionRequest,
    question_answers: list[QuestionAnswer],
    validated_draft: str,
    draft_title: Optional[str],
    outline_text: str,
    previous_chapters: list[dict[str, Any]],
    current_section: dict[str, Any],
    story_bible: Optional[dict[str, Any]],
    is_long_form_part1: bool = False,
    is_long_form_part2: bool = False,
    part1_text: Optional[str] = None,
) -> tuple[str, str]:
    shared = dict(
        form_data=form_data,
        question_answers=question_answers,
        validated_draft=validated_draft,
        draft_title=draft_title,
        outline_text=outline_text,
        story_bible=story_bible,
    )
    prefix = format_writer_prefix(**shared)
    turn = format_writer_turn(
        **shared,
        previous_chapters=previous_chapters,
        current_section=current_section,
        is_long_form_part1=is_long_form_part1,
        is_long_form_part2=is_long_form_part2,
        part1_text=part1_text,
    )
    return prefix, turn


async def _generate_chapter_part(
    *,
    agent_context: str,
    prefix: str,
    turn: str,
    gemini_model: str,
    api_key: Optional[str] = None,
    current_section_title: str,
    session_id: str | None = None,
    request_label: str,
) -> tuple[str, dict[str, int]]:
    return await generate_chapter_with_prefix_cache(
        agent_context=agent_context,
        prefix=prefix,
        turn=turn,
        gemini_model=gemini_model,
        api_key=api_key,
        current_section_title=current_section_title,
        session_id=session_id,
        request_label=request_label,
        response_validator=lambda text: _validate_chapter_part(text, current_section_title),
    )


async def generate_chapter(
    form_data: SubmissionRequest,
    question_answers: list[QuestionAnswer],
    validated_draft: str,
    draft_title: Optional[str],
    outline_text: str,
    previous_chapters: list[dict[str, Any]],
    current_section: dict[str, Any],
    story_bible: Optional[dict[str, Any]],
    api_key: Optional[str] = None,
    session_id: str | None = None,
) -> tuple[str, dict[str, int]]:
    """
    Genera il testo di un singolo capitolo/sezione usando il contesto completo.

    Supporta due modalità:
    - Standard: 1 chiamata singola
    - Ultra: 2 chiamate sequenziali (senza review)
    """
    agent_context = load_writer_agent_context()
    is_long_form = get_writer_split_calls(form_data=form_data) >= 2
    gemini_model = get_stage_model("chapters", form_data.llm_model, form_data=form_data)
    trace = LLMTraceRecorder(
        stage="chapter-generation",
        session_id=session_id,
        request_id=current_section.get("title", "chapter"),
    )
    trace.record(
        "chapter_generation_started",
        long_form=is_long_form,
        model=gemini_model,
        section=current_section.get("title"),
        previous_chapters=len(previous_chapters),
    )

    if is_long_form:
        prefix, turn_part1 = _build_prefix_and_turn(
            form_data=form_data,
            question_answers=question_answers,
            validated_draft=validated_draft,
            draft_title=draft_title,
            outline_text=outline_text,
            previous_chapters=previous_chapters,
            current_section=current_section,
            story_bible=story_bible,
            is_long_form_part1=True,
        )
        part1_text, token_usage_part1 = await _generate_chapter_part(
            agent_context=agent_context,
            prefix=prefix,
            turn=turn_part1,
            gemini_model=gemini_model,
            api_key=api_key,
            current_section_title=current_section["title"],
            session_id=session_id,
            request_label=f"{current_section['title']}-part1",
        )

        _, turn_part2 = _build_prefix_and_turn(
            form_data=form_data,
            question_answers=question_answers,
            validated_draft=validated_draft,
            draft_title=draft_title,
            outline_text=outline_text,
            previous_chapters=previous_chapters,
            current_section=current_section,
            story_bible=story_bible,
            is_long_form_part2=True,
            part1_text=part1_text,
        )
        part2_text, token_usage_part2 = await _generate_chapter_part(
            agent_context=agent_context,
            prefix=prefix,
            turn=turn_part2,
            gemini_model=gemini_model,
            api_key=api_key,
            current_section_title=current_section["title"],
            session_id=session_id,
            request_label=f"{current_section['title']}-part2",
        )

        chapter_text = f"{part1_text}\n\n{part2_text}".strip()
        token_usage = combine_token_usage(token_usage_part1, token_usage_part2)
        app_config = get_app_config()
        chapter_text = validate_generated_chapter_text(
            chapter_text,
            current_section["title"],
            app_config=app_config,
        )
        trace.record(
            "chapter_generation_completed",
            section=current_section["title"],
            long_form=True,
            chapter_characters=len(chapter_text),
            token_usage=token_usage,
        )
        return chapter_text, token_usage

    prefix, turn = _build_prefix_and_turn(
        form_data=form_data,
        question_answers=question_answers,
        validated_draft=validated_draft,
        draft_title=draft_title,
        outline_text=outline_text,
        previous_chapters=previous_chapters,
        current_section=current_section,
        story_bible=story_bible,
    )
    chapter_text, token_usage = await _generate_chapter_part(
        agent_context=agent_context,
        prefix=prefix,
        turn=turn,
        gemini_model=gemini_model,
        api_key=api_key,
        current_section_title=current_section["title"],
        session_id=session_id,
        request_label=current_section["title"],
    )
    app_config = get_app_config()
    chapter_text = validate_generated_chapter_text(
        chapter_text,
        current_section["title"],
        app_config=app_config,
    )
    trace.record(
        "chapter_generation_completed",
        section=current_section["title"],
        long_form=False,
        chapter_characters=len(chapter_text),
        token_usage=token_usage,
    )
    logger.info(
        "Capitolo generato con successo",
        context={
            "session_id": session_id,
            "section_title": current_section["title"],
            "long_form": is_long_form,
        },
    )
    return chapter_text, token_usage

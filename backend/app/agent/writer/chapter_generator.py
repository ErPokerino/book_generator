"""Generazione dei singoli capitoli, inclusa la modalità long-form."""

from __future__ import annotations

from typing import Any, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from app.agent.writer.common import combine_token_usage, validate_generated_chapter_text
from app.agent.writer.context_builder import format_writer_context
from app.agent.writer.prompts import load_writer_agent_context
from app.agent.writer.review import review_and_maybe_revise_chapter
from app.core.config import get_app_config, get_temperature_for_agent
from app.core.logging import get_logger
from app.llm import (
    LLMTraceRecorder,
    build_google_chat_model,
    get_max_output_tokens,
    invoke_chat_model,
    map_book_model_name,
)
from app.models import QuestionAnswer, SubmissionRequest

logger = get_logger("writer-chapter-generator")


def _validate_chapter_part(text: str, current_section_title: str) -> str:
    cleaned = text.strip()
    if len(cleaned) < 20:
        raise ValueError(
            f"Parte del capitolo generata vuota o troppo corta per '{current_section_title}'"
        )
    return cleaned


async def _generate_chapter_part(
    *,
    agent_context: str,
    formatted_context: str,
    gemini_model: str,
    api_key: Optional[str] = None,
    current_section_title: str,
    session_id: str | None = None,
    request_label: str,
) -> tuple[str, dict[str, int]]:
    """Helper per generare una parte di un capitolo (usato per modalità long form)."""
    llm = build_google_chat_model(
        model_name=gemini_model,
        api_key=api_key,
        temperature=get_temperature_for_agent("writer_generator", gemini_model),
        max_output_tokens=get_max_output_tokens(gemini_model),
    )
    return await invoke_chat_model(
        llm=llm,
        messages=[
            SystemMessage(content=agent_context),
            HumanMessage(
                content=(
                    "Scrivi la sezione del romanzo indicata di seguito.\n\n"
                    f"{formatted_context}\n\n"
                    "Scrivi SOLO il testo narrativo della sezione, senza titoli o numerazioni. "
                    "Inizia direttamente con la narrazione."
                )
            ),
        ],
        model_name=gemini_model,
        stage="chapter-generation",
        request_label=request_label,
        session_id=session_id,
        trace_recorder=LLMTraceRecorder(
            stage="chapter-generation",
            session_id=session_id,
            request_id=request_label,
        ),
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
    - Long Form (`gemini-3-ultra`): 2 chiamate sequenziali
    """
    agent_context = load_writer_agent_context()
    is_long_form = form_data.llm_model.lower() == "gemini-3-ultra"
    gemini_model = map_book_model_name(form_data.llm_model)
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
        formatted_context_part1 = format_writer_context(
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
            formatted_context=formatted_context_part1,
            gemini_model=gemini_model,
            api_key=api_key,
            current_section_title=current_section["title"],
            session_id=session_id,
            request_label=f"{current_section['title']}-part1",
        )

        formatted_context_part2 = format_writer_context(
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
            formatted_context=formatted_context_part2,
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
        review_context = format_writer_context(
            form_data=form_data,
            question_answers=question_answers,
            validated_draft=validated_draft,
            draft_title=draft_title,
            outline_text=outline_text,
            previous_chapters=previous_chapters,
            current_section=current_section,
            story_bible=story_bible,
        )
        chapter_text, review_token_usage = await review_and_maybe_revise_chapter(
            agent_context=agent_context,
            formatted_context=review_context,
            gemini_model=gemini_model,
            api_key=api_key,
            form_data=form_data,
            current_section=current_section,
            story_bible=story_bible,
            chapter_text=chapter_text,
        )
        final_usage = combine_token_usage(token_usage, review_token_usage)
        trace.record(
            "chapter_generation_completed",
            section=current_section["title"],
            long_form=True,
            chapter_characters=len(chapter_text),
            token_usage=final_usage,
        )
        return chapter_text, final_usage

    formatted_context = format_writer_context(
        form_data=form_data,
        question_answers=question_answers,
        validated_draft=validated_draft,
        draft_title=draft_title,
        outline_text=outline_text,
        previous_chapters=previous_chapters,
        current_section=current_section,
        story_bible=story_bible,
    )
    standard_llm = build_google_chat_model(
        model_name=gemini_model,
        api_key=api_key,
        temperature=get_temperature_for_agent("writer_generator", gemini_model),
        max_output_tokens=get_max_output_tokens(gemini_model),
    )
    chapter_text, token_usage = await invoke_chat_model(
        llm=standard_llm,
        messages=[
            SystemMessage(content=agent_context),
            HumanMessage(
                content=(
                    "Scrivi la sezione del romanzo indicata di seguito.\n\n"
                    f"{formatted_context}\n\n"
                    "Scrivi SOLO il testo narrativo della sezione, senza titoli o numerazioni. "
                    "Inizia direttamente con la narrazione."
                )
            ),
        ],
        model_name=gemini_model,
        stage="chapter-generation",
        request_label=current_section["title"],
        session_id=session_id,
        trace_recorder=trace,
    )
    app_config = get_app_config()
    chapter_text = validate_generated_chapter_text(
        chapter_text,
        current_section["title"],
        app_config=app_config,
    )
    chapter_text, review_token_usage = await review_and_maybe_revise_chapter(
        agent_context=agent_context,
        formatted_context=formatted_context,
        gemini_model=gemini_model,
        api_key=api_key,
        form_data=form_data,
        current_section=current_section,
        story_bible=story_bible,
        chapter_text=chapter_text,
    )
    final_usage = combine_token_usage(token_usage, review_token_usage)
    trace.record(
        "chapter_generation_completed",
        section=current_section["title"],
        long_form=False,
        chapter_characters=len(chapter_text),
        token_usage=final_usage,
    )
    logger.info(
        "Capitolo generato con successo",
        context={
            "session_id": session_id,
            "section_title": current_section["title"],
            "long_form": is_long_form,
        },
    )
    return chapter_text, final_usage

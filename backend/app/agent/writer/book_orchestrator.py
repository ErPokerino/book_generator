"""Orchestrazione della generazione completa del libro e della ripresa."""

from __future__ import annotations

import math
from typing import Any, Optional

from app.agent.session_store import get_session_store
from app.agent.session_store_helpers import (
    end_chapter_timing_async,
    get_session_async,
    pause_writing_async,
    resume_writing_async,
    start_chapter_timing_async,
    update_book_chapter_async,
    update_token_usage_async,
    update_writing_progress_async,
)
from app.agent.writer.chapter_generator import generate_chapter
from app.agent.writer.common import refresh_story_bible_for_session, validate_generated_chapter_text
from app.agent.writer.outline_ast import parse_outline_sections
from app.core.config import get_app_config
from app.core.logging import get_logger
from app.llm import LLMTraceRecorder
from app.models import QuestionAnswer, SubmissionRequest
from app.services.pdf_service import calculate_page_count

logger = get_logger("writer-book-orchestrator")


def _get_retry_count(app_config: Optional[dict[str, Any]] = None) -> int:
    if app_config is None:
        app_config = get_app_config()
    retry_config = app_config.get("retry", {}).get("chapter_generation", {})
    return int(retry_config.get("max_retries", 2))


def _calculate_total_pages(completed_chapters: list[dict[str, Any]]) -> int:
    chapters_pages = sum(calculate_page_count(chapter.get("content", "")) for chapter in completed_chapters)
    cover_pages = 1
    app_config = get_app_config()
    toc_chapters_per_page = app_config.get("validation", {}).get("toc_chapters_per_page", 30)
    toc_pages = math.ceil(len(completed_chapters) / toc_chapters_per_page) if completed_chapters else 0
    return chapters_pages + cover_pages + toc_pages


async def _initialize_writing_progress(
    *,
    session_id: str,
    sections: list[dict[str, Any]],
) -> Any:
    session_store = get_session_store()
    total_sections = len(sections)
    existing_session = await get_session_async(session_store, session_id, user_id=None)
    if existing_session and existing_session.writing_progress:
        existing_total = existing_session.writing_progress.get("total_steps", 0)
        if existing_total != total_sections:
            await update_writing_progress_async(
                session_store,
                session_id=session_id,
                current_step=0,
                total_steps=total_sections,
                current_section_name=sections[0]["title"] if sections else None,
                is_complete=False,
                is_paused=False,
            )
    else:
        await update_writing_progress_async(
            session_store,
            session_id=session_id,
            current_step=0,
            total_steps=total_sections,
            current_section_name=sections[0]["title"] if sections else None,
            is_complete=False,
            is_paused=False,
        )
    session = await get_session_async(session_store, session_id, user_id=None)
    if not session:
        raise ValueError(f"Sessione {session_id} non trovata durante la preparazione della story bible")
    return session


async def _finalize_completed_book(
    *,
    session_id: str,
    completed_chapters: list[dict[str, Any]],
    total_sections: int,
) -> None:
    session_store = get_session_store()
    total_pages = _calculate_total_pages(completed_chapters)
    await update_writing_progress_async(
        session_store,
        session_id=session_id,
        current_step=total_sections,
        total_steps=total_sections,
        current_section_name=None,
        is_complete=True,
        is_paused=False,
        total_pages=total_pages,
        completed_chapters_count=len(completed_chapters),
    )
    logger.info(
        "Scrittura libro completata",
        context={
            "session_id": session_id,
            "sections": total_sections,
            "total_pages": total_pages,
        },
    )


async def _run_book_generation_loop(
    *,
    session_id: str,
    form_data: SubmissionRequest,
    question_answers: list[QuestionAnswer],
    validated_draft: str,
    draft_title: Optional[str],
    outline_text: str,
    sections: list[dict[str, Any]],
    story_bible: dict[str, Any],
    api_key: str,
    start_index: int,
    completed_chapters: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], bool]:
    session_store = get_session_store()
    total_sections = len(sections)
    app_config = get_app_config()
    max_retries = _get_retry_count(app_config)
    trace = LLMTraceRecorder(
        stage="book-orchestrator",
        session_id=session_id,
        request_id=f"start-{start_index}",
    )

    for index in range(start_index, total_sections):
        section = sections[index]
        trace.record("chapter_started", section_index=index, section_title=section["title"])
        await update_writing_progress_async(
            session_store,
            session_id=session_id,
            current_step=index,
            total_steps=total_sections,
            current_section_name=section["title"],
            is_complete=False,
            is_paused=False,
        )
        await start_chapter_timing_async(session_store, session_id)
        chapter_content: str | None = None

        for retry in range(max_retries):
            try:
                chapter_content, chapter_token_usage = await generate_chapter(
                    form_data=form_data,
                    question_answers=question_answers,
                    validated_draft=validated_draft,
                    draft_title=draft_title,
                    outline_text=outline_text,
                    previous_chapters=completed_chapters,
                    current_section=section,
                    story_bible=story_bible,
                    api_key=api_key,
                    session_id=session_id,
                )
                await update_token_usage_async(
                    session_store,
                    session_id,
                    phase="chapters",
                    input_tokens=chapter_token_usage.get("input_tokens", 0),
                    output_tokens=chapter_token_usage.get("output_tokens", 0),
                    model=chapter_token_usage.get("model", "gemini-3.1-pro-preview"),
                )
                chapter_content = validate_generated_chapter_text(
                    chapter_content,
                    section["title"],
                    app_config=app_config,
                )
                await end_chapter_timing_async(session_store, session_id)
                break
            except ValueError as exc:
                if retry < max_retries - 1:
                    trace.record(
                        "chapter_retry",
                        section_index=index,
                        retry=retry + 1,
                        error_type=type(exc).__name__,
                        error=str(exc),
                    )
                    continue

                await end_chapter_timing_async(session_store, session_id)
                error_msg = (
                    f"Contenuto non valido per la sezione '{section['title']}' "
                    f"dopo {max_retries} tentativi: {exc}"
                )
                await pause_writing_async(
                    session_store,
                    session_id=session_id,
                    current_step=index,
                    total_steps=total_sections,
                    current_section_name=section["title"],
                    error_msg=error_msg,
                )
                trace.record("chapter_paused", section_index=index, error=error_msg)
                logger.warning(
                    "Generazione messa in pausa per output non valido",
                    context={"session_id": session_id, "section_title": section["title"]},
                )
                return completed_chapters, False
            except Exception as exc:  # pragma: no cover - exercised via runtime flow
                if retry < max_retries - 1:
                    trace.record(
                        "chapter_retry",
                        section_index=index,
                        retry=retry + 1,
                        error_type=type(exc).__name__,
                        error=str(exc),
                    )
                    continue

                await end_chapter_timing_async(session_store, session_id)
                error_msg = f"Errore nella generazione della sezione '{section['title']}': {exc}"
                await pause_writing_async(
                    session_store,
                    session_id=session_id,
                    current_step=index,
                    total_steps=total_sections,
                    current_section_name=section["title"],
                    error_msg=error_msg,
                )
                trace.record("chapter_paused", section_index=index, error=error_msg)
                logger.exception(
                    "Generazione messa in pausa per errore inatteso",
                    context={"session_id": session_id, "section_title": section["title"]},
                )
                return completed_chapters, False

        if chapter_content:
            chapter_dict = {
                "title": section["title"],
                "content": chapter_content,
                "section_index": index,
            }
            session = await update_book_chapter_async(
                session_store,
                session_id=session_id,
                chapter_title=section["title"],
                chapter_content=chapter_content,
                section_index=index,
            )
            completed_chapters.append(chapter_dict)
            story_bible = await refresh_story_bible_for_session(session_store, session, sections)
            trace.record(
                "chapter_completed",
                section_index=index,
                section_title=section["title"],
                chapter_characters=len(chapter_content),
            )

    return completed_chapters, True


async def generate_full_book(
    session_id: str,
    form_data: SubmissionRequest,
    question_answers: list[QuestionAnswer],
    validated_draft: str,
    draft_title: Optional[str],
    outline_text: str,
    api_key: str,
) -> list[dict[str, Any]]:
    """Genera l'intero romanzo sezione per sezione in modo autoregressivo."""
    sections = parse_outline_sections(outline_text)
    session_store = get_session_store()
    session = await _initialize_writing_progress(session_id=session_id, sections=sections)
    story_bible = await refresh_story_bible_for_session(session_store, session, sections)
    completed_chapters, completed = await _run_book_generation_loop(
        session_id=session_id,
        form_data=form_data,
        question_answers=question_answers,
        validated_draft=validated_draft,
        draft_title=draft_title,
        outline_text=outline_text,
        sections=sections,
        story_bible=story_bible,
        api_key=api_key,
        start_index=0,
        completed_chapters=[],
    )
    if completed:
        await _finalize_completed_book(
            session_id=session_id,
            completed_chapters=completed_chapters,
            total_sections=len(sections),
        )
    return completed_chapters


async def resume_book_generation(
    session_id: str,
    api_key: str,
) -> list[dict[str, Any]]:
    """Riprende la generazione del libro dal capitolo fallito."""
    session_store = get_session_store()
    session = await get_session_async(session_store, session_id, user_id=None)
    if not session:
        raise ValueError(f"Sessione {session_id} non trovata")
    if not session.writing_progress:
        raise ValueError(f"Sessione {session_id} non ha uno stato di scrittura")

    progress = session.writing_progress
    if not progress.get("is_paused", False):
        raise ValueError(f"Sessione {session_id} non è in stato di pausa")

    await resume_writing_async(session_store, session_id)

    form_data = session.form_data
    question_answers = session.question_answers
    validated_draft = session.current_draft
    draft_title = session.current_title
    outline_text = session.current_outline
    if not validated_draft or not outline_text:
        raise ValueError(f"Sessione {session_id} non ha bozza validata o outline")

    sections = parse_outline_sections(outline_text)
    completed_chapters = session.book_chapters.copy()
    story_bible = await refresh_story_bible_for_session(session_store, session, sections)
    failed_step = int(progress.get("current_step", 0) or 0)

    completed_chapters, completed = await _run_book_generation_loop(
        session_id=session_id,
        form_data=form_data,
        question_answers=question_answers,
        validated_draft=validated_draft,
        draft_title=draft_title,
        outline_text=outline_text,
        sections=sections,
        story_bible=story_bible,
        api_key=api_key,
        start_index=failed_step,
        completed_chapters=completed_chapters,
    )
    if completed:
        await _finalize_completed_book(
            session_id=session_id,
            completed_chapters=completed_chapters,
            total_sections=len(sections),
        )
    return completed_chapters

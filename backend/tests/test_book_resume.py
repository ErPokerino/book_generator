from unittest.mock import AsyncMock

import pytest
from fastapi import BackgroundTasks, HTTPException

from app.agent.writer import book_orchestrator
from app.api.routers import book
from app.models import BookGenerationRequest
from app.services import book_generation_service
from app.services.process_job_service import begin_process_job_async, merge_process_progress_async


@pytest.fixture
def paused_book(session_store, monkeypatch):
    session = session_store.get_session("session-1")
    session.current_draft = "Una detective indaga su una scomparsa."
    session.validated = True
    session.current_outline = "## Capitolo 1\nLa scomparsa.\n\n## Capitolo 2\nLa soluzione."
    session.book_chapters = [{"section_index": 0, "title": "Capitolo 1", "content": "Capitolo già salvato."}]
    # Simulate a crash after saving chapter 1, before advancing the checkpoint.
    session_store.pause_writing(session.session_id, 0, 2, "Capitolo 1", "Riavvio")
    for module in (book, book_generation_service, book_orchestrator):
        monkeypatch.setattr(module, "get_session_store", lambda: session_store)
    monkeypatch.setattr(book_generation_service, "_run_post_book_completion_pipeline", AsyncMock())
    return session


@pytest.mark.asyncio
async def test_resume_endpoint_runs_worker_and_skips_persisted_chapters(paused_book, monkeypatch):
    generate = AsyncMock(return_value=("Una scena con dialoghi e azioni concrete. " * 80, {"input_tokens": 10, "output_tokens": 20}))
    monkeypatch.setattr(book_orchestrator, "generate_chapter", generate)
    tasks = BackgroundTasks()
    await book.resume_book_generation_endpoint(paused_book.session_id, tasks)

    duplicate_tasks = BackgroundTasks()
    duplicate = await book.resume_book_generation_endpoint(paused_book.session_id, duplicate_tasks)
    assert duplicate.already_running
    assert not duplicate_tasks.tasks

    await tasks()
    assert generate.await_count == 1
    assert generate.call_args.kwargs["current_section"]["title"] == "Capitolo 2"
    assert len(generate.call_args.kwargs["previous_chapters"]) == 2  # List includes newly appended chapter.
    assert paused_book.book_chapters[0]["content"] == "Capitolo già salvato."
    assert [ch["section_index"] for ch in paused_book.book_chapters] == [0, 1]
    assert paused_book.writing_progress["is_complete"]


@pytest.mark.asyncio
async def test_unexpected_resume_failure_remains_recoverable(paused_book, monkeypatch):
    paused_book.writing_progress["current_step"] = 1
    monkeypatch.setattr(book_generation_service, "resume_book_generation", AsyncMock(side_effect=RuntimeError("Interruzione")))
    tasks = BackgroundTasks()
    await book.resume_book_generation_endpoint(paused_book.session_id, tasks)
    await tasks()
    assert paused_book.writing_progress["is_paused"]
    assert paused_book.writing_progress["current_step"] == 1
    assert paused_book.writing_progress["recoverable"]
    assert len(paused_book.book_chapters) == 1


@pytest.mark.asyncio
async def test_generate_cannot_overwrite_existing_chapters(paused_book):
    with pytest.raises(HTTPException) as error:
        await book.generate_book_endpoint(BookGenerationRequest(session_id=paused_book.session_id), BackgroundTasks())
    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_restarted_job_resets_completion_and_accepts_timezone_dates(session_store):
    session = session_store.get_session("session-1")
    session.writing_progress = {"is_complete": True, "status": "completed"}
    started, progress = await begin_process_job_async(session_store, session.session_id, "book")
    assert started and not progress["is_complete"]
    result = await merge_process_progress_async(session_store, session.session_id, "book", {
        "started_at": "2026-09-20T08:00:00+02:00", "completed_at": "2026-09-20T06:01:00Z",
    })
    assert result["job_metrics"]["duration_seconds"] == 60

import pytest

from app.agent.session_store import SessionStore
from app.services.process_job_service import (
    begin_process_job_async,
    mark_process_completed_async,
    mark_process_failed_async,
    mark_process_running_async,
    refresh_process_metrics_async,
    recover_interrupted_processes_async,
)


@pytest.mark.asyncio
async def test_begin_process_job_async_is_idempotent(session_store: SessionStore) -> None:
    created, progress = await begin_process_job_async(
        session_store,
        "session-1",
        "draft",
        total_steps=3,
    )

    assert created is True
    assert progress["status"] == "pending"
    assert progress["job_id"] == "draft:session-1"
    assert progress["attempt"] == 1

    duplicate_created, duplicate_progress = await begin_process_job_async(
        session_store,
        "session-1",
        "draft",
        total_steps=3,
    )

    assert duplicate_created is False
    assert duplicate_progress["job_id"] == progress["job_id"]
    assert duplicate_progress["attempt"] == 1


@pytest.mark.asyncio
async def test_recover_interrupted_processes_marks_jobs_recoverable(
    session_store: SessionStore,
) -> None:
    await mark_process_running_async(
        session_store,
        "session-1",
        "draft",
        current_step=1,
        total_steps=3,
    )
    await mark_process_running_async(
        session_store,
        "session-1",
        "book",
        current_step=2,
        total_steps=5,
        current_section_name="Capitolo 2",
    )

    recovered = await recover_interrupted_processes_async(session_store)
    session = session_store.get_session("session-1")

    assert recovered == 2
    assert session is not None
    assert session.draft_progress["status"] == "failed"
    assert session.draft_progress["recoverable"] is True
    assert "riavvio del server" in session.draft_progress["error"]
    assert session.writing_progress["status"] == "paused"
    assert session.writing_progress["recoverable"] is True
    assert session.writing_progress["job_id"] == "book:session-1"


@pytest.mark.asyncio
async def test_completed_process_exposes_observability_metrics(
    session_store: SessionStore,
) -> None:
    await begin_process_job_async(session_store, "session-1", "draft", total_steps=1)
    await mark_process_running_async(session_store, "session-1", "draft", current_step=0, total_steps=1)
    session_store.update_token_usage("session-1", "draft", 13, 21, "gemini-test")

    progress = await mark_process_completed_async(
        session_store,
        "session-1",
        "draft",
        current_step=1,
        total_steps=1,
        progress_percentage=100.0,
    )

    assert progress["job_metrics"]["error_count"] == 0
    assert progress["job_metrics"]["duration_seconds"] >= 0
    assert progress["job_metrics"]["token_usage"] == {
        "input_tokens": 13,
        "output_tokens": 21,
        "model": "gemini-test",
        "calls": 1,
    }


@pytest.mark.asyncio
async def test_refresh_metrics_syncs_book_costs_and_failures(
    session_store: SessionStore,
) -> None:
    await begin_process_job_async(session_store, "session-1", "book", total_steps=2)
    await mark_process_running_async(session_store, "session-1", "book", current_step=1, total_steps=2)
    session_store.update_token_usage("session-1", "chapters", 50, 80, "gemini-book")
    session_store.set_real_cost("session-1", 0.123456)
    session_store.update_writing_progress(
        "session-1",
        current_step=1,
        total_steps=2,
        current_section_name="Capitolo 1",
        is_complete=False,
        error=None,
    )

    refreshed = await refresh_process_metrics_async(session_store, "session-1", "book")
    failed = await mark_process_failed_async(
        session_store,
        "session-1",
        "book",
        "Errore di test",
        recoverable=True,
    )

    assert refreshed["job_metrics"]["token_usage"]["input_tokens"] == 50
    assert refreshed["job_metrics"]["real_cost_eur"] == 0.123456
    assert failed["job_metrics"]["error_count"] == 1

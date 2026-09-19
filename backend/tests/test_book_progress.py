import pytest

from app.agent.session_store import SessionStore
from app.api.routers import book as book_router
from app.models import SubmissionRequest


@pytest.mark.asyncio
async def test_book_progress_succeeds_while_writing(
    submission_request: SubmissionRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = SessionStore()
    session = store.create_session("progress-session", submission_request, [])
    session.current_outline = "## Capitolo 1\n- Apertura.\n## Capitolo 2\n- Svolta."
    session.writing_progress = {
        "current_step": 1,
        "total_steps": 2,
        "is_complete": False,
        "status": "running",
        "current_section_name": "Capitolo 2",
    }
    session.book_chapters = [
        {
            "title": "Capitolo 1",
            "content": "Testo del primo capitolo. " * 20,
            "section_index": 0,
        }
    ]

    async def fake_get_session(_store, session_id, user_id=None):
        return store.get_session(session_id)

    monkeypatch.setattr(book_router, "get_session_store", lambda: store)
    monkeypatch.setattr(book_router, "get_session_async", fake_get_session)
    monkeypatch.setattr(book_router, "calculate_real_generation_cost", lambda _session: 0.01)

    result = await book_router.get_book_progress_endpoint("progress-session")

    assert result.session_id == "progress-session"
    assert result.current_step == 1
    assert result.total_steps == 2
    assert result.is_complete is False
    assert result.error is None

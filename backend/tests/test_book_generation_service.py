import pytest

from app.agent.session_store import SessionStore
from app.services.book_generation_service import (
    _generate_critique_artifact,
    _persist_writing_completion,
    _run_post_book_completion_pipeline,
)
from app.models import SubmissionRequest


@pytest.fixture
def book_session_store(submission_request: SubmissionRequest) -> SessionStore:
    store = SessionStore()
    enriched_request = submission_request.model_copy(
        update={
            "user_name": "Ada",
            "cover_style": "cinematic",
        }
    )
    session = store.create_session("session-book", enriched_request, [])
    session.current_title = "La prova condivisa"
    session.current_draft = "Una bozza pronta per cover e critica."
    session.book_chapters = [
        {
            "title": "Capitolo 1",
            "content": "Testo del capitolo uno.",
            "section_index": 0,
        }
    ]
    session.writing_progress = {
        "current_step": 3,
        "total_steps": 3,
        "current_section_name": "Capitolo 3",
        "is_complete": True,
        "is_paused": False,
        "error": "errore precedente",
        "completed_chapters_count": 3,
        "status": "running",
    }
    return store


@pytest.mark.asyncio
async def test_persist_writing_completion_sets_minutes_and_clears_error(
    book_session_store: SessionStore,
) -> None:
    await _persist_writing_completion(
        book_session_store,
        "session-book",
        writing_time_minutes=18.5,
    )

    session = book_session_store.get_session("session-book")
    assert session is not None
    assert session.writing_progress["writing_time_minutes"] == pytest.approx(18.5)
    assert session.writing_progress["error"] is None


@pytest.mark.asyncio
async def test_run_post_book_completion_pipeline_uses_shared_step_order(
    book_session_store: SessionStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict]] = []

    async def fake_notify(_store, _session_id, **kwargs):
        calls.append(("notify", kwargs))

    async def fake_persist(_store, _session_id, **kwargs):
        calls.append(("persist", kwargs))

    async def fake_mark_completed(_store, _session_id, _job_type, **kwargs):
        calls.append(("mark_completed", kwargs))

    async def fake_cover(_store, _session_id, **kwargs):
        calls.append(("cover", kwargs))

    async def fake_critique(_store, _session_id, **kwargs):
        calls.append(("critique", kwargs))

    async def fake_cost(_store, _session_id):
        calls.append(("cost", {}))

    monkeypatch.setattr("app.services.book_generation_service._send_book_completed_notification", fake_notify)
    monkeypatch.setattr("app.services.book_generation_service._persist_writing_completion", fake_persist)
    monkeypatch.setattr("app.services.book_generation_service.mark_process_completed_async", fake_mark_completed)
    monkeypatch.setattr("app.services.book_generation_service._generate_cover_artifact", fake_cover)
    monkeypatch.setattr("app.services.book_generation_service._generate_critique_artifact", fake_critique)
    monkeypatch.setattr("app.services.book_generation_service._refresh_book_process_cost", fake_cost)

    await _run_post_book_completion_pipeline(
        book_session_store,
        "session-book",
        writing_time_minutes=9.75,
        api_key="google-key",
        title_fallback="Fallback title",
        author_fallback="Fallback author",
        plot_fallback="Fallback plot",
    )

    assert [name for name, _payload in calls] == [
        "notify",
        "persist",
        "mark_completed",
        "cover",
        "critique",
        "cost",
    ]
    assert calls[1][1]["writing_time_minutes"] == pytest.approx(9.75)
    assert calls[3][1]["api_key"] == "google-key"
    assert "generate_pdf_callback" in calls[4][1]


@pytest.mark.asyncio
async def test_generate_critique_artifact_auto_detects_provider_credentials(
    book_session_store: SessionStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def fake_resolve_pdf_bytes(_session_id, generate_pdf_callback=None):
        captured["generate_pdf_callback"] = generate_pdf_callback
        return b"%PDF-1.4 fake"

    async def fake_generate_literary_critique_from_pdf(**kwargs):
        captured.update(kwargs)
        return (
            {
                "score": 8.4,
                "pros": ["Struttura solida"],
                "cons": ["Finale rapido"],
                "summary": "Critica completata.",
            },
            {"input_tokens": 11, "output_tokens": 7, "model": "gpt-5.2"},
        )

    monkeypatch.setattr("app.services.book_generation_service._resolve_pdf_bytes", fake_resolve_pdf_bytes)
    monkeypatch.setattr(
        "app.services.book_generation_service.generate_literary_critique_from_pdf",
        fake_generate_literary_critique_from_pdf,
    )

    await _generate_critique_artifact(
        book_session_store,
        "session-book",
        api_key="google-key",
        title_fallback="Fallback title",
        author_fallback="Fallback author",
    )

    session = book_session_store.get_session("session-book")
    assert session is not None
    assert captured["api_key"] is None
    assert captured["google_api_key"] == "google-key"
    assert captured["title"] == "La prova condivisa"
    assert session.critique_status == "completed"
    assert session.literary_critique["score"] == pytest.approx(8.4)
    assert session.token_usage["critique"]["model"] == "gpt-5.2"

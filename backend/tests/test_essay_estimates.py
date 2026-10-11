from fastapi.testclient import TestClient
import pytest

from app.essay.main import create_app
from app.essay.models import EssayBrief
from app.essay.store import EssayStore


@pytest.fixture
def store(tmp_path):
    return EssayStore(tmp_path / "saggia.sqlite3")


def test_forecast_is_available_before_first_essay_without_creating_jobs(store):
    with TestClient(create_app(store, run_worker=False)) as client:
        response = client.post("/api/essay-estimates", json={"topic": "Stima di prova", "target_words": 35000})
    assert response.status_code == 200
    data = response.json()
    assert data["pages"] == 140
    assert data["cost_eur"] > 0 and data["minutes"] > 0
    assert data["time_basis"] == "configuration"
    assert store.get_all_sessions() == {}
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM usage_events").fetchone()[0] == 0


def test_amplitude_review_and_model_change_the_estimate(store):
    from app.essay.estimates import essay_estimate
    estimate = lambda **changes: essay_estimate(EssayBrief(topic="Un saggio", **changes), store)
    base = estimate(revision_mode="writing")
    assert estimate(target_words=60000)["cost_eur"] > base["cost_eur"]
    assert estimate()["cost_eur"] > base["cost_eur"]
    assert estimate(llm_model="gemini-3.5-flash-lite", revision_mode="writing")["cost_eur"] < base["cost_eur"]
    assert estimate(model_overrides={"chapters": "gemini-3.5-flash-lite"}, revision_mode="writing")["minutes"] < base["minutes"]
    assert estimate(cover_style="illustrated")["cover_extra"] is True
    assert estimate()["cover_extra"] is False


def test_unknown_tariff_does_not_become_zero(store, monkeypatch):
    from app.essay import estimates
    monkeypatch.setattr(estimates, "pricing_snapshot", lambda model: None)
    data = estimates.essay_estimate(EssayBrief(topic="Un saggio"), store)
    assert data["cost_eur"] is None and data["cost_low_eur"] is None


def test_times_use_comparable_uninterrupted_runs_and_exclude_resumed_work(store):
    from app.essay.estimates import essay_estimate
    for i in range(6):
        session = store.create_session(str(i), EssayBrief(topic="Un saggio", target_words=1000))
        session.book_chapters = [{"section_index": 0, "content": "testo " * 1000}]
        session.writing_progress = {"status": "completed", "attempt": 1 if i < 3 or i == 5 else 2,
                                    "started_at": "2026-10-11T10:00:00+00:00",
                                    "completed_at": "2026-10-11T10:10:00+00:00"}
        store.save_session(session)
        if i == 5:
            with store.connection(write=True) as db:
                db.execute("INSERT INTO jobs(id,session_id,kind,status,attempt,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
                           ("recovered", str(i), "book", "completed", 2, 1, 1))
    data = essay_estimate(EssayBrief(topic="Un saggio", target_words=1000), store)
    assert data["time_basis"] == "history" and data["time_samples"] == 3
    assert 10 <= data["minutes"] <= 12
    different = essay_estimate(EssayBrief(topic="Un saggio", revision_mode="writing"), store)
    assert different["time_basis"] == "configuration" and different["time_samples"] == 0


@pytest.mark.parametrize("target", [0, 120001])
def test_forecast_rejects_invalid_lengths(store, target):
    with TestClient(create_app(store, run_worker=False)) as client:
        assert client.post("/api/essay-estimates", json={"topic": "Un saggio", "target_words": target}).status_code == 422

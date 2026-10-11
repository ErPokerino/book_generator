"""The three modes coexist, keep their archives and share a real bookshelf."""
import asyncio
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.agent import session_store
from app.agent.session_store import get_session_store
from app.essay.models import EssayBrief
from app.essay.store import EssayStore
from app.models import SubmissionRequest
from app.persistence.sqlite_store import SQLiteSessionStore
from app.services.usage_service import metered_call
from app.services.durable_worker import DurableWorker


@pytest.fixture
def studio(tmp_path, monkeypatch):
    from app import main
    narrative = SQLiteSessionStore(tmp_path / "narrai.sqlite3")
    essays = EssayStore(tmp_path / "saggia.sqlite3")
    monkeypatch.setattr(session_store, "_session_store", narrative)
    monkeypatch.setattr(main.essay_api.state, "store", essays, raising=False)

    async def idle(self):
        await asyncio.Event().wait()

    monkeypatch.setattr("app.services.durable_worker.DurableWorker.run", idle)
    with TestClient(main.app) as client:
        yield client, narrative, essays


def test_essay_routes_do_not_replace_narrative_routes_or_store(studio):
    client, narrative, essays = studio
    narrative.create_session("book1", SubmissionRequest(plot="Una storia", llm_model="gemini-3.8-flash"), [])
    created = client.post("/api/saggistica/essays", json={"topic": "Le ragioni del confronto"})
    assert created.status_code == 201, created.text
    sid = created.json()["session_id"]
    assert essays.get_session(sid).form_data.topic == "Le ragioni del confronto"
    assert narrative.get_session(sid) is None
    assert get_session_store() is narrative
    assert client.get("/api/config").status_code == 200
    assert client.get("/api/library").json()["total"] == 1
    assert client.get("/api/saggistica/essay-config").status_code == 200
    assert client.get("/api/saggistica/essays/unknown").status_code == 404
    assert client.post("/api/saggistica/essays/" + sid + "/jobs/book").status_code == 422
    assert client.get("/health").status_code == 200


def test_shared_bookshelf_filters_sorts_and_paginates_after_combining(studio):
    client, narrative, essays = studio
    narrative.create_session("book1", SubmissionRequest(plot="Un mondo nuovo", llm_model="gemini-3.8-flash", user_name="Ada"), [])
    essays.create_session("essay1", EssayBrief(topic="Zeta: una domanda", author_name="Bruno"))
    essays.create_session("essay2", EssayBrief(topic="Alfa: una tesi", profile="academic"))
    response = client.get("/api/works?sort_by=title&sort_order=asc&limit=1").json()
    assert response["total"] == 3 and response["has_more"]
    assert response["books"][0]["title"] == "Alfa: una tesi"
    next_page = client.get("/api/works?sort_by=title&sort_order=asc&limit=1&skip=1").json()
    assert next_page["books"][0]["session_id"] != response["books"][0]["session_id"]
    assert client.get("/api/works?content_type=essay").json()["total"] == 2
    assert client.get("/api/works?content_type=book").json()["total"] == 1
    assert client.get("/api/works?content_type=manga").json()["total"] == 0
    assert client.get("/api/works?search=bruno").json()["books"][0]["session_id"] == "essay1"
    assert client.get("/api/works?genre=Accademico").json()["total"] == 1
    assert client.get("/api/works?mode=Standard").status_code == 200
    assert client.get("/api/works?skip=-1").status_code == 422
    assert client.get("/api/works?content_type=unknown").status_code == 422
    assert client.delete("/api/saggistica/essays/essay1").status_code == 204
    assert client.get("/api/works").json()["total"] == 2
    assert narrative.get_session("book1") is not None


@pytest.mark.asyncio
async def test_concurrent_modes_meter_identical_ids_to_their_own_archives(tmp_path, monkeypatch):
    narrative = SQLiteSessionStore(tmp_path / "narrai.sqlite3")
    essays = EssayStore(tmp_path / "saggia.sqlite3")
    narrative.create_session("same-id", SubmissionRequest(plot="Una storia", llm_model="gemini-3.8-flash"), [])
    essays.create_session("same-id", EssayBrief(topic="Una domanda"))
    monkeypatch.setattr(session_store, "_session_store", narrative)

    narrative.enqueue_job("same-id", "questions", {"status": "pending"})
    essays.enqueue("same-id", "questions")

    async def handler(job, store):
        async def result():
            await asyncio.sleep(0)
            assert get_session_store() is store
            return SimpleNamespace(usage_metadata={"prompt_token_count": 10, "candidates_token_count": 5})
        phase = "chapters" if store is narrative else "essay-writing"
        await metered_call(result, session_id="same-id", model="gemini-3.8-flash", phase=phase)
        project = store.get_session("same-id")
        project.questions_progress["status"] = "completed"
        store.save_session(project)

    await asyncio.gather(DurableWorker(narrative, handler=handler).run_once(), DurableWorker(essays, handler=handler).run_once())
    assert [event["phase"] for event in narrative.usage_events("same-id")] == ["chapters"]
    assert [event["phase"] for event in essays.usage_events("same-id")] == ["essay-writing"]
    assert get_session_store() is narrative

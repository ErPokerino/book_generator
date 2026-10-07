"""Review IDs must belong to the supplied batch; invalid reports are repaired once."""
import pytest
from fastapi.testclient import TestClient
from google.genai import _transformers
from app.essay.generation import review_chapters, scoped_review_schema, global_review_id, dispatch
from app.essay.models import EssayReview
from app.essay.store import EssayStore
from app.essay.main import create_app
from app.services.durable_worker import DurableWorker
from test_essay_revision import ready, issue, payload, parsed_prompt


@pytest.fixture
def store(tmp_path):
    return EssayStore(tmp_path / "review-scope.sqlite3")


def test_provider_schema_only_allows_current_batch_including_global_issues():
    schema = scoped_review_schema(["C3", "custom-id"])
    field = schema.model_json_schema()["$defs"]["ReviewIssue"]["properties"]["section_id"]
    assert field["enum"] == ["WHOLE_MANUSCRIPT", "C3", "custom-id"]
    assert "" not in field["enum"]  # Gemini rejects empty enum values.
    # Exercise the installed SDK's actual Pydantic-to-provider conversion.
    converted = _transformers.t_schema(None, schema)
    assert converted.properties["issues"].items.properties["section_id"].enum == ["WHOLE_MANUSCRIPT", "C3", "custom-id"]
    assert scoped_review_schema(["C1"]).model_json_schema()["$defs"]["ReviewIssue"]["properties"]["section_id"]["enum"] == ["WHOLE_MANUSCRIPT", "C1"]


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_id", ["C2", "C99", "Capitolo 1", "Premesse"])
async def test_repairs_off_batch_or_invented_identifier_with_explicit_context(store, monkeypatch, invalid_id):
    session = ready(store)
    chapter = session.book_chapters[0]
    calls = []
    async def request(session, phase, prompt, schema, **kwargs):
        calls.append(prompt)
        return EssayReview(summary="Una premessa da precisare.", issues=[
            issue(invalid_id if len(calls) == 1 else "C1") |
            {"quote": "Una premessa originale offre una ragione da discutere e qualificare."}])
    monkeypatch.setattr("app.essay.generation.request", request)
    review = await review_chapters(session, [chapter])
    assert review.issues[0].section_id == "C1"
    assert review.issues[0].quote in chapter["content"]
    assert len(calls) == 2
    data = parsed_prompt(calls[0])
    assert data["reviewable_section_ids"] == ["C1"]
    assert any(section["id"] == "C2" for section in data["plan"]["sections"])
    assert "non sono mancanti dal libro" in calls[0]
    assert "Risposta precedente:" in calls[1]
    assert invalid_id in calls[1]
    assert "Capitoli ammessi: C1" in calls[1]


@pytest.mark.asyncio
async def test_repair_is_bounded_and_does_not_silently_drop_invalid_issues(store, monkeypatch):
    calls = []
    async def request(*args, **kwargs):
        calls.append(args)
        return EssayReview(summary="Non valido", issues=[issue("C99")])
    monkeypatch.setattr("app.essay.generation.request", request)
    session = ready(store)
    with pytest.raises(ValueError, match="C99.*assente dal gruppo"):
        await review_chapters(session, session.book_chapters)
    assert len(calls) == 2
    assert store.get_session("P1").book_chapters == session.book_chapters


@pytest.mark.asyncio
async def test_repairs_quote_in_wrong_chapter_without_reassigning_it(store, monkeypatch):
    session = ready(store)
    session.book_chapters[1]["content"] = "Il secondo capitolo analizza una questione differente. " * 20
    calls = []
    async def request(session, phase, prompt, schema, **kwargs):
        calls.append(prompt)
        quote = "Il secondo capitolo analizza una questione differente." if len(calls) == 1 else "Una premessa originale"
        return EssayReview(summary="Precisazione", issues=[issue("C1") | {"quote": quote}])
    monkeypatch.setattr("app.essay.generation.request", request)
    review = await review_chapters(session, session.book_chapters)
    assert review.issues[0].section_id == "C1"
    assert review.issues[0].quote == "Una premessa originale"
    assert "non compare nel manoscritto" in calls[1]


@pytest.mark.asyncio
async def test_repair_preserves_documented_global_and_targeted_issues(store, monkeypatch):
    session = ready(store)
    calls = []
    async def request(*args, **kwargs):
        calls.append(args)
        return EssayReview(summary="Rapporto", issues=[issue(""), issue("C1"), issue("C99" if len(calls) == 1 else "C2")])
    monkeypatch.setattr("app.essay.generation.request", request)
    result = await review_chapters(session, session.book_chapters)
    assert [i.section_id for i in result.issues] == ["", "C1", "C2"]


@pytest.mark.asyncio
async def test_resume_second_pass_verification_never_rewrites_saved_chapters(store, monkeypatch):
    session = ready(store)
    session.review = None
    session.revision_progress = {"status": "failed", "error": "La revisione richiama un capitolo inesistente."}
    from app.essay.citations import content_hash
    hashes = {c["section_id"]: content_hash(c["content"]) for c in session.book_chapters}
    session.revision_request = {"source_version": session.current_version, "hashes": hashes,
        "pass": 2, "stage": "checking", "completed_ids": ["C1", "C2"],
        "updated_ids": ["C1", "C2"], "review_groups": []}
    store.save_session(session)
    original_chapters = store.get_session("P1").book_chapters
    calls = []
    async def request(session, phase, prompt, schema, **kwargs):
        assert phase == "review"
        progress = store.get_session("P1").revision_progress
        assert progress["pass_number"] == 2
        assert progress["updated_sections"] == 2
        calls.append(prompt)
        return EssayReview(summary="Verifica completata", issues=[issue("C99")] if len(calls) == 1 else [])
    monkeypatch.setattr("app.essay.generation.request", request)
    with TestClient(create_app(store, run_worker=False)) as client:
        assert client.get("/api/essays/P1").json()["can_resume_revision"]
        assert client.post("/api/essays/P1/revision", json=payload(client, True)).status_code == 200
        await DurableWorker(store, handler=dispatch).run_once()
    final = store.get_session("P1")
    assert len(calls) == 2
    assert final.revision_progress["status"] == "completed"
    assert final.revision_progress["pass_number"] == 2
    assert final.revision_progress["updated_sections"] == 2
    assert final.revision_request["stage"] == "done"
    assert final.book_chapters[0]["content"] == original_chapters[0]["content"]
    assert final.book_chapters[1]["content"] == original_chapters[1]["content"]
    assert final.review["issues"] == []


@pytest.mark.asyncio
async def test_provider_global_id_is_normalized_without_colliding_with_chapter_ids(store, monkeypatch):
    session = ready(store)
    chapter = session.book_chapters[0]
    chapter["section_id"] = "WHOLE_MANUSCRIPT"
    assert global_review_id(["WHOLE_MANUSCRIPT", "_WHOLE_MANUSCRIPT"]) == "__WHOLE_MANUSCRIPT"
    async def request(session, phase, prompt, schema, **kwargs):
        data = parsed_prompt(prompt)
        assert data["global_issue_section_id"] == "_WHOLE_MANUSCRIPT"
        ids = schema.model_json_schema()["$defs"]["ReviewIssue"]["properties"]["section_id"]["enum"]
        assert ids == ["_WHOLE_MANUSCRIPT", "WHOLE_MANUSCRIPT"]
        return EssayReview(summary="Controllo generale", issues=[issue(data["global_issue_section_id"]),
            issue("WHOLE_MANUSCRIPT")])
    monkeypatch.setattr("app.essay.generation.request", request)
    result = await review_chapters(session, [chapter])
    assert [i.section_id for i in result.issues] == ["", "WHOLE_MANUSCRIPT"]

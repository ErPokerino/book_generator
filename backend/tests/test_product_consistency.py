import asyncio
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.agent import session_store
from app.agent.session_store import get_session_store
from app.core.comics import COMIC_GENRES
from app.essay.models import EssayBrief
from app.essay.store import EssayStore
from app.models import MangaCreateRequest, MangaPlan, MangaPagePlan, SubmissionRequest
from app.persistence.sqlite_store import SQLiteSessionStore


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


@pytest.mark.parametrize("format,genre", [(f,g) for f,genres in COMIC_GENRES.items() for g in genres])
def test_each_comic_genre_reaches_every_visual_prompt(format, genre):
    from app.services.manga_generation_service import _build_page_prompt, _build_cover_prompt, _build_back_cover_prompt
    request = MangaCreateRequest(plot="Una storia", comic_format=format, comic_genre=genre)
    page = MangaPagePlan(page_number=1, title="Apertura", narrative_goal="Conflitto", scene_description="Una piazza", summary="Il viaggio comincia")
    plan = MangaPlan(title="Il viaggio", synopsis="Una ricerca", tone="Intimo", page_plans=[page])
    for prompt in (_build_page_prompt(request=request, plan=plan, page_plan=page, previous_pages=[]),
                   _build_cover_prompt(request=request, plan=plan),
                   _build_back_cover_prompt(request=request, plan=plan, previous_pages=[])):
        assert COMIC_GENRES[format][genre] in prompt
        assert "Graphic Novel" in prompt if format == "graphic_novel" else "Formato: Manga" in prompt
        assert "sinistra a destra" in prompt
        if format == "graphic_novel":
            assert "Tipo di manga:" not in prompt
            assert "Stile manga" not in prompt


def test_legacy_manga_is_readable_and_cross_format_genres_are_rejected():
    old = MangaCreateRequest(plot="Avventura", manga_type="seinen")
    assert old.comic_format == "manga" and old.comic_genre == "action"
    with pytest.raises(ValidationError):
        MangaCreateRequest(plot="Avventura", comic_format="manga", comic_genre="memoir")
    with pytest.raises(ValidationError):
        MangaCreateRequest(plot="Avventura", comic_format="graphic_novel", comic_genre="sports")


@pytest.mark.parametrize("format,genre", [("manga","sports"),("graphic_novel","memoir")])
def test_storyboard_uses_the_requested_comic_format(monkeypatch, format, genre):
    from app.agent.manga import planner
    request = MangaCreateRequest(plot="Un ricordo d'infanzia", comic_format=format, comic_genre=genre)
    invocation = AsyncMock(return_value=(MangaPlan(title="Un ricordo",synopsis="Una vita",tone="Intimo"),{},""))
    monkeypatch.setattr(planner,"_build_manga_chat_llm",lambda **kwargs:object())
    monkeypatch.setattr(planner,"invoke_structured_chat_model",invocation)
    asyncio.run(planner.generate_manga_plan(session_id="comic",request=request))
    prompts = invocation.await_args.kwargs["messages"]
    for prompt in prompts:
        assert COMIC_GENRES[format][genre] in prompt.content
        assert ("Formato: Graphic Novel" if format == "graphic_novel" else "Formato: Manga") in prompt.content
        assert "Il manga deve" not in prompt.content


def test_analytics_distinguishes_words_tavole_and_unknown_costs(studio):
    client, novels, essays = studio
    book = novels.create_session("book", SubmissionRequest(plot="Una storia", llm_model="gemini-3.8-flash"), [])
    book.current_title = "Il mondo"
    book.book_chapters = [{"title":"Uno", "content":"una storia in quattro", "section_index":0}]
    book.writing_progress = {"status":"completed", "is_complete":True}
    novels.save_session(book)
    comic = novels.create_session("comic", SubmissionRequest(plot="Una tavola", llm_model="gemini-3.8-flash"), [])
    comic.content_type = "manga"
    comic.manga_form_data = {"comic_format":"graphic_novel", "comic_genre":"memoir", "manga_type":"shonen"}
    comic.manga_pages = [{"page_number":1, "status":"completed"}, {"page_number":2, "status":"failed"}]
    comic.manga_progress = {"status":"paused", "is_paused":True}
    novels.save_session(comic)
    essay = essays.create_session("essay", EssayBrief(topic="Una tesi"))
    essay.book_chapters = [{"title":"Tesi", "content":"ragioni ben documentate", "section_index":0}]
    essays.save_session(essay)
    for store,sid,cost in ((novels,"book",2),(essays,"essay",1),(novels,"comic",None)):
        store.record_usage({"id":sid,"session_id":sid,"created_at":1,"phase":"chapters","model":"gemini-3.8-flash","cost_usd":cost,"usd_to_eur":.9,"status":"measured" if cost is not None else "unknown","usage":{"input_tokens":10,"output_tokens":5} if cost is not None else None})
    data = client.get("/api/works/analytics").json()
    assert data["total"] == 3 and data["completed"] == 1 and data["paused"] == 1
    assert data["words"] == 7 and data["comic_pages"] == 1
    assert data["cost_eur"] == pytest.approx(2.7)
    assert data["cost_partial_works"] == 1
    assert data["models"][0]["unknown_calls"] == 1
    comics = client.get("/api/works/analytics?content_type=manga").json()
    assert comics["total"] == 1 and comics["cost_eur"] is None
    shelf = client.get("/api/works?content_type=manga").json()["books"][0]
    assert shelf["comic_format"] == "graphic_novel" and shelf["estimated_cost"] is None


@pytest.mark.parametrize("kind", ["book", "essay", "manga"])
def test_every_work_can_be_deleted_without_affecting_other_archive(studio, kind):
    client, novels, essays = studio
    book = novels.create_session("same", SubmissionRequest(plot="Un mondo", llm_model="gemini-3.8-flash"), [])
    if kind == "manga":
        book.content_type = "manga"
        book.manga_form_data = {"manga_type":"shonen"}
        novels.save_session(book)
    essays.create_session("same", EssayBrief(topic="Una domanda"))
    endpoint = "/api/saggistica/essays/same" if kind == "essay" else "/api/library/same"
    assert client.delete(endpoint).status_code in {200,204}
    assert (novels.get_session("same") is not None) == (kind == "essay")
    assert (essays.get_session("same") is not None) == (kind != "essay")


def test_reader_can_open_partial_narrative_without_starting_writing(studio):
    client, novels, _ = studio
    book = novels.create_session("draft", SubmissionRequest(plot="Da scrivere", llm_model="gemini-3.8-flash"), [])
    assert client.get("/api/book/draft").status_code == 400
    partial = client.get("/api/book/draft?allow_partial=true")
    assert partial.status_code == 200 and partial.json()["chapters"] == []
    assert not partial.json()["is_complete"]
    assert novels.list_jobs("draft") == []


@pytest.mark.parametrize("kind", ["book", "essay", "manga"])
def test_pdf_evaluation_forwards_the_selected_format(studio, monkeypatch, kind):
    client, _, _ = studio
    evaluator = AsyncMock(return_value=({"score":7,"pros":["Chiaro"],"cons":["Da affinare"],"summary":"Un parere","criteria":[{"name":"Chiarezza","score":7,"explanation":"Pagina 1"}]}, {}))
    monkeypatch.setattr("app.api.routers.critique.analyze_pdf_from_bytes", evaluator)
    response = client.post("/api/critique/analyze-pdf", data={"work_type":kind}, files={"file":("test.pdf",b"%PDF-1.4 test","application/pdf")})
    assert response.status_code == 200
    assert evaluator.await_args.kwargs["work_type"] == kind
    assert response.json()["criteria"][0]["name"] == "Chiarezza"
    assert client.post("/api/critique/analyze-pdf",data={"work_type":"unknown"},files={"file":("test.pdf",b"pdf","application/pdf")}).status_code == 422


def test_essay_evaluation_uses_the_essay_usage_context(studio, monkeypatch):
    client, novels, essays = studio
    novels.create_session("same", SubmissionRequest(plot="Romanzo", llm_model="gemini-3.8-flash"), [])
    essay = essays.create_session("same", EssayBrief(topic="Tesi"))
    essay.plan = {"title":"Il saggio"}
    essay.book_chapters = [{"content":"Una tesi", "title":"Uno", "section_index":0}]
    essays.save_session(essay)
    monkeypatch.setattr("app.essay.exports.export_book", lambda *args:(b"%PDF-1.4 essay", "application/pdf"))
    async def evaluator(pdf, **kwargs):
        assert get_session_store() is essays
        assert kwargs["work_type"] == "essay" and kwargs["session_id"] == "same"
        assert pdf.endswith(b"essay")
        return {"score":8,"pros":["Tesi"],"cons":["Limiti"],"summary":"Coerente"}, {}
    monkeypatch.setattr("app.api.routers.critique.analyze_pdf_from_bytes", evaluator)
    assert client.post("/api/critique/analyze-work/essay/same").status_code == 200
    assert get_session_store() is novels


def test_pause_comic_stops_before_another_paid_step(studio, monkeypatch):
    client, novels, _ = studio
    comic = novels.create_session("comic", SubmissionRequest(plot="Un mondo", llm_model="gemini-3.8-flash"), [])
    comic.content_type = "manga"
    comic.manga_form_data = {"plot":"Un mondo","manga_type":"shonen"}
    comic.manga_progress = {"status":"running", "is_complete":False}
    novels.save_session(comic)
    assert client.post("/api/manga/comic/pause").status_code == 200
    planner = AsyncMock()
    monkeypatch.setattr("app.services.manga_generation_service.generate_manga_plan", planner)
    from app.services.manga_generation_service import background_manga_generation
    asyncio.run(background_manga_generation(session_id="comic", request=MangaCreateRequest(**comic.manga_form_data)))
    planner.assert_not_awaited()
    assert novels.get_session("comic").manga_progress["is_paused"]


def test_evaluation_criteria_follow_the_medium():
    from app.agent.evaluation_prompts import evaluation_prompts
    essay, _ = evaluation_prompts({},"essay")
    comic, _ = evaluation_prompts({},"manga")
    assert "catena delle ragioni" in essay and "non dichiarare verificati" in essay
    assert "immagini delle tavole" in comic and "non inventare dettagli grafici" in comic


def test_pause_during_a_comic_page_saves_it_and_skips_the_next_call(studio, monkeypatch):
    client, novels, _ = studio
    request = MangaCreateRequest(plot="Una storia a fumetti")
    comic = novels.create_session("comic", SubmissionRequest(plot=request.plot, llm_model="gemini-3.8-flash"), [])
    comic.content_type = "manga"
    comic.manga_form_data = request.model_dump()
    comic.cover_image_path = "existing-cover.png"
    comic.manga_plan = MangaPlan(title="Il viaggio", synopsis="Una ricerca", tone="Intimo", page_plans=[
        MangaPagePlan(page_number=i, title=f"Tavola {i}", narrative_goal="Un incontro", scene_description="Una piazza", summary="Il viaggio prosegue")
        for i in range(1, 11)
    ]).model_dump()
    comic.manga_progress = {"status":"running", "is_complete":False}
    novels.save_session(comic)

    async def pause_while_generating(**kwargs):
        assert client.post("/api/manga/comic/pause").status_code == 200
        return b"saved-image", {"input_tokens":10, "output_tokens":5}
    image = AsyncMock(side_effect=pause_while_generating)
    back_cover = AsyncMock()
    monkeypatch.setattr("app.services.manga_generation_service._generate_page_image", image)
    monkeypatch.setattr("app.services.manga_generation_service._generate_back_cover_image", back_cover)
    monkeypatch.setattr("app.services.manga_generation_service._store_page_image", AsyncMock(return_value="saved-page.png"))
    from app.services.manga_generation_service import background_manga_generation
    asyncio.run(background_manga_generation(session_id="comic", request=request))
    saved = novels.get_session("comic")
    assert saved.manga_progress["is_paused"] and not saved.manga_progress["is_complete"]
    assert saved.manga_pages[0]["image_path"] == "saved-page.png"
    assert len(saved.manga_pages) == image.await_count == 1
    back_cover.assert_not_awaited()


def test_reading_a_comic_does_not_generate_missing_artwork(studio, monkeypatch):
    client, novels, _ = studio
    comic = novels.create_session("comic", SubmissionRequest(plot="Un mondo", llm_model="gemini-3.8-flash"), [])
    comic.content_type = "manga"
    comic.manga_form_data = MangaCreateRequest(plot="Un mondo", comic_format="graphic_novel", comic_genre="memoir").model_dump()
    comic.manga_plan = MangaPlan(title="Una vita", synopsis="Un ricordo", tone="Intimo").model_dump()
    comic.manga_progress = {"status":"completed", "is_complete":True}
    comic.manga_pages = [{"page_number":1, "status":"completed", "image_path":"page.png"}]
    novels.save_session(comic)
    cover = AsyncMock()
    back_cover = AsyncMock()
    monkeypatch.setattr("app.api.routers.manga.backfill_manga_cover_if_missing", cover)
    monkeypatch.setattr("app.api.routers.manga.backfill_manga_back_cover_if_missing", back_cover)
    response = client.get("/api/manga/comic")
    assert response.status_code == 200 and response.json()["comic_format"] == "graphic_novel"
    assert len(response.json()["pages"]) == 1
    cover.assert_not_awaited()
    back_cover.assert_not_awaited()

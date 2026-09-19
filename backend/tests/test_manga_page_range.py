import pytest
from pydantic import ValidationError

import app.services.manga_generation_service as manga_service
from app.agent.manga.planner import _validate_manga_plan
from app.models import (
    MangaCharacterInput,
    MangaCreateRequest,
    MangaPagePlan,
    MangaPlan,
)
from app.services.manga_generation_service import (
    build_manga_progress_response,
    build_manga_reader_response,
)


def _make_request(
    min_pages: int = 30,
    max_pages: int = 60,
    *,
    page_count: int | None = None,
) -> MangaCreateRequest:
    return MangaCreateRequest(
        title="Cronache di Akira",
        plot="Un giovane corriere scopre un segreto che puo salvare la citta sospesa.",
        manga_type="shonen",
        page_color_mode="black_and_white",
        main_characters=[
            MangaCharacterInput(
                name="Akira",
                description="Corriere impulsivo, capelli scuri, giacca rossa.",
            )
        ],
        page_count=page_count,
        min_pages=min_pages,
        max_pages=max_pages,
    )


def _make_plan(page_count: int) -> MangaPlan:
    return MangaPlan(
        title="Cronache di Akira",
        synopsis="Akira affronta una cospirazione che minaccia la sua citta.",
        tone="Avventuroso e intenso",
        style_guide=["Bianco e nero netto", "Balloon leggibili"],
        character_profiles=[],
        page_plans=[
            MangaPagePlan(
                page_number=999,
                title=f"Pagina {index}",
                narrative_goal="Far avanzare il conflitto",
                scene_description="Una scena dinamica con i protagonisti.",
                dialogue=["Andiamo!", "Non c'e tempo."],
                visual_notes=["Taglio cinematografico"],
                continuity_notes=["Mantieni la giacca rossa di Akira"],
                summary="Il conflitto procede.",
            )
            for index in range(1, page_count + 1)
        ],
    )


def test_manga_create_request_rejects_invalid_page_range() -> None:
    with pytest.raises(ValidationError):
        _make_request(min_pages=61, max_pages=60)


def test_manga_create_request_accepts_exact_page_count_and_normalizes_range() -> None:
    request = _make_request(page_count=60)

    assert request.page_count == 60
    assert request.min_pages == 60
    assert request.max_pages == 60


def test_validate_manga_plan_accepts_requested_range_and_renumbers_pages() -> None:
    request = _make_request(min_pages=30, max_pages=60)
    plan = _make_plan(42)

    validated = _validate_manga_plan(plan, request=request)

    assert len(validated.page_plans) == 42
    assert validated.page_plans[0].page_number == 1
    assert validated.page_plans[-1].page_number == 42


def test_validate_manga_plan_strips_editorial_prefixes_from_dialogue() -> None:
    request = _make_request(min_pages=10, max_pages=10)
    plan = MangaPlan(
        title="Cronache di Akira",
        synopsis="Akira affronta una cospirazione che minaccia la sua citta.",
        tone="Avventuroso e intenso",
        style_guide=["Bianco e nero netto"],
        character_profiles=[],
        page_plans=[
            MangaPagePlan(
                page_number=7,
                title="Scoperta",
                narrative_goal="Rivelare il segnale",
                scene_description="Akira osserva il monitor.",
                dialogue=['SFX: "VRRRROM"', "Caption: Finalmente ci siamo."],
                visual_notes=["Taglio cinematografico"],
                continuity_notes=["Mantieni la giacca rossa di Akira"],
                summary="Il conflitto procede.",
            )
            for _index in range(10)
        ],
    )

    validated = _validate_manga_plan(plan, request=request)

    assert validated.page_plans[0].dialogue == ["VRRRROM", "Finalmente ci siamo."]


def test_validate_manga_plan_rejects_page_count_outside_requested_range() -> None:
    request = _make_request(min_pages=30, max_pages=60)
    plan = _make_plan(29)

    with pytest.raises(ValueError):
        _validate_manga_plan(plan, request=request)


def test_manga_progress_and_reader_use_resolved_page_count(session_store) -> None:
    session = session_store.get_session("session-1")
    assert session is not None

    request = _make_request(min_pages=30, max_pages=60)
    plan = _make_plan(42)

    session.content_type = "manga"
    session.current_title = plan.title
    session.manga_form_data = request.model_dump()
    session.manga_plan = plan.model_dump()
    session.manga_pages = [
        {
            "page_number": page_number,
            "title": f"Pagina {page_number}",
            "summary": "Il conflitto procede.",
            "dialogue": ["Andiamo!"],
            "image_path": f"manga/session-1/page_{page_number:02d}.png",
            "status": "completed",
        }
        for page_number in range(1, 4)
    ]
    session.manga_progress = {
        "status": "running",
        "current_phase": "generating_pages",
        "current_step": 3,
        "total_steps": 60,
        "requested_min_pages": 30,
        "requested_max_pages": 60,
        "current_page_number": 4,
        "current_page_title": "Pagina 4",
    }

    progress = build_manga_progress_response(session)
    reader = build_manga_reader_response(session)

    assert progress.requested_min_pages == 30
    assert progress.requested_max_pages == 60
    assert progress.planned_total_pages == 42
    assert progress.total_steps == 42
    assert reader.requested_min_pages == 30
    assert reader.requested_max_pages == 60
    assert reader.planned_total_pages == 42
    assert reader.page_color_mode == "black_and_white"
    assert reader.total_pages == 42
    assert len(reader.pages) == 3


def test_manga_progress_exposes_live_cost_and_started_at(session_store) -> None:
    session = session_store.get_session("session-1")
    assert session is not None

    request = _make_request(page_count=10)
    plan = _make_plan(10)

    session.content_type = "manga"
    session.manga_form_data = request.model_dump()
    session.manga_plan = plan.model_dump()
    session.cover_image_path = "cover.png"
    session.manga_pages = [
        {
            "page_number": 1,
            "title": "Pagina 1",
            "summary": "Il conflitto procede.",
            "dialogue": ["Andiamo!"],
            "image_path": "manga/session-1/page_01.png",
            "status": "completed",
        }
    ]
    session.token_usage = {
        "manga_planning": {
            "input_tokens": 1000,
            "output_tokens": 500,
            "model": "gemini-3.8-flash",
        }
    }
    session.manga_progress = {
        "status": "running",
        "current_phase": "generating_pages",
        "current_step": 1,
        "total_steps": 10,
        "queued_at": "2026-09-19T12:00:00",
        "current_page_number": 2,
        "current_page_title": "Pagina 2",
    }

    progress = build_manga_progress_response(session)

    assert progress.started_at is not None
    assert progress.started_at.isoformat().startswith("2026-09-19T12:00:00")
    assert progress.current_cost_eur is not None
    assert progress.estimated_cost is not None
    assert progress.current_cost_eur > 0
    assert progress.estimated_cost > progress.current_cost_eur
    assert progress.cost_breakdown is not None
    assert progress.cost_breakdown["generated_pages_count"] == 1
    assert progress.cost_breakdown["cover_generated"] is True


def test_build_back_cover_reference_image_paths_uses_cover_and_final_pages(monkeypatch) -> None:
    monkeypatch.setattr(manga_service, "_get_max_reference_images", lambda: 4)

    reference_paths = manga_service._build_back_cover_reference_image_paths(
        previous_pages=[
            {"page_number": 1, "image_path": "page-1.png"},
            {"page_number": 2, "image_path": "page-2.png"},
            {"page_number": 3, "image_path": "page-3.png"},
            {"page_number": 4, "image_path": "page-4.png"},
        ],
        cover_image_path="cover.png",
    )

    assert reference_paths == ["cover.png", "page-4.png", "page-3.png", "page-2.png"]


def test_is_manga_back_cover_outdated_checks_prompt_version() -> None:
    stale_session = type(
        "Session",
        (),
        {"back_cover_image_path": "back-cover.png", "back_cover_prompt_version": 1},
    )()
    fresh_session = type(
        "Session",
        (),
        {
            "back_cover_image_path": "back-cover.png",
            "back_cover_prompt_version": manga_service.MANGA_BACK_COVER_PROMPT_VERSION,
        },
    )()

    assert manga_service.is_manga_back_cover_outdated(stale_session) is True
    assert manga_service.is_manga_back_cover_outdated(fresh_session) is False

"""Router per la sezione manga beta."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import RedirectResponse, Response, StreamingResponse

from app.agent.session_store import get_session_store
from app.agent.session_store_helpers import create_session_async, get_session_async, save_session_async
from app.models import (
    MangaCreateRequest,
    MangaGenerationResponse,
    MangaProgress,
    MangaReaderResponse,
    SubmissionRequest,
)
from app.services.manga_generation_service import (
    backfill_manga_artwork_if_missing,
    backfill_manga_back_cover_if_missing,
    backfill_manga_cover_if_missing,
    background_manga_generation,
    background_resume_manga_generation,
    build_manga_progress_response,
    build_manga_reader_response,
    get_manga_back_cover_image_bytes,
    get_requested_manga_page_range,
    get_runtime_manga_total_steps,
    get_manga_page_image_bytes,
    is_manga_back_cover_outdated,
    localize_manga_metadata_in_italian_if_needed,
)
from app.services.process_job_service import begin_process_job_async
from app.services.pdf_service import cache_manga_pdf, generate_manga_pdf
from app.services.storage_service import get_storage_service

router = APIRouter(prefix="/api/manga", tags=["manga"])


def _iter_bytes_chunks(data: bytes, chunk_size: int = 1024 * 1024):
    for offset in range(0, len(data), chunk_size):
        yield data[offset : offset + chunk_size]


def _build_placeholder_submission(request: MangaCreateRequest) -> SubmissionRequest:
    protagonist = ", ".join(character.name for character in request.main_characters[:2]) or None
    return SubmissionRequest(
        llm_model="gemini-3-flash",
        plot=request.plot,
        genre=f"manga-beta-{request.manga_type}",
        protagonist=protagonist,
    )


async def _cache_generated_manga_pdf(session_id: str, pdf_bytes: bytes, filename: str) -> None:
    session_store = get_session_store()
    session = await get_session_async(session_store, session_id)
    if not session:
        return
    if getattr(session, "pdf_path", None) and getattr(session, "pdf_filename", None):
        return

    cached_pdf_path = await asyncio.to_thread(cache_manga_pdf, session, pdf_bytes, filename)
    if cached_pdf_path:
        await save_session_async(session_store, session)


async def _get_manga_session_or_404(session_id: str):
    session_store = get_session_store()
    session = await get_session_async(session_store, session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Sessione manga {session_id} non trovata")
    if getattr(session, "content_type", "book") != "manga":
        raise HTTPException(status_code=400, detail="La sessione richiesta non appartiene alla sezione manga")
    return session


@router.post("/generate", response_model=MangaGenerationResponse)
async def generate_manga_endpoint(
    request: MangaCreateRequest,
    background_tasks: BackgroundTasks,
):
    """Crea una sessione manga beta e avvia la generazione in background."""
    session_store = get_session_store()
    requested_min_pages, requested_max_pages = get_requested_manga_page_range(request=request)

    session_id = str(uuid4())
    placeholder_form = _build_placeholder_submission(request)

    session = await create_session_async(session_store, session_id, placeholder_form, [])
    session.content_type = "manga"
    session.current_title = request.title
    session.manga_form_data = request.model_dump()
    session.manga_pages = []
    session.manga_plan = None
    session.manga_progress = None
    await save_session_async(session_store, session)

    started, job = await begin_process_job_async(
        session_store,
        session_id,
        "manga",
        total_steps=requested_max_pages,
        current_section_name="Preparazione storyboard",
    )
    if not started:
        return MangaGenerationResponse(
            success=True,
            session_id=session_id,
            message="Generazione manga gia in corso.",
            job_id=job.get("job_id"),
            job_type="manga",
            already_running=True,
        )

    session = await get_session_async(session_store, session_id)
    if not session:
        raise HTTPException(status_code=500, detail="Impossibile inizializzare la sessione manga")
    progress = (session.manga_progress or {}).copy()
    progress.update(
        {
            "session_id": session_id,
            "job_id": job.get("job_id"),
            "job_type": "manga",
            "status": "pending",
            "current_phase": "planning",
            "current_step": 0,
            "total_steps": requested_max_pages,
            "requested_min_pages": requested_min_pages,
            "requested_max_pages": requested_max_pages,
            "planned_total_pages": None,
            "current_page_number": 1,
            "current_page_title": "Preparazione storyboard",
            "current_section_name": "Preparazione storyboard",
            "is_complete": False,
            "is_paused": False,
            "error": None,
        }
    )
    session.manga_progress = progress
    await save_session_async(session_store, session)

    background_tasks.add_task(
        background_manga_generation,
        session_id=session_id,
        request=request,
        api_key=os.getenv("GOOGLE_API_KEY") or None,
    )

    return MangaGenerationResponse(
        success=True,
        session_id=session_id,
        message="Generazione manga avviata.",
        job_id=job.get("job_id"),
        job_type="manga",
        already_running=False,
    )


@router.post("/resume/{session_id}", response_model=MangaGenerationResponse)
async def resume_manga_endpoint(
    session_id: str,
    background_tasks: BackgroundTasks,
):
    """Riprende una sessione manga beta messa in pausa."""
    session_store = get_session_store()
    session = await _get_manga_session_or_404(session_id)
    progress = session.manga_progress or {}
    requested_min_pages, requested_max_pages = get_requested_manga_page_range(session=session)

    if progress.get("status") in {"pending", "running"} and not progress.get("is_paused", False):
        return MangaGenerationResponse(
            success=True,
            session_id=session_id,
            message="Generazione manga gia in corso.",
            job_id=progress.get("job_id"),
            job_type="manga",
            already_running=True,
        )

    if progress.get("is_complete", False):
        raise HTTPException(status_code=400, detail="Il manga e gia stato completato.")

    if not progress.get("is_paused", False):
        raise HTTPException(status_code=400, detail="La sessione manga non e in pausa.")

    started, job = await begin_process_job_async(
        session_store,
        session_id,
        "manga",
        total_steps=get_runtime_manga_total_steps(session),
        current_step=int(progress.get("current_step", 0) or 0),
        current_section_name=progress.get("current_page_title") or progress.get("current_section_name"),
    )
    if not started:
        return MangaGenerationResponse(
            success=True,
            session_id=session_id,
            message="Ripresa manga gia in corso.",
            job_id=job.get("job_id"),
            job_type="manga",
            already_running=True,
        )

    progress.update(
        {
            "status": "pending",
            "is_paused": False,
            "error": None,
            "requested_min_pages": int(progress.get("requested_min_pages", requested_min_pages) or requested_min_pages),
            "requested_max_pages": int(progress.get("requested_max_pages", requested_max_pages) or requested_max_pages),
            "planned_total_pages": progress.get("planned_total_pages"),
        }
    )
    session.manga_progress = progress
    await save_session_async(session_store, session)

    background_tasks.add_task(
        background_resume_manga_generation,
        session_id=session_id,
        api_key=os.getenv("GOOGLE_API_KEY") or None,
    )

    return MangaGenerationResponse(
        success=True,
        session_id=session_id,
        message="Ripresa della generazione manga avviata.",
        job_id=job.get("job_id"),
        job_type="manga",
        already_running=False,
    )


@router.get("/progress/{session_id}", response_model=MangaProgress)
async def get_manga_progress_endpoint(
    session_id: str,
):
    """Restituisce il progresso della generazione manga."""
    session = await _get_manga_session_or_404(session_id)
    return build_manga_progress_response(session)


@router.get("/{session_id}", response_model=MangaReaderResponse)
async def get_manga_reader_endpoint(
    session_id: str,
    background_tasks: BackgroundTasks,
):
    """Restituisce il payload del reader beta, anche durante la generazione."""
    session = await _get_manga_session_or_404(session_id)
    if getattr(session, "manga_plan", None):
        await localize_manga_metadata_in_italian_if_needed(
            session_id=session_id,
            api_key=os.getenv("GOOGLE_API_KEY") or None,
        )
        session = await _get_manga_session_or_404(session_id)
    progress = getattr(session, "manga_progress", None) or {}
    should_regenerate_back_cover = is_manga_back_cover_outdated(session)
    should_backfill_cover = (
        (
            not getattr(session, "cover_image_path", None)
            or not getattr(session, "back_cover_image_path", None)
            or should_regenerate_back_cover
        )
        and (progress.get("is_complete") or progress.get("status") in {"paused", "completed"})
        and (getattr(session, "manga_plan", None) or getattr(session, "manga_pages", None))
    )
    if should_backfill_cover:
        background_tasks.add_task(
            backfill_manga_artwork_if_missing,
            session_id=session_id,
            force_back_cover_regeneration=should_regenerate_back_cover,
            api_key=os.getenv("GOOGLE_API_KEY") or None,
        )
    return build_manga_reader_response(session)


@router.get("/{session_id}/pages/{page_number}/image")
async def get_manga_page_image_endpoint(
    session_id: str,
    page_number: int,
):
    """Restituisce o redirige all'immagine di una pagina manga gia generata."""
    session = await _get_manga_session_or_404(session_id)
    page = next(
        (candidate for candidate in session.manga_pages if int(candidate.get("page_number", -1)) == int(page_number)),
        None,
    )
    if not page or not page.get("image_path"):
        raise HTTPException(status_code=404, detail=f"Pagina {page_number} non disponibile")

    image_path = page["image_path"]
    storage_service = get_storage_service()
    if image_path.startswith("gs://"):
        signed_url = storage_service.get_signed_url(image_path, expiration_minutes=60)
        if signed_url and signed_url.startswith("http"):
            return RedirectResponse(url=signed_url)

    try:
        image_bytes = await get_manga_page_image_bytes(session_id, page_number)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    media_type = "image/png" if Path(str(image_path)).suffix.lower() != ".jpg" else "image/jpeg"
    return Response(content=image_bytes, media_type=media_type)


@router.get("/{session_id}/back-cover/image")
async def get_manga_back_cover_image_endpoint(
    session_id: str,
):
    """Restituisce o redirige all'immagine della retro-copertina manga."""
    session = await _get_manga_session_or_404(session_id)
    image_path = getattr(session, "back_cover_image_path", None)
    if not image_path:
        raise HTTPException(status_code=404, detail="Retro copertina non disponibile")

    storage_service = get_storage_service()
    if image_path.startswith("gs://"):
        signed_url = storage_service.get_signed_url(image_path, expiration_minutes=60)
        if signed_url and signed_url.startswith("http"):
            return RedirectResponse(url=signed_url)

    try:
        image_bytes = await get_manga_back_cover_image_bytes(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    media_type = "image/png" if Path(str(image_path)).suffix.lower() != ".jpg" else "image/jpeg"
    return Response(content=image_bytes, media_type=media_type)


@router.get("/pdf/{session_id}")
async def download_manga_pdf_endpoint(
    session_id: str,
    background_tasks: BackgroundTasks,
):
    """Genera e scarica il PDF completo del manga."""
    session = await _get_manga_session_or_404(session_id)
    progress = session.manga_progress or {}

    if not progress.get("is_complete", False):
        raise HTTPException(status_code=400, detail="Il manga non e ancora completo. Attendi il completamento della generazione.")

    if not session.manga_pages:
        raise HTTPException(status_code=400, detail="Nessuna pagina disponibile per il manga richiesto.")

    if not getattr(session, "cover_image_path", None) and getattr(session, "manga_plan", None):
        await backfill_manga_cover_if_missing(
            session_id=session_id,
            api_key=os.getenv("GOOGLE_API_KEY") or None,
        )
        session = await _get_manga_session_or_404(session_id)

    should_regenerate_back_cover = is_manga_back_cover_outdated(session)
    if (
        (not getattr(session, "back_cover_image_path", None) or should_regenerate_back_cover)
        and getattr(session, "manga_plan", None)
    ):
        await backfill_manga_back_cover_if_missing(
            session_id=session_id,
            force_regenerate=should_regenerate_back_cover,
            api_key=os.getenv("GOOGLE_API_KEY") or None,
        )
        session = await _get_manga_session_or_404(session_id)

    cached_pdf_path = getattr(session, "pdf_path", None)
    cached_pdf_filename = getattr(session, "pdf_filename", None)
    if cached_pdf_path and cached_pdf_filename and getattr(session, "cover_image_path", None) and getattr(session, "back_cover_image_path", None):
        storage_service = get_storage_service()
        try:
            pdf_bytes = await asyncio.to_thread(storage_service.download_file, cached_pdf_path)
            headers = {"Content-Disposition": f'attachment; filename="{cached_pdf_filename}"'}
            return StreamingResponse(
                _iter_bytes_chunks(pdf_bytes),
                media_type="application/pdf",
                headers=headers,
            )
        except Exception:
            session.pdf_path = None
            session.pdf_filename = None
            await save_session_async(get_session_store(), session)

    pdf_bytes, filename = await asyncio.to_thread(generate_manga_pdf, session)
    background_tasks.add_task(_cache_generated_manga_pdf, session_id, pdf_bytes, filename)
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(
        _iter_bytes_chunks(pdf_bytes),
        media_type="application/pdf",
        headers=headers,
    )

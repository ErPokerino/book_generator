"""Service per la generazione autoregressiva del manga beta."""

from __future__ import annotations

import asyncio
import base64
from datetime import datetime
from io import BytesIO
from typing import Any, Optional

from PIL import Image as PILImage
from google import genai
from google.genai import types
from app.agent.manga import generate_manga_plan
from app.agent.manga.planner import MANGA_LANGUAGE_RULE, MANGA_NO_META_RULE
from app.agent.session_store import get_session_store
from app.agent.session_store_helpers import get_session_async, save_session_async
from app.core.config import get_app_config, get_exchange_rate_usd_to_eur, get_model_pricing
from app.core.logging import get_logger
from app.llm import (
    DEFAULT_RETRY_DELAY_SECONDS,
    build_google_genai_client,
    get_stage_model,
    is_retryable_llm_error,
    image_size_for_model,
)
from app.models import (
    MangaCharacterProfile,
    MangaCreateRequest,
    MangaPageArtifact,
    MangaPagePlan,
    MangaPlan,
    MangaProgress,
    MangaReaderResponse,
)
from app.services.process_job_service import (
    mark_process_completed_async,
    mark_process_failed_async,
    mark_process_paused_async,
    mark_process_running_async,
    refresh_process_metrics_async,
)
from app.services.storage_service import get_storage_service

logger = get_logger("manga-generation-service")

MANGA_TYPE_LABELS = {
    "shonen": "Shonen - azione e avventura",
    "shojo": "Shojo - romantico ed emotivo",
    "seinen": "Seinen - maturo e realistico",
    "josei": "Josei - quotidiano e relazionale",
    "kodomo": "Kodomo - per bambini",
}

MANGA_PAGE_COLOR_MODE_LABELS = {
    "black_and_white": "Bianco e nero / scala di grigi",
    "color": "A colori",
}

MANGA_BACK_COVER_PROMPT_VERSION = 2


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _get_page_count() -> int:
    return _get_page_count_limits()[2]


def _get_page_count_limits() -> tuple[int, int, int]:
    manga_cfg = get_app_config().get("manga_generation", {})
    min_page_count = int(manga_cfg.get("min_page_count", 10) or 10)
    max_page_count = int(manga_cfg.get("max_page_count", 100) or 100)
    default_page_count = int(manga_cfg.get("page_count", min_page_count) or min_page_count)
    if min_page_count > max_page_count:
        min_page_count, max_page_count = 10, 100
    default_page_count = max(min_page_count, min(default_page_count, max_page_count))
    return min_page_count, max_page_count, default_page_count


def get_requested_manga_page_range(
    *,
    request: Optional[MangaCreateRequest] = None,
    session=None,
) -> tuple[int, int]:
    min_limit, max_limit, default_page_count = _get_page_count_limits()
    if request is not None:
        min_pages = int(request.min_pages or default_page_count)
        max_pages = int(request.max_pages or min_pages)
    elif session is not None and getattr(session, "manga_form_data", None):
        restored_request = MangaCreateRequest(**(getattr(session, "manga_form_data", None) or {}))
        min_pages = restored_request.min_pages
        max_pages = restored_request.max_pages
    else:
        min_pages = default_page_count
        max_pages = default_page_count

    min_pages = max(min_limit, min(min_pages, max_limit))
    max_pages = max(min_pages, min(max_pages, max_limit))
    return min_pages, max_pages


def get_requested_manga_page_color_mode(
    *,
    request: Optional[MangaCreateRequest] = None,
    session=None,
) -> str:
    if request is not None:
        return str(request.page_color_mode or "black_and_white")
    if session is not None and getattr(session, "manga_form_data", None):
        restored_request = MangaCreateRequest(**(getattr(session, "manga_form_data", None) or {}))
        return str(restored_request.page_color_mode or "black_and_white")
    return "black_and_white"


def _describe_page_color_mode(mode: str) -> str:
    return MANGA_PAGE_COLOR_MODE_LABELS.get(mode, MANGA_PAGE_COLOR_MODE_LABELS["black_and_white"])


def _build_page_color_instruction(mode: str) -> str:
    if mode == "color":
        return (
            "Le pagine interne devono essere a colori, con palette coerente e resa cromatica stabile "
            "dalla prima all'ultima pagina."
        )
    return (
        "Le pagine interne devono essere esclusivamente in bianco e nero o scala di grigi, senza elementi "
        "a colori, con retini/contrasti coerenti dalla prima all'ultima pagina."
    )


def _invalidate_cached_manga_pdf(session) -> None:
    session.pdf_path = None
    session.pdf_filename = None


def _get_planned_page_count(plan_or_dict: Any) -> Optional[int]:
    if not plan_or_dict:
        return None
    if isinstance(plan_or_dict, MangaPlan):
        page_plans = plan_or_dict.page_plans
    elif isinstance(plan_or_dict, dict):
        page_plans = plan_or_dict.get("page_plans", []) or []
    else:
        page_plans = getattr(plan_or_dict, "page_plans", []) or []
    return len(page_plans) if page_plans else None


def get_resolved_manga_page_count(session) -> Optional[int]:
    planned_from_plan = _get_planned_page_count(getattr(session, "manga_plan", None))
    if planned_from_plan is not None:
        return planned_from_plan

    progress = getattr(session, "manga_progress", None) or {}
    planned_from_progress = progress.get("planned_total_pages")
    if planned_from_progress:
        return int(planned_from_progress)

    completed_pages = getattr(session, "manga_pages", None) or []
    if progress.get("is_complete") and completed_pages:
        return len(completed_pages)
    return None


def get_runtime_manga_total_steps(session) -> int:
    resolved_total_pages = get_resolved_manga_page_count(session)
    if resolved_total_pages is not None:
        return resolved_total_pages

    progress = getattr(session, "manga_progress", None) or {}
    if progress.get("total_steps"):
        return int(progress.get("total_steps", 0) or 0)

    _requested_min_pages, requested_max_pages = get_requested_manga_page_range(session=session)
    return requested_max_pages


def _manga_overrides(session=None, request: Optional[MangaCreateRequest] = None) -> dict[str, str]:
    if request is not None and getattr(request, "model_overrides", None):
        return dict(request.model_overrides)
    if session is not None:
        form = getattr(session, "manga_form_data", None) or {}
        overrides = form.get("model_overrides") or {}
        if isinstance(overrides, dict):
            return {str(key): str(value) for key, value in overrides.items() if value}
        form_data = getattr(session, "form_data", None)
        if form_data is not None and getattr(form_data, "model_overrides", None):
            return dict(form_data.model_overrides)
    return {}


def _get_image_model(
    stage: str = "manga_pages",
    *,
    session=None,
    request: Optional[MangaCreateRequest] = None,
) -> str:
    return get_stage_model(
        stage,
        overrides=_manga_overrides(session=session, request=request),
        form_data=getattr(session, "form_data", None) if session is not None else None,
    )


def _get_image_aspect_ratio() -> str:
    return str(get_app_config().get("manga_generation", {}).get("aspect_ratio", "3:4"))


def _get_cover_aspect_ratio() -> str:
    return str(get_app_config().get("cover_generation", {}).get("aspect_ratio", "2:3"))


def _get_max_reference_images() -> int:
    return int(get_app_config().get("manga_generation", {}).get("max_reference_images", 2) or 2)


def _get_retry_config() -> tuple[int, int]:
    retry_cfg = get_app_config().get("retry", {}).get("manga_generation", {})
    max_retries = int(retry_cfg.get("max_retries", 2) or 2)
    delay_seconds = int(retry_cfg.get("page_retry_delay_seconds", DEFAULT_RETRY_DELAY_SECONDS) or DEFAULT_RETRY_DELAY_SECONDS)
    return max_retries, delay_seconds


def _is_unsupported_image_size_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "image size" in text and ("not supported" in text or "invalid_argument" in text)


def _image_generation_config(aspect_ratio: str, image_size: str) -> dict[str, Any]:
    return {
        "response_modalities": ["IMAGE"],
        "image_config": {
            "aspect_ratio": aspect_ratio,
            "image_size": image_size,
        },
    }


def _build_manga_image_client(api_key: Optional[str] = None) -> genai.Client:
    return build_google_genai_client(api_key=api_key)


def _extract_google_genai_token_usage(response: Any, model_name: str) -> dict[str, int]:
    token_usage = {"input_tokens": 0, "output_tokens": 0, "model": model_name}
    usage = getattr(response, "usage_metadata", None)
    if usage:
        token_usage["input_tokens"] = int(getattr(usage, "prompt_token_count", 0) or 0)
        token_usage["output_tokens"] = int(getattr(usage, "candidates_token_count", 0) or 0)
    return token_usage


def _accumulate_token_usage(
    token_usage_state: dict[str, Any],
    *,
    phase: str,
    token_usage: dict[str, int],
    model_name: str,
) -> None:
    phase_state = token_usage_state.setdefault(
        phase,
        {"input_tokens": 0, "output_tokens": 0, "model": None, "calls": 0},
    )
    phase_state["input_tokens"] = int(phase_state.get("input_tokens", 0) or 0) + int(token_usage.get("input_tokens", 0) or 0)
    phase_state["output_tokens"] = int(phase_state.get("output_tokens", 0) or 0) + int(token_usage.get("output_tokens", 0) or 0)
    phase_state["model"] = model_name
    phase_state["calls"] = int(phase_state.get("calls", 0) or 0) + 1

    total_state = token_usage_state.setdefault("total", {"input_tokens": 0, "output_tokens": 0})
    total_state["input_tokens"] = int(total_state.get("input_tokens", 0) or 0) + int(token_usage.get("input_tokens", 0) or 0)
    total_state["output_tokens"] = int(total_state.get("output_tokens", 0) or 0) + int(token_usage.get("output_tokens", 0) or 0)


def _calculate_text_cost_eur(token_usage: dict[str, int], model_name: str) -> float:
    if not model_name:
        return 0.0
    pricing = get_model_pricing(model_name)
    exchange_rate = get_exchange_rate_usd_to_eur()
    cost_usd = (
        (int(token_usage.get("input_tokens", 0) or 0) * pricing["input_cost_per_million"] / 1_000_000)
        + (int(token_usage.get("output_tokens", 0) or 0) * pricing["output_cost_per_million"] / 1_000_000)
    )
    return round(cost_usd * exchange_rate, 6)


def _get_image_page_cost_eur(page_count: int = 1) -> float:
    app_config = get_app_config()
    cost_cfg = app_config.get("cost_estimation", {})
    per_page_usd = float(cost_cfg.get("manga_image_generation_cost", cost_cfg.get("image_generation_cost", 0.02)))
    return round(per_page_usd * get_exchange_rate_usd_to_eur() * page_count, 6)


def _replace_or_append_page(pages: list[dict[str, Any]], new_page: dict[str, Any]) -> list[dict[str, Any]]:
    filtered = [page for page in pages if int(page.get("page_number", -1)) != int(new_page["page_number"])]
    filtered.append(new_page)
    filtered.sort(key=lambda page: int(page.get("page_number", 0)))
    return filtered


def _first_generated_page(session) -> Optional[dict[str, Any]]:
    pages = sorted(
        getattr(session, "manga_pages", []) or [],
        key=lambda page: int(page.get("page_number", 0) or 0),
    )
    for page in pages:
        if page.get("image_path"):
            return page
    return None


def _build_cover_image_url(session) -> Optional[str]:
    if getattr(session, "cover_image_path", None):
        return f"/api/library/cover/{session.session_id}"
    first_page = _first_generated_page(session)
    if first_page:
        page_number = int(first_page.get("page_number", 1) or 1)
        return f"/api/manga/{session.session_id}/pages/{page_number}/image"
    return None


def _build_back_cover_image_url(session) -> Optional[str]:
    if getattr(session, "back_cover_image_path", None):
        return f"/api/manga/{session.session_id}/back-cover/image"
    return None


def _manga_cost_snapshot(session) -> dict[str, Any]:
    planning_phase = (getattr(session, "token_usage", None) or {}).get("manga_planning", {})
    planning_text_cost_eur = _calculate_text_cost_eur(
        planning_phase,
        planning_phase.get("model", "gemini-3.8-flash"),
    )
    total_pages = get_resolved_manga_page_count(session) or get_runtime_manga_total_steps(session)
    return _build_cost_breakdown(
        planning_text_cost_eur=planning_text_cost_eur,
        generated_pages_count=len(getattr(session, "manga_pages", []) or []),
        has_cover=bool(getattr(session, "cover_image_path", None)),
        has_back_cover=bool(getattr(session, "back_cover_image_path", None)),
        total_pages=total_pages,
    )


def _build_cost_breakdown(
    *,
    planning_text_cost_eur: float,
    generated_pages_count: int,
    has_cover: bool,
    has_back_cover: bool,
    total_pages: int,
) -> dict[str, Any]:
    per_image_eur = _get_image_page_cost_eur(1)
    generated_images_count = generated_pages_count + (1 if has_cover else 0) + (1 if has_back_cover else 0)
    estimated_image_count = total_pages + 2
    current_cost_eur = planning_text_cost_eur + (generated_images_count * per_image_eur)
    estimated_total_eur = planning_text_cost_eur + (estimated_image_count * per_image_eur)
    return {
        "planning_text_eur": round(planning_text_cost_eur, 6),
        "image_page_eur": round(per_image_eur, 6),
        "cover_image_eur": round(per_image_eur, 6),
        "cover_generated": has_cover,
        "back_cover_generated": has_back_cover,
        "generated_pages_count": generated_pages_count,
        "generated_images_count": generated_images_count,
        "estimated_total_eur": round(estimated_total_eur, 6),
        "current_cost_eur": round(current_cost_eur, 6),
    }


def _build_reader_page(session_id: str, page: dict[str, Any]) -> MangaPageArtifact:
    page_number = int(page.get("page_number", 0) or 0)
    image_path = page.get("image_path")
    image_url = None
    if image_path:
        image_url = f"/api/manga/{session_id}/pages/{page_number}/image"
    return MangaPageArtifact(
        page_number=page_number,
        title=page.get("title", f"Pagina {page_number}"),
        summary=page.get("summary", ""),
        dialogue=page.get("dialogue", []) or [],
        image_path=image_path,
        image_url=image_url,
        prompt_excerpt=page.get("prompt_excerpt"),
        status=page.get("status", "completed"),
    )


def build_manga_progress_response(session) -> MangaProgress:
    progress = (getattr(session, "manga_progress", None) or {}).copy()
    pages = [_build_reader_page(session.session_id, page) for page in getattr(session, "manga_pages", [])]
    pages.sort(key=lambda page: page.page_number)
    requested_min_pages, requested_max_pages = get_requested_manga_page_range(session=session)
    planned_total_pages = get_resolved_manga_page_count(session)
    total_steps = planned_total_pages or int(progress.get("total_steps", 0) or 0)
    if total_steps <= 0:
        total_steps = planned_total_pages or get_runtime_manga_total_steps(session)

    cost_breakdown = _manga_cost_snapshot(session)
    stored_breakdown = progress.get("cost_breakdown")
    if isinstance(stored_breakdown, dict):
        cost_breakdown = {**stored_breakdown, **cost_breakdown}

    estimated_cost = cost_breakdown.get("estimated_total_eur")
    current_cost_eur = cost_breakdown.get("current_cost_eur")
    started_at = progress.get("started_at") or progress.get("queued_at")

    return MangaProgress(
        session_id=session.session_id,
        status=progress.get("status"),
        job_id=progress.get("job_id"),
        job_type=progress.get("job_type"),
        recoverable=progress.get("recoverable", False),
        attempt=progress.get("attempt"),
        updated_at=progress.get("updated_at"),
        queued_at=progress.get("queued_at"),
        started_at=started_at,
        completed_at=progress.get("completed_at"),
        job_metrics=progress.get("job_metrics"),
        requested_min_pages=int(progress.get("requested_min_pages", requested_min_pages) or requested_min_pages),
        requested_max_pages=int(progress.get("requested_max_pages", requested_max_pages) or requested_max_pages),
        planned_total_pages=planned_total_pages,
        current_step=int(progress.get("current_step", len(pages)) or 0),
        total_steps=total_steps,
        current_phase=progress.get("current_phase"),
        current_page_number=progress.get("current_page_number"),
        current_page_title=progress.get("current_page_title"),
        completed_pages=pages,
        is_complete=progress.get("is_complete", False),
        is_paused=progress.get("is_paused", False),
        error=progress.get("error"),
        estimated_cost=estimated_cost,
        current_cost_eur=current_cost_eur,
        cost_breakdown=cost_breakdown,
    )


def build_manga_reader_response(session) -> MangaReaderResponse:
    plan_dict = getattr(session, "manga_plan", None) or {}
    plan = MangaPlan(**plan_dict) if plan_dict else None
    progress = (getattr(session, "manga_progress", None) or {}).copy()
    title = getattr(session, "current_title", None) or (plan.title if plan else "Mini Manga")
    manga_form_data = getattr(session, "manga_form_data", None) or {}
    pages = [_build_reader_page(session.session_id, page) for page in getattr(session, "manga_pages", [])]
    pages.sort(key=lambda page: page.page_number)
    requested_min_pages, requested_max_pages = get_requested_manga_page_range(session=session)
    page_color_mode = get_requested_manga_page_color_mode(session=session)
    planned_total_pages = get_resolved_manga_page_count(session)

    return MangaReaderResponse(
        session_id=session.session_id,
        title=title,
        manga_type=manga_form_data.get("manga_type", "shonen"),
        page_color_mode=page_color_mode,  # type: ignore[arg-type]
        requested_min_pages=requested_min_pages,
        requested_max_pages=requested_max_pages,
        planned_total_pages=planned_total_pages,
        synopsis=(plan.synopsis if plan else ""),
        characters=list(plan.character_profiles) if plan else [],
        cover_image_url=_build_cover_image_url(session),
        back_cover_image_url=_build_back_cover_image_url(session),
        pages=pages,
        is_complete=progress.get("is_complete", False),
        total_pages=planned_total_pages or 0,
    )


async def _save_session(session_store, session) -> None:
    await save_session_async(session_store, session)
    await refresh_process_metrics_async(session_store, session.session_id, "manga")


async def _update_progress(
    session_store,
    session_id: str,
    **updates: Any,
):
    session = await get_session_async(session_store, session_id)
    if not session:
        raise ValueError(f"Sessione manga {session_id} non trovata")

    progress = (session.manga_progress or {}).copy()
    requested_min_pages, requested_max_pages = get_requested_manga_page_range(session=session)
    planned_total_pages = get_resolved_manga_page_count(session)
    progress.setdefault("session_id", session_id)
    progress.setdefault("job_id", f"manga:{session_id}")
    progress.setdefault("job_type", "manga")
    progress.setdefault("current_step", 0)
    progress.setdefault("total_steps", get_runtime_manga_total_steps(session))
    progress.setdefault("requested_min_pages", requested_min_pages)
    progress.setdefault("requested_max_pages", requested_max_pages)
    progress.setdefault("status", "running")
    progress.setdefault("current_phase", "planning")
    if not progress.get("started_at"):
        progress["started_at"] = _now_iso()
    if progress.get("estimated_cost") is None or progress.get("current_cost_eur") is None:
        cost_breakdown = _manga_cost_snapshot(session)
        progress.setdefault("estimated_cost", cost_breakdown["estimated_total_eur"])
        progress.setdefault("current_cost_eur", cost_breakdown["current_cost_eur"])
        progress.setdefault("cost_breakdown", cost_breakdown)
    if planned_total_pages is not None:
        progress["planned_total_pages"] = planned_total_pages
    else:
        progress.setdefault("planned_total_pages", None)
    progress["updated_at"] = _now_iso()
    progress.update(updates)
    if progress.get("requested_min_pages") is None:
        progress["requested_min_pages"] = requested_min_pages
    if progress.get("requested_max_pages") is None:
        progress["requested_max_pages"] = requested_max_pages
    if progress.get("planned_total_pages") is None and planned_total_pages is not None:
        progress["planned_total_pages"] = planned_total_pages
    session.manga_progress = progress
    await _save_session(session_store, session)
    return session


def _build_page_prompt(
    *,
    request: MangaCreateRequest,
    plan: MangaPlan,
    page_plan: MangaPagePlan,
    previous_pages: list[dict[str, Any]],
) -> str:
    total_pages = len(plan.page_plans)
    page_color_mode = get_requested_manga_page_color_mode(request=request)
    style_guide_fallback = (
        "- Stile manga pulito a colori, con palette coerente, balloon leggibili e ritmo visivo chiaro."
        if page_color_mode == "color"
        else "- Stile manga pulito in bianco e nero, con balloon leggibili e ritmo visivo chiaro."
    )
    previous_summaries = [
        f"Pagina {page.get('page_number')}: {page.get('summary', '')}"
        for page in previous_pages[-3:]
    ]
    style_guide = "\n".join(f"- {item}" for item in plan.style_guide)
    characters = "\n".join(
        f"- {character.name}: ruolo={character.role or 'non specificato'}; aspetto={character.appearance}; personalita={character.personality}; note={character.notes}"
        for character in plan.character_profiles
    )
    dialogue = "\n".join(f"- {line}" for line in page_plan.dialogue) or "- Mantieni il testo minimo."
    continuity = "\n".join(f"- {line}" for line in page_plan.continuity_notes) or "- Mantieni la continuita generale."
    previous_pages_block = "\n".join(previous_summaries) or "- Questa e la pagina di apertura."

    return (
        "Genera una singola pagina completa di manga.\n\n"
        f"Titolo del progetto: {plan.title}\n"
        f"Tipo di manga: {MANGA_TYPE_LABELS.get(request.manga_type, request.manga_type)}\n"
        f"Modalita cromatica interna: {_describe_page_color_mode(page_color_mode)}\n"
        f"Sinossi completa: {plan.synopsis}\n"
        f"Tono della serie: {plan.tone}\n\n"
        f"{MANGA_LANGUAGE_RULE}\n\n"
        "Guida stilistica globale:\n"
        f"{style_guide or style_guide_fallback}\n\n"
        "Bible personaggi:\n"
        f"{characters or '- Nessuna bible personaggi disponibile.'}\n\n"
        f"Riferimento interno non visibile: pagina {page_plan.page_number} di {total_pages}, titolo interno '{page_plan.title}'.\n"
        f"Obiettivo narrativo: {page_plan.narrative_goal}\n"
        f"Descrizione della scena: {page_plan.scene_description}\n"
        f"Riassunto della pagina: {page_plan.summary}\n\n"
        "Dialoghi da inserire nei balloon, in italiano:\n"
        f"{dialogue}\n\n"
        "Note visive:\n"
        + "\n".join(f"- {line}" for line in page_plan.visual_notes)
        + "\n\n"
        "Vincoli di continuita per questa pagina:\n"
        f"{continuity}\n\n"
        "Contesto delle pagine recenti:\n"
        f"{previous_pages_block}\n\n"
        "Vincoli rigidi:\n"
        "- Restituisci solo l'immagine della pagina manga, senza spiegazioni.\n"
        f"- {_build_page_color_instruction(page_color_mode)}\n"
        "- Stile, tratto, personaggi e proporzioni identici alla prima pagina e alle recenti.\n"
        "- Balloon e testo diegetico nell'illustrazione; onomatopee come suono, senza prefissi.\n"
        f"- {MANGA_NO_META_RULE}\n"
        "- Testo sintetico e leggibile. Niente watermark, UI o margini bianchi esterni."
    )


def _build_cover_prompt(
    *,
    request: MangaCreateRequest,
    plan: MangaPlan,
) -> str:
    style_guide = "\n".join(f"- {item}" for item in plan.style_guide)
    characters = "\n".join(
        f"- {character.name}: ruolo={character.role or 'non specificato'}; aspetto={character.appearance}; personalita={character.personality}; note={character.notes}"
        for character in plan.character_profiles[:4]
    )

    return (
        "Genera la copertina illustrata di un mini manga.\n\n"
        f"Titolo da inserire in copertina: {plan.title}\n"
        f"Tipo di manga: {MANGA_TYPE_LABELS.get(request.manga_type, request.manga_type)}\n"
        f"Sinossi: {plan.synopsis}\n"
        f"Tono: {plan.tone}\n\n"
        f"{MANGA_LANGUAGE_RULE}\n\n"
        "Guida stilistica:\n"
        f"{style_guide or '- Copertina editoriale in stile manga, forte impatto visivo, composizione pulita.'}\n\n"
        "Personaggi principali da rappresentare, se coerente:\n"
        f"{characters or '- Nessun personaggio da mostrare in primo piano.'}\n\n"
        "Vincoli rigidi:\n"
        "- Restituisci solo l'immagine della copertina, senza spiegazioni.\n"
        "- Copertina verticale singola, non una pagina a vignette.\n"
        "- La copertina deve essere sempre a colori, anche se le pagine interne sono in bianco e nero.\n"
        "- Inserisci il titolo in modo leggibile e professionale.\n"
        "- Non inserire il nome dell'autore.\n"
        "- Look editoriale coerente con il manga e con i protagonisti.\n"
        f"- {MANGA_NO_META_RULE}\n"
        "- Evita watermark, elementi UI, testo casuale o margini bianchi esterni."
    )


def _build_back_cover_prompt(
    *,
    request: MangaCreateRequest,
    plan: MangaPlan,
    previous_pages: list[dict[str, Any]],
) -> str:
    style_guide = "\n".join(f"- {item}" for item in plan.style_guide)
    characters = "\n".join(
        f"- {character.name}: ruolo={character.role or 'non specificato'}; aspetto={character.appearance}; personalita={character.personality}; note={character.notes}"
        for character in plan.character_profiles[:4]
    )
    recent_summaries = "\n".join(
        f"- Pagina {page.get('page_number')}: {page.get('summary', '')}"
        for page in previous_pages[-3:]
    ) or "- Conclusione non disponibile."

    return (
        "Genera la retro-copertina illustrata di un mini manga.\n\n"
        f"Titolo del manga: {plan.title}\n"
        f"Tipo di manga: {MANGA_TYPE_LABELS.get(request.manga_type, request.manga_type)}\n"
        f"Tono: {plan.tone}\n"
        f"Sinossi generale: {plan.synopsis}\n\n"
        "Contesto finale della storia:\n"
        f"{recent_summaries}\n\n"
        "Guida stilistica:\n"
        f"{style_guide or '- Retro-copertina editoriale illustrata, forte coerenza con la copertina frontale.'}\n\n"
        "Personaggi/elementi principali da mantenere riconoscibili:\n"
        f"{characters or '- Nessun personaggio da mostrare obbligatoriamente.'}\n\n"
        "Vincoli rigidi:\n"
        "- Restituisci solo l'immagine della retro-copertina, senza spiegazioni.\n"
        "- Retro-copertina verticale singola, non una pagina a vignette.\n"
        "- Deve essere sempre a colori, con look editoriale coerente alla copertina frontale.\n"
        "- Usa la copertina frontale solo come riferimento di stile: non copiarne posa, inquadratura, composizione o sfondo.\n"
        "- La retro-copertina deve mostrare un momento o un'atmosfera diversa dalla copertina frontale, legata al finale o al dopo-finale.\n"
        "- Se compaiono gli stessi personaggi, mostrali con espressione, distanza camera, assetto del corpo o ambientazione chiaramente differenti dalla copertina frontale.\n"
        f"- {MANGA_NO_META_RULE} Niente titolo, barcode, prezzo o testo promozionale.\n"
        "- Coerenza di protagonisti, abiti, palette e stile con il manga.\n"
        "- Evita watermark, elementi UI, testo casuale o margini bianchi esterni."
    )


def _select_reference_pages(previous_pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not previous_pages:
        return []

    max_reference_images = _get_max_reference_images()
    if max_reference_images <= 0:
        return []

    selected_pages: list[dict[str, Any]] = []
    first_page = previous_pages[0]
    if first_page.get("image_path"):
        selected_pages.append(first_page)

    for page in reversed(previous_pages):
        if len(selected_pages) >= max_reference_images:
            break
        if not page.get("image_path"):
            continue
        page_number = int(page.get("page_number", 0) or 0)
        if any(int(candidate.get("page_number", 0) or 0) == page_number for candidate in selected_pages):
            continue
        selected_pages.append(page)

    selected_pages.sort(key=lambda page: int(page.get("page_number", 0) or 0))
    return selected_pages[:max_reference_images]


def _build_back_cover_reference_image_paths(
    *,
    previous_pages: list[dict[str, Any]],
    cover_image_path: Optional[str],
) -> list[str]:
    max_reference_images = max(1, _get_max_reference_images())
    selected_paths: list[str] = []
    seen_paths: set[str] = set()

    if cover_image_path:
        selected_paths.append(cover_image_path)
        seen_paths.add(cover_image_path)

    remaining_slots = max_reference_images - len(selected_paths)
    if remaining_slots <= 0:
        return selected_paths

    for page in reversed(previous_pages):
        image_path = page.get("image_path")
        if not image_path or image_path in seen_paths:
            continue
        selected_paths.append(image_path)
        seen_paths.add(image_path)
        if len(selected_paths) >= max_reference_images:
            break

    return selected_paths


async def _load_reference_image_parts(
    previous_pages: list[dict[str, Any]],
    reference_image_paths: Optional[list[str]] = None,
) -> list[types.Part]:
    storage_service = get_storage_service()
    reference_parts: list[types.Part] = []
    seen_paths: set[str] = set()
    image_paths: list[str] = []

    for image_path in reference_image_paths or []:
        if image_path and image_path not in seen_paths:
            image_paths.append(image_path)
            seen_paths.add(image_path)

    for page in _select_reference_pages(previous_pages):
        image_path = page.get("image_path")
        if image_path and image_path not in seen_paths:
            image_paths.append(image_path)
            seen_paths.add(image_path)

    for image_path in image_paths:
        if not image_path:
            continue
        try:
            image_bytes = await asyncio.to_thread(storage_service.download_file, image_path)
            reference_parts.append(
                types.Part(
                    inline_data=types.Blob(
                        mime_type="image/png",
                        data=image_bytes,
                    )
                )
            )
        except Exception as exc:
            logger.warning(
                "Impossibile caricare immagine precedente come contesto",
                context={"image_path": image_path, "error": str(exc)},
            )
    return reference_parts


def _extract_png_bytes_from_image_response(response: Any) -> bytes:
    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None) or []
        for part in parts:
            try:
                image_obj = part.as_image()
                buffer = BytesIO()
                image_obj.save(buffer, format="PNG")
                return buffer.getvalue()
            except Exception:
                pass

            inline_data = getattr(part, "inline_data", None)
            if inline_data and getattr(inline_data, "data", None):
                raw_data = inline_data.data
                if isinstance(raw_data, str):
                    raw_data = base64.b64decode(raw_data)
                buffer = BytesIO(bytes(raw_data))
                image = PILImage.open(buffer)
                normalized = BytesIO()
                image.save(normalized, format="PNG")
                return normalized.getvalue()
    raise ValueError("La risposta del modello immagine non contiene alcuna immagine valida")


async def _generate_image_asset(
    *,
    session_id: str,
    prompt: str,
    aspect_ratio: str,
    previous_pages: Optional[list[dict[str, Any]]] = None,
    reference_image_paths: Optional[list[str]] = None,
    api_key: Optional[str] = None,
    model_name: Optional[str] = None,
) -> tuple[bytes, dict[str, int]]:
    client = _build_manga_image_client(api_key=api_key)
    resolved_model = model_name or _get_image_model()
    image_size = image_size_for_model(resolved_model)
    config = _image_generation_config(aspect_ratio, image_size)
    config_obj = types.GenerateContentConfig(**config) if hasattr(types, "GenerateContentConfig") else config
    reference_parts = await _load_reference_image_parts(previous_pages or [], reference_image_paths)
    contents = [
        types.Content(
            role="user",
            parts=[types.Part(text=prompt), *reference_parts],
        )
    ]

    max_retries, retry_delay_seconds = _get_retry_config()
    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=resolved_model,
                contents=contents,
                config=config_obj,
            )
            image_bytes = _extract_png_bytes_from_image_response(response)
            return image_bytes, _extract_google_genai_token_usage(response, resolved_model)
        except Exception as exc:
            last_error = exc
            if (
                image_size != "1K"
                and _is_unsupported_image_size_error(exc)
            ):
                logger.warning(
                    "Dimensione immagine non supportata, riprovo a 1K",
                    context={
                        "session_id": session_id,
                        "model": resolved_model,
                        "image_size": image_size,
                        "error": str(exc),
                    },
                )
                image_size = "1K"
                config = _image_generation_config(aspect_ratio, image_size)
                config_obj = types.GenerateContentConfig(**config) if hasattr(types, "GenerateContentConfig") else config
                continue
            retryable = is_retryable_llm_error(exc)
            if retryable and attempt < max_retries - 1:
                delay = retry_delay_seconds * (attempt + 1)
                logger.warning(
                    "Generazione pagina manga fallita, riprovo",
                    context={
                        "session_id": session_id,
                        "attempt": attempt + 1,
                        "delay_seconds": delay,
                        "error": str(exc),
                    },
                )
                await asyncio.sleep(delay)
                continue
            raise

    if last_error:
        raise last_error
    raise RuntimeError("Generazione immagine manga fallita senza errore esplicito")


async def _generate_page_image(
    *,
    session_id: str,
    prompt: str,
    previous_pages: list[dict[str, Any]],
    api_key: Optional[str] = None,
    model_name: Optional[str] = None,
) -> tuple[bytes, dict[str, int]]:
    return await _generate_image_asset(
        session_id=session_id,
        prompt=prompt,
        aspect_ratio=_get_image_aspect_ratio(),
        previous_pages=previous_pages,
        reference_image_paths=None,
        api_key=api_key,
        model_name=model_name,
    )


async def _generate_cover_image(
    *,
    session_id: str,
    prompt: str,
    api_key: Optional[str] = None,
    model_name: Optional[str] = None,
) -> tuple[bytes, dict[str, int]]:
    return await _generate_image_asset(
        session_id=session_id,
        prompt=prompt,
        aspect_ratio=_get_cover_aspect_ratio(),
        previous_pages=None,
        reference_image_paths=None,
        api_key=api_key,
        model_name=model_name,
    )


async def _generate_back_cover_image(
    *,
    session_id: str,
    prompt: str,
    previous_pages: Optional[list[dict[str, Any]]] = None,
    reference_image_paths: Optional[list[str]] = None,
    api_key: Optional[str] = None,
    model_name: Optional[str] = None,
) -> tuple[bytes, dict[str, int]]:
    return await _generate_image_asset(
        session_id=session_id,
        prompt=prompt,
        aspect_ratio=_get_cover_aspect_ratio(),
        previous_pages=previous_pages,
        reference_image_paths=reference_image_paths,
        api_key=api_key,
        model_name=model_name,
    )


async def _store_page_image(
    *,
    session,
    page_number: int,
    image_bytes: bytes,
) -> str:
    storage_service = get_storage_service()
    destination_path = f"manga/{session.session_id}/page_{page_number:02d}.png"
    return await asyncio.to_thread(
        storage_service.upload_file,
        image_bytes,
        destination_path,
        "image/png",
        getattr(session, "user_id", None),
    )


async def _store_cover_image(
    *,
    session,
    image_bytes: bytes,
) -> str:
    storage_service = get_storage_service()
    destination_path = f"manga/{session.session_id}/cover.png"
    return await asyncio.to_thread(
        storage_service.upload_file,
        image_bytes,
        destination_path,
        "image/png",
        getattr(session, "user_id", None),
    )


async def _store_back_cover_image(
    *,
    session,
    image_bytes: bytes,
) -> str:
    storage_service = get_storage_service()
    destination_path = f"manga/{session.session_id}/back_cover.png"
    return await asyncio.to_thread(
        storage_service.upload_file,
        image_bytes,
        destination_path,
        "image/png",
        getattr(session, "user_id", None),
    )


def _recalculate_manga_costs(session) -> dict[str, Any]:
    cost_breakdown = _manga_cost_snapshot(session)
    total_pages = get_resolved_manga_page_count(session) or get_runtime_manga_total_steps(session)
    session.manga_cost_eur = cost_breakdown["current_cost_eur"]
    progress = (getattr(session, "manga_progress", None) or {}).copy()
    if progress:
        requested_min_pages, requested_max_pages = get_requested_manga_page_range(session=session)
        progress["requested_min_pages"] = int(progress.get("requested_min_pages", requested_min_pages) or requested_min_pages)
        progress["requested_max_pages"] = int(progress.get("requested_max_pages", requested_max_pages) or requested_max_pages)
        progress["planned_total_pages"] = get_resolved_manga_page_count(session)
        progress["total_steps"] = total_pages
        progress["estimated_cost"] = cost_breakdown["estimated_total_eur"]
        progress["current_cost_eur"] = cost_breakdown["current_cost_eur"]
        progress["cost_breakdown"] = cost_breakdown
        session.manga_progress = progress
    return cost_breakdown


def is_manga_back_cover_outdated(session) -> bool:
    if not getattr(session, "back_cover_image_path", None):
        return False
    current_version = int(getattr(session, "back_cover_prompt_version", 0) or 0)
    return current_version < MANGA_BACK_COVER_PROMPT_VERSION


async def backfill_manga_cover_if_missing(
    *,
    session_id: str,
    api_key: Optional[str] = None,
) -> Optional[str]:
    session_store = get_session_store()
    session = await get_session_async(session_store, session_id)
    if not session or getattr(session, "content_type", "book") != "manga":
        return None
    if getattr(session, "cover_image_path", None):
        return session.cover_image_path

    plan_dict = getattr(session, "manga_plan", None) or {}
    form_dict = getattr(session, "manga_form_data", None) or {}
    if not plan_dict or not form_dict:
        return None

    plan = MangaPlan(**plan_dict)
    request = MangaCreateRequest(**form_dict)
    try:
        cover_prompt = _build_cover_prompt(request=request, plan=plan)
        cover_bytes, cover_token_usage = await _generate_cover_image(
            session_id=session_id,
            prompt=cover_prompt,
            api_key=api_key,
            model_name=_get_image_model("manga_cover", session=session, request=request),
        )
        cover_path = await _store_cover_image(session=session, image_bytes=cover_bytes)
        session.cover_image_path = cover_path
        _invalidate_cached_manga_pdf(session)
        _accumulate_token_usage(
            session.token_usage,
            phase="manga_images",
            token_usage=cover_token_usage,
            model_name=cover_token_usage.get("model", _get_image_model()),
        )
        _recalculate_manga_costs(session)
        await _save_session(session_store, session)
        return cover_path
    except Exception as exc:
        logger.warning(
            "Backfill copertina manga fallito",
            context={"session_id": session_id, "error": str(exc)},
        )
        return None


async def backfill_manga_back_cover_if_missing(
    *,
    session_id: str,
    force_regenerate: bool = False,
    api_key: Optional[str] = None,
) -> Optional[str]:
    session_store = get_session_store()
    session = await get_session_async(session_store, session_id)
    if not session or getattr(session, "content_type", "book") != "manga":
        return None
    if getattr(session, "back_cover_image_path", None) and not force_regenerate:
        return session.back_cover_image_path

    plan_dict = getattr(session, "manga_plan", None) or {}
    form_dict = getattr(session, "manga_form_data", None) or {}
    if not plan_dict or not form_dict:
        return None

    plan = MangaPlan(**plan_dict)
    request = MangaCreateRequest(**form_dict)
    previous_pages = getattr(session, "manga_pages", []) or []
    reference_paths = _build_back_cover_reference_image_paths(
        previous_pages=previous_pages,
        cover_image_path=getattr(session, "cover_image_path", None),
    )
    try:
        back_cover_prompt = _build_back_cover_prompt(
            request=request,
            plan=plan,
            previous_pages=previous_pages,
        )
        back_cover_bytes, back_cover_token_usage = await _generate_back_cover_image(
            session_id=session_id,
            prompt=back_cover_prompt,
            previous_pages=previous_pages,
            reference_image_paths=reference_paths,
            api_key=api_key,
            model_name=_get_image_model("manga_back_cover", session=session, request=request),
        )
        back_cover_path = await _store_back_cover_image(session=session, image_bytes=back_cover_bytes)
        session.back_cover_image_path = back_cover_path
        session.back_cover_prompt_version = MANGA_BACK_COVER_PROMPT_VERSION
        _invalidate_cached_manga_pdf(session)
        _accumulate_token_usage(
            session.token_usage,
            phase="manga_images",
            token_usage=back_cover_token_usage,
            model_name=back_cover_token_usage.get("model", _get_image_model()),
        )
        _recalculate_manga_costs(session)
        await _save_session(session_store, session)
        return back_cover_path
    except Exception as exc:
        logger.warning(
            "Backfill retro-copertina manga fallito",
            context={"session_id": session_id, "error": str(exc)},
        )
        return None


async def backfill_manga_artwork_if_missing(
    *,
    session_id: str,
    force_back_cover_regeneration: bool = False,
    api_key: Optional[str] = None,
) -> None:
    await backfill_manga_cover_if_missing(session_id=session_id, api_key=api_key)
    await backfill_manga_back_cover_if_missing(
        session_id=session_id,
        force_regenerate=force_back_cover_regeneration,
        api_key=api_key,
    )


async def _run_generation_loop(
    *,
    session_id: str,
    request: MangaCreateRequest,
    session,
    api_key: Optional[str],
) -> None:
    requested_min_pages, requested_max_pages = get_requested_manga_page_range(request=request, session=session)
    plan_dict = session.manga_plan
    plan: MangaPlan

    if plan_dict:
        plan = MangaPlan(**plan_dict)
        total_pages = len(plan.page_plans)
    else:
        plan, plan_token_usage, _raw_plan = await generate_manga_plan(
            session_id=session_id,
            request=request,
            api_key=api_key,
        )
        total_pages = len(plan.page_plans)
        session = await get_session_async(get_session_store(), session_id)
        if not session:
            raise ValueError(f"Sessione manga {session_id} non trovata dopo il planning")
        session.current_title = plan.title
        session.manga_plan = plan.model_dump()
        session.manga_form_data = request.model_dump()
        _accumulate_token_usage(
            session.token_usage,
            phase="manga_planning",
            token_usage=plan_token_usage,
            model_name=plan_token_usage.get("model", ""),
        )
        planning_text_cost_eur = _calculate_text_cost_eur(plan_token_usage, plan_token_usage.get("model", "gemini-3-flash-preview"))
        cost_breakdown = _build_cost_breakdown(
            planning_text_cost_eur=planning_text_cost_eur,
            generated_pages_count=len(session.manga_pages),
            has_cover=bool(getattr(session, "cover_image_path", None)),
            has_back_cover=bool(getattr(session, "back_cover_image_path", None)),
            total_pages=total_pages,
        )
        session.manga_cost_eur = cost_breakdown["current_cost_eur"]
        progress = (session.manga_progress or {}).copy()
        progress.update(
            {
                "requested_min_pages": requested_min_pages,
                "requested_max_pages": requested_max_pages,
                "planned_total_pages": total_pages,
                "current_phase": "generating_cover" if not getattr(session, "cover_image_path", None) else "generating_pages",
                "current_step": len(session.manga_pages),
                "total_steps": total_pages,
                "current_page_number": len(session.manga_pages) + 1 if getattr(session, "cover_image_path", None) else 0,
                "current_page_title": (
                    plan.page_plans[len(session.manga_pages)].title
                    if getattr(session, "cover_image_path", None) and len(session.manga_pages) < total_pages
                    else "Copertina"
                ),
                "estimated_cost": cost_breakdown["estimated_total_eur"],
                "current_cost_eur": cost_breakdown["current_cost_eur"],
                "cost_breakdown": cost_breakdown,
                "status": "running",
                "is_paused": False,
                "error": None,
                "updated_at": _now_iso(),
            }
        )
        session.manga_progress = progress
        await _save_session(get_session_store(), session)

    if not getattr(session, "cover_image_path", None):
        cover_prompt = _build_cover_prompt(request=request, plan=plan)
        await _update_progress(
            get_session_store(),
            session_id,
            requested_min_pages=requested_min_pages,
            requested_max_pages=requested_max_pages,
            planned_total_pages=total_pages,
            current_phase="generating_cover",
            current_step=len(session.manga_pages),
            total_steps=total_pages,
            current_page_number=0,
            current_page_title="Copertina",
            current_section_name="Copertina",
            error=None,
            is_paused=False,
            status="running",
        )

        cover_bytes, cover_token_usage = await _generate_cover_image(
            session_id=session_id,
            prompt=cover_prompt,
            api_key=api_key,
            model_name=_get_image_model("manga_cover", session=session, request=request),
        )

        session = await get_session_async(get_session_store(), session_id)
        if not session:
            raise ValueError(f"Sessione manga {session_id} non trovata durante il salvataggio copertina")

        cover_path = await _store_cover_image(session=session, image_bytes=cover_bytes)
        session.cover_image_path = cover_path
        _invalidate_cached_manga_pdf(session)
        _accumulate_token_usage(
            session.token_usage,
            phase="manga_images",
            token_usage=cover_token_usage,
            model_name=cover_token_usage.get("model", _get_image_model()),
        )

        planning_phase = session.token_usage.get("manga_planning", {})
        planning_text_cost_eur = _calculate_text_cost_eur(
            planning_phase,
            planning_phase.get("model", "gemini-3-flash-preview"),
        )
        cost_breakdown = _build_cost_breakdown(
            planning_text_cost_eur=planning_text_cost_eur,
            generated_pages_count=len(session.manga_pages),
            has_cover=True,
            has_back_cover=bool(getattr(session, "back_cover_image_path", None)),
            total_pages=total_pages,
        )
        session.manga_cost_eur = cost_breakdown["current_cost_eur"]
        progress = (session.manga_progress or {}).copy()
        progress.update(
            {
                "requested_min_pages": requested_min_pages,
                "requested_max_pages": requested_max_pages,
                "planned_total_pages": total_pages,
                "current_phase": "generating_pages" if len(session.manga_pages) < total_pages else "completed",
                "current_step": len(session.manga_pages),
                "total_steps": total_pages,
                "current_page_number": len(session.manga_pages) + 1 if len(session.manga_pages) < total_pages else total_pages,
                "current_page_title": plan.page_plans[len(session.manga_pages)].title if len(session.manga_pages) < total_pages else "Copertina pronta",
                "current_section_name": "Copertina",
                "estimated_cost": cost_breakdown["estimated_total_eur"],
                "current_cost_eur": cost_breakdown["current_cost_eur"],
                "cost_breakdown": cost_breakdown,
                "updated_at": _now_iso(),
                "error": None,
                "is_paused": False,
                "status": "running" if len(session.manga_pages) < total_pages else "completed",
            }
        )
        session.manga_progress = progress
        await _save_session(get_session_store(), session)

    completed_pages = list(session.manga_pages)
    start_index = len(completed_pages)

    for page_plan in plan.page_plans[start_index:]:
        prompt = _build_page_prompt(
            request=request,
            plan=plan,
            page_plan=page_plan,
            previous_pages=completed_pages,
        )
        await _update_progress(
            get_session_store(),
            session_id,
            requested_min_pages=requested_min_pages,
            requested_max_pages=requested_max_pages,
            planned_total_pages=total_pages,
            current_phase="generating_pages",
            current_step=len(completed_pages),
            total_steps=total_pages,
            current_page_number=page_plan.page_number,
            current_page_title=page_plan.title,
            current_section_name=page_plan.title,
            error=None,
            is_paused=False,
            status="running",
        )

        image_bytes, image_token_usage = await _generate_page_image(
            session_id=session_id,
            prompt=prompt,
            previous_pages=completed_pages,
            api_key=api_key,
            model_name=_get_image_model("manga_pages", session=session, request=request),
        )

        session = await get_session_async(get_session_store(), session_id)
        if not session:
            raise ValueError(f"Sessione manga {session_id} non trovata durante il salvataggio pagina")
        image_path = await _store_page_image(session=session, page_number=page_plan.page_number, image_bytes=image_bytes)
        _accumulate_token_usage(
            session.token_usage,
            phase="manga_images",
            token_usage=image_token_usage,
            model_name=image_token_usage.get("model", _get_image_model()),
        )
        page_dict = {
            "page_number": page_plan.page_number,
            "title": page_plan.title,
            "summary": page_plan.summary,
            "dialogue": page_plan.dialogue,
            "image_path": image_path,
            "prompt_excerpt": prompt[:500],
            "status": "completed",
        }
        session.manga_pages = _replace_or_append_page(session.manga_pages, page_dict)
        completed_pages = list(session.manga_pages)

        planning_text_cost_eur = _calculate_text_cost_eur(
            session.token_usage.get("manga_planning", {}),
            session.token_usage.get("manga_planning", {}).get("model", "gemini-3-flash-preview"),
        )
        cost_breakdown = _build_cost_breakdown(
            planning_text_cost_eur=planning_text_cost_eur,
            generated_pages_count=len(completed_pages),
            has_cover=bool(getattr(session, "cover_image_path", None)),
            has_back_cover=bool(getattr(session, "back_cover_image_path", None)),
            total_pages=total_pages,
        )
        session.manga_cost_eur = cost_breakdown["current_cost_eur"]
        progress = (session.manga_progress or {}).copy()
        progress.update(
            {
                "requested_min_pages": requested_min_pages,
                "requested_max_pages": requested_max_pages,
                "planned_total_pages": total_pages,
                "current_phase": "generating_pages" if len(completed_pages) < total_pages else "generating_back_cover",
                "current_step": len(completed_pages),
                "total_steps": total_pages,
                "current_page_number": page_plan.page_number if len(completed_pages) < total_pages else total_pages,
                "current_page_title": page_plan.title,
                "current_section_name": page_plan.title,
                "estimated_cost": cost_breakdown["estimated_total_eur"],
                "current_cost_eur": cost_breakdown["current_cost_eur"],
                "cost_breakdown": cost_breakdown,
                "updated_at": _now_iso(),
                "error": None,
                "is_paused": False,
                "status": "running",
                "is_complete": False,
            }
        )
        session.manga_progress = progress
        await _save_session(get_session_store(), session)

    back_cover_prompt = _build_back_cover_prompt(
        request=request,
        plan=plan,
        previous_pages=completed_pages,
    )
    await _update_progress(
        get_session_store(),
        session_id,
        requested_min_pages=requested_min_pages,
        requested_max_pages=requested_max_pages,
        planned_total_pages=total_pages,
        current_phase="generating_back_cover",
        current_step=len(completed_pages),
        total_steps=total_pages,
        current_page_number=total_pages,
        current_page_title="Retro copertina",
        current_section_name="Retro copertina",
        error=None,
        is_paused=False,
        status="running",
        is_complete=False,
    )

    back_cover_reference_paths = _build_back_cover_reference_image_paths(
        previous_pages=completed_pages,
        cover_image_path=getattr(session, "cover_image_path", None),
    )
    back_cover_bytes, back_cover_token_usage = await _generate_back_cover_image(
        session_id=session_id,
        prompt=back_cover_prompt,
        previous_pages=completed_pages,
        reference_image_paths=back_cover_reference_paths,
        api_key=api_key,
        model_name=_get_image_model("manga_back_cover", session=session, request=request),
    )

    session = await get_session_async(get_session_store(), session_id)
    if not session:
        raise ValueError(f"Sessione manga {session_id} non trovata durante il salvataggio retro-copertina")

    back_cover_path = await _store_back_cover_image(session=session, image_bytes=back_cover_bytes)
    session.back_cover_image_path = back_cover_path
    session.back_cover_prompt_version = MANGA_BACK_COVER_PROMPT_VERSION
    _invalidate_cached_manga_pdf(session)
    _accumulate_token_usage(
        session.token_usage,
        phase="manga_images",
        token_usage=back_cover_token_usage,
        model_name=back_cover_token_usage.get("model", _get_image_model()),
    )

    final_planning_text_cost_eur = _calculate_text_cost_eur(
        session.token_usage.get("manga_planning", {}),
        session.token_usage.get("manga_planning", {}).get("model", "gemini-3-flash-preview"),
    )
    final_cost_breakdown = _build_cost_breakdown(
        planning_text_cost_eur=final_planning_text_cost_eur,
        generated_pages_count=len(session.manga_pages),
        has_cover=bool(getattr(session, "cover_image_path", None)),
        has_back_cover=True,
        total_pages=total_pages,
    )
    session.manga_cost_eur = final_cost_breakdown["current_cost_eur"]
    progress = (session.manga_progress or {}).copy()
    progress.update(
        {
            "requested_min_pages": requested_min_pages,
            "requested_max_pages": requested_max_pages,
            "planned_total_pages": total_pages,
            "current_phase": "completed",
            "current_step": len(session.manga_pages),
            "total_steps": total_pages,
            "current_page_number": total_pages,
            "current_page_title": "Retro copertina pronta",
            "current_section_name": "Retro copertina",
            "estimated_cost": final_cost_breakdown["estimated_total_eur"],
            "current_cost_eur": final_cost_breakdown["current_cost_eur"],
            "cost_breakdown": final_cost_breakdown,
            "updated_at": _now_iso(),
            "error": None,
            "is_paused": False,
            "status": "completed",
            "is_complete": True,
        }
    )
    session.manga_progress = progress
    await _save_session(get_session_store(), session)


async def background_manga_generation(
    *,
    session_id: str,
    request: MangaCreateRequest,
    api_key: Optional[str] = None,
) -> None:
    session_store = get_session_store()
    try:
        await mark_process_running_async(
            session_store,
            session_id,
            "manga",
            recoverable=False,
            error=None,
        )
        session = await get_session_async(session_store, session_id)
        if not session:
            raise ValueError(f"Sessione manga {session_id} non trovata")
        await _run_generation_loop(
            session_id=session_id,
            request=request,
            session=session,
            api_key=api_key,
        )
        session = await get_session_async(session_store, session_id)
        total_pages = get_runtime_manga_total_steps(session) if session else request.max_pages
        await mark_process_completed_async(
            session_store,
            session_id,
            "manga",
            recoverable=False,
            current_phase="completed",
            is_complete=True,
            current_step=total_pages,
            total_steps=total_pages,
            current_page_number=total_pages,
        )
    except Exception as exc:
        logger.exception("Errore nella generazione manga", context={"session_id": session_id})
        session = await get_session_async(session_store, session_id)
        current_step = len(getattr(session, "manga_pages", []) or []) if session else 0
        total_steps = get_runtime_manga_total_steps(session) if session else request.max_pages
        current_phase = (
            ((getattr(session, "manga_progress", None) or {}).get("current_phase"))
            if session
            else None
        ) or ("generating_pages" if current_step else "planning")
        message = f"Errore nella generazione manga: {exc}"
        await _update_progress(
            session_store,
            session_id,
            current_step=current_step,
            total_steps=total_steps,
            current_phase=current_phase,
            is_paused=True,
            is_complete=False,
            error=message,
            status="paused",
        )
        await mark_process_paused_async(
            session_store,
            session_id,
            "manga",
            message,
            current_step=current_step,
            total_steps=total_steps,
            current_phase=current_phase,
            is_complete=False,
            is_paused=True,
        )


async def background_resume_manga_generation(
    *,
    session_id: str,
    api_key: Optional[str] = None,
) -> None:
    session_store = get_session_store()
    session = await get_session_async(session_store, session_id)
    if not session:
        await mark_process_failed_async(session_store, session_id, "manga", "Sessione manga non trovata", recoverable=True)
        return

    manga_form_data = getattr(session, "manga_form_data", None) or {}
    request = MangaCreateRequest(**manga_form_data)
    await background_manga_generation(session_id=session_id, request=request, api_key=api_key)


async def get_manga_page_image_bytes(session_id: str, page_number: int) -> bytes:
    session_store = get_session_store()
    session = await get_session_async(session_store, session_id)
    if not session:
        raise ValueError(f"Sessione manga {session_id} non trovata")

    page = next(
        (candidate for candidate in session.manga_pages if int(candidate.get("page_number", -1)) == int(page_number)),
        None,
    )
    if not page or not page.get("image_path"):
        raise ValueError(f"Pagina {page_number} non disponibile")

    storage_service = get_storage_service()
    return await asyncio.to_thread(storage_service.download_file, page["image_path"])


async def get_manga_back_cover_image_bytes(session_id: str) -> bytes:
    session_store = get_session_store()
    session = await get_session_async(session_store, session_id)
    if not session:
        raise ValueError(f"Sessione manga {session_id} non trovata")
    if not getattr(session, "back_cover_image_path", None):
        raise ValueError("Retro copertina non disponibile")

    storage_service = get_storage_service()
    return await asyncio.to_thread(storage_service.download_file, session.back_cover_image_path)

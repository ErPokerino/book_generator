"""Servizio per orchestrare e recuperare i job AI persistiti nella sessione."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from app.agent.session_store import SessionData, SessionStore
from app.agent.session_store_helpers import (
    get_all_sessions_async,
    get_session_async,
    save_session_async,
    update_writing_progress_async,
)
from app.core.logging import get_logger

ProcessJobType = Literal["questions", "draft", "outline", "book"]

_PROCESS_FIELD_MAP: dict[ProcessJobType, str] = {
    "questions": "questions_progress",
    "draft": "draft_progress",
    "outline": "outline_progress",
    "book": "writing_progress",
}
_TOKEN_PHASE_MAP: dict[ProcessJobType, str] = {
    "questions": "questions",
    "draft": "draft",
    "outline": "outline",
    "book": "total",
}
_ACTIVE_STATUSES = {"pending", "running"}
logger = get_logger("process-jobs")


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _build_job_id(session_id: str, job_type: ProcessJobType) -> str:
    return f"{job_type}:{session_id}"


def _parse_iso(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _get_progress(session: SessionData, job_type: ProcessJobType) -> dict[str, Any]:
    value = getattr(session, _PROCESS_FIELD_MAP[job_type], None) or {}
    return value.copy() if isinstance(value, dict) else {}


def _build_job_metrics(
    session: SessionData,
    job_type: ProcessJobType,
    progress: dict[str, Any],
) -> dict[str, Any]:
    started_at = _parse_iso(progress.get("started_at"))
    completed_at = _parse_iso(progress.get("completed_at"))
    updated_at = _parse_iso(progress.get("updated_at"))

    metrics: dict[str, Any] = {
        "error_count": int(progress.get("error_count", 0) or 0),
    }

    if started_at:
        end_at = completed_at or updated_at or datetime.utcnow()
        duration_seconds = max((end_at - started_at).total_seconds(), 0.0)
        metrics["duration_seconds"] = round(duration_seconds, 2)

    token_usage = getattr(session, "token_usage", None) or {}
    token_phase = _TOKEN_PHASE_MAP[job_type]
    phase_tokens = token_usage.get(token_phase, {}) or {}
    if phase_tokens:
        token_metrics = {
            "input_tokens": int(phase_tokens.get("input_tokens", 0) or 0),
            "output_tokens": int(phase_tokens.get("output_tokens", 0) or 0),
        }
        if phase_tokens.get("model"):
            token_metrics["model"] = phase_tokens["model"]
        if "calls" in phase_tokens:
            token_metrics["calls"] = int(phase_tokens.get("calls", 0) or 0)
        metrics["token_usage"] = token_metrics

    if job_type == "book":
        writing_progress = session.writing_progress or {}
        estimated_cost = progress.get("estimated_cost", writing_progress.get("estimated_cost"))
        writing_time_minutes = progress.get("writing_time_minutes", writing_progress.get("writing_time_minutes"))
        if estimated_cost is not None:
            metrics["estimated_cost_eur"] = round(float(estimated_cost), 6)
        if getattr(session, "real_cost_eur", None) is not None:
            metrics["real_cost_eur"] = round(float(session.real_cost_eur), 6)
        if writing_time_minutes is not None:
            metrics["writing_time_minutes"] = round(float(writing_time_minutes), 2)

    return metrics


def derive_process_status(
    progress: dict[str, Any] | None,
    job_type: ProcessJobType,
) -> str | None:
    """Determina lo stato corrente del job partendo dal payload persistito."""
    if not progress:
        return None

    if job_type == "book":
        if progress.get("is_complete", False):
            return "completed"
        if progress.get("is_paused", False):
            return "paused"
        if progress.get("status"):
            return progress.get("status")
        if progress.get("error"):
            return "failed"
        return "running"

    if progress.get("status"):
        return progress["status"]
    if progress.get("error"):
        return "failed"
    return "pending"


async def merge_process_progress_async(
    session_store: SessionStore,
    session_id: str,
    job_type: ProcessJobType,
    updates: dict[str, Any],
) -> dict[str, Any]:
    """Aggiorna in modo merge-safe il payload di tracking del job."""
    session = await get_session_async(session_store, session_id)
    if not session:
        raise ValueError(f"Sessione {session_id} non trovata")

    progress = _get_progress(session, job_type)
    progress.update(updates)
    progress.setdefault("job_id", _build_job_id(session_id, job_type))
    progress.setdefault("job_type", job_type)
    progress.setdefault("attempt", 1)
    progress["updated_at"] = _now_iso()

    if job_type == "book":
        session.writing_progress = (session.writing_progress or {}) | progress | {"session_id": session_id}
        progress = session.writing_progress.copy()
    else:
        setattr(session, _PROCESS_FIELD_MAP[job_type], progress)

    progress["job_metrics"] = _build_job_metrics(session, job_type, progress)

    if job_type == "book":
        session.writing_progress = progress.copy()
    else:
        setattr(session, _PROCESS_FIELD_MAP[job_type], progress)

    await save_session_async(session_store, session)
    return progress


async def refresh_process_metrics_async(
    session_store: SessionStore,
    session_id: str,
    job_type: ProcessJobType,
) -> dict[str, Any]:
    """Ricalcola le metriche osservabili del job senza alterarne lo stato."""
    return await merge_process_progress_async(session_store, session_id, job_type, {})


async def begin_process_job_async(
    session_store: SessionStore,
    session_id: str,
    job_type: ProcessJobType,
    *,
    total_steps: int = 1,
    current_step: int = 0,
    current_section_name: str | None = None,
) -> tuple[bool, dict[str, Any]]:
    """Prepara un job per l'avvio, rendendo l'operazione idempotente."""
    session = await get_session_async(session_store, session_id)
    if not session:
        raise ValueError(f"Sessione {session_id} non trovata")

    existing = _get_progress(session, job_type)
    existing_status = derive_process_status(existing, job_type)
    if existing_status in _ACTIVE_STATUSES:
        logger.info(
            "Richiesta start idempotente: job già attivo",
            context={"session_id": session_id, "job_type": job_type, "status": existing_status},
        )
        return False, existing

    updates: dict[str, Any] = {
        "status": "pending",
        "error": None,
        "result": None,
        "recoverable": False,
        "error_count": 0,
        "attempt": int(existing.get("attempt", 0) or 0) + 1,
        "queued_at": _now_iso(),
        "started_at": None,
        "completed_at": None,
    }

    if job_type == "book":
        updates["current_step"] = current_step
        updates["total_steps"] = total_steps
        updates["current_section_name"] = current_section_name
        updates["is_paused"] = False
    else:
        updates["current_step"] = current_step
        updates["total_steps"] = total_steps
        updates["progress_percentage"] = 0.0

    progress = await merge_process_progress_async(session_store, session_id, job_type, updates)
    return True, progress


async def mark_process_running_async(
    session_store: SessionStore,
    session_id: str,
    job_type: ProcessJobType,
    **updates: Any,
) -> dict[str, Any]:
    """Segna il job come running."""
    updates.setdefault("status", "running")
    updates.setdefault("error", None)
    updates.setdefault("recoverable", False)
    updates.setdefault("started_at", _now_iso())
    return await merge_process_progress_async(session_store, session_id, job_type, updates)


async def mark_process_completed_async(
    session_store: SessionStore,
    session_id: str,
    job_type: ProcessJobType,
    **updates: Any,
) -> dict[str, Any]:
    """Segna il job come completato."""
    updates.setdefault("status", "completed")
    updates.setdefault("recoverable", False)
    updates.setdefault("completed_at", _now_iso())
    return await merge_process_progress_async(session_store, session_id, job_type, updates)


async def mark_process_failed_async(
    session_store: SessionStore,
    session_id: str,
    job_type: ProcessJobType,
    error: str,
    *,
    recoverable: bool = True,
    **updates: Any,
) -> dict[str, Any]:
    """Segna il job come fallito."""
    session = await get_session_async(session_store, session_id)
    current_progress = _get_progress(session, job_type) if session else {}
    updates.update(
        {
            "status": "failed",
            "error": error,
            "recoverable": recoverable,
            "completed_at": _now_iso(),
            "error_count": int(current_progress.get("error_count", 0) or 0) + 1,
        }
    )
    return await merge_process_progress_async(session_store, session_id, job_type, updates)


async def mark_process_paused_async(
    session_store: SessionStore,
    session_id: str,
    job_type: ProcessJobType,
    error: str,
    **updates: Any,
) -> dict[str, Any]:
    """Segna il job come pausato e recuperabile."""
    session = await get_session_async(session_store, session_id)
    current_progress = _get_progress(session, job_type) if session else {}
    updates.update(
        {
            "status": "paused",
            "error": error,
            "recoverable": True,
            "error_count": int(current_progress.get("error_count", 0) or 0) + 1,
        }
    )
    return await merge_process_progress_async(session_store, session_id, job_type, updates)


async def recover_interrupted_processes_async(session_store: SessionStore) -> int:
    """Converte i job in esecuzione al riavvio in stati recuperabili."""
    recovered = 0
    sessions = await get_all_sessions_async(session_store)

    for session in sessions.values():
        session_id = session.session_id

        for job_type in ("questions", "draft", "outline"):
            progress = _get_progress(session, job_type)
            status = derive_process_status(progress, job_type)
            if status not in _ACTIVE_STATUSES:
                continue

            await mark_process_failed_async(
                session_store,
                session_id,
                job_type,
                "Processo interrotto da un riavvio del server. Riprova.",
                recoverable=True,
            )
            recovered += 1

        book_progress = _get_progress(session, "book")
        book_status = derive_process_status(book_progress, "book")
        if book_status not in _ACTIVE_STATUSES:
            continue

        message = "Generazione interrotta da un riavvio del server. Puoi riprendere dal punto raggiunto."
        current_step = int(book_progress.get("current_step", 0) or 0)
        total_steps = int(book_progress.get("total_steps", 0) or 0) or max(1, current_step or 1)

        await update_writing_progress_async(
            session_store,
            session_id=session_id,
            current_step=current_step,
            total_steps=total_steps,
            current_section_name=book_progress.get("current_section_name"),
            is_complete=False,
            is_paused=True,
            error=message,
        )
        await mark_process_paused_async(
            session_store,
            session_id,
            "book",
            message,
        )
        recovered += 1

    return recovered

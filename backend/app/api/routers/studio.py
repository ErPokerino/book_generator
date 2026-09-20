"""Manuscript workspace: saved chapters, evidence, revisions and itemized usage."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.agent.session_store import get_session_store
from app.agent.writer.outline_ast import parse_outline_sections
from app.agent.narrative_memory import content_hash
from app.services.usage_service import usage_summary

router = APIRouter(prefix="/api/studio", tags=["studio"])


class ChapterEdit(BaseModel):
    content: str = Field(min_length=1, max_length=200_000)
    expected_hash: str = Field(min_length=64, max_length=64)


def _session(session_id):
    store = get_session_store()
    session = store.get_session(session_id)
    if not session or session.content_type != "book":
        raise HTTPException(404, "Progetto non trovato")
    return store, session


@router.get("/{session_id}")
async def get_studio(session_id: str):
    store, session = _session(session_id)
    chapters = [c | {"content_hash": content_hash(c["content"])} for c in session.book_chapters]
    try:
        sections = parse_outline_sections(session.current_outline) if session.current_outline else []
    except ValueError:
        sections = []
    jobs = store.list_jobs(session_id) if hasattr(store, "list_jobs") else []
    return {"session_id": session_id, "title": session.current_title or "Manoscritto senza titolo",
            "author": session.form_data.user_name, "status": session.get_status(), "updated_at": session.updated_at.isoformat(),
            "draft": session.current_draft, "validated": session.validated, "outline": session.current_outline,
            "sections": sections, "chapters": chapters, "progress": session.writing_progress,
            "memory": session.narrative_memory, "jobs": jobs,
            "costs": usage_summary(session, getattr(session, "_usage_events", []))}


@router.put("/{session_id}/chapters/{section_index}")
async def edit_chapter(session_id: str, section_index: int, request: ChapterEdit):
    store, _ = _session(session_id)
    if not request.content.strip():
        raise HTTPException(422, "Il capitolo non può essere vuoto")
    store.edit_chapter(session_id, section_index, request.content, request.expected_hash)
    return await get_studio(session_id)


@router.get("/{session_id}/chapters/{section_index}/revisions")
async def get_revisions(session_id: str, section_index: int):
    store, _ = _session(session_id)
    return store.chapter_revisions(session_id, section_index)


@router.get("/{session_id}/costs")
async def get_costs(session_id: str):
    _, session = _session(session_id)
    return usage_summary(session, getattr(session, "_usage_events", []))


@router.post("/{session_id}/pause")
async def pause_at_checkpoint(session_id: str):
    store, session = _session(session_id)
    progress = session.writing_progress or {}
    if progress.get("status") not in {"pending", "running"}:
        raise HTTPException(409, "La scrittura non è in corso")
    progress["pause_requested"] = True
    session.writing_progress = progress
    store.save_session(session)
    return {"message": "Pausa richiesta: il capitolo in corso sarà salvato prima di fermarsi."}


@router.post("/{session_id}/memory/rebuild")
async def rebuild_memory(session_id: str):
    from app.services.process_job_service import begin_process_job_async
    store, session = _session(session_id)
    if not session.book_chapters:
        raise HTTPException(409, "Non ci sono ancora capitoli da analizzare")
    started, progress = await begin_process_job_async(store, session_id, "memory")
    return {"started": started, "job_id": progress["job_id"]}

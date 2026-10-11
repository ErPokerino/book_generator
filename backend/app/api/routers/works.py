"""A single, paginated bookshelf over the compatible narrative and essay archives."""
import asyncio
import math
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Query, Request

from app.api.routers.library import get_library_endpoint
from app.llm.model_routing import resolve_generation_mode
from app.services.usage_service import usage_summary

router = APIRouter(prefix="/api/works", tags=["works"])
PROFILES = {"argumentative": "Argomentativo", "popular": "Divulgativo", "academic": "Accademico"}
STATUSES = {"planned": "outline", "pending": "writing", "running": "writing", "completed": "complete", "failed": "paused"}


@router.get("/analytics")
async def analytics(request: Request, content_type: Literal["book", "essay", "manga"] | None = None):
    from app.agent.session_store import get_session_store
    from app.services.studio_analytics import collect_metrics, summarize_metrics
    projects = await asyncio.to_thread(collect_metrics, get_session_store(), request.app.state.essay_api.state.store)
    if content_type:
        projects = [p for p in projects if p["content_type"] == content_type]
    return summarize_metrics(projects)


def essay_page_count(store, project):
    if not project.plan or not project.book_chapters or store.active(project.session_id):
        return None
    cache = getattr(store, "_library_pdf_pages", None)
    if cache is None:
        cache = store._library_pdf_pages = {}
    key = (project.session_id, project.updated_at, project.current_version)
    if key not in cache:
        from app.essay.exports import pdf_page_count
        try:
            pages = pdf_page_count(project)
        except (ValueError, OSError):
            return None
        if len(cache) >= 64:
            cache.pop(next(iter(cache)), None)
        cache[key] = pages
    return cache[key]


@router.get("")
async def works(request: Request, background_tasks: BackgroundTasks,
                content_type: Literal["book", "essay", "manga"] | None = None,
                status: str | None = None, mode: str | None = None,
                genre: str | None = None, search: str | None = None,
                sort_by: str = "created_at", sort_order: Literal["asc", "desc"] = "desc",
                skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=200)):
    narrative = await get_library_endpoint(background_tasks=background_tasks, skip=0, limit=2**31-1)
    entries = [item.model_dump(mode="json") for item in narrative.books]
    from app.agent.session_store import get_session_store
    from app.services.studio_analytics import project_metrics
    narrative_store = get_session_store()
    def narrative_metadata():
        from app.core.comics import COMIC_GENRES
        sessions = narrative_store.get_all_sessions()
        for entry in entries:
            session = sessions.get(entry["session_id"])
            if session:
                metrics = project_metrics(session, narrative_store, entry["content_type"])
                for key in ("word_count", "comic_format", "comic_genre", "active", "cost_coverage_complete"):
                    entry[key] = metrics[key]
                entry["estimated_cost"] = metrics["cost_eur"]
                if entry["content_type"] == "manga" and metrics["comic_genre"]:
                    entry["genre"] = COMIC_GENRES[metrics["comic_format"]].get(metrics["comic_genre"], entry.get("genre"))
    await asyncio.to_thread(narrative_metadata)
    store = request.app.state.essay_api.state.store

    def essay_entries():
        result = []
        for project in store.get_all_sessions().values():
            brief = project.form_data
            words = sum(len(chapter["content"].split()) for chapter in project.book_chapters)
            usage = usage_summary(project, store.usage_events(project.session_id))
            result.append({
                "session_id": project.session_id, "content_type": "essay",
                "title": brief.title or (project.plan or {}).get("title") or brief.topic,
                "author": brief.author_name, "llm_model": brief.llm_model,
                "genre": PROFILES[brief.profile], "essay_profile": brief.profile,
                "essay_topic": brief.topic, "word_count": words,
                "created_at": project.created_at, "updated_at": project.updated_at,
                "status": STATUSES.get(project.get_status(), project.get_status()),
                "total_chapters": len((project.plan or {}).get("sections", [])),
                "completed_chapters": len(project.book_chapters), "total_pages": math.ceil(words / 250),
                "essay_pdf_pages": essay_page_count(store, project),
                "estimated_cost": usage["converted_cost_eur"],
                "cost_coverage_complete": usage["coverage_complete"] and not any(event.get("tool_cost_unknown") for event in usage["events"]), "active": store.active(project.session_id),
                "cover_url": f"/api/saggistica/essays/{project.session_id}/cover?v={project.current_version}" if project.cover_image_path else None,
            })
        return result

    entries.extend(await asyncio.to_thread(essay_entries))
    if content_type:
        entries = [entry for entry in entries if entry["content_type"] == content_type]
    if status and status != "all":
        entries = [entry for entry in entries if entry["status"] == status]
    if genre and genre != "all":
        entries = [entry for entry in entries if entry.get("genre") == genre]
    if mode and mode != "all":
        # Standard/Ultra are narrative generation modes, independent of essay profiles.
        entries = [entry for entry in entries if entry["content_type"] != "essay" and
                   resolve_generation_mode(model_name=entry["llm_model"]) == mode.lower()]
    if search:
        query = search.casefold().strip()
        entries = [entry for entry in entries if query in " ".join(str(entry.get(key) or "") for key in
                   ("title", "author", "genre", "essay_topic")).casefold()]
    key = {"cost": "estimated_cost", "score": "critique_score"}.get(sort_by, sort_by)
    if key not in {"title", "created_at", "updated_at", "estimated_cost", "critique_score", "total_pages"}:
        key = "created_at"
    known = [entry for entry in entries if entry.get(key) is not None]
    missing = [entry for entry in entries if entry.get(key) is None]
    known.sort(key=lambda entry: entry[key].casefold() if key == "title" else entry[key], reverse=sort_order == "desc")
    entries = known + missing
    return {"books": entries[skip:skip+limit], "total": len(entries), "has_more": skip+limit < len(entries)}

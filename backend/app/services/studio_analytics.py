"""Comparable production metrics, with usage evidence kept separate from estimates."""
from collections import Counter

from app.services.usage_service import usage_summary

TYPE_LABELS = {"book": "Narrativa", "essay": "Saggi", "manga": "Fumetti"}
STATUS_MAP = {"planned": "outline", "pending": "writing", "running": "writing", "completed": "complete", "failed": "paused"}


def project_metrics(session, store, kind):
    events = store.usage_events(session.session_id)
    usage = usage_summary(session, events)
    active = any(job["status"] in {"pending", "running"} for job in store.list_jobs(session.session_id))
    comic_data = getattr(session, "manga_form_data", None) or {}
    chapters = session.book_chapters or []
    words = sum(len(ch.get("content", "").split()) for ch in chapters) if kind != "manga" else 0
    title = (session.form_data.title or (session.plan or {}).get("title") or session.form_data.topic) if kind == "essay" else session.current_title or comic_data.get("title") or "Opera senza titolo"
    return {
        "session_id": session.session_id, "content_type": kind, "title": title,
        "status": STATUS_MAP.get(session.get_status(), session.get_status()), "active": active,
        "created_at": session.created_at.isoformat() if hasattr(session.created_at, "isoformat") else session.created_at,
        "updated_at": session.updated_at.isoformat() if hasattr(session.updated_at, "isoformat") else session.updated_at,
        "word_count": words, "chapters": len(chapters),
        "completed_pages": sum(page.get("status", "completed") == "completed" for page in (getattr(session, "manga_pages", None) or [])),
        "comic_format": comic_data.get("comic_format", "manga") if kind == "manga" else None,
        "comic_genre": comic_data.get("comic_genre"),
        "cost_eur": usage["converted_cost_eur"],
        "cost_coverage_complete": usage["coverage_complete"] and not any(e.get("tool_cost_unknown") for e in events),
        "events": events,
    }


def collect_metrics(narrative_store, essay_store):
    result = []
    for session in narrative_store.get_all_sessions().values():
        result.append(project_metrics(session, narrative_store, getattr(session, "content_type", "book")))
    for session in essay_store.get_all_sessions().values():
        result.append(project_metrics(session, essay_store, "essay"))
    return result


def summarize_metrics(projects):
    costs = [p["cost_eur"] for p in projects if p["cost_eur"] is not None]
    statuses = Counter(p["status"] for p in projects)
    types = []
    for kind, label in TYPE_LABELS.items():
        subset = [p for p in projects if p["content_type"] == kind]
        values = [p["cost_eur"] for p in subset if p["cost_eur"] is not None]
        types.append({"type": kind, "label": label, "works": len(subset),
                      "completed": sum(p["status"] == "complete" for p in subset),
                      "words": sum(p["word_count"] for p in subset),
                      "chapters": sum(p["chapters"] for p in subset),
                      "pages": sum(p["completed_pages"] for p in subset),
                      "cost_eur": sum(values) if values else None})
    months = Counter(p["created_at"][:7] for p in projects)
    phases, models = {}, {}
    for p in projects:
        for e in p["events"]:
            cost = e.get("cost_usd")
            eur = cost * e["usd_to_eur"] if cost is not None else None
            for groups, key in ((phases, e["phase"]), (models, e["model"])):
                row = groups.setdefault(key, {"name": key, "calls": 0, "measured_calls": 0, "unknown_calls": 0,
                                              "cost_eur": None, "input_tokens": 0, "output_tokens": 0})
                row["calls"] += 1
                row["unknown_calls"] += cost is None or bool(e.get("tool_cost_unknown"))
                if eur is not None:
                    row["measured_calls"] += 1
                    row["cost_eur"] = (row["cost_eur"] or 0) + eur
                usage = e.get("usage") or {}
                row["input_tokens"] += usage.get("input_tokens", 0)
                row["output_tokens"] += usage.get("output_tokens", 0)
    return {
        "total": len(projects), "completed": statuses["complete"],
        "active": sum(p["active"] for p in projects), "paused": statuses["paused"],
        "drafts": statuses["draft"] + statuses["outline"], "statuses": dict(statuses),
        "words": sum(p["word_count"] for p in projects),
        "comic_pages": sum(p["completed_pages"] for p in projects),
        "comic_formats": dict(Counter(p["comic_format"] for p in projects if p["content_type"] == "manga")),
        "cost_eur": sum(costs) if costs else None,
        "cost_complete_works": sum(p["cost_coverage_complete"] for p in projects),
        "cost_partial_works": sum(not p["cost_coverage_complete"] for p in projects),
        "types": types, "months": [{"month": m, "works": months[m]} for m in sorted(months)],
        "phases": sorted(phases.values(), key=lambda r: -(r["cost_eur"] or 0)),
        "models": sorted(models.values(), key=lambda r: -(r["cost_eur"] or 0)),
        "recent": [{k:v for k,v in p.items() if k != "events"} for p in sorted(projects, key=lambda p:p["updated_at"], reverse=True)[:6]],
    }

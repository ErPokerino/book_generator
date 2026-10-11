"""Read-only planning estimates; never generate content or record provider usage."""
from datetime import datetime
import math
from statistics import median

from app.core.config import get_app_config, get_exchange_rate_usd_to_eur
from app.essay.settings import settings, stage_model
from app.services.usage_service import pricing_snapshot


def essay_estimate(brief, store):
    config = settings()["estimation"]
    pages = math.ceil(brief.target_words / 250)
    sections = max(2, math.ceil(brief.target_words / config["words_per_section"]))
    parts_per_section = math.ceil(brief.target_words / sections / config["words_per_part"])
    parts = sections * parts_per_section
    tokens = brief.target_words * config["tokens_per_word"]
    reviewed = brief.revision_mode == "reviewed"
    writing_input = parts * config["context_tokens"] + tokens * (parts_per_section - 1) / 2
    calls = [("questions", 1200, 800), ("plan", 3500, 3500), ("chapters", writing_input, tokens)]
    if reviewed:
        calls.append(("review", tokens + sections * config["context_tokens"], sections * 1200))
    costs = []
    for phase, incoming, outgoing in calls:
        pricing = pricing_snapshot(stage_model(brief, phase))
        if pricing is None:
            costs = None
            break
        rates = pricing["rates"]
        costs.append((incoming * rates["input"] + outgoing * rates["output"]) / 1_000_000)
    # Resolution is provider-selected: an AI cover remains an explicitly additional cost.
    cost = sum(costs) * get_exchange_rate_usd_to_eur() if costs is not None else None
    time_config = get_app_config().get("time_estimation", {})
    times = time_config.get("fallback_by_model", {})
    def seconds(phase):
        return times.get(stage_model(brief, phase), time_config.get("fallback_seconds_per_chapter", 45))
    duration = (seconds("questions") + seconds("plan") + parts * seconds("chapters")
                + (sections * seconds("review") if reviewed else 0)) / 60
    # Only uninterrupted completed runs provide trustworthy writing durations.
    samples = []
    for session in store.get_all_sessions().values():
        progress = session.writing_progress or {}
        if progress.get("status") != "completed" or progress.get("attempt") != 1:
            continue
        jobs = [job for job in store.list_jobs(session.session_id) if job["kind"] == "book"]
        if len(jobs) > 1 or any(job["attempt"] > 1 for job in jobs):
            continue  # A lease recovery can reset started_at without a new UI attempt.
        old = session.form_data
        if old.revision_mode != brief.revision_mode or any(
            stage_model(old, phase) != stage_model(brief, phase) for phase in ("chapters", "review")
        ):
            continue
        words = sum(len(ch["content"].split()) for ch in session.book_chapters)
        try:
            start = datetime.fromisoformat(progress["started_at"])
            end = datetime.fromisoformat(progress["completed_at"])
            elapsed = (end - start).total_seconds()
        except (KeyError, TypeError, ValueError):
            continue
        if words > 0 and elapsed > 0:
            samples.append(elapsed / words)
    historical = len(samples) >= 3
    if historical:
        duration = (median(samples) * brief.target_words + seconds("questions") + seconds("plan")) / 60
    return {"pages": pages, "sections": sections, "parts": parts,
            "cost_eur": cost, "cost_low_eur": cost * .65 if cost is not None else None,
            "cost_high_eur": cost * 1.6 if cost is not None else None,
            "minutes": max(1, round(duration)), "time_basis": "history" if historical else "configuration",
            "time_samples": len(samples), "cover_extra": brief.cover_style != "typographic",
            "basis": "planning_token_budget", "words_per_page": 250}

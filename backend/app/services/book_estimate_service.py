"""Forecast manuscript size from completed books, keeping writing modes separate."""
import math
from statistics import median

from app.core.config import get_app_config
from app.llm.model_routing import resolve_generation_mode

CHAPTER_TARGETS = {"breve": 6, "media": 12, "lunga": 20}
MIN_COHORT = 3


def estimate_book_sizes(sessions, *, model: str, length: str | None = None):
    samples = []
    for session in sessions:
        progress = session.writing_progress or {}
        chapters = session.book_chapters or []
        if session.content_type != "book" or not progress.get("is_complete") or not chapters:
            continue
        if sorted(c["section_index"] for c in chapters) != list(range(len(chapters))):
            continue
        if progress.get("total_steps", len(chapters)) != len(chapters):
            continue
        counts = [len(c.get("content", "").split()) for c in chapters]
        if not all(counts):
            continue
        form = session.form_data
        mode = resolve_generation_mode(form_data=form)
        # Prefer actual recorded chapter models; don't remap historic model aliases
        # to today's replacements and falsely claim they are comparable samples.
        measured_models = {e["model"] for e in getattr(session, "_usage_events", [])
                           if e.get("phase") == "chapter-generation" and e.get("status") == "measured"}
        historic_model = next(iter(measured_models)) if len(measured_models) == 1 else (
            "mixed" if measured_models else (form.model_overrides or {}).get("chapters")
            or (form.model_overrides or {}).get("text") or form.llm_model)
        samples.append({"mode": mode, "model": historic_model, "length": form.length,
                        "chapters": len(chapters), "words_per_chapter": sum(counts) / len(chapters)})

    words_per_page = max(1, int(get_app_config().get("validation", {}).get("words_per_page", 250)))
    result = {}
    for mode in ("standard", "ultra"):
        cohort = [s for s in samples if s["mode"] == mode]
        mode_count = len(cohort)
        same_model = [s for s in cohort if s["model"] == model]
        scope = "mode"
        if len(same_model) >= MIN_COHORT:
            cohort, scope = same_model, "mode_model"
        same_length = [s for s in cohort if s["length"] == length] if length else []
        if len(same_length) >= MIN_COHORT:
            cohort, scope = same_length, scope + "_length"
        if not cohort:
            result[mode] = {"available": False, "sample_count": 0, "mode_sample_count": 0,
                            "scope": "mode", "words_per_page": words_per_page}
            continue
        chapter_count = CHAPTER_TARGETS.get(length) or max(1, round(median(s["chapters"] for s in cohort)))
        densities = sorted(s["words_per_chapter"] for s in cohort)
        # Each book gets one vote; a long book must not dominate the forecast.
        def quantile(p):
            position = p * (len(densities)-1)
            low, high = math.floor(position), math.ceil(position)
            return densities[low] + (densities[high]-densities[low]) * (position-low)
        low = quantile(.2) if len(cohort) >= 5 else min(densities)
        high = quantile(.8) if len(cohort) >= 5 else max(densities)
        pages = lambda density: max(1, math.ceil(chapter_count * density / words_per_page))
        result[mode] = {"available": True, "sample_count": len(cohort), "mode_sample_count": mode_count,
                        "scope": scope, "chapters": chapter_count, "pages": pages(median(densities)),
                        "pages_low": pages(low), "pages_high": pages(high),
                        "words": round(chapter_count * median(densities)), "words_per_page": words_per_page,
                        "chapter_basis": "requested_length" if length else "history",
                        "limited_history": len(cohort) < MIN_COHORT}
    return result

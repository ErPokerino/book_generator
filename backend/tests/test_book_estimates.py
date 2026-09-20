from types import SimpleNamespace
import pytest
from app.models import SubmissionRequest
from app.services.book_estimate_service import estimate_book_sizes


def book(mode, words, *, chapters=4, model="flash", length=None, complete=True):
    return SimpleNamespace(content_type="book", writing_progress={"is_complete": complete, "total_steps": chapters},
        form_data=SubmissionRequest(plot="Trama", llm_model=model, generation_mode=mode, length=length),
        book_chapters=[{"section_index": i, "content": "parola " * words} for i in range(chapters)])


def test_modes_use_their_own_observed_lengths():
    sizes = estimate_book_sizes([book("standard", 500), book("ultra", 1500)], model="flash")
    assert sizes["ultra"]["pages"] == sizes["standard"]["pages"] * 3
    assert sizes["standard"]["chapters"] == 4


def test_no_other_mode_or_fixed_page_fallback():
    sizes = estimate_book_sizes([book("standard", 500)], model="flash")
    assert not sizes["ultra"]["available"]
    assert "pages" not in sizes["ultra"]
    assert not estimate_book_sizes([], model="flash")["standard"]["available"]


def test_incomplete_empty_manga_and_gapped_books_are_excluded():
    manga = book("standard", 500)
    manga.content_type = "manga"
    gap = book("standard", 500)
    gap.book_chapters[1]["section_index"] = 7
    sessions = [manga, gap, book("standard", 500, complete=False), book("standard", 0)]
    assert not estimate_book_sizes(sessions, model="flash")["standard"]["available"]


def test_requested_length_scales_chapters_from_observed_density():
    history = [book("standard", 500)]
    short = estimate_book_sizes(history, model="flash", length="breve")["standard"]
    long = estimate_book_sizes(history, model="flash", length="lunga")["standard"]
    assert short["chapters"] == 6 and long["chapters"] == 20
    assert long["pages"] / short["pages"] == pytest.approx(20/6)
    assert short["limited_history"]


def test_model_cohort_and_robust_per_book_median():
    history = [book("standard", 500, model="lite") for _ in range(3)]
    history += [book("standard", 5000, model="flash", chapters=50)]
    result = estimate_book_sizes(history, model="lite")["standard"]
    assert result["sample_count"] == 3 and result["scope"] == "mode_model"
    assert result["pages"] == 8
    assert estimate_book_sizes(history, model="unknown")["standard"]["pages"] == 8

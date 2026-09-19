import pytest

from app.agent.question_generator import (
    build_default_questions,
    form_is_rich_enough_to_skip_llm,
    generate_questions,
)
from app.models import SubmissionRequest


@pytest.fixture
def rich_form(submission_request: SubmissionRequest) -> SubmissionRequest:
    return submission_request.model_copy(
        update={
            "genre": "fantasy",
            "subgenre": "epico",
            "style": "lirico",
            "theme": "identità",
            "target_audience": "adulti",
            "protagonist": "Ada",
            "character_arc": "crescita",
            "point_of_view": "terza limitata",
        }
    )


def test_sparse_form_is_not_rich(submission_request: SubmissionRequest) -> None:
    assert form_is_rich_enough_to_skip_llm(submission_request) is False


def test_rich_form_skips_llm_and_returns_fixed_questions(rich_form: SubmissionRequest) -> None:
    assert form_is_rich_enough_to_skip_llm(rich_form) is True

    questions = build_default_questions(rich_form)
    asked = " ".join(item.text.lower() for item in questions)
    assert 2 <= len(questions) <= 4
    assert "secondar" in asked or "antagonist" in asked or "relazione" in asked


@pytest.mark.asyncio
async def test_generate_questions_on_rich_form_does_not_call_model(
    rich_form: SubmissionRequest,
    monkeypatch,
) -> None:
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("Il form ricco non deve chiamare il modello")

    monkeypatch.setattr(
        "app.agent.question_generator.build_google_chat_model",
        fail_if_called,
    )

    response, token_usage = await generate_questions(rich_form)

    assert response.success is True
    assert len(response.questions) >= 2
    assert token_usage["input_tokens"] == 0
    assert token_usage["output_tokens"] == 0

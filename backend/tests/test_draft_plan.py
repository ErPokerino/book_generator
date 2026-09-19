from app.agent.outline_generator import generate_outline
from app.llm.contracts import DraftGenerationPayload, OutlineSectionPayload
from app.models import QuestionAnswer, SubmissionRequest
import pytest


def test_draft_payload_includes_outline_sections() -> None:
    payload = DraftGenerationPayload(
        title="La Città delle Maree",
        character_profiles="**Ada** | Ruolo: protagonista",
        draft_text="Ada scopre il sabotaggio delle chiuse.",
        sections=[
            OutlineSectionPayload(
                title="Capitolo 1: Le chiuse",
                description="Ada nota il ritmo irregolare.",
                level=3,
            )
        ],
    )

    assert payload.sections[0].title.startswith("Capitolo 1")


@pytest.mark.asyncio
async def test_generate_outline_reuses_existing_plan(
    submission_request: SubmissionRequest,
    monkeypatch,
) -> None:
    stored = "## Capitolo 1\n- Apertura."

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("L'outline già prodotto col piano non deve richiedere un'altra chiamata")

    monkeypatch.setattr(
        "app.agent.outline_generator.build_google_chat_model",
        fail_if_called,
    )

    outline_text, token_usage = await generate_outline(
        form_data=submission_request,
        question_answers=[QuestionAnswer(question_id="tono", answer="Malinconico")],
        validated_draft="Bozza",
        session_id="s1",
        draft_title="Titolo",
        existing_outline=stored,
    )

    assert outline_text == stored
    assert token_usage["input_tokens"] == 0

from app.agent.cover_generator import build_cover_prompt
from app.models import SubmissionRequest


def test_cover_prompt_uses_logline_not_full_draft(submission_request: SubmissionRequest) -> None:
    long_draft = (
        "Ada conta le sirene all'alba e capisce che le chiuse mentono. " * 80
        + "A mezzanotte trova la prova del sabotaggio e lascia la città."
    )
    form = submission_request.model_copy(
        update={"genre": "fantasy", "theme": "identità", "style": "lirico"}
    )

    prompt = build_cover_prompt(
        title="La Città delle Maree",
        author="Ada",
        plot=long_draft,
        form_data=form,
        cover_style="simbolico",
    )

    assert "La Città delle Maree" in prompt
    assert "Ada" in prompt
    assert "fantasy" in prompt.lower() or "Fantasy" in prompt
    assert long_draft not in prompt
    assert len(prompt) < 1800
    assert "sabotaggio" in prompt or "chiuse" in prompt

import pytest

from app.agent.session_store import SessionStore
from app.models import SubmissionRequest


@pytest.fixture
def submission_request() -> SubmissionRequest:
    return SubmissionRequest(
        llm_model="gemini-2.0-flash",
        plot="Una detective deve risolvere un mistero in una città sospesa nel tempo.",
        author="NarrAI",
    )


@pytest.fixture
def session_store(submission_request: SubmissionRequest) -> SessionStore:
    store = SessionStore()
    store.create_session("session-1", submission_request, [])
    return store

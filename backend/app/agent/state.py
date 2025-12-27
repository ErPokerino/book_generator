from typing import TypedDict, Optional
from app.models import SubmissionRequest, Question, QuestionAnswer


class AgentState(TypedDict):
    """Stato per il flusso LangGraph."""
    form_data: SubmissionRequest
    context: str
    questions: list[Question]
    answers: list[QuestionAnswer]
    session_id: str


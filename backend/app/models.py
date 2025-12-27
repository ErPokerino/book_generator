from typing import Literal, Optional
from pydantic import BaseModel, Field


class FieldOption(BaseModel):
    value: str
    label: Optional[str] = None


class FieldConfig(BaseModel):
    id: str
    label: str
    type: Literal["select", "text"]
    required: bool = False
    options: Optional[list[FieldOption]] = None
    placeholder: Optional[str] = None
    description: Optional[str] = None


class ConfigResponse(BaseModel):
    llm_models: list[str]
    fields: list[FieldConfig]


class SubmissionRequest(BaseModel):
    llm_model: str
    plot: str = Field(..., min_length=1, description="Trama del romanzo (obbligatoria)")
    genre: Optional[str] = None
    subgenre: Optional[str] = None
    theme: Optional[str] = None
    protagonist: Optional[str] = None
    character_arc: Optional[str] = None
    point_of_view: Optional[str] = None
    narrative_voice: Optional[str] = None
    style: Optional[str] = None
    temporal_structure: Optional[str] = None
    pace: Optional[str] = None
    realism: Optional[str] = None
    ambiguity: Optional[str] = None
    intentionality: Optional[str] = None
    author: Optional[str] = None
    user_name: Optional[str] = None


class SubmissionResponse(BaseModel):
    success: bool
    message: str
    data: Optional[SubmissionRequest] = None


# Modelli per le domande preliminari
class Question(BaseModel):
    id: str
    text: str
    type: Literal["text", "multiple_choice"]
    options: Optional[list[str]] = None


class QuestionsResponse(BaseModel):
    success: bool
    session_id: str
    questions: list[Question]
    message: Optional[str] = None


class QuestionAnswer(BaseModel):
    question_id: str
    answer: Optional[str] = None  # None se la domanda è stata saltata


class AnswersRequest(BaseModel):
    session_id: str
    answers: list[QuestionAnswer]


class AnswersResponse(BaseModel):
    success: bool
    message: str
    session_id: str


class QuestionGenerationRequest(BaseModel):
    form_data: SubmissionRequest


# Modelli per la bozza estesa
class DraftGenerationRequest(BaseModel):
    form_data: SubmissionRequest
    question_answers: list[QuestionAnswer]
    session_id: str


class DraftResponse(BaseModel):
    success: bool
    session_id: str
    draft_text: str
    title: Optional[str] = None
    version: int
    message: Optional[str] = None


class DraftModificationRequest(BaseModel):
    session_id: str
    user_feedback: str
    current_version: int


class DraftValidationRequest(BaseModel):
    session_id: str
    validated: bool


class DraftValidationResponse(BaseModel):
    success: bool
    session_id: str
    message: str


# Modelli per la struttura/indice
class OutlineGenerateRequest(BaseModel):
    session_id: str


class OutlineResponse(BaseModel):
    success: bool
    session_id: str
    outline_text: str
    version: int
    message: Optional[str] = None


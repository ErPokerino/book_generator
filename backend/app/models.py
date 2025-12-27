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


class SubmissionResponse(BaseModel):
    success: bool
    message: str
    data: Optional[SubmissionRequest] = None


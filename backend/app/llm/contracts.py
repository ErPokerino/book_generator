"""Contratti tipizzati per gli stadi LLM non-prosa."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

class GeneratedQuestionPayload(BaseModel):
    """Domanda generata dal modello prima della normalizzazione applicativa."""

    id: str = Field(default="", description="Identificativo stabile della domanda.")
    text: str = Field(min_length=1, description="Testo della domanda in italiano.")
    type: Literal["text", "multiple_choice"] = Field(
        default="text",
        description="Tipo domanda. Usa `text` o `multiple_choice`.",
    )
    options: list[str] | None = Field(
        default=None,
        description="Opzioni se la domanda è a scelta multipla.",
    )

    @model_validator(mode="after")
    def _validate_multiple_choice_options(self) -> "GeneratedQuestionPayload":
        if self.type == "multiple_choice" and not self.options:
            raise ValueError("Le domande multiple_choice devono includere almeno un'opzione.")
        return self


class QuestionsPayload(BaseModel):
    """Output strutturato della fase domande."""

    questions: list[GeneratedQuestionPayload] = Field(
        default_factory=list,
        description="Lista di domande opzionali generate per chiarire il progetto narrativo.",
    )


class DraftGenerationPayload(BaseModel):
    """Output strutturato della fase bozza."""

    title: str = Field(min_length=1, description="Titolo del romanzo.")
    character_profiles: str = Field(
        default="",
        description="Schede sintetiche dei personaggi principali e secondari rilevanti.",
    )
    draft_text: str = Field(
        min_length=1,
        description="Bozza estesa della trama, completa e coerente con le istruzioni.",
    )


class OutlineSectionPayload(BaseModel):
    """Nodo tipizzato dell'outline prima del rendering markdown."""

    title: str = Field(min_length=1, description="Titolo della sezione o del capitolo.")
    description: str = Field(
        min_length=1,
        description="Descrizione dettagliata della sezione, pronta per essere resa in markdown.",
    )
    level: int = Field(
        default=2,
        ge=2,
        le=6,
        description="Livello markdown della sezione (2 per capitolo diretto, 3+ per capitoli annidati).",
    )


class OutlineGenerationPayload(BaseModel):
    """Output strutturato della fase outline."""

    sections: list[OutlineSectionPayload] = Field(
        min_length=1,
        description="Sezioni ordinate del romanzo, già pronte per il rendering in markdown.",
    )


class ChapterReviewPayload(BaseModel):
    """Output JSON del reviewer capitolo."""

    needs_revision: bool = Field(
        default=False,
        description="True se il capitolo deve essere rivisto prima del salvataggio.",
    )
    issues: list[str] = Field(
        default_factory=list,
        description="Problemi concreti che richiedono revisione editoriale.",
    )
    preserve: list[str] = Field(
        default_factory=list,
        description="Elementi del capitolo da preservare nella revisione.",
    )

    @field_validator("issues", "preserve", mode="before")
    @classmethod
    def _normalize_points(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            return [
                line.lstrip("-•* ").strip()
                for line in value.splitlines()
                if line.strip()
            ]
        coerced = str(value).strip()
        return [coerced] if coerced else []

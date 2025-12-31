from typing import Literal, Optional, Any, Dict
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


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
    target_audience: Optional[str] = None
    theme: Optional[str] = None
    protagonist: Optional[str] = None
    protagonist_archetype: Optional[str] = None
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
    cover_style: Optional[str] = None


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


class OutlineSection(BaseModel):
    """Sezione dell'outline (capitolo)."""
    title: str
    description: str
    level: int
    section_index: int


class OutlineUpdateRequest(BaseModel):
    """Richiesta per aggiornare l'outline con sezioni modificate."""
    session_id: str
    sections: list[OutlineSection]


# Modelli per la scrittura del romanzo
class Chapter(BaseModel):
    """Rappresenta un singolo capitolo/sezione del romanzo."""
    title: str
    content: str
    section_index: int  # Indice nella struttura (0-based)
    page_count: int = 0  # Numero di pagine calcolato (parole/250 arrotondato per eccesso)


class LiteraryCritique(BaseModel):
    """Valutazione critica del libro."""
    score: float = Field(ge=0.0, le=10.0, description="Valutazione da 0 a 10")
    pros: list[str] = Field(default_factory=list, description="Punti di forza del libro")
    cons: list[str] = Field(default_factory=list, description="Punti di debolezza del libro")
    summary: str = Field(description="Sintesi della valutazione (max 500 caratteri)")

    @field_validator("pros", "cons", mode="before")
    @classmethod
    def _coerce_points(cls, v: Any) -> list[str]:
        """
        Accetta sia lista che stringa (retro-compatibilità) e normalizza a list[str].
        """
        if v is None:
            return []
        if isinstance(v, list):
            out: list[str] = []
            for item in v:
                if item is None:
                    continue
                s = str(item).strip()
                if s:
                    out.append(s)
            return out
        if isinstance(v, str):
            # Split su newline e rimuovi bullet comuni
            lines = [ln.strip() for ln in v.splitlines()]
            cleaned: list[str] = []
            for ln in lines:
                ln = ln.lstrip("-•* ").strip()
                if ln:
                    cleaned.append(ln)
            # Se è una stringa singola senza newline
            if not cleaned and v.strip():
                cleaned = [v.strip()]
            return cleaned
        # Fallback: coercizione a stringa
        s = str(v).strip()
        return [s] if s else []


class BookProgress(BaseModel):
    """Stato di avanzamento della scrittura del romanzo."""
    session_id: str
    current_step: int  # Indice del capitolo corrente in scrittura (0-based)
    total_steps: int  # Numero totale di sezioni da scrivere
    current_section_name: Optional[str] = None  # Nome/titolo della sezione in corso
    completed_chapters: list[Chapter] = []  # Capitoli già completati
    is_complete: bool = False
    is_paused: bool = False  # Indica se la generazione è in pausa (dopo errori)
    error: Optional[str] = None
    total_pages: Optional[int] = None  # Numero totale di pagine (calcolato quando is_complete=True)
    writing_time_minutes: Optional[float] = None  # Tempo di scrittura in minuti (solo generazione capitoli)
    critique: Optional["LiteraryCritique"] = None  # Valutazione critica del libro
    critique_status: Optional[Literal["pending", "running", "completed", "failed"]] = None
    critique_error: Optional[str] = None
    estimated_time_minutes: Optional[float] = None  # Stima tempo rimanente in minuti
    estimated_time_confidence: Optional[Literal["high", "medium", "low"]] = None  # Affidabilità della stima


class BookGenerationRequest(BaseModel):
    """Richiesta per avviare la generazione del romanzo."""
    session_id: str


class BookGenerationResponse(BaseModel):
    """Risposta all'avvio della generazione."""
    success: bool
    session_id: str
    message: str


class BookResponse(BaseModel):
    """Risposta con il libro completo."""
    title: str
    author: str
    chapters: list[Chapter]
    total_pages: Optional[int] = None  # Numero totale di pagine
    writing_time_minutes: Optional[float] = None  # Tempo di scrittura in minuti (solo generazione capitoli)
    critique: Optional["LiteraryCritique"] = None  # Valutazione critica del libro
    critique_status: Optional[Literal["pending", "running", "completed", "failed"]] = None
    critique_error: Optional[str] = None


# Modelli per la libreria personale
class LibraryEntry(BaseModel):
    """Entry singola nella libreria."""
    session_id: str
    title: str
    author: str
    llm_model: str
    genre: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    status: Literal["draft", "outline", "writing", "paused", "complete"]
    total_chapters: int
    completed_chapters: int
    total_pages: Optional[int] = None
    critique_score: Optional[float] = None
    critique_status: Optional[str] = None
    pdf_path: Optional[str] = None
    pdf_filename: Optional[str] = None
    cover_image_path: Optional[str] = None
    writing_time_minutes: Optional[float] = None


class LibraryStats(BaseModel):
    """Statistiche aggregate della libreria."""
    total_books: int
    completed_books: int
    in_progress_books: int
    average_score: Optional[float] = None
    average_pages: float
    average_writing_time_minutes: float
    books_by_model: Dict[str, int] = Field(default_factory=dict)
    books_by_genre: Dict[str, int] = Field(default_factory=dict)
    score_distribution: Dict[str, int] = Field(default_factory=dict)  # es: {"0-2": 1, "2-4": 3, "4-6": 5, "6-8": 2, "8-10": 1}
    average_score_by_model: Dict[str, float] = Field(default_factory=dict)


class LibraryResponse(BaseModel):
    """Risposta con lista libri della libreria."""
    books: list[LibraryEntry]
    total: int
    stats: Optional[LibraryStats] = None


class PdfEntry(BaseModel):
    """Entry per un PDF disponibile."""
    filename: str
    session_id: Optional[str] = None  # Session ID se collegato a una sessione
    title: Optional[str] = None
    author: Optional[str] = None
    created_date: Optional[datetime] = None
    size_bytes: Optional[int] = None


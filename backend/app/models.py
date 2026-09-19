from typing import Literal, Optional, Any, Dict
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, ConfigDict, model_validator


class FieldOption(BaseModel):
    value: str
    label: Optional[str] = None


class FieldConfig(BaseModel):
    model_config = ConfigDict(exclude_none=False)
    
    id: str
    label: str
    type: Literal["select", "text"]
    required: bool = False
    options: Optional[list[FieldOption]] = None
    placeholder: Optional[str] = None
    description: Optional[str] = None


class ConfigResponse(BaseModel):
    model_config = ConfigDict(exclude_none=False)
    
    llm_models: list[str]
    fields: list[FieldConfig]


class SubmissionRequest(BaseModel):
    llm_model: str
    generation_mode: Literal["standard", "ultra"] = "standard"
    model_overrides: Optional[Dict[str, str]] = None
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

    @field_validator("generation_mode", mode="before")
    @classmethod
    def _coerce_generation_mode(cls, value: Any) -> str:
        if value is None or str(value).strip() == "":
            return "standard"
        normalized = str(value).strip().lower()
        if normalized == "ultra":
            return "ultra"
        return "standard"

    @model_validator(mode="after")
    def _legacy_ultra_alias(self) -> "SubmissionRequest":
        if self.generation_mode == "standard" and "ultra" in (self.llm_model or "").lower():
            self.generation_mode = "ultra"
        return self


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


class DraftManualUpdateRequest(BaseModel):
    session_id: str
    draft_text: str
    title: Optional[str] = None
    current_version: int


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
    status: Optional[Literal["pending", "running", "paused", "completed", "failed", "cancelled"]] = None
    job_id: Optional[str] = None
    job_type: Optional[str] = None
    recoverable: bool = False
    attempt: Optional[int] = None
    updated_at: Optional[datetime] = None
    queued_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    job_metrics: Optional[Dict[str, Any]] = None
    current_step: int  # Indice del capitolo corrente in scrittura (0-based)
    total_steps: int  # Numero totale di sezioni da scrivere
    current_section_name: Optional[str] = None  # Nome/titolo della sezione in corso
    completed_chapters: list[Chapter] = []  # Capitoli già completati
    is_complete: bool = False
    is_paused: bool = False  # Indica se la generazione è in pausa (dopo errori)
    error: Optional[str] = None
    total_pages: Optional[int] = None  # Numero totale di pagine (calcolato quando is_complete=True)
    writing_time_minutes: Optional[float] = None  # Tempo di scrittura in minuti (solo generazione capitoli)
    estimated_cost: Optional[float] = None  # Costo stimato in EUR
    critique: Optional["LiteraryCritique"] = None  # Valutazione critica del libro
    critique_status: Optional[Literal["pending", "running", "completed", "failed"]] = None
    critique_error: Optional[str] = None
    estimated_time_minutes: Optional[float] = None  # Stima tempo rimanente in minuti
    estimated_time_confidence: Optional[Literal["high", "medium", "low"]] = None  # Affidabilità della stima


class BookGenerationRequest(BaseModel):
    """Richiesta per avviare la generazione del romanzo."""
    session_id: str


class MangaCharacterInput(BaseModel):
    """Personaggio principale descritto dall'utente per il manga beta."""
    name: str = Field(..., min_length=1, description="Nome del personaggio")
    description: str = Field(..., min_length=1, description="Descrizione sintetica del personaggio")


class MangaCreateRequest(BaseModel):
    """Richiesta per avviare la generazione del manga beta."""
    title: Optional[str] = Field(None, min_length=1, description="Titolo opzionale del manga")
    plot: str = Field(..., min_length=1, description="Trama di partenza del mini manga")
    manga_type: Literal["shonen", "shojo", "seinen", "josei", "kodomo"]
    model_overrides: Optional[Dict[str, str]] = Field(
        None,
        description="Override modelli per fase: text, image, manga_planning, manga_pages, manga_cover, manga_back_cover",
    )
    main_characters: list[MangaCharacterInput] = Field(
        default_factory=list,
        description="Personaggi principali descritti dall'utente",
    )
    page_color_mode: Literal["black_and_white", "color"] = Field(
        "black_and_white",
        description="Modalita cromatica delle pagine interne del manga",
    )
    page_count: Optional[int] = Field(
        None,
        ge=10,
        le=100,
        description="Numero esatto di pagine desiderato",
    )
    min_pages: int = Field(10, ge=10, le=100, description="Numero minimo di pagine desiderato")
    max_pages: int = Field(10, ge=10, le=100, description="Numero massimo di pagine desiderato")

    @model_validator(mode="after")
    def validate_page_range(self) -> "MangaCreateRequest":
        if self.page_count is not None:
            self.min_pages = self.page_count
            self.max_pages = self.page_count
            return self

        if self.min_pages > self.max_pages:
            raise ValueError("min_pages non puo essere maggiore di max_pages")

        if self.min_pages == self.max_pages:
            self.page_count = self.min_pages
        return self


class MangaCharacterProfile(BaseModel):
    """Scheda personaggio generata nella fase di planning del manga."""
    name: str
    role: Optional[str] = None
    appearance: str
    personality: str
    notes: str


class MangaPagePlan(BaseModel):
    """Piano testuale di una singola pagina manga."""
    page_number: int = Field(ge=1, description="Numero pagina 1-indexed")
    title: str
    narrative_goal: str
    scene_description: str
    dialogue: list[str] = Field(default_factory=list)
    visual_notes: list[str] = Field(default_factory=list)
    continuity_notes: list[str] = Field(default_factory=list)
    summary: str


class MangaPlan(BaseModel):
    """Storyboard completo del mini manga generato dal modello testuale."""
    title: str
    synopsis: str
    tone: str
    style_guide: list[str] = Field(default_factory=list)
    character_profiles: list[MangaCharacterProfile] = Field(default_factory=list)
    page_plans: list[MangaPagePlan] = Field(default_factory=list)


class MangaPageArtifact(BaseModel):
    """Pagina manga generata e persistita."""
    page_number: int = Field(ge=1)
    title: str
    summary: str
    dialogue: list[str] = Field(default_factory=list)
    image_path: Optional[str] = None
    image_url: Optional[str] = None
    prompt_excerpt: Optional[str] = None
    status: Literal["pending", "completed", "failed"] = "completed"


class MangaProgress(BaseModel):
    """Stato di avanzamento della generazione del manga beta."""
    session_id: str
    status: Optional[Literal["pending", "running", "paused", "completed", "failed", "cancelled"]] = None
    job_id: Optional[str] = None
    job_type: Optional[str] = None
    recoverable: bool = False
    attempt: Optional[int] = None
    updated_at: Optional[datetime] = None
    queued_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    job_metrics: Optional[Dict[str, Any]] = None
    requested_min_pages: Optional[int] = None
    requested_max_pages: Optional[int] = None
    planned_total_pages: Optional[int] = None
    current_step: int = 0  # numero di pagine completate
    total_steps: int = 0
    current_phase: Optional[
        Literal["planning", "generating_cover", "generating_pages", "generating_back_cover", "completed"]
    ] = None
    current_page_number: Optional[int] = None
    current_page_title: Optional[str] = None
    completed_pages: list[MangaPageArtifact] = Field(default_factory=list)
    is_complete: bool = False
    is_paused: bool = False
    error: Optional[str] = None
    estimated_cost: Optional[float] = None
    current_cost_eur: Optional[float] = None
    cost_breakdown: Optional[Dict[str, Any]] = None


class MangaGenerationResponse(BaseModel):
    """Risposta all'avvio o alla ripresa della generazione manga."""
    success: bool
    session_id: str
    message: str
    job_id: Optional[str] = None
    job_type: Optional[str] = None
    already_running: bool = False


class MangaReaderResponse(BaseModel):
    """Payload completo del reader manga beta."""
    session_id: str
    title: str
    manga_type: Literal["shonen", "shojo", "seinen", "josei", "kodomo"]
    page_color_mode: Literal["black_and_white", "color"] = "black_and_white"
    requested_min_pages: Optional[int] = None
    requested_max_pages: Optional[int] = None
    planned_total_pages: Optional[int] = None
    synopsis: str
    characters: list[MangaCharacterProfile] = Field(default_factory=list)
    cover_image_url: Optional[str] = None
    back_cover_image_url: Optional[str] = None
    pages: list[MangaPageArtifact] = Field(default_factory=list)
    is_complete: bool = False
    total_pages: int = 0


class SessionRestoreResponse(BaseModel):
    """Risposta per ripristinare lo stato di una sessione."""
    session_id: str
    form_data: SubmissionRequest
    content_type: Literal["book", "manga"] = "book"
    questions: Optional[list[Question]] = None
    question_answers: list[QuestionAnswer] = Field(default_factory=list)
    draft: Optional[DraftResponse] = None
    outline: Optional[str] = None
    writing_progress: Optional["BookProgress"] = None
    manga_form_data: Optional["MangaCreateRequest"] = None
    manga_progress: Optional["MangaProgress"] = None
    manga: Optional["MangaReaderResponse"] = None
    current_step: Literal["questions", "draft", "summary", "writing", "manga"]


class BookGenerationResponse(BaseModel):
    """Risposta all'avvio della generazione."""
    success: bool
    session_id: str
    message: str
    job_id: Optional[str] = None
    job_type: Optional[str] = None
    already_running: bool = False


class ProcessProgress(BaseModel):
    """Stato di avanzamento di un processo AI."""
    status: Literal["pending", "running", "paused", "completed", "failed", "cancelled"]
    job_id: Optional[str] = None
    job_type: Optional[str] = None
    recoverable: bool = False
    attempt: Optional[int] = None
    updated_at: Optional[datetime] = None
    queued_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    job_metrics: Optional[Dict[str, Any]] = None
    current_step: Optional[int] = None
    total_steps: Optional[int] = None
    progress_percentage: Optional[float] = None
    estimated_time_seconds: Optional[float] = None
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None  # QuestionsResponse, DraftResponse, OutlineResponse


class ProcessStartResponse(BaseModel):
    """Risposta all'avvio di un processo in background."""
    success: bool
    session_id: str
    message: str
    job_id: Optional[str] = None
    job_type: Optional[str] = None
    already_running: bool = False


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
    content_type: Literal["book", "manga"] = "book"
    title: str
    author: str
    llm_model: str
    genre: Optional[str] = None
    manga_type: Optional[Literal["shonen", "shojo", "seinen", "josei", "kodomo"]] = None
    created_at: datetime
    updated_at: datetime
    status: Literal["draft", "outline", "writing", "paused", "complete"]
    total_chapters: int
    completed_chapters: int
    completed_pages: Optional[int] = None
    total_pages: Optional[int] = None
    critique_score: Optional[float] = None
    critique_status: Optional[str] = None
    pdf_path: Optional[str] = None  # Path locale
    pdf_filename: Optional[str] = None
    pdf_url: Optional[str] = None  # Path API locale per accesso PDF
    cover_image_path: Optional[str] = None  # Path locale
    cover_url: Optional[str] = None  # Path API locale per accesso copertina
    writing_time_minutes: Optional[float] = None
    estimated_cost: Optional[float] = None  # Costo stimato in EUR


class UserBookCount(BaseModel):
    """Conteggio libri per utente."""
    user_id: str
    name: str
    email: str
    books_count: int
    created_at: Optional[datetime] = None


class UsersStats(BaseModel):
    """Statistiche utenti per admin."""
    total_users: int
    users_with_books: list[UserBookCount]


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
    average_writing_time_by_model: Dict[str, float] = Field(default_factory=dict)  # Tempo medio libro per modello (minuti)
    average_time_per_page_by_model: Dict[str, float] = Field(default_factory=dict)  # Tempo medio per pagina per modello (minuti)
    average_pages_by_model: Dict[str, float] = Field(default_factory=dict)  # Pagine medie per modello
    average_cost_by_model: Dict[str, float] = Field(default_factory=dict)  # Costo medio per libro per modello (EUR)
    average_cost_per_page_by_model: Dict[str, float] = Field(default_factory=dict)  # Costo medio per pagina per modello (EUR)


class ModelComparisonEntry(BaseModel):
    """Entry per confronto dettagliato modelli."""
    model: str
    total_books: int
    completed_books: int
    average_score: Optional[float] = None
    average_pages: float = 0.0
    average_cost: Optional[float] = None  # Costo medio per libro in EUR
    average_writing_time: float = 0.0
    average_time_per_page: float = 0.0
    score_range: Dict[str, int] = Field(default_factory=dict)  # Distribuzione voti {"0-2": 1, "2-4": 2, etc}


class AdvancedStats(BaseModel):
    """Statistiche avanzate con analisi temporali e confronto modelli."""
    books_over_time: Dict[str, int] = Field(default_factory=dict)  # date (YYYY-MM-DD) -> count
    score_trend_over_time: Dict[str, float] = Field(default_factory=dict)  # date (YYYY-MM-DD) -> voto medio
    model_comparison: list[ModelComparisonEntry] = Field(default_factory=list)


class LibraryResponse(BaseModel):
    """Risposta con lista libri della libreria."""
    books: list[LibraryEntry]
    total: int
    has_more: bool = False  # Indica se ci sono altri libri da caricare
    stats: Optional[LibraryStats] = None


class PdfEntry(BaseModel):
    """Entry per un PDF disponibile."""
    filename: str
    session_id: Optional[str] = None  # Session ID se collegato a una sessione
    title: Optional[str] = None
    author: Optional[str] = None
    created_date: Optional[datetime] = None
    size_bytes: Optional[int] = None



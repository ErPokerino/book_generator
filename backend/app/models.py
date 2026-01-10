from typing import Literal, Optional, Any, Dict
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, ConfigDict


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
    mode_availability: Optional[Dict[str, int]] = None


class ConfigResponse(BaseModel):
    model_config = ConfigDict(exclude_none=False)
    
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
    estimated_cost: Optional[float] = None  # Costo stimato in EUR
    critique: Optional["LiteraryCritique"] = None  # Valutazione critica del libro
    critique_status: Optional[Literal["pending", "running", "completed", "failed"]] = None
    critique_error: Optional[str] = None
    estimated_time_minutes: Optional[float] = None  # Stima tempo rimanente in minuti
    estimated_time_confidence: Optional[Literal["high", "medium", "low"]] = None  # Affidabilità della stima


class BookGenerationRequest(BaseModel):
    """Richiesta per avviare la generazione del romanzo."""
    session_id: str


class SessionRestoreResponse(BaseModel):
    """Risposta per ripristinare lo stato di una sessione."""
    session_id: str
    form_data: SubmissionRequest
    questions: Optional[list[Question]] = None
    question_answers: list[QuestionAnswer] = Field(default_factory=list)
    draft: Optional[DraftResponse] = None
    outline: Optional[str] = None
    writing_progress: Optional["BookProgress"] = None
    current_step: Literal["questions", "draft", "summary", "writing"]


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
    pdf_path: Optional[str] = None  # Path GCS (gs://bucket/path) o path locale
    pdf_filename: Optional[str] = None
    pdf_url: Optional[str] = None  # URL firmato temporaneo per accesso PDF
    cover_image_path: Optional[str] = None  # Path GCS (gs://bucket/path) o path locale
    cover_url: Optional[str] = None  # URL firmato temporaneo per accesso copertina
    writing_time_minutes: Optional[float] = None
    estimated_cost: Optional[float] = None  # Costo stimato in EUR
    is_shared: bool = False  # True se è un libro condiviso (per destinatario)
    shared_by_id: Optional[str] = None  # ID utente che ha condiviso (per destinatario)
    shared_by_name: Optional[str] = None  # Nome utente che ha condiviso (per destinatario)


class UserBookCount(BaseModel):
    """Conteggio libri per utente."""
    user_id: str
    name: str
    email: str
    books_count: int


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


# Modelli per autenticazione utente
class User(BaseModel):
    """Modello per utente del sistema."""
    id: str  # UUID
    email: str  # unique
    password_hash: str
    name: str
    role: Literal["user", "admin"] = "user"
    is_active: bool = True
    is_verified: bool = False  # Email verificata
    created_at: datetime
    updated_at: datetime
    password_reset_token: Optional[str] = None
    password_reset_expires: Optional[datetime] = None
    verification_token: Optional[str] = None
    verification_expires: Optional[datetime] = None


class UserResponse(BaseModel):
    """Risposta con dati utente (senza password)."""
    id: str
    email: str
    name: str
    role: Literal["user", "admin"]
    is_active: bool
    is_verified: bool = False
    created_at: datetime


class RegisterRequest(BaseModel):
    """Richiesta registrazione nuovo utente."""
    email: str = Field(..., min_length=1)
    password: str = Field(..., min_length=8)
    name: str = Field(..., min_length=1)
    ref_token: Optional[str] = Field(None, description="Token referral opzionale per tracking inviti")


class LoginRequest(BaseModel):
    """Richiesta login."""
    email: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class ForgotPasswordRequest(BaseModel):
    """Richiesta reset password."""
    email: str = Field(..., min_length=1)


class ResetPasswordRequest(BaseModel):
    """Richiesta reset password con token."""
    token: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8)


# Modelli per le notifiche
class Notification(BaseModel):
    """Modello per una notifica."""
    id: str  # UUID
    user_id: str  # destinatario
    type: Literal["connection_request", "connection_accepted", "book_shared", "book_share_accepted", "system"]
    title: str
    message: str
    data: Optional[Dict[str, Any]] = None  # dati extra (es: from_user_id, book_id)
    is_read: bool = False
    created_at: datetime


class NotificationResponse(BaseModel):
    """Risposta con lista notifiche."""
    notifications: list[Notification]
    unread_count: int
    total: int
    has_more: bool = False


# Modelli per le connessioni tra utenti
class Connection(BaseModel):
    """Modello per una connessione tra utenti."""
    id: str  # UUID
    from_user_id: str  # Chi invia la richiesta
    to_user_id: str  # Chi riceve la richiesta
    status: Literal["pending", "accepted"]
    created_at: datetime
    updated_at: datetime
    from_user_name: Optional[str] = None  # Nome utente mittente (per frontend)
    to_user_name: Optional[str] = None  # Nome utente destinatario (per frontend)
    from_user_email: Optional[str] = None  # Email utente mittente (per frontend)
    to_user_email: Optional[str] = None  # Email utente destinatario (per frontend)


class ConnectionRequest(BaseModel):
    """Richiesta invio connessione."""
    email: str = Field(..., min_length=1, description="Email dell'utente da connettere")


class ConnectionResponse(BaseModel):
    """Risposta con lista connessioni."""
    connections: list[Connection]
    total: int
    has_more: bool = False


class UserSearchResponse(BaseModel):
    """Risposta ricerca utente."""
    found: bool
    user: Optional["UserResponse"] = None
    is_connected: bool = False
    has_pending_request: bool = False
    pending_request_from_me: bool = False
    connection_id: Optional[str] = None  # ID della connessione se esiste


# Modelli per condivisione libri
class BookShare(BaseModel):
    """Modello per una condivisione di libro."""
    id: str  # UUID
    book_session_id: str  # ID sessione libro condiviso
    owner_id: str  # Proprietario originale
    recipient_id: str  # Destinatario
    status: Literal["pending", "accepted", "declined"]
    created_at: datetime
    updated_at: datetime
    owner_name: Optional[str] = None  # Nome proprietario (per frontend)
    recipient_name: Optional[str] = None  # Nome destinatario (per frontend)
    book_title: Optional[str] = None  # Titolo libro (per frontend)


class BookShareRequest(BaseModel):
    """Richiesta condivisione libro."""
    recipient_email: str = Field(..., min_length=1, description="Email del destinatario")


class BookShareResponse(BaseModel):
    """Risposta con lista condivisioni."""
    shares: list[BookShare]
    total: int
    has_more: bool = False


class BookShareActionRequest(BaseModel):
    """Richiesta azione su condivisione (accept/decline)."""
    action: Literal["accept", "decline"]


# Modelli per sistema referral (inviti esterni)
class Referral(BaseModel):
    """Modello per un referral/invito esterno."""
    id: str  # UUID
    referrer_id: str  # Chi ha invitato (ID utente)
    invited_email: str  # Email invitato (lowercase)
    status: Literal["pending", "registered", "expired"]  # Stato invito
    token: str  # Token univoco per tracking
    created_at: datetime
    registered_at: Optional[datetime] = None  # Quando si è registrato
    invited_user_id: Optional[str] = None  # ID utente dopo registrazione
    referrer_name: Optional[str] = None  # Nome di chi ha invitato (per frontend)


class ReferralRequest(BaseModel):
    """Richiesta invio referral."""
    email: str = Field(..., min_length=1, description="Email del destinatario da invitare")


class ReferralStats(BaseModel):
    """Statistiche referral per utente."""
    total_sent: int  # Inviti inviati
    total_registered: int  # Utenti registrati tramite invito
    pending: int  # Inviti in attesa


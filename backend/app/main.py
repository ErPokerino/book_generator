import os
import sys
from pathlib import Path
from typing import Optional, Literal, List
from io import BytesIO
from datetime import datetime
from collections import defaultdict
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image, PageTemplate, BaseDocTemplate
from reportlab.platypus.frames import Frame
from reportlab.platypus.flowables import HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib import colors
from PIL import Image as PILImage
import markdown
import base64
import math
from xhtml2pdf import pisa
from pathlib import Path as PathLib
from app.core.config import (
    get_config, reload_config, get_app_config,
    get_tokens_per_page, get_model_pricing, get_image_generation_cost,
    get_cost_currency, get_exchange_rate_usd_to_eur, get_token_estimates
)
from app.api.routers import config as config_router, submission, questions, draft, outline, auth, notifications, connections, book_shares, referrals, book, library, critique, session, admin, health, files
from app.middleware.auth import get_current_user, get_current_user_optional, require_admin
from app.models import (
    ConfigResponse,
    SubmissionRequest,
    SubmissionResponse,
    OutlineUpdateRequest,
    QuestionGenerationRequest,
    QuestionsResponse,
    QuestionAnswer,
    AnswersRequest,
    AnswersResponse,
    DraftGenerationRequest,
    DraftResponse,
    DraftModificationRequest,
    DraftValidationRequest,
    DraftValidationResponse,
    OutlineGenerateRequest,
    OutlineResponse,
    ProcessProgress,
    ProcessStartResponse,
    OutlineUpdateRequest,
    BookGenerationRequest,
    BookGenerationResponse,
    BookProgress,
    SessionRestoreResponse,
    BookResponse,
    Chapter,
    LiteraryCritique,
    UsersStats,
    LibraryEntry,
    LibraryStats,
    LibraryResponse,
    PdfEntry,
    AdvancedStats,
    UsersStats,
    UserBookCount,
    ModelComparisonEntry,
)
from app.agent.question_generator import generate_questions
from app.agent.draft_generator import generate_draft
from app.agent.outline_generator import generate_outline
from app.agent.writer_generator import generate_full_book, parse_outline_sections, resume_book_generation, regenerate_outline_markdown
from app.agent.cover_generator import generate_book_cover
from app.agent.literary_critic import generate_literary_critique_from_pdf
from app.agent.session_store import get_session_store, FileSessionStore
from app.agent.session_store_helpers import (
    get_session_async, update_writing_progress_async, update_critique_async, 
    update_critique_status_async, update_writing_times_async, update_cover_image_path_async,
    set_estimated_cost_async, delete_session_async, update_questions_progress_async,
    update_draft_progress_async, update_outline_progress_async, save_generated_questions_async,
    update_draft_async, update_outline_async, create_session_async
)
from app.services.pdf_service import generate_complete_book_pdf
from app.services.export_service import generate_epub, generate_docx
from app.services.storage_service import get_storage_service


def get_model_abbreviation(model_name: str) -> str:
    """
    Converte il nome completo del modello in una versione abbreviata per il nome del PDF.
    
    Args:
        model_name: Nome completo del modello (es: "gemini-2.5-flash", "gemini-3-pro-preview")
    
    Returns:
        Abbreviazione del modello (es: "g25f", "g3p")
    """
    model_lower = model_name.lower()
    if "gemini-2.5-flash" in model_lower:
        return "g25f"
    elif "gemini-2.5-pro" in model_lower:
        return "g25p"
    elif "gemini-3-flash" in model_lower:
        return "g3f"
    elif "gemini-3-pro" in model_lower:
        return "g3p"
    else:
        # Fallback: usa le prime lettere del modello
        return model_name.replace("gemini-", "g").replace("-", "").replace("_", "")[:6]


def llm_model_to_mode(model_name: Optional[str]) -> str:
    """
    Converte il nome del modello LLM in modalità (Flash, Pro, Ultra).
    
    Args:
        model_name: Nome del modello (es: "gemini-2.5-flash", "gemini-3-pro", "gemini-3-ultra")
    
    Returns:
        Modalità corrispondente: "Flash", "Pro", "Ultra", o "Sconosciuto"
    """
    if not model_name:
        return "Sconosciuto"
    
    model_lower = model_name.lower()
    if "ultra" in model_lower:
        return "Ultra"
    elif "flash" in model_lower:
        return "Flash"
    elif "pro" in model_lower:
        return "Pro"
    else:
        return "Sconosciuto"


def mode_to_llm_models(mode: str) -> List[str]:
    """
    Converte una modalità in lista di modelli LLM corrispondenti.
    
    Args:
        mode: Modalità ("Flash", "Pro", "Ultra")
    
    Returns:
        Lista di nomi di modelli che appartengono a quella modalità
    """
    mode_lower = mode.lower()
    if mode_lower == "flash":
        return ["gemini-2.5-flash", "gemini-3-flash"]
    elif mode_lower == "pro":
        return ["gemini-2.5-pro", "gemini-3-pro"]
    elif mode_lower == "ultra":
        return ["gemini-3-ultra"]
    else:
        return []


# Carica variabili d'ambiente dal file .env
# Il file .env è nella root del progetto (un livello sopra backend)
# Path(__file__) = backend/app/main.py
# parent = backend/app
# parent.parent = backend
# parent.parent.parent = root del progetto
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Carica anche dalla directory corrente come fallback
load_dotenv()

app = FastAPI(title="Scrittura Libro API", version="0.1.0")

# Cache in memoria per statistiche (TTL: 30 secondi)
_stats_cache = {}
_stats_cache_ttl = 30  # secondi

def get_cached_stats(cache_key: str):
    """Recupera statistiche dalla cache se valide."""
    if cache_key in _stats_cache:
        data, timestamp = _stats_cache[cache_key]
        if (datetime.now() - timestamp).total_seconds() < _stats_cache_ttl:
            return data
        else:
            # Cache scaduta, rimuovi
            del _stats_cache[cache_key]
    return None

def set_cached_stats(cache_key: str, data):
    """Salva statistiche nella cache."""
    _stats_cache[cache_key] = (data, datetime.now())

# CORS per sviluppo locale e produzione
frontend_url = os.getenv("FRONTEND_URL", "")
cors_origins = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:3000",
]
if frontend_url:
    cors_origins.append(frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(config_router.router)
app.include_router(submission.router)
app.include_router(questions.router)
app.include_router(draft.router)
app.include_router(outline.router)
app.include_router(auth.router)
app.include_router(notifications.router)
app.include_router(connections.router)
app.include_router(book_shares.router)
app.include_router(referrals.router)
app.include_router(book.router)
app.include_router(library.router)
app.include_router(critique.router)
app.include_router(session.router)
app.include_router(admin.router)
app.include_router(health.router)
app.include_router(files.router)


# ============================================================================
# Constants
# ============================================================================

# Campi MongoDB necessari per creare LibraryEntry (ottimizzazione performance)
# ESCLUSI per performance:
# - current_draft: può essere molto grande (migliaia di righe)
# - book_chapters: contiene il testo completo di tutti i capitoli
# - current_outline: può essere grande
# Invece, usiamo total_pages e completed_chapters_count pre-calcolati in writing_progress
LIBRARY_ENTRY_FIELDS = [
    "_id",
    "user_id",
    "session_id",
    "current_title",
    "form_data",
    "question_answers",  # Necessario per SessionData.from_dict()
    "created_at",
    "updated_at",
    # book_chapters RIMOSSO - troppo pesante, usa writing_progress.total_pages
    "writing_progress",
    # current_outline RIMOSSO - usa writing_progress.total_steps per conteggio sezioni
    "literary_critique",
    "cover_image_path",
    "writing_start_time",
    "writing_end_time",
    "critique_status",
]


# Lifecycle hooks per MongoDB
@app.on_event("startup")
async def startup_db():
    """Connette al database MongoDB all'avvio se configurato."""
    try:
        session_store = get_session_store()
        if hasattr(session_store, 'connect'):
            await session_store.connect()
            print("[STARTUP] MongoDB (sessions) connesso con successo")
        
        # Inizializza anche UserStore
        from app.agent.user_store import get_user_store
        user_store = get_user_store()
        await user_store.connect()
        print("[STARTUP] MongoDB (users) connesso con successo")

        # Inizializza anche NotificationStore
        from app.agent.notification_store import get_notification_store
        notification_store = get_notification_store()
        await notification_store.connect()
        print("[STARTUP] MongoDB (notifications) connesso con successo")

        # Inizializza anche ConnectionStore
        from app.agent.connection_store import get_connection_store
        connection_store = get_connection_store()
        await connection_store.connect()
        print("[STARTUP] MongoDB (connections) connesso con successo")
        
        # Inizializza anche BookShareStore
        from app.agent.book_share_store import get_book_share_store
        book_share_store = get_book_share_store()
        await book_share_store.connect()
        print("[STARTUP] MongoDB (book_shares) connesso con successo")
        
        # Inizializza anche ReferralStore
        from app.agent.referral_store import get_referral_store
        referral_store = get_referral_store()
        await referral_store.connect()
        print("[STARTUP] MongoDB (referrals) connesso con successo")
    except Exception as e:
        print(f"[STARTUP] Avviso: MongoDB non disponibile: {e}")


@app.on_event("shutdown")
async def shutdown_db():
    """Chiude la connessione MongoDB allo shutdown."""
    try:
        session_store = get_session_store()
        if hasattr(session_store, 'disconnect'):
            await session_store.disconnect()
            print("[SHUTDOWN] MongoDB (sessions) disconnesso")
        
        # Chiudi anche UserStore
        from app.agent.user_store import get_user_store
        user_store = get_user_store()
        await user_store.disconnect()
        print("[SHUTDOWN] MongoDB (users) disconnesso")
        
        # Chiudi anche NotificationStore
        from app.agent.notification_store import get_notification_store
        notification_store = get_notification_store()
        await notification_store.disconnect()
        print("[SHUTDOWN] MongoDB (notifications) disconnesso")
        
        # Chiudi anche ConnectionStore
        from app.agent.connection_store import get_connection_store
        connection_store = get_connection_store()
        await connection_store.disconnect()
        print("[SHUTDOWN] MongoDB (connections) disconnesso")
        
        # Chiudi anche BookShareStore
        from app.agent.book_share_store import get_book_share_store
        book_share_store = get_book_share_store()
        await book_share_store.disconnect()
        print("[SHUTDOWN] MongoDB (book_shares) disconnesso")
        
        # Chiudi anche ReferralStore
        from app.agent.referral_store import get_referral_store
        referral_store = get_referral_store()
        await referral_store.disconnect()
        print("[SHUTDOWN] MongoDB (referrals) disconnesso")
    except Exception as e:
        print(f"[SHUTDOWN] Errore nella disconnessione MongoDB: {e}")


# NOTE: Gli endpoint sono stati spostati nei router:
# - /api/config -> app/api/routers/config.py
# - /api/submissions -> app/api/routers/submission.py
# - /api/questions -> app/api/routers/questions.py
# - /api/draft -> app/api/routers/draft.py
# - /api/outline -> app/api/routers/outline.py

# NOTE: Gli endpoint /api/questions/* sono stati spostati in app/api/routers/questions.py
# Endpoint questions, draft progress, outline start, PDF legacy e files migrati ai rispettivi router

# Endpoint questions migrati in app/api/routers/questions.py
# Endpoint draft progress migrati in app/api/routers/draft.py  
# Endpoint outline start migrati in app/api/routers/outline.py
# Endpoint PDF legacy: rimosso (ora disponibile in /api/book/pdf/{session_id})
# Endpoint files migrati in app/api/routers/files.py
# Background functions migrati in app/services/generation_service.py


# Endpoint critique migrati in app/api/routers/critique.py


# Endpoint health migrati in app/api/routers/health.py


# Background functions migrati in app/services/generation_service.py


# Endpoint questions migrati in app/api/routers/questions.py
# Rimossi endpoint duplicati: /api/questions/generate/start, /api/questions/progress/{session_id}


# Endpoint draft progress migrati in app/api/routers/draft.py
# Rimossi endpoint duplicati: /api/draft/progress/{session_id}


# Endpoint outline start migrati in app/api/routers/outline.py
# Rimossi endpoint duplicati: /api/outline/generate/start


# Endpoint PDF legacy: rimosso (ora disponibile in /api/book/pdf/{session_id})
# Rimossi endpoint duplicati: /api/pdf/{session_id}


# Endpoint files migrati in app/api/routers/files.py
# Rimossi endpoint duplicati: /api/files/{tipo}/{filename}


# Le seguenti funzioni sono ancora necessarie per backward compatibility o sono usate da altri endpoint
# Non rimuovere: session_to_library_entry, calculate_library_stats, calculate_advanced_stats, scan_pdf_directory


# Helper functions e utility (mantenute in main.py per ora)
class NumberedCanvas:
    """Classe per aggiungere header e footer con numerazione pagine."""
    def __init__(self, canvas, doc, book_title, book_author):
        self.canvas = canvas
        self.doc = doc
        self.book_title = book_title
        self.book_author = book_author
        
    def draw_header_footer(self):
        """Disegna header e footer su ogni pagina."""
        canvas = self.canvas
        page_num = canvas.getPageNumber()
        
        # Salva lo stato corrente
        canvas.saveState()
        
        # Header - linea sottile in alto
        canvas.setStrokeColor(colors.grey)
        canvas.setLineWidth(0.5)
        canvas.line(2*cm, A4[1] - 1.5*cm, A4[0] - 2*cm, A4[1] - 1.5*cm)
        
        # Footer - linea sottile in basso e numero pagina
        canvas.line(2*cm, 1.5*cm, A4[0] - 2*cm, 1.5*cm)
        
        # Numero pagina centrato in basso
        canvas.setFont("Helvetica", 9)
        canvas.setFillColor(colors.grey)
        canvas.drawCentredString(A4[0] / 2.0, 1*cm, str(page_num))
        
        # Ripristina lo stato
        canvas.restoreState()

def escape_html(text: str) -> str:
    """Escapa caratteri speciali per HTML."""
    if not text:
        return ""
    return (text.replace("&", "&amp;")
              .replace("<", "&lt;")
              .replace(">", "&gt;")
              .replace('"', "&quot;")
              .replace("'", "&#39;"))

def markdown_to_html(text: str) -> str:
    """Converte markdown base a HTML."""
    if not text:
        return ""
    # Usa la libreria markdown per conversione completa
    html = markdown.markdown(text, extensions=['nl2br', 'fenced_code'])
    return html

def calculate_page_count(content: str) -> int:
    """Calcola il numero di pagine basato sul contenuto (parole/250 arrotondato per eccesso)."""
    if not content:
        return 0
    try:
        app_config = get_app_config()
        words_per_page = app_config.get("validation", {}).get("words_per_page", 250)
        
        # Conta le parole dividendo per spazi
        words = content.split()
        word_count = len(words)
        # Calcola pagine: parole/words_per_page arrotondato per eccesso
        page_count = math.ceil(word_count / words_per_page)
        return max(1, page_count)  # Almeno 1 pagina
    except Exception as e:
        print(f"[CALCULATE_PAGE_COUNT] Errore nel calcolo pagine: {e}")
        return 0


def get_generation_method(model_name: str) -> str:
    """
    Determina il metodo di generazione in base al modello.
    
    Args:
        model_name: Nome del modello (es. "gemini-3-ultra", "gemini-3-flash")
    
    Returns:
        'flash', 'pro', 'ultra', o 'default'
    """
    if not model_name:
        return "default"
    model_lower = model_name.lower()
    if "ultra" in model_lower:
        return "ultra"
    elif "pro" in model_lower:
        return "pro"
    elif "flash" in model_lower:
        return "flash"
    return "default"


def estimate_linear_params_from_history(sessions: list, method: str) -> Optional[tuple[float, float]]:
    """
    Stima i parametri a e b del modello lineare t(i) = a*i + b dai dati storici.
    
    Args:
        sessions: Lista di sessioni con chapter_timings
        method: Metodo di generazione ('flash', 'pro', 'ultra')
    
    Returns:
        Tupla (a, b) o None se non ci sono abbastanza dati
    """
    # Raccogli tutti i punti (indice_capitolo, tempo_misurato)
    data_points = []
    
    for session in sessions:
        if not session.chapter_timings or len(session.chapter_timings) == 0:
            continue
        
        # Verifica che il metodo della sessione corrisponda
        session_method = get_generation_method(session.form_data.llm_model if session.form_data else None)
        if session_method != method:
            continue
        
        # Aggiungi coppie (indice_capitolo, tempo)
        for idx, timing in enumerate(session.chapter_timings, start=1):
            data_points.append((idx, timing))
    
    if len(data_points) < 2:
        # Serve almeno 2 punti per regressione lineare
        return None
    
    # Regressione lineare: y = ax + b
    # Formula minimi quadrati:
    # a = (n*Σ(xy) - Σ(x)*Σ(y)) / (n*Σ(x²) - (Σ(x))²)
    # b = (Σ(y) - a*Σ(x)) / n
    
    n = len(data_points)
    sum_x = sum(x for x, y in data_points)
    sum_y = sum(y for x, y in data_points)
    sum_xy = sum(x * y for x, y in data_points)
    sum_x2 = sum(x * x for x, y in data_points)
    
    denominator = n * sum_x2 - sum_x * sum_x
    if abs(denominator) < 1e-10:  # Evita divisione per zero
        return None
    
    a = (n * sum_xy - sum_x * sum_y) / denominator
    b = (sum_y - a * sum_x) / n
    
    # Verifica che i parametri siano ragionevoli
    if a < 0 or b < 0:
        return None
    
    return (a, b)


def get_linear_params_for_method(method: str, app_config: dict) -> tuple[float, float]:
    """
    Ottiene i parametri a e b per un metodo di generazione.
    
    Priorità:
    1. Configurazione esplicita
    2. Valori default dalla configurazione
    
    Args:
        method: Metodo di generazione ('flash', 'pro', 'ultra')
        app_config: Configurazione dell'app
    
    Returns:
        Tupla (a, b) sempre valida
    """
    time_config = app_config.get("time_estimation", {})
    linear_params = time_config.get("linear_model_params", {})
    
    # 1. Prova configurazione esplicita
    if method in linear_params:
        method_params = linear_params[method]
        a = method_params.get("a")
        b = method_params.get("b")
        if a is not None and b is not None and a >= 0 and b >= 0:
            return (a, b)
    
    # 2. Usa valori default
    default_params = linear_params.get("default", {})
    a = default_params.get("a", 1.1)
    b = default_params.get("b", 44.3)
    return (a, b)


def calculate_residual_time_linear(k: int, N: int, a: float, b: float) -> float:
    """
    Calcola tempo residuo usando formula chiusa del modello lineare.
    
    Formula: T_res(k, N) = a * ((N(N+1) - (k-1)k) / 2) + b * (N - k + 1)
    
    Args:
        k: Primo capitolo ancora da processare (1-indexed)
        N: Ultimo capitolo (totale)
        a: Parametro moltiplicatore (s/capitolo)
        b: Parametro tempo base (s)
    
    Returns:
        Tempo residuo in secondi
    """
    if k > N or k < 1:
        return 0.0
    
    # Formula chiusa: a * ((N(N+1) - (k-1)k) / 2) + b * (N - k + 1)
    sum_term = (N * (N + 1) - (k - 1) * k) / 2
    count_term = N - k + 1
    return a * sum_term + b * count_term


def get_fallback_seconds_for_model(model_name: str, app_config: dict) -> float:
    """
    Ottiene il fallback in secondi per un modello specifico.
    
    Args:
        model_name: Nome del modello (es. "gemini-3-ultra", "gemini-3-flash")
        app_config: Configurazione dell'app
    
    Returns:
        Fallback in secondi per il modello specificato
    """
    time_config = app_config.get("time_estimation", {})
    fallback_by_model = time_config.get("fallback_by_model", {})
    
    # Normalizza il nome del modello per matching
    model_lower = model_name.lower() if model_name else ""
    
    # Cerca match esatto o parziale
    if "ultra" in model_lower:
        return fallback_by_model.get("gemini-3-ultra", fallback_by_model.get("default", 45))
    elif "3-pro" in model_lower or "3-pro-preview" in model_lower:
        return fallback_by_model.get("gemini-3-pro", fallback_by_model.get("default", 45))
    elif "3-flash" in model_lower or "3-flash-preview" in model_lower:
        return fallback_by_model.get("gemini-3-flash", fallback_by_model.get("default", 45))
    elif "2.5-pro" in model_lower:
        return fallback_by_model.get("gemini-2.5-pro", fallback_by_model.get("default", 45))
    elif "2.5-flash" in model_lower:
        return fallback_by_model.get("gemini-2.5-flash", fallback_by_model.get("default", 45))
    else:
        return fallback_by_model.get("default", time_config.get("fallback_seconds_per_chapter", 45))


async def calculate_estimated_time(session_id: str, current_step: int, total_steps: int) -> tuple[Optional[float], Optional[str]]:
    """
    Calcola la stima del tempo rimanente per completare il libro usando modello lineare.
    
    Modello: t(i) = a*i + b dove i è l'indice del capitolo
    Tempo residuo: T_res(k, N) = a * ((N(N+1) - (k-1)k) / 2) + b * (N - k + 1)
    
    Restituisce (estimated_minutes, None) dove confidence è None per retrocompatibilità.
    """
    try:
        # Casting esplicito a int per evitare errori con stringhe
        try:
            current_step = int(current_step)
        except (ValueError, TypeError):
            print(f"[CALCULATE_ESTIMATED_TIME] WARNING: current_step non è un numero valido ({current_step}), uso 0")
            current_step = 0
        
        try:
            total_steps = int(total_steps)
        except (ValueError, TypeError):
            print(f"[CALCULATE_ESTIMATED_TIME] WARNING: total_steps non è un numero valido ({total_steps}), uso 0")
            total_steps = 0
        
        print(f"[CALCULATE_ESTIMATED_TIME] Calcolo stima per session_id={session_id[:8]}..., current_step={current_step}, total_steps={total_steps}")
        
        # Verifica edge cases
        if total_steps <= 0:
            print(f"[CALCULATE_ESTIMATED_TIME] total_steps <= 0, restituisco None")
            return None, None
        
        remaining_chapters = total_steps - current_step
        if remaining_chapters <= 0:
            print(f"[CALCULATE_ESTIMATED_TIME] Nessun capitolo rimanente, restituisco None")
            return None, None
        
        # Ottieni configurazione e sessione
        app_config = get_app_config()
        from app.agent.session_store import get_session_store
        session_store = get_session_store()
        session = await get_session_async(session_store, session_id)
        
        # Ottieni il modello della sessione corrente
        current_model = session.form_data.llm_model if session and session.form_data else None
        print(f"[CALCULATE_ESTIMATED_TIME] Modello sessione corrente: {current_model}")
        
        # Determina il metodo di generazione
        method = get_generation_method(current_model)
        print(f"[CALCULATE_ESTIMATED_TIME] Metodo determinato: {method}")
        
        # Ottieni parametri a e b per il metodo
        a, b = get_linear_params_for_method(method, app_config)
        print(f"[CALCULATE_ESTIMATED_TIME] Parametri modello lineare: a={a:.2f} s/cap, b={b:.2f} s")
        
        # Calcola k: primo capitolo ancora da processare (1-indexed)
        k = current_step + 1
        N = total_steps
        
        print(f"[CALCULATE_ESTIMATED_TIME] Calcolo tempo residuo: k={k}, N={N}")
        
        # Calcola tempo residuo usando formula chiusa
        estimated_seconds = calculate_residual_time_linear(k, N, a, b)
        estimated_minutes = estimated_seconds / 60
        
        result = round(estimated_minutes, 1), None  # confidence = None per retrocompatibilità
        
        print(f"[CALCULATE_ESTIMATED_TIME] Risultato finale: {result[0]} minuti")
        return result
        
    except Exception as e:
        print(f"[CALCULATE_ESTIMATED_TIME] ERRORE nel calcolo stima tempo: {e}")
        import traceback
        traceback.print_exc()
        
        # Fallback: usa modello lineare con parametri default
        try:
            current_step_int = int(current_step) if not isinstance(current_step, int) else current_step
            total_steps_int = int(total_steps) if not isinstance(total_steps, int) else total_steps
            remaining_chapters = total_steps_int - current_step_int
            
            if remaining_chapters > 0:
                app_config = get_app_config()
                from app.agent.session_store import get_session_store
                session_store = get_session_store()
                session = await get_session_async(session_store, session_id)
                current_model = session.form_data.llm_model if session and session.form_data else None
                method = get_generation_method(current_model)
                
                # Usa solo parametri default (senza session_store per evitare loop)
                a, b = get_linear_params_for_method(method, app_config)
                k = current_step_int + 1
                estimated_seconds = calculate_residual_time_linear(k, total_steps_int, a, b)
                estimated_minutes = estimated_seconds / 60
                print(f"[CALCULATE_ESTIMATED_TIME] Fallback: {estimated_minutes:.1f} minuti")
                return round(estimated_minutes, 1), None
        except Exception as fallback_err:
            print(f"[CALCULATE_ESTIMATED_TIME] ERRORE anche nel fallback: {fallback_err}")
            import traceback
            traceback.print_exc()
        
        return None, None


def calculate_generation_cost(
    session,
    total_pages: Optional[int],
) -> Optional[float]:
    """
    Calcola il costo stimato di generazione dei capitoli del libro.
    
    Considera solo il costo di generazione dei capitoli (processo autoregressivo),
    escludendo bozza, outline, critica e copertina.
    
    Args:
        session: SessionData object
        total_pages: Numero totale di pagine del libro (None se non disponibile)
    
    Returns:
        Costo stimato in EUR, o None se non calcolabile
    """
    # Calcola solo se il libro è completo e abbiamo total_pages
    if not total_pages or total_pages <= 0:
        return None
    
    try:
        # Recupera configurazione costi
        tokens_per_page = get_tokens_per_page()
        model_name = session.form_data.llm_model if session.form_data else None
        if not model_name:
            return None
        
        # Mappa il nome del modello al nome API
        from app.agent.writer_generator import map_model_name
        gemini_model = map_model_name(model_name)
        
        # Recupera pricing del modello
        pricing = get_model_pricing(gemini_model)
        input_cost_per_million = pricing["input_cost_per_million"]
        output_cost_per_million = pricing["output_cost_per_million"]
        
        # Recupera stime token
        token_estimates = get_token_estimates()
        
        # Calcola pagine capitoli (escludendo copertina e TOC)
        chapters_pages = total_pages - 1  # -1 per copertina
        app_config = get_app_config()
        toc_chapters_per_page = app_config.get("validation", {}).get("toc_chapters_per_page", 30)
        
        # Usa writing_progress.completed_chapters_count se disponibile (più efficiente, non richiede book_chapters)
        if session.writing_progress and session.writing_progress.get("completed_chapters_count"):
            completed_chapters = session.writing_progress.get("completed_chapters_count")
        elif session.book_chapters:
            completed_chapters = len(session.book_chapters)
        else:
            completed_chapters = 0
        
        toc_pages = math.ceil(completed_chapters / toc_chapters_per_page) if completed_chapters > 0 else 0
        chapters_pages = chapters_pages - toc_pages  # Rimuovi anche TOC
        
        if chapters_pages <= 0:
            chapters_pages = max(1, total_pages - 1)  # Fallback minimo
        
        if completed_chapters == 0:
            # Non loggare più questo messaggio per evitare spam nei log
            return None  # Nessun capitolo, non calcolabile
        
        print(f"[COST CALCULATION] Calcolo costo per: modello={gemini_model}, capitoli={completed_chapters}, pagine={chapters_pages}")
        
        # Calcolo costo Capitoli (processo autoregressivo)
        # Formula: per ogni capitolo i (da 1 a N):
        #   Input per capitolo i = context_base + somma(pagine di tutti i capitoli precedenti 0..i-1) × tokens_per_page
        #   Output per capitolo i = pagine_capitolo_i × tokens_per_page
        #
        # Input totale = sum(i=1 to N) di [context_base + sum(j=0 to i-1) di (pages[j] × tokens_per_page)]
        # Con approssimazione pagine uniformi:
        #   = N × context_base + tokens_per_page × avg_pages × sum(i=1 to N) di (i-1)
        #   = N × context_base + tokens_per_page × avg_pages × [N × (N-1) / 2]
        
        num_chapters = completed_chapters
        context_base = token_estimates.get("chapter", {}).get("context_base", 8000)
        avg_pages_per_chapter = chapters_pages / num_chapters if num_chapters > 0 else chapters_pages
        
        # Input totale per tutti i capitoli
        # Base: ogni capitolo include il context_base (draft + outline + form_data + system_prompt)
        chapters_input = num_chapters * context_base
        
        # Somma cumulativa: per ogni capitolo i, aggiungi i capitoli precedenti (0..i-1)
        # Formula chiusa O(1): sum(i=1 to N) di (i-1) = N * (N-1) / 2
        # Questo rappresenta il fatto che ogni capitolo vede tutti i capitoli precedenti nel contesto
        cumulative_pages_sum = (num_chapters * (num_chapters - 1) / 2) * avg_pages_per_chapter
        chapters_input += cumulative_pages_sum * tokens_per_page
        
        # Output totale: tutte le pagine generate dai capitoli
        chapters_output = chapters_pages * tokens_per_page
        
        # Calcola costo
        chapters_cost_usd = (
            (chapters_input * input_cost_per_million / 1_000_000) +
            (chapters_output * output_cost_per_million / 1_000_000)
        )
        
        # Converti USD -> EUR
        exchange_rate = get_exchange_rate_usd_to_eur()
        total_cost_eur = chapters_cost_usd * exchange_rate
        
        # Log ridotto: solo per modelli pro o calcoli costosi
        if num_chapters > 30 or "pro" in gemini_model.lower():
            print(f"[COST CALCULATION] Risultato: ${chapters_cost_usd:.6f} USD = €{total_cost_eur:.4f} EUR")
        
        return round(total_cost_eur, 4)
        
    except Exception as e:
        print(f"[COST CALCULATION] Errore nel calcolo costo: {e}")
        import traceback
        traceback.print_exc()
        return None


def session_to_library_entry(session, skip_cost_calculation: bool = False) -> "LibraryEntry":
    """Converte una SessionData in una LibraryEntry.
    
    Args:
        session: SessionData da convertire
        skip_cost_calculation: Se True, salta il calcolo dei costi (ottimizzazione per statistiche aggregate)
    """
    from app.models import LibraryEntry
    from app.agent.session_store import get_session_store
    
    status = session.get_status()
    
    # Ottimizzazione: usa valori pre-calcolati da writing_progress
    # Questi sono stati salvati quando il libro è stato completato, evitando di caricare book_chapters
    total_chapters = 0
    completed_chapters = 0
    total_pages = None
    
    if session.writing_progress:
        total_chapters = session.writing_progress.get('total_steps', 0)
        # Usa completed_chapters_count pre-calcolato se disponibile
        completed_chapters = session.writing_progress.get('completed_chapters_count', 
                                                           session.writing_progress.get('current_step', 0))
        # Usa total_pages pre-calcolato se disponibile
        total_pages = session.writing_progress.get('total_pages')
    
    # Fallback per libri che non hanno valori pre-calcolati
    # (book_chapters potrebbe non essere caricato nella proiezione)
    if completed_chapters == 0 and session.book_chapters:
        completed_chapters = len(session.book_chapters)
    
    # Per total_pages, usiamo il valore pre-calcolato
    # Se non disponibile e book_chapters è presente (caricato per altri motivi), calcola
    if total_pages is None and status == "complete" and session.book_chapters:
        chapters_pages = sum(calculate_page_count(ch.get('content', '')) for ch in session.book_chapters)
        cover_pages = 1
        app_config = get_app_config()
        toc_chapters_per_page = app_config.get("validation", {}).get("toc_chapters_per_page", 30)
        toc_pages = math.ceil(len(session.book_chapters) / toc_chapters_per_page)
        total_pages = chapters_pages + cover_pages + toc_pages
    
    # Estrai critique_score
    critique_score = None
    if session.literary_critique and isinstance(session.literary_critique, dict):
        critique_score = session.literary_critique.get('score')
    elif session.literary_critique:
        # Potrebbe essere un oggetto LiteraryCritique
        critique_score = getattr(session.literary_critique, 'score', None)
    
    # Cerca PDF collegato
    pdf_path = None
    pdf_filename = None
    pdf_url = None
    cover_url = None
    
    # Ottimizzazione: non generiamo URL firmati qui per evitare chiamate GCS sincrone
    # Gli URL verranno generati on-demand dagli endpoint dedicati
    storage_service = get_storage_service()
    
    if status == "complete":
        # Prova a costruire il path atteso
        date_prefix = session.created_at.strftime("%Y-%m-%d")
        model_abbrev = get_model_abbreviation(session.form_data.llm_model)
        title_sanitized = "".join(c for c in (session.current_title or "Romanzo") if c.isalnum() or c in (' ', '-', '_')).rstrip()
        title_sanitized = title_sanitized.replace(" ", "_")
        if not title_sanitized:
            title_sanitized = f"Libro_{session.session_id[:8]}"
        expected_filename = f"{date_prefix}_{model_abbrev}_{title_sanitized}.pdf"
        
        # Costruisci path senza verificare esistenza (verificato on-demand)
        if storage_service.gcs_enabled:
            # Assumiamo che il PDF sia su GCS se GCS è abilitato
            pdf_path = f"gs://{storage_service.bucket_name}/books/{expected_filename}"
            pdf_filename = expected_filename
        else:
            # Verifica locale (veloce, no chiamate HTTP)
            local_pdf_path = Path(__file__).parent.parent / "books" / expected_filename
            if local_pdf_path.exists():
                pdf_path = str(local_pdf_path)
                pdf_filename = expected_filename
            # Rimosso glob costoso: se il file non esiste con il nome atteso, non cerchiamo
            # (ottimizzazione performance - il PDF verrà trovato quando necessario)
    
    # Calcola writing_time_minutes
    writing_time_minutes = None
    if session.writing_progress:
        writing_time_minutes = session.writing_progress.get('writing_time_minutes')
    if writing_time_minutes is None and session.writing_start_time and session.writing_end_time:
        delta = session.writing_end_time - session.writing_start_time
        writing_time_minutes = delta.total_seconds() / 60
    
    # Calcola costo stimato
    estimated_cost = None
    
    # PRIMA: sempre prova a leggere il costo già salvato (veloce, nessun calcolo)
    if status == "complete" and session.writing_progress:
        estimated_cost = session.writing_progress.get("estimated_cost")
    
    # SECONDA: calcola solo se non già salvato E skip_cost_calculation=False
    if estimated_cost is None and not skip_cost_calculation and status == "complete" and total_pages:
        estimated_cost = calculate_generation_cost(session, total_pages)
        # Salva il costo calcolato in writing_progress per le prossime richieste (in background)
        if estimated_cost is not None and session.writing_progress:
            # Aggiorna il dict in-place (verrà salvato al prossimo save_session)
            session.writing_progress["estimated_cost"] = estimated_cost
    
    # Converti il modello in modalità per la visualizzazione
    original_model = session.form_data.llm_model if session.form_data else None
    mode = llm_model_to_mode(original_model)
    print(f"[SESSION_TO_LIBRARY_ENTRY] Modello originale: {original_model}, Modalità convertita: {mode}")
    
    return LibraryEntry(
        session_id=session.session_id,
        title=session.current_title or "Romanzo",
        author=session.form_data.user_name or "Autore",
        llm_model=mode,  # Ora contiene la modalità invece del nome del modello
        genre=session.form_data.genre,
        created_at=session.created_at,
        updated_at=session.updated_at,
        status=status,
        total_chapters=total_chapters,
        completed_chapters=completed_chapters,
        total_pages=total_pages,
        critique_score=critique_score,
        critique_status=session.critique_status,
        pdf_path=pdf_path,
        pdf_filename=pdf_filename,
        pdf_url=pdf_url,
        cover_image_path=session.cover_image_path,
        cover_url=cover_url,
        writing_time_minutes=writing_time_minutes,
        estimated_cost=estimated_cost,
    )


def scan_pdf_directory() -> list["PdfEntry"]:
    """Scansiona la directory books/ e restituisce lista di PDF disponibili."""
    from app.models import PdfEntry
    from datetime import datetime
    
    books_dir = Path(__file__).parent.parent / "books"
    pdf_entries = []
    
    if not books_dir.exists():
        return pdf_entries
    
    session_store = get_session_store()
    
    for pdf_file in sorted(books_dir.glob("*.pdf"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            # Prova a parsare il nome file: YYYY-MM-DD_g3p_TitoloLibro.pdf
            filename = pdf_file.name
            stem = pdf_file.stem
            
            # Estrai data (prima parte prima di _)
            parts = stem.split('_', 2)
            created_date = None
            if len(parts) >= 1:
                try:
                    created_date = datetime.strptime(parts[0], "%Y-%m-%d")
                except:
                    pass
            
            # Cerca session_id corrispondente (potrebbe essere nel nome o cercando per titolo)
            session_id = None
            title = None
            author = None
            
            # Prova a cercare nelle sessioni per matchare il PDF
            for sid, session in session_store._sessions.items():
                # Genera il nome file atteso per questa sessione
                if session.current_title:
                    date_prefix = session.created_at.strftime("%Y-%m-%d")
                    model_abbrev = get_model_abbreviation(session.form_data.llm_model)
                    title_sanitized = "".join(c for c in session.current_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                    title_sanitized = title_sanitized.replace(" ", "_")
                    expected_filename = f"{date_prefix}_{model_abbrev}_{title_sanitized}.pdf"
                    
                    if filename == expected_filename:
                        session_id = sid
                        title = session.current_title
                        author = session.form_data.user_name
                        break
            
            # Se non trovato, prova a estrarre titolo dal nome file
            if not title and len(parts) >= 3:
                title = parts[2].replace('_', ' ')
            
            size_bytes = pdf_file.stat().st_size
            
            pdf_entries.append(PdfEntry(
                filename=filename,
                session_id=session_id,
                title=title,
                author=author,
                created_date=created_date,
                size_bytes=size_bytes,
            ))
        except Exception as e:
            print(f"[SCAN PDF] Errore nel processare {pdf_file.name}: {e}")
            continue
    
    return pdf_entries


def calculate_library_stats(entries: list["LibraryEntry"]) -> "LibraryStats":
    """Calcola statistiche aggregate dalla lista di LibraryEntry."""
    from app.models import LibraryStats
    from collections import defaultdict
    
    if not entries:
        return LibraryStats(
            total_books=0,
            completed_books=0,
            in_progress_books=0,
            average_score=None,
            average_pages=0.0,
            average_writing_time_minutes=0.0,
            books_by_model={},
            books_by_genre={},
            score_distribution={},
            average_score_by_model={},
            average_writing_time_by_model={},
            average_time_per_page_by_model={},
            average_pages_by_model={},
            average_cost_by_model={},
            average_cost_per_page_by_model={},
        )
    
    completed = [e for e in entries if e.status == "complete"]
    in_progress = [e for e in entries if e.status in ["draft", "outline", "writing", "paused"]]
    
    # Calcola voto medio solo sui libri completati con voto
    scores = [e.critique_score for e in completed if e.critique_score is not None]
    average_score = sum(scores) / len(scores) if scores else None
    
    # Calcola pagine medie (solo libri completati con pagine)
    pages_list = [e.total_pages for e in completed if e.total_pages is not None and e.total_pages > 0]
    average_pages = sum(pages_list) / len(pages_list) if pages_list else 0.0
    
    # Calcola tempo medio scrittura
    time_list = [e.writing_time_minutes for e in entries if e.writing_time_minutes is not None and e.writing_time_minutes > 0]
    average_writing_time_minutes = sum(time_list) / len(time_list) if time_list else 0.0
    
    # Distribuzione per modalità (e.llm_model ora contiene la modalità, non il modello)
    books_by_mode = defaultdict(int)
    for e in entries:
        books_by_mode[e.llm_model] += 1  # llm_model ora contiene la modalità
    
    # Distribuzione per genere
    books_by_genre = defaultdict(int)
    for e in entries:
        if e.genre:
            books_by_genre[e.genre] += 1
    
    # Distribuzione voti (0-2, 2-4, 4-6, 6-8, 8-10)
    score_distribution = defaultdict(int)
    for e in completed:
        if e.critique_score is not None:
            score = e.critique_score
            if score < 2:
                score_distribution["0-2"] += 1
            elif score < 4:
                score_distribution["2-4"] += 1
            elif score < 6:
                score_distribution["4-6"] += 1
            elif score < 8:
                score_distribution["6-8"] += 1
            else:
                score_distribution["8-10"] += 1
    
    # Calcola voto medio per modalità (e.llm_model ora contiene la modalità)
    mode_scores = defaultdict(list)
    for e in completed:
        if e.critique_score is not None:
            mode_scores[e.llm_model].append(e.critique_score)  # llm_model ora contiene la modalità
    
    average_score_by_model = {}
    for mode, scores_list in mode_scores.items():
        if scores_list:
            average_score_by_model[mode] = round(sum(scores_list) / len(scores_list), 2)
    
    # Calcola tempo medio di generazione per modalità (solo libri completati con tempo valido)
    mode_times = defaultdict(list)
    for e in completed:
        if e.writing_time_minutes is not None and e.writing_time_minutes > 0:
            mode_times[e.llm_model].append(e.writing_time_minutes)  # llm_model ora contiene la modalità
    
    average_writing_time_by_model = {}
    for mode, times_list in mode_times.items():
        if times_list:
            average_writing_time_by_model[mode] = round(sum(times_list) / len(times_list), 1)
    
    # Calcola tempo medio per pagina per modalità (MEDIA PESATA):
    # (somma tempi) / (somma pagine) sui libri completati con tempo e pagine valide
    mode_time_sum_minutes = defaultdict(float)
    mode_pages_sum_for_time = defaultdict(float)
    for e in completed:
        if (
            e.writing_time_minutes is not None
            and e.writing_time_minutes > 0
            and e.total_pages is not None
            and e.total_pages > 0
        ):
            mode_time_sum_minutes[e.llm_model] += float(e.writing_time_minutes)  # llm_model ora contiene la modalità
            mode_pages_sum_for_time[e.llm_model] += float(e.total_pages)

    average_time_per_page_by_model = {}
    for mode in set(list(mode_time_sum_minutes.keys()) + list(mode_pages_sum_for_time.keys())):
        pages_sum = mode_pages_sum_for_time.get(mode, 0.0)
        if pages_sum > 0:
            average_time_per_page_by_model[mode] = round(mode_time_sum_minutes.get(mode, 0.0) / pages_sum, 2)
    
    # Calcola pagine medie per modalità (solo libri completati con pagine valide)
    mode_pages = defaultdict(list)
    for e in completed:
        if e.total_pages is not None and e.total_pages > 0:
            mode_pages[e.llm_model].append(e.total_pages)  # llm_model ora contiene la modalità
    
    average_pages_by_model = {}
    for mode, pages_list in mode_pages.items():
        if pages_list:
            average_pages_by_model[mode] = round(sum(pages_list) / len(pages_list), 1)
    
    # Calcola costo medio per libro per modalità (solo libri completati con costo valido)
    mode_costs = defaultdict(list)
    for e in completed:
        if e.estimated_cost is not None and e.estimated_cost > 0:
            mode_costs[e.llm_model].append(e.estimated_cost)  # llm_model ora contiene la modalità
    
    average_cost_by_model = {}
    for mode, costs_list in mode_costs.items():
        if costs_list:
            average_cost_by_model[mode] = round(sum(costs_list) / len(costs_list), 4)
    
    # Calcola costo medio per pagina per modalità (solo libri completati con costo e pagine valide)
    mode_costs_per_page = defaultdict(list)
    for e in completed:
        if (e.estimated_cost is not None and e.estimated_cost > 0 and
            e.total_pages is not None and e.total_pages > 0):
            cost_per_page = e.estimated_cost / e.total_pages
            mode_costs_per_page[e.llm_model].append(cost_per_page)  # llm_model ora contiene la modalità
    
    average_cost_per_page_by_model = {}
    for mode, costs_per_page_list in mode_costs_per_page.items():
        if costs_per_page_list:
            average_cost_per_page_by_model[mode] = round(sum(costs_per_page_list) / len(costs_per_page_list), 4)
    
    return LibraryStats(
        total_books=len(entries),
        completed_books=len(completed),
        in_progress_books=len(in_progress),
        average_score=round(average_score, 2) if average_score else None,
        average_pages=round(average_pages, 1),
        average_writing_time_minutes=round(average_writing_time_minutes, 1),
        books_by_model=dict(books_by_mode),  # Ora contiene modalità invece di modelli
        books_by_genre=dict(books_by_genre),
        score_distribution=dict(score_distribution),
        average_score_by_model=average_score_by_model,
        average_writing_time_by_model=average_writing_time_by_model,
        average_time_per_page_by_model=average_time_per_page_by_model,
        average_pages_by_model=average_pages_by_model,
        average_cost_by_model=average_cost_by_model,
        average_cost_per_page_by_model=average_cost_per_page_by_model,
    )


def calculate_advanced_stats(entries: list["LibraryEntry"]) -> "AdvancedStats":
    """Calcola statistiche avanzate con analisi temporali e confronto modelli."""
    from app.models import AdvancedStats, ModelComparisonEntry
    from collections import defaultdict
    from datetime import datetime, timedelta
    
    if not entries:
        return AdvancedStats(
            books_over_time={},
            score_trend_over_time={},
            model_comparison=[],
        )
    
    completed = [e for e in entries if e.status == "complete"]
    
    # Calcola libri creati nel tempo (raggruppati per giorno)
    books_over_time = defaultdict(int)
    for entry in entries:
        # Formatta la data come YYYY-MM-DD
        date_str = entry.created_at.strftime("%Y-%m-%d")
        books_over_time[date_str] += 1
    
    # Ordina per data
    books_over_time_sorted = dict(sorted(books_over_time.items()))
    
    # Calcola trend voto nel tempo (voto medio per giorno)
    score_by_date = defaultdict(list)
    for entry in completed:
        if entry.critique_score is not None:
            date_str = entry.created_at.strftime("%Y-%m-%d")
            score_by_date[date_str].append(entry.critique_score)
    
    score_trend_over_time = {}
    for date_str, scores in sorted(score_by_date.items()):
        score_trend_over_time[date_str] = round(sum(scores) / len(scores), 2)
    
    # Calcola confronto dettagliato per ogni modalità (entry.llm_model ora contiene la modalità)
    mode_comparison_data = defaultdict(lambda: {
        'total': 0,
        'completed': 0,
        'scores': [],
        'pages': [],
        'costs': [],
        'writing_times': [],
        # Tempo/pagina (MEDIA PESATA): accumuli per calcolare (somma tempi) / (somma pagine)
        'time_sum_minutes_for_pages': 0.0,
        'pages_sum_for_time': 0.0,
        'score_distribution': defaultdict(int),
    })
    
    for entry in entries:
        mode = entry.llm_model  # llm_model ora contiene la modalità
        mode_comparison_data[mode]['total'] += 1
        if entry.status == "complete":
            mode_comparison_data[mode]['completed'] += 1
            
            if entry.critique_score is not None:
                mode_comparison_data[mode]['scores'].append(entry.critique_score)
                # Distribuzione voti per modalità
                score = entry.critique_score
                if score < 2:
                    mode_comparison_data[mode]['score_distribution']["0-2"] += 1
                elif score < 4:
                    mode_comparison_data[mode]['score_distribution']["2-4"] += 1
                elif score < 6:
                    mode_comparison_data[mode]['score_distribution']["4-6"] += 1
                elif score < 8:
                    mode_comparison_data[mode]['score_distribution']["6-8"] += 1
                else:
                    mode_comparison_data[mode]['score_distribution']["8-10"] += 1
            
            if entry.total_pages is not None and entry.total_pages > 0:
                mode_comparison_data[mode]['pages'].append(entry.total_pages)
            
            if entry.estimated_cost is not None and entry.estimated_cost > 0:
                mode_comparison_data[mode]['costs'].append(entry.estimated_cost)
            
            if entry.writing_time_minutes is not None and entry.writing_time_minutes > 0:
                mode_comparison_data[mode]['writing_times'].append(entry.writing_time_minutes)
                if entry.total_pages is not None and entry.total_pages > 0:
                    mode_comparison_data[mode]['time_sum_minutes_for_pages'] += float(entry.writing_time_minutes)
                    mode_comparison_data[mode]['pages_sum_for_time'] += float(entry.total_pages)
    
    # Crea lista ModelComparisonEntry (ora contiene modalità invece di modelli)
    model_comparison = []
    for mode, data in sorted(mode_comparison_data.items()):
        avg_score = None
        if data['scores']:
            avg_score = round(sum(data['scores']) / len(data['scores']), 2)
        
        avg_pages = 0.0
        if data['pages']:
            avg_pages = round(sum(data['pages']) / len(data['pages']), 1)
        
        avg_cost = None
        if data['costs']:
            avg_cost = round(sum(data['costs']) / len(data['costs']), 1)
        
        avg_writing_time = 0.0
        if data['writing_times']:
            avg_writing_time = round(sum(data['writing_times']) / len(data['writing_times']), 1)
        
        avg_time_per_page = 0.0
        pages_sum = float(data.get('pages_sum_for_time', 0.0) or 0.0)
        if pages_sum > 0:
            avg_time_per_page = round(float(data.get('time_sum_minutes_for_pages', 0.0) or 0.0) / pages_sum, 2)
        
        model_comparison.append(ModelComparisonEntry(
            model=mode,  # Ora contiene la modalità invece del modello
            total_books=data['total'],
            completed_books=data['completed'],
            average_score=avg_score,
            average_pages=avg_pages,
            average_cost=avg_cost,
            average_writing_time=avg_writing_time,
            average_time_per_page=avg_time_per_page,
            score_range=dict(data['score_distribution']),
        ))
    
    return AdvancedStats(
        books_over_time=books_over_time_sorted,
        score_trend_over_time=score_trend_over_time,
        model_comparison=model_comparison,
        )


# Endpoint files migrati in app/api/routers/files.py


# Endpoint critique migrati in app/api/routers/critique.py


# Endpoint health migrati in app/api/routers/health.py


# Background functions migrati in app/services/generation_service.py


# Endpoint session migrati in app/api/routers/session.py


# Endpoint library migrati in app/api/routers/library.py


# Endpoint admin migrati in app/api/routers/admin.py


def sanitize_plot_for_cover(plot: str) -> str:
    """
    Sanitizza il plot creando un riassunto molto generico con solo elementi atmosferici e visivi.
    Usata solo per la rigenerazione manuale della copertina per evitare blocchi da contenuti sensibili.
    """
    if not plot:
        return ""
    
    import re
    
    # Estrai solo elementi chiave per la copertina: setting, atmosfera, temi visuali
    plot_lower = plot.lower()
    
    # Cerca luoghi/setting
    places = []
    if 'villa' in plot_lower:
        places.append('villa')
    if 'vienna' in plot_lower:
        places.append('Vienna')
    if 'new york' in plot_lower or 'newyork' in plot_lower:
        places.append('New York')
    if 'roma' in plot_lower:
        places.append('Roma')
    if 'parigi' in plot_lower or 'paris' in plot_lower:
        places.append('Parigi')
    if 'ligure' in plot_lower or 'liguria' in plot_lower:
        places.append('costa ligure')
    
    # Cerca elementi atmosferici
    atmosphere = []
    if 'estate' in plot_lower:
        atmosphere.append('estate')
    if 'neve' in plot_lower:
        atmosphere.append('neve')
    if 'mare' in plot_lower:
        atmosphere.append('mare')
    if 'caldo' in plot_lower:
        atmosphere.append('caldo opprimente')
    if 'luce' in plot_lower or 'tramonto' in plot_lower:
        atmosphere.append('luce del tramonto')
    
    # Cerca temi principali (senza dettagli narrativi)
    themes = []
    if 'architettura' in plot_lower:
        themes.append('architettura')
    if 'musica' in plot_lower or 'violoncello' in plot_lower:
        themes.append('musica')
    if 'tempo' in plot_lower or 'memoria' in plot_lower:
        themes.append('tempo e memoria')
    if 'spazio' in plot_lower:
        themes.append('spazio')
    
    # Cerca elementi visivi
    visual_elements = []
    if 'serra' in plot_lower:
        visual_elements.append('serra')
    if 'giardino' in plot_lower:
        visual_elements.append('giardino')
    if 'stanza' in plot_lower or 'camera' in plot_lower:
        visual_elements.append('stanza')
    
    # Crea un riassunto molto generico e sicuro
    sanitized_parts = []
    
    if places:
        sanitized_parts.append(f"Ambientato in {', '.join(set(places[:3]))}")
    
    if atmosphere:
        sanitized_parts.append(f"Atmosfera: {', '.join(set(atmosphere[:3]))}")
    
    if themes:
        sanitized_parts.append(f"Temi: {', '.join(set(themes[:3]))}")
    
    if visual_elements:
        sanitized_parts.append(f"Elementi visivi: {', '.join(set(visual_elements[:3]))}")
    
    # Crea un riassunto finale molto generico
    if sanitized_parts:
        sanitized = "Romanzo " + ". ".join(sanitized_parts) + "."
    else:
        # Fallback: estrai solo la prima frase descrittiva senza dettagli
        sentences = re.split(r'[.!?]', plot)
        first_safe_sentences = []
        for sent in sentences[:3]:
            sent_clean = sent.strip()
            if len(sent_clean) > 20 and len(sent_clean) < 200:
                # Verifica che non contenga parole problematiche
                sent_lower = sent_clean.lower()
                if not any(word in sent_lower for word in ['amore', 'bacio', 'corpo', 'intim', 'fisic', 'nud']):
                    first_safe_sentences.append(sent_clean)
        if first_safe_sentences:
            sanitized = ". ".join(first_safe_sentences) + "."
        else:
            # Ultimo fallback: descrizione generica
            sanitized = "Romanzo con temi di architettura, musica e memoria. Ambientato in luoghi che variano nel tempo."
    
    # Limita lunghezza per sicurezza
    if len(sanitized) > 500:
        sanitized = sanitized[:500]
    
    return sanitized


# Serve static files for frontend (only in production/Docker)
static_path = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.exists(static_path):
    # Mount assets directory for Vite build assets
    assets_path = os.path.join(static_path, "assets")
    if os.path.exists(assets_path):
        app.mount("/assets", StaticFiles(directory=assets_path), name="assets")
    
    # Serve favicon
    @app.get("/favicon.svg")
    async def serve_favicon():
        favicon_path = os.path.join(static_path, "favicon.svg")
        if os.path.exists(favicon_path):
            return FileResponse(favicon_path, media_type="image/svg+xml")
        raise HTTPException(status_code=404, detail="Favicon not found")
    
    # Serve PWA manifest
    @app.get("/manifest.webmanifest")
    async def serve_manifest():
        manifest_path = os.path.join(static_path, "manifest.webmanifest")
        if os.path.exists(manifest_path):
            return FileResponse(manifest_path, media_type="application/manifest+json")
        raise HTTPException(status_code=404, detail="Manifest not found")
    
    # Serve PWA icons
    @app.get("/icon-192.png")
    async def serve_icon_192():
        icon_path = os.path.join(static_path, "icon-192.png")
        if os.path.exists(icon_path):
            return FileResponse(icon_path, media_type="image/png")
        raise HTTPException(status_code=404, detail="Icon not found")
    
    @app.get("/icon-512.png")
    async def serve_icon_512():
        icon_path = os.path.join(static_path, "icon-512.png")
        if os.path.exists(icon_path):
            return FileResponse(icon_path, media_type="image/png")
        raise HTTPException(status_code=404, detail="Icon not found")
    
    @app.get("/apple-touch-icon.png")
    async def serve_apple_touch_icon():
        icon_path = os.path.join(static_path, "apple-touch-icon.png")
        if os.path.exists(icon_path):
            return FileResponse(icon_path, media_type="image/png")
        raise HTTPException(status_code=404, detail="Icon not found")
    
    @app.get("/favicon.png")
    async def serve_favicon_png():
        icon_path = os.path.join(static_path, "favicon.png")
        if os.path.exists(icon_path):
            return FileResponse(icon_path, media_type="image/png")
        raise HTTPException(status_code=404, detail="Icon not found")
    
    # Serve index.html for all non-API routes (SPA routing)
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Skip if it's an API route, favicon, manifest, or PWA icons
        if (full_path.startswith("api/") or 
            full_path == "favicon.svg" or 
            full_path == "manifest.webmanifest" or
            full_path in ["icon-192.png", "icon-512.png", "apple-touch-icon.png", "favicon.png"]):
            raise HTTPException(status_code=404, detail="Not found")
        # Serve index.html for SPA routing
        index_path = os.path.join(static_path, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        raise HTTPException(status_code=404, detail="Frontend not found")


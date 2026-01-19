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
from app.services.stats_service import (
    calculate_page_count,
    get_model_abbreviation,
    llm_model_to_mode,
)
from app.utils.stats_utils import get_generation_method


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


# NOTE: Gli endpoint sono stati migrati nei rispettivi router:
# - /api/config -> app/api/routers/config.py
# - /api/submissions -> app/api/routers/submission.py
# - /api/questions -> app/api/routers/questions.py
# - /api/draft -> app/api/routers/draft.py
# - /api/outline -> app/api/routers/outline.py
# - /api/critique -> app/api/routers/critique.py
# - /api/health -> app/api/routers/health.py
# - /api/session -> app/api/routers/session.py
# - /api/library -> app/api/routers/library.py
# - /api/admin -> app/api/routers/admin.py
# - /api/files -> app/api/routers/files.py
# Background functions migrati in app/services/generation_service.py
# Funzioni statistiche disponibili in app.services.stats_service


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
    
    @app.get("/logo-narrai.png")
    async def serve_logo_narrai():
        logo_path = os.path.join(static_path, "logo-narrai.png")
        if os.path.exists(logo_path):
            return FileResponse(logo_path, media_type="image/png")
        raise HTTPException(status_code=404, detail="Logo not found")
    
    @app.get("/logo-narrai-header.png")
    async def serve_logo_narrai_header():
        logo_path = os.path.join(static_path, "logo-narrai-header.png")
        if os.path.exists(logo_path):
            return FileResponse(logo_path, media_type="image/png")
        raise HTTPException(status_code=404, detail="Logo not found")
    
    # Serve index.html for all non-API routes (SPA routing)
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Skip if it's an API route, favicon, manifest, or PWA icons/logos
        if (full_path.startswith("api/") or 
            full_path == "favicon.svg" or 
            full_path == "manifest.webmanifest" or
            full_path in ["icon-192.png", "icon-512.png", "apple-touch-icon.png", "favicon.png", "logo-narrai.png", "logo-narrai-header.png"]):
            raise HTTPException(status_code=404, detail="Not found")
        # Serve index.html for SPA routing with no-cache to ensure fresh code
        index_path = os.path.join(static_path, "index.html")
        if os.path.exists(index_path):
            return FileResponse(
                index_path,
                headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
            )
        raise HTTPException(status_code=404, detail="Frontend not found")


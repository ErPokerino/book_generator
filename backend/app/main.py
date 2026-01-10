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
from app.api.routers import config, submission, questions, draft, outline, auth, notifications, connections, book_shares
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
    set_estimated_cost_async,
    delete_session_async
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
app.include_router(config.router)
app.include_router(submission.router)
app.include_router(questions.router)
app.include_router(draft.router)
app.include_router(outline.router)
app.include_router(auth.router)
app.include_router(notifications.router)
app.include_router(connections.router)
app.include_router(book_shares.router)


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
    except Exception as e:
        print(f"[SHUTDOWN] Errore nella disconnessione MongoDB: {e}")


# NOTE: Gli endpoint sono stati spostati nei router:
# - /api/config -> app/api/routers/config.py
# - /api/submissions -> app/api/routers/submission.py
# - /api/questions -> app/api/routers/questions.py
# - /api/draft -> app/api/routers/draft.py
# - /api/outline -> app/api/routers/outline.py

# NOTE: Gli endpoint /api/questions/* sono stati spostati in app/api/routers/questions.py
# Gli endpoint rimanenti (da spostare nei router in futuro):
@app.post("/api/questions/generate", response_model=QuestionsResponse)
async def generate_questions_endpoint_OLD(request: QuestionGenerationRequest):
    """Genera domande preliminari basate sul form compilato."""
    try:
        # Verifica che l'API key sia configurata
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="GOOGLE_API_KEY non configurata. Verifica il file .env nella root del progetto."
            )
        
        # Genera le domande (la funzione userà automaticamente la variabile d'ambiente se non passata)
        response = await generate_questions(request.form_data, api_key=api_key)
        
        # IMPORTANTE: Crea la sessione nel session store subito dopo aver generato le domande
        # Questo garantisce che la sessione esista anche se il backend si riavvia
        session_store = get_session_store()
        try:
            # Crea la sessione con form_data e question_answers vuote (verranno aggiunte dopo)
            session_store.create_session(
                session_id=response.session_id,
                form_data=request.form_data,
                question_answers=[],  # Vuote per ora, verranno aggiunte quando l'utente risponde
            )
            # Salva le questions generate nella sessione per poterle recuperare dopo
            questions_dict = [q.model_dump() for q in response.questions]
            session_store.save_generated_questions(
                session_id=response.session_id,
                questions=questions_dict,
            )
            print(f"[DEBUG] Sessione {response.session_id} creata nel session store dopo generazione domande")
        except Exception as session_error:
            # Log l'errore ma non bloccare il flusso
            print(f"[WARNING] Errore nella creazione sessione: {session_error}")
        
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Errore nella generazione delle domande: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nella generazione delle domande: {str(e)}"
        )


@app.post("/api/questions/answers", response_model=AnswersResponse)
async def submit_answers(data: AnswersRequest):
    """Riceve le risposte alle domande e continua il flusso."""
    print(f"[SUBMIT ANSWERS] Ricevute risposte per sessione {data.session_id}")
    print(f"[SUBMIT ANSWERS] Numero di risposte: {len(data.answers)}")
    try:
        # Aggiorna la sessione con le risposte alle domande
        session_store = get_session_store()
        print(f"[SUBMIT ANSWERS] Session store ottenuto: {type(session_store).__name__}")
        
        session = await get_session_async(session_store, data.session_id)
        
        if not session:
            print(f"[SUBMIT ANSWERS] ERRORE: Sessione {data.session_id} NON trovata!")
            raise HTTPException(
                status_code=404,
                detail=f"Sessione {data.session_id} non trovata. Ricarica la pagina e riprova."
            )
        
        print(f"[SUBMIT ANSWERS] Sessione trovata, aggiorno le risposte...")
        # Aggiorna le risposte nella sessione
        session.question_answers = data.answers
        print(f"[SUBMIT ANSWERS] Aggiornate {len(data.answers)} risposte nella sessione")
        
        # Salva la sessione aggiornata
        if isinstance(session_store, FileSessionStore):
            print(f"[SUBMIT ANSWERS] Salvataggio sessioni su file...")
            try:
                session_store._save_sessions()
                print(f"[SUBMIT ANSWERS] Sessioni salvate con successo")
            except Exception as save_error:
                print(f"[SUBMIT ANSWERS] ERRORE nel salvataggio: {save_error}")
                import traceback
                traceback.print_exc()
                # Non blocchiamo il flusso se il salvataggio fallisce, ma logghiamo l'errore
        
        print(f"[SUBMIT ANSWERS] Invio risposta di successo...")
        return AnswersResponse(
            success=True,
            message="Risposte ricevute con successo. Pronto per la fase di scrittura.",
            session_id=data.session_id,
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[SUBMIT ANSWERS] ERRORE CRITICO: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nell'elaborazione delle risposte: {str(e)}"
        )


@app.post("/api/draft/generate", response_model=DraftResponse)
async def generate_draft_endpoint(request: DraftGenerationRequest):
    """Genera una bozza estesa della trama."""
    print(f"[DEBUG] Generazione bozza per sessione {request.session_id}")
    try:
        # Verifica che l'API key sia configurata
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            print("[DEBUG] GOOGLE_API_KEY mancante!")
            raise HTTPException(
                status_code=500,
                detail="GOOGLE_API_KEY non configurata. Verifica il file .env nella root del progetto."
            )
        
        # Crea o recupera la sessione
        session_store = get_session_store()
        session = await get_session_async(session_store, request.session_id)
        
        if not session:
            print(f"[DEBUG] Sessione {request.session_id} non trovata, creazione nuova...")
            # Crea nuova sessione
            session = session_store.create_session(
                session_id=request.session_id,
                form_data=request.form_data,
                question_answers=request.question_answers,
            )
        
        print("[DEBUG] Chiamata a generate_draft...")
        # Genera la bozza
        draft_text, title, version = await generate_draft(
            form_data=request.form_data,
            question_answers=request.question_answers,
            session_id=request.session_id,
            api_key=api_key,
        )
        
        print(f"[DEBUG] Bozza generata: {title}, v{version}")
        # Salva la bozza nella sessione
        session_store.update_draft(request.session_id, draft_text, version, title=title)
        
        return DraftResponse(
            success=True,
            session_id=request.session_id,
            draft_text=draft_text,
            title=title,
            version=version,
            message="Bozza generata con successo",
        )
    
    except Exception as e:
        print(f"[ERROR] Errore critico in generate_draft_endpoint: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nella generazione della bozza: {str(e)}"
        )


@app.post("/api/draft/modify", response_model=DraftResponse)
async def modify_draft_endpoint(request: DraftModificationRequest):
    """Rigenera la bozza con le modifiche richieste dall'utente."""
    try:
        # Verifica che l'API key sia configurata
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="GOOGLE_API_KEY non configurata. Verifica il file .env nella root del progetto."
            )
        
        # Recupera la sessione
        session_store = get_session_store()
        session = await get_session_async(session_store, request.session_id)
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Sessione {request.session_id} non trovata"
            )
        
        if not session.current_draft:
            raise HTTPException(
                status_code=400,
                detail="Nessuna bozza esistente da modificare"
            )
        
        # Rigenera la bozza con le modifiche
        draft_text, title, version = await generate_draft(
            form_data=session.form_data,
            question_answers=session.question_answers,
            session_id=request.session_id,
            api_key=api_key,
            previous_draft=session.current_draft,
            user_feedback=request.user_feedback,
        )
        
        # Salva la nuova versione
        session_store.update_draft(request.session_id, draft_text, version, title=title)
        
        return DraftResponse(
            success=True,
            session_id=request.session_id,
            draft_text=draft_text,
            title=title,
            version=version,
            message="Bozza modificata con successo",
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Errore nella modifica della bozza: {str(e)}"
        )


@app.post("/api/draft/validate", response_model=DraftValidationResponse)
async def validate_draft_endpoint(request: DraftValidationRequest):
    """Valida la bozza finale."""
    try:
        session_store = get_session_store()
        session = await get_session_async(session_store, request.session_id)
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Sessione {request.session_id} non trovata"
            )
        
        if not session.current_draft:
            raise HTTPException(
                status_code=400,
                detail="Nessuna bozza da validare"
            )
        
        if request.validated:
            session_store.validate_session(request.session_id)
            # Log per debug
            print(f"[DEBUG] Bozza validata per sessione {request.session_id}")
            print(f"[DEBUG] Draft presente: {bool(session.current_draft)}")
            print(f"[DEBUG] Titolo: {session.current_title}")
            return DraftValidationResponse(
                success=True,
                session_id=request.session_id,
                message="Bozza validata con successo. Pronto per la fase di scrittura.",
            )
        else:
            return DraftValidationResponse(
                success=False,
                session_id=request.session_id,
                message="Validazione annullata.",
            )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Errore nella validazione della bozza: {str(e)}"
        )


@app.get("/api/draft/{session_id}", response_model=DraftResponse)
async def get_draft_endpoint(session_id: str):
    """Recupera la bozza corrente di una sessione."""
    try:
        session_store = get_session_store()
        session = await get_session_async(session_store, session_id)
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Sessione {session_id} non trovata"
            )
        
        if not session.current_draft:
            raise HTTPException(
                status_code=404,
                detail="Nessuna bozza disponibile per questa sessione"
            )
        
        return DraftResponse(
            success=True,
            session_id=session_id,
            draft_text=session.current_draft,
            title=session.current_title,
            version=session.current_version,
            message="Bozza recuperata con successo",
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Errore nel recupero della bozza: {str(e)}"
        )


@app.post("/api/outline/generate", response_model=OutlineResponse)
async def generate_outline_endpoint(request: OutlineGenerateRequest):
    """Genera la struttura/indice del libro basandosi sulla bozza validata."""
    try:
        # Verifica che l'API key sia configurata
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="GOOGLE_API_KEY non configurata. Verifica il file .env nella root del progetto."
            )
        
        # Recupera la sessione
        session_store = get_session_store()
        session = await get_session_async(session_store, request.session_id)
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Sessione {request.session_id} non trovata"
            )
        
        if not session.current_draft:
            raise HTTPException(
                status_code=400,
                detail="Nessuna bozza validata disponibile. Valida prima la bozza estesa."
            )
        
        if not session.validated:
            raise HTTPException(
                status_code=400,
                detail="La bozza deve essere validata prima di generare la struttura."
            )
        
        # Genera l'outline
        print(f"[DEBUG OUTLINE] Inizio generazione outline per sessione {request.session_id}")
        print(f"[DEBUG OUTLINE] Draft length: {len(session.current_draft) if session.current_draft else 0}")
        print(f"[DEBUG OUTLINE] Titolo: {session.current_title}")
        
        outline_text = await generate_outline(
            form_data=session.form_data,
            question_answers=session.question_answers,
            validated_draft=session.current_draft,
            session_id=request.session_id,
            draft_title=session.current_title,
            api_key=api_key,
        )
        
        print(f"[DEBUG OUTLINE] Outline generato, length: {len(outline_text) if outline_text else 0}")
        print(f"[DEBUG OUTLINE] Preview: {outline_text[:200] if outline_text else 'None'}...")
        
        # Salva l'outline nella sessione
        session_store.update_outline(request.session_id, outline_text)
        print(f"[DEBUG OUTLINE] Outline salvato nella sessione")
        
        return OutlineResponse(
            success=True,
            session_id=request.session_id,
            outline_text=outline_text,
            version=session.outline_version,
            message="Struttura generata con successo",
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Errore nella generazione della struttura: {str(e)}"
        )


@app.get("/api/outline/{session_id}", response_model=OutlineResponse)
async def get_outline_endpoint(session_id: str):
    """Recupera la struttura corrente di una sessione."""
    try:
        session_store = get_session_store()
        session = await get_session_async(session_store, session_id)
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Sessione {session_id} non trovata"
            )
        
        if not session.current_outline:
            raise HTTPException(
                status_code=404,
                detail="Nessuna struttura disponibile per questa sessione"
            )
        
        return OutlineResponse(
            success=True,
            session_id=session_id,
            outline_text=session.current_outline,
            version=session.outline_version,
            message="Struttura recuperata con successo",
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Errore nel recupero della struttura: {str(e)}"
        )


@app.post("/api/outline/update", response_model=OutlineResponse)
async def update_outline_endpoint(request: OutlineUpdateRequest):
    """Aggiorna l'outline con sezioni modificate dall'utente."""
    try:
        session_store = get_session_store()
        session = await get_session_async(session_store, request.session_id)
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Sessione {request.session_id} non trovata"
            )
        
        if not session.current_outline:
            raise HTTPException(
                status_code=400,
                detail="Nessun outline esistente da modificare. Genera prima la struttura."
            )
        
        # Valida le sezioni
        if not request.sections or len(request.sections) == 0:
            raise HTTPException(
                status_code=400,
                detail="La lista di sezioni non può essere vuota"
            )
        
        # Valida che ogni sezione abbia un titolo
        for i, section in enumerate(request.sections):
            if not section.title or not section.title.strip():
                raise HTTPException(
                    status_code=400,
                    detail=f"La sezione {i+1} non può avere un titolo vuoto"
                )
        
        # Converti le sezioni in dizionari per regenerate_outline_markdown
        sections_dict = [
            {
                "title": s.title,
                "description": s.description,
                "level": s.level,
                "section_index": s.section_index,
            }
            for s in request.sections
        ]
        
        # Rigenera il markdown dall'array di sezioni
        try:
            updated_outline_text = regenerate_outline_markdown(sections_dict)
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Errore nella generazione del markdown: {str(e)}"
            )
        
        # Salva l'outline modificato (non permettere se writing già iniziato)
        try:
            session_store.update_outline(request.session_id, updated_outline_text, allow_if_writing=False)
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=str(e)
            )
        
        # Recupera la sessione aggiornata per avere la versione corretta
        session = await get_session_async(session_store, request.session_id)
        
        return OutlineResponse(
            success=True,
            session_id=request.session_id,
            outline_text=updated_outline_text,
            version=session.outline_version,
            message="Struttura aggiornata con successo",
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Errore nell'aggiornamento della struttura: {str(e)}"
        )


@app.get("/api/pdf/{session_id}")
async def download_pdf_endpoint(session_id: str):
    """Genera e scarica un PDF con tutte le informazioni del romanzo."""
    try:
        print(f"[DEBUG PDF] Richiesta PDF per sessione: {session_id}")
        session_store = get_session_store()
        session = await get_session_async(session_store, session_id)
        
        if not session:
            print(f"[DEBUG PDF] Sessione {session_id} non trovata")
            raise HTTPException(
                status_code=404,
                detail=f"Sessione {session_id} non trovata"
            )
        
        print(f"[DEBUG PDF] Sessione trovata, draft: {bool(session.current_draft)}, outline: {bool(session.current_outline)}")
        
        # Crea il PDF in memoria
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        story = []
        styles = getSampleStyleSheet()
        
        # Stile per i titoli
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor='#213547',
            spaceAfter=12,
            alignment=TA_CENTER,
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor='#213547',
            spaceAfter=10,
            spaceBefore=12,
        )
        
        # Titolo del documento
        if session.current_title:
            story.append(Paragraph(session.current_title, title_style))
        else:
            story.append(Paragraph("Romanzo", title_style))
        
        if session.form_data.user_name:
            story.append(Paragraph(f"Autore: {session.form_data.user_name}", styles['Normal']))
        
        story.append(Spacer(1, 0.3*inch))
        story.append(Paragraph("=" * 50, styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
        
        # Configurazione iniziale
        story.append(Paragraph("Configurazione Iniziale", heading_style))
        
        config_lines = []
        config_lines.append(f"<b>Modello LLM:</b> {session.form_data.llm_model}")
        config_lines.append(f"<b>Trama iniziale:</b> {session.form_data.plot}")
        
        optional_fields = {
            "Genere": session.form_data.genre,
            "Sottogenere": session.form_data.subgenre,
            "Tema": session.form_data.theme,
            "Protagonista": session.form_data.protagonist,
            "Arco del personaggio": session.form_data.character_arc,
            "Punto di vista": session.form_data.point_of_view,
            "Voce narrante": session.form_data.narrative_voice,
            "Stile": session.form_data.style,
            "Struttura temporale": session.form_data.temporal_structure,
            "Ritmo": session.form_data.pace,
            "Realismo": session.form_data.realism,
            "Ambiguità": session.form_data.ambiguity,
            "Intenzionalità": session.form_data.intentionality,
            "Autore di riferimento": session.form_data.author,
        }
        
        for label, value in optional_fields.items():
            if value:
                config_lines.append(f"<b>{label}:</b> {value}")
        
        for line in config_lines:
            story.append(Paragraph(line, styles['Normal']))
            story.append(Spacer(1, 0.1*inch))
        
        # Risposte alle domande
        if session.question_answers:
            story.append(PageBreak())
            story.append(Paragraph("Risposte alle Domande Preliminari", heading_style))
            for qa in session.question_answers:
                if qa.answer:
                    story.append(Paragraph(f"<b>Domanda:</b> {qa.question_id}", styles['Normal']))
                    story.append(Paragraph(f"<b>Risposta:</b> {qa.answer}", styles['Normal']))
                    story.append(Spacer(1, 0.15*inch))
        
        # Bozza estesa validata
        if session.current_draft:
            story.append(PageBreak())
            story.append(Paragraph("Bozza Estesa della Trama", heading_style))
            # Converti markdown base a testo semplice per il PDF
            draft_text = session.current_draft
            # Rimuovi markdown base (##, **, etc.) per semplicità
            draft_text = draft_text.replace("## ", "").replace("### ", "")
            draft_text = draft_text.replace("**", "").replace("*", "")
            # Dividi in paragrafi
            paragraphs = draft_text.split("\n\n")
            for para in paragraphs:
                if para.strip():
                    story.append(Paragraph(para.strip(), styles['Normal']))
                    story.append(Spacer(1, 0.15*inch))
        
        # Struttura/Indice
        if session.current_outline:
            story.append(PageBreak())
            story.append(Paragraph("Struttura del Romanzo", heading_style))
            # Converti markdown base a testo semplice
            outline_text = session.current_outline
            outline_text = outline_text.replace("## ", "").replace("### ", "")
            outline_text = outline_text.replace("**", "").replace("*", "")
            paragraphs = outline_text.split("\n\n")
            for para in paragraphs:
                if para.strip():
                    story.append(Paragraph(para.strip(), styles['Normal']))
                    story.append(Spacer(1, 0.15*inch))
        
        # Costruisci il PDF
        doc.build(story)
        buffer.seek(0)
        
        # Nome file
        if session.current_title:
            filename = "".join(c for c in session.current_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
            filename = filename.replace(" ", "_")
        else:
            filename = f"Romanzo_{session_id[:8]}"
        filename = f"{filename}.pdf"
        
        return Response(
            content=buffer.getvalue(),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Errore nella generazione del PDF: {str(e)}"
        )


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


@app.get("/api/book/pdf/{session_id}")
async def download_book_pdf_endpoint(
    session_id: str,
    current_user = Depends(get_current_user_optional),
):
    """Genera e scarica un PDF del libro completo con titolo, indice e capitoli usando WeasyPrint."""
    try:
        print(f"[BOOK PDF] Richiesta PDF libro completo per sessione: {session_id}")
        session_store = get_session_store()
        user_id = current_user.id if current_user else None
        session = await get_session_async(session_store, session_id, user_id=user_id)
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Sessione {session_id} non trovata"
            )
        
        # Verifica accesso: ownership o condivisione accettata
        if current_user and session.user_id and session.user_id != current_user.id:
            # Verifica se l'utente ha accesso tramite condivisione
            from app.agent.book_share_store import get_book_share_store
            book_share_store = get_book_share_store()
            await book_share_store.connect()
            has_access = await book_share_store.check_user_has_access(
                book_session_id=session_id,
                user_id=current_user.id,
                owner_id=session.user_id,
            )
            if not has_access:
                raise HTTPException(
                    status_code=403,
                    detail="Accesso negato: questa sessione appartiene a un altro utente o non hai accesso"
                )
        
        if not session.writing_progress or not session.writing_progress.get('is_complete'):
            raise HTTPException(
                status_code=400,
                detail="Il libro non è ancora completo. Attendi il completamento della scrittura."
            )
        
        if not session.book_chapters or len(session.book_chapters) == 0:
            raise HTTPException(
                status_code=400,
                detail="Nessun capitolo trovato nel libro."
            )
        
        # Prepara dati libro
        book_title = session.current_title or "Romanzo"
        book_author = session.form_data.user_name or "Autore"
        
        print(f"[BOOK PDF] Generazione PDF con WeasyPrint per: {book_title}")
        
        # Leggi il file CSS
        css_path = Path(__file__).parent / "static" / "book_styles.css"
        if not css_path.exists():
            raise Exception(f"File CSS non trovato: {css_path}")
        
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()
        
        print(f"[BOOK PDF] CSS caricato da: {css_path}")
        
        # Prepara immagine copertina
        cover_image_data = None
        cover_image_mime = None
        cover_image_path_for_html = None
        cover_image_width = None
        cover_image_height = None
        cover_image_style = None
        
        print(f"[BOOK PDF] Verifica copertina - cover_image_path nella sessione: {session.cover_image_path}")
        
        if session.cover_image_path:
            try:
                storage_service = get_storage_service()
                print(f"[BOOK PDF] Caricamento copertina da: {session.cover_image_path}")
                image_bytes = storage_service.download_file(session.cover_image_path)
                print(f"[BOOK PDF] Immagine copertina caricata: {len(image_bytes)} bytes")
                
                # Leggi dimensioni originali dell'immagine con PIL da bytes
                with PILImage.open(BytesIO(image_bytes)) as img:
                    cover_image_width, cover_image_height = img.size
                    print(f"[BOOK PDF] Dimensioni originali immagine: {cover_image_width} x {cover_image_height}")
                    print(f"[BOOK PDF] Proporzioni: {cover_image_width / cover_image_height:.3f}")
                
                # Determina MIME type dal path
                cover_path_str = session.cover_image_path.lower()
                if '.png' in cover_path_str:
                    cover_image_mime = 'image/png'
                elif '.jpg' in cover_path_str or '.jpeg' in cover_path_str:
                    cover_image_mime = 'image/jpeg'
                else:
                    cover_image_mime = 'image/png'  # Default
                
                # Calcola dimensioni per A4 (595.276pt x 841.890pt) mantenendo proporzioni
                # A4 ratio: 841.890 / 595.276 = 1.414 (circa)
                a4_width_pt = 595.276
                a4_height_pt = 841.890
                a4_ratio = a4_height_pt / a4_width_pt
                image_ratio = cover_image_height / cover_image_width
                
                print(f"[BOOK PDF] Ratio A4: {a4_ratio:.3f}, Ratio immagine: {image_ratio:.3f}")
                
                # Se l'immagine è più larga che alta rispetto ad A4, usa width: 100%
                # Se l'immagine è più alta che larga rispetto ad A4, usa height: 100%
                if image_ratio > a4_ratio:
                    # Immagine più alta: usa height: 100%, width: auto
                    cover_image_style = "width: auto; height: 100%;"
                    print(f"[BOOK PDF] Immagine più alta di A4, uso height: 100%, width: auto")
                else:
                    # Immagine più larga o simile: usa width: 100%, height: auto
                    cover_image_style = "width: 100%; height: auto;"
                    print(f"[BOOK PDF] Immagine più larga di A4, uso width: 100%, height: auto")
                
                # Converti i bytes in base64 per l'HTML
                cover_image_data = base64.b64encode(image_bytes).decode('utf-8')
                print(f"[BOOK PDF] Immagine copertina caricata, MIME: {cover_image_mime}")
                print(f"[BOOK PDF] Base64 generato: {len(cover_image_data)} caratteri")
            except Exception as e:
                print(f"[BOOK PDF] Errore nel caricamento copertina: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"[BOOK PDF] Nessuna copertina disponibile (path: {session.cover_image_path})")
        
        # Ordina i capitoli per section_index
        sorted_chapters = sorted(session.book_chapters, key=lambda x: x.get('section_index', 0))
        
        # Prepara HTML per indice - usa div invece di li per garantire andata a capo
        toc_items = []
        for idx, chapter in enumerate(sorted_chapters, 1):
            chapter_title = chapter.get('title', f'Capitolo {idx}')
            toc_items.append(f'<div class="toc-item">{idx}. {escape_html(chapter_title)}</div>')
        
        toc_html = '\n            '.join(toc_items)
        
        # Prepara HTML per capitoli
        chapters_html = []
        for idx, chapter in enumerate(sorted_chapters, 1):
            chapter_title = chapter.get('title', f'Capitolo {idx}')
            chapter_content = chapter.get('content', '')
            
            # Converti markdown a HTML
            content_html = markdown_to_html(chapter_content)
            
            chapters_html.append(f'''    <div class="chapter">
        <h1 class="chapter-title">{escape_html(chapter_title)}</h1>
        <div class="chapter-content">
            {content_html}
        </div>
    </div>''')
        
        chapters_html_str = '\n\n'.join(chapters_html)
        
        # Genera HTML completo
        cover_section = ''
        # Usa lo stile calcolato per mantenere le proporzioni
        image_style = cover_image_style or "width: 100%; height: auto;"
        container_style = "width: 595.276pt; height: 841.890pt; margin: 0; padding: 0; position: relative; overflow: hidden; display: flex; align-items: center; justify-content: center;"
        
        # Usa base64 per la copertina (funziona sia per file locali che GCS)
        if cover_image_data and cover_image_mime:
            cover_section = f'''    <!-- Copertina -->
    <div class="cover-page" style="{container_style}">
        <img src="data:{cover_image_mime};base64,{cover_image_data}" class="cover-image" alt="Copertina" style="{image_style} margin: 0; padding: 0; display: block;">
    </div>
    <div style="page-break-after: always;"></div>'''
            print(f"[BOOK PDF] Copertina aggiunta con base64, stile: {image_style}")
        
        html_content = f'''<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{escape_html(book_title)}</title>
    <style>
        {css_content}
    </style>
</head>
<body>
    <div class="content-wrapper">
{cover_section}
        
        <!-- Indice -->
        <div class="table-of-contents">
            <h1>Indice</h1>
            <div class="toc-list">
                {toc_html}
            </div>
        </div>
        
        <!-- Capitoli -->
{chapters_html_str}
    </div>
</body>
</html>'''
        
        print(f"[BOOK PDF] HTML generato, lunghezza: {len(html_content)} caratteri")
        
        # Genera PDF con xhtml2pdf
        print(f"[BOOK PDF] Generazione PDF con xhtml2pdf...")
        buffer = BytesIO()
        
        try:
            # xhtml2pdf genera PDF direttamente da HTML+CSS
            result = pisa.CreatePDF(
                src=html_content,
                dest=buffer,
                encoding='utf-8'
            )
            
            if result.err:
                raise Exception(f"Errore nella generazione PDF: {result.err}")
            
            print(f"[BOOK PDF] PDF generato con successo")
        except Exception as e:
            print(f"[BOOK PDF] Errore nella generazione PDF con xhtml2pdf: {e}")
            import traceback
            traceback.print_exc()
            raise
        
        buffer.seek(0)
        pdf_content = buffer.getvalue()
        
        # Nome file con data, modello e titolo (formato: YYYY-MM-DD_g3p_TitoloLibro.pdf)
        date_prefix = datetime.now().strftime("%Y-%m-%d")
        model_abbrev = get_model_abbreviation(session.form_data.llm_model)
        title_sanitized = "".join(c for c in book_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        title_sanitized = title_sanitized.replace(" ", "_")
        if not title_sanitized:
            title_sanitized = f"Libro_{session_id[:8]}"
        filename = f"{date_prefix}_{model_abbrev}_{title_sanitized}.pdf"
        
        # Salva PDF su GCS o locale tramite StorageService
        try:
            storage_service = get_storage_service()
            user_id = session.user_id if hasattr(session, 'user_id') else None
            gcs_path = storage_service.upload_file(
                data=pdf_content,
                destination_path=f"books/{filename}",
                content_type="application/pdf",
                user_id=user_id,
            )
            print(f"[BOOK PDF] PDF salvato: {gcs_path}")
        except Exception as e:
            print(f"[BOOK PDF] Errore nel salvataggio PDF: {e}")
            import traceback
            traceback.print_exc()
            # Non blocchiamo il download HTTP se il salvataggio fallisce
        
        return Response(
            content=pdf_content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[BOOK PDF] ERRORE nella generazione del PDF: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nella generazione del PDF del libro: {str(e)}"
        )


@app.get("/api/book/export/{session_id}")
async def export_book_endpoint(
    session_id: str,
    format: str = "pdf",
    current_user = Depends(get_current_user_optional),
):
    """
    Genera e scarica il libro in diversi formati: PDF, EPUB o DOCX.
    
    Args:
        session_id: ID della sessione del libro
        format: Formato di export ("pdf", "epub", "docx"), default "pdf"
    
    Returns:
        File Response con il libro nel formato richiesto
    """
    try:
        print(f"[BOOK EXPORT] Richiesta export {format} per sessione: {session_id}")
        session_store = get_session_store()
        user_id = current_user.id if current_user else None
        session = await get_session_async(session_store, session_id, user_id=user_id)
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Sessione {session_id} non trovata"
            )
        
        # Verifica accesso: ownership o condivisione accettata
        if current_user and session.user_id and session.user_id != current_user.id:
            # Verifica se l'utente ha accesso tramite condivisione
            from app.agent.book_share_store import get_book_share_store
            book_share_store = get_book_share_store()
            await book_share_store.connect()
            has_access = await book_share_store.check_user_has_access(
                book_session_id=session_id,
                user_id=current_user.id,
                owner_id=session.user_id,
            )
            if not has_access:
                raise HTTPException(
                    status_code=403,
                    detail="Accesso negato: questa sessione appartiene a un altro utente o non hai accesso"
                )
        
        if not session.writing_progress or not session.writing_progress.get('is_complete'):
            raise HTTPException(
                status_code=400,
                detail="Il libro non è ancora completo. Attendi il completamento della scrittura."
            )
        
        if not session.book_chapters or len(session.book_chapters) == 0:
            raise HTTPException(
                status_code=400,
                detail="Nessun capitolo trovato nel libro."
            )
        
        format_lower = format.lower()
        
        # Genera il file nel formato richiesto
        if format_lower == "pdf":
            file_content, filename = generate_complete_book_pdf(session)
            media_type = "application/pdf"
        elif format_lower == "epub":
            file_content, filename = generate_epub(session)
            media_type = "application/epub+zip"
        elif format_lower == "docx":
            file_content, filename = generate_docx(session)
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Formato non supportato: {format}. Formati supportati: pdf, epub, docx"
            )
        
        print(f"[BOOK EXPORT] File {format} generato con successo: {filename}")
        
        return Response(
            content=file_content,
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[BOOK EXPORT] ERRORE nella generazione del file {format}: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nella generazione del file {format}: {str(e)}"
        )


@app.get("/api/files/{tipo}/{filename}")
async def get_file_endpoint(tipo: str, filename: str):
    """
    Genera un URL firmato temporaneo per accedere a un file su GCS.
    
    Args:
        tipo: Tipo di file ("books" o "covers")
        filename: Nome del file
    
    Returns:
        Redirect all'URL firmato GCS o file locale
    """
    try:
        storage_service = get_storage_service()
        
        if tipo not in ["books", "covers"]:
            raise HTTPException(
                status_code=400,
                detail=f"Tipo non valido: {tipo}. Tipi supportati: books, covers"
            )
        
        # Costruisci il path
        if storage_service.gcs_enabled:
            gcs_path = f"gs://{storage_service.bucket_name}/{tipo}/{filename}"
        else:
            # Fallback locale
            if tipo == "books":
                local_path = Path(__file__).parent.parent / "books" / filename
            else:  # covers
                local_path = Path(__file__).parent.parent / "sessions" / filename
            
            if not local_path.exists():
                raise HTTPException(
                    status_code=404,
                    detail=f"File non trovato: {filename}"
                )
            
            # Per locale, restituisci il file direttamente
            return FileResponse(
                path=str(local_path),
                filename=filename,
                media_type="application/pdf" if filename.endswith(".pdf") else "image/png"
            )
        
        # Verifica che il file esista
        if not storage_service.file_exists(gcs_path):
            raise HTTPException(
                status_code=404,
                detail=f"File non trovato: {filename}"
            )
        
        # Genera URL firmato (valido 15 minuti)
        signed_url = storage_service.get_signed_url(gcs_path, expiration_minutes=15)
        
        # Redirect all'URL firmato
        return RedirectResponse(url=signed_url, status_code=307)
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[GET FILE] Errore nel recupero file: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nel recupero del file: {str(e)}"
        )


@app.post("/api/book/critique/{session_id}")
async def regenerate_book_critique_endpoint(
    session_id: str,
    current_user = Depends(get_current_user_optional),
):
    """
    Rigenera la valutazione critica usando come input il PDF finale del libro.
    Utile per test e per rigenerare in caso di errore.
    """
    session_store = get_session_store()
    user_id = current_user.id if current_user else None
    session = await get_session_async(session_store, session_id, user_id=user_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Sessione {session_id} non trovata")
    
    if current_user and session.user_id and session.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Accesso negato: questa sessione appartiene a un altro utente"
        )

    if not session.writing_progress or not session.writing_progress.get("is_complete"):
        raise HTTPException(status_code=400, detail="Il libro non è ancora completo.")

    # Genera/recupera PDF (salvato anche su disco da download_book_pdf_endpoint)
    try:
        await update_critique_status_async(session_store, session_id, "running", error=None)
        pdf_response = await download_book_pdf_endpoint(session_id, current_user=None)
        pdf_bytes = getattr(pdf_response, "body", None) or getattr(pdf_response, "content", None)
        if not isinstance(pdf_bytes, (bytes, bytearray)) or len(pdf_bytes) == 0:
            raise ValueError("PDF bytes non disponibili.")
    except Exception as e:
        await update_critique_status_async(session_store, session_id, "failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Errore nel generare il PDF per la critica: {e}")

    api_key = os.getenv("GOOGLE_API_KEY")
    try:
        critique = await generate_literary_critique_from_pdf(
            title=session.current_title or "Romanzo",
            author=session.form_data.user_name or "Autore",
            pdf_bytes=bytes(pdf_bytes),
            api_key=api_key,
        )
    except Exception as e:
        await update_critique_status_async(session_store, session_id, "failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Errore nella generazione della critica: {e}")

    await update_critique_async(session_store, session_id, critique)
    return critique


@app.post("/api/critique/audio/{session_id}")
async def generate_critique_audio_endpoint(
    session_id: str,
    voice_name: Optional[str] = None,  # Default: it-IT-Standard-A (voce italiana femminile)
    current_user = Depends(get_current_user_optional),
):
    """
    Genera audio MP3 della critica letteraria usando Google Cloud Text-to-Speech.
    Restituisce un file MP3 che può essere riprodotto nel browser.
    """
    try:
        from google.cloud import texttospeech
        
        session_store = get_session_store()
        user_id = current_user.id if current_user else None
        session = await get_session_async(session_store, session_id, user_id=user_id)
        
        if not session:
            raise HTTPException(status_code=404, detail=f"Sessione {session_id} non trovata")
        
        if current_user and session.user_id and session.user_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="Accesso negato: questa sessione appartiene a un altro utente"
            )
        
        if not session.literary_critique:
            raise HTTPException(status_code=404, detail="Critica non disponibile per questo libro")
        
        # Converti critica in LiteraryCritique se è un dict
        critique = session.literary_critique
        if isinstance(critique, dict):
            critique = LiteraryCritique(**critique)
        
        # Costruisci testo completo per la sintesi vocale
        text_parts = []
        
        if critique.summary:
            text_parts.append(f"Sintesi: {critique.summary}")
        
        if critique.pros and len(critique.pros) > 0:
            pros_text = ". ".join(critique.pros)
            text_parts.append(f"Punti di forza: {pros_text}")
        
        if critique.cons and len(critique.cons) > 0:
            cons_text = ". ".join(critique.cons)
            text_parts.append(f"Punti di debolezza: {cons_text}")
        
        if not text_parts:
            raise HTTPException(status_code=400, detail="Critica vuota, nessun contenuto da leggere")
        
        full_text = ". ".join(text_parts)
        
        # Limita la lunghezza del testo (Google TTS ha un limite di ~5000 caratteri per richiesta)
        max_chars = 4500  # Lascia margine per sicurezza
        if len(full_text) > max_chars:
            full_text = full_text[:max_chars] + "..."
            print(f"[CRITIQUE AUDIO] Testo troncato a {max_chars} caratteri", file=sys.stderr)
        
        # Configurazione voce italiana (default: femminile)
        if not voice_name:
            voice_name = "it-IT-Standard-A"  # Voce italiana femminile standard
        
        # Inizializza client Google Cloud Text-to-Speech
        # Usa le credenziali da GOOGLE_APPLICATION_CREDENTIALS o da variabili d'ambiente
        try:
            # Correggi path credenziali se relativo (stessa logica di StorageService)
            cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            
            # Se non è impostata, prova a usare il file di credenziali di default
            if not cred_path:
                root_dir = Path(__file__).parent.parent.parent
                default_cred_path = root_dir / "credentials" / "narrai-app-credentials.json"
                if default_cred_path.exists():
                    cred_path = str(default_cred_path)
                    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = cred_path
                    print(f"[CRITIQUE AUDIO] Usando credenziali di default: {cred_path}", file=sys.stderr)
                else:
                    print(f"[CRITIQUE AUDIO] WARNING: Nessuna credenziale trovata. Cerca GOOGLE_APPLICATION_CREDENTIALS o credentials/narrai-app-credentials.json", file=sys.stderr)
            elif not Path(cred_path).is_absolute():
                # Converti path relativo in assoluto rispetto alla root del progetto
                root_dir = Path(__file__).parent.parent.parent
                abs_cred_path = (root_dir / cred_path.lstrip("./")).resolve()
                if abs_cred_path.exists():
                    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(abs_cred_path)
                    print(f"[CRITIQUE AUDIO] Credenziali caricate da: {abs_cred_path}", file=sys.stderr)
                else:
                    print(f"[CRITIQUE AUDIO] WARNING: Path credenziali non trovato: {abs_cred_path}", file=sys.stderr)
            else:
                if Path(cred_path).exists():
                    print(f"[CRITIQUE AUDIO] Credenziali caricate da: {cred_path}", file=sys.stderr)
                else:
                    print(f"[CRITIQUE AUDIO] WARNING: Path credenziali non trovato: {cred_path}", file=sys.stderr)
            
            client = texttospeech.TextToSpeechClient()
            print(f"[CRITIQUE AUDIO] Client TTS inizializzato con successo", file=sys.stderr)
        except Exception as e:
            error_str = str(e)
            print(f"[CRITIQUE AUDIO] Errore nell'inizializzazione client TTS: {error_str}", file=sys.stderr)
            
            # Gestisci errori specifici con messaggi user-friendly
            if "SERVICE_DISABLED" in error_str or "has not been used" in error_str or "it is disabled" in error_str:
                project_id = "274471015864"
                import re
                project_match = re.search(r'project[:\s]+(\d+)', error_str, re.IGNORECASE)
                if project_match:
                    project_id = project_match.group(1)
                
                raise HTTPException(
                    status_code=503,
                    detail=f"L'API Text-to-Speech non è abilitata nel progetto Google Cloud. Per abilitarla, visita: https://console.cloud.google.com/apis/library/texttospeech.googleapis.com?project={project_id} e clicca su 'Abilita'. Dopo l'abilitazione, attendi alcuni minuti prima di riprovare."
                )
            elif "403" in error_str or "permission" in error_str.lower() or "forbidden" in error_str.lower():
                raise HTTPException(
                    status_code=403,
                    detail="Permessi insufficienti per utilizzare il servizio Text-to-Speech. Verifica che il service account abbia il ruolo 'Cloud Text-to-Speech API User'."
                )
            elif "401" in error_str or "unauthorized" in error_str.lower() or "invalid credentials" in error_str.lower():
                raise HTTPException(
                    status_code=401,
                    detail="Credenziali Google Cloud non valide o scadute. Verifica il file di credenziali."
                )
            else:
                raise HTTPException(
                    status_code=500,
                    detail="Errore nella configurazione del servizio di sintesi vocale. Verifica le credenziali Google Cloud."
                )
        
        # Configura sintesi vocale
        synthesis_input = texttospeech.SynthesisInput(text=full_text)
        
        # Seleziona voce italiana
        voice = texttospeech.VoiceSelectionParams(
            language_code="it-IT",
            name=voice_name,
            ssml_gender=texttospeech.SsmlVoiceGender.FEMALE,
        )
        
        # Configurazione audio: MP3, velocità normale, tono normale
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=1.0,  # Velocità normale (1.0 = 100%)
            pitch=0.0,  # Tono normale
            volume_gain_db=0.0,  # Volume normale
        )
        
        # Genera audio
        try:
            response = client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config,
            )
            
            print(f"[CRITIQUE AUDIO] Audio generato con successo per sessione {session_id} ({len(response.audio_content)} bytes)", file=sys.stderr)
            
        except Exception as e:
            error_str = str(e)
            print(f"[CRITIQUE AUDIO] Errore nella sintesi vocale: {error_str}", file=sys.stderr)
            
            # Gestisci errori specifici con messaggi user-friendly
            if "SERVICE_DISABLED" in error_str or "has not been used" in error_str or "it is disabled" in error_str:
                # Estrai project ID se presente
                project_id = "274471015864"  # Default, può essere estratto dall'errore se necessario
                if "project" in error_str.lower():
                    import re
                    project_match = re.search(r'project[:\s]+(\d+)', error_str, re.IGNORECASE)
                    if project_match:
                        project_id = project_match.group(1)
                
                raise HTTPException(
                    status_code=503,
                    detail=f"L'API Text-to-Speech non è abilitata nel progetto Google Cloud. Per abilitarla, visita: https://console.cloud.google.com/apis/library/texttospeech.googleapis.com?project={project_id} e clicca su 'Abilita'. Dopo l'abilitazione, attendi alcuni minuti prima di riprovare."
                )
            elif "403" in error_str or "permission" in error_str.lower() or "forbidden" in error_str.lower():
                raise HTTPException(
                    status_code=403,
                    detail="Permessi insufficienti per utilizzare il servizio Text-to-Speech. Verifica che il service account abbia il ruolo 'Cloud Text-to-Speech API User'."
                )
            elif "401" in error_str or "unauthorized" in error_str.lower() or "invalid credentials" in error_str.lower():
                raise HTTPException(
                    status_code=401,
                    detail="Credenziali Google Cloud non valide o scadute. Verifica il file di credenziali e che sia configurato correttamente."
                )
            else:
                # Per altri errori, mostra un messaggio generico ma utile
                raise HTTPException(
                    status_code=500,
                    detail=f"Errore nella generazione dell'audio. Se il problema persiste, verifica la configurazione di Google Cloud Text-to-Speech."
                )
        
        # Restituisci come file MP3
        return Response(
            content=response.audio_content,
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": f'attachment; filename="critique_{session_id}.mp3"',
                "Cache-Control": "public, max-age=3600",  # Cache per 1 ora
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[CRITIQUE AUDIO] Errore generico: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nella generazione audio: {str(e)}"
        )


@app.get("/health")
async def health():
    """Endpoint di health check."""
    return {"status": "ok"}


@app.get("/api/ping")
async def ping():
    """Endpoint di diagnostica per verificare se il backend è attivo e aggiornato."""
    return {
        "status": "pong",
        "version": "0.1.1",
        "routes": [route.path for route in app.routes]
    }


async def background_book_generation(
    session_id: str,
    form_data: SubmissionRequest,
    question_answers: list[QuestionAnswer],
    validated_draft: str,
    draft_title: Optional[str],
    outline_text: str,
    api_key: str,
):
    """Funzione eseguita in background per generare il libro completo."""
    session_store = get_session_store()
    try:
        print(f"[BOOK GENERATION] Avvio generazione libro per sessione {session_id}")
        
        # Verifica che il progresso sia stato inizializzato
        session = await get_session_async(session_store, session_id)
        if not session or not session.writing_progress:
            print(f"[BOOK GENERATION] WARNING: Progresso non inizializzato per sessione {session_id}, inizializzo ora...")
            # Fallback: inizializza il progresso se non è stato fatto
            sections = parse_outline_sections(outline_text)
            await update_writing_progress_async(
                session_store,
                session_id=session_id,
                current_step=0,
                total_steps=len(sections),
                current_section_name=sections[0]['title'] if sections else None,
                is_complete=False,
                is_paused=False,
            )
        
        # Registra timestamp inizio scrittura capitoli
        start_time = datetime.now()
        await update_writing_times_async(session_store, session_id, start_time=start_time)
        print(f"[BOOK GENERATION] Timestamp inizio scrittura: {start_time.isoformat()}")
        
        await generate_full_book(
            session_id=session_id,
            form_data=form_data,
            question_answers=question_answers,
            validated_draft=validated_draft,
            draft_title=draft_title,
            outline_text=outline_text,
            api_key=api_key,
        )
        
        # Verifica se la generazione è stata messa in pausa
        session = await get_session_async(session_store, session_id)
        if session and session.writing_progress and session.writing_progress.get('is_paused', False):
            print(f"[BOOK GENERATION] Generazione messa in pausa per sessione {session_id}")
            # Non continuare con copertina e critica se è in pausa
            return
        
        print(f"[BOOK GENERATION] Generazione completata per sessione {session_id}")
        
        # Registra timestamp fine scrittura capitoli e calcola tempo
        end_time = datetime.now()
        await update_writing_times_async(session_store, session_id, end_time=end_time)
        writing_time_minutes = (end_time - start_time).total_seconds() / 60
        print(f"[BOOK GENERATION] Timestamp fine scrittura: {end_time.isoformat()}, tempo totale: {writing_time_minutes:.2f} minuti")
        
        # Aggiorna writing_progress con il tempo calcolato
        session = await get_session_async(session_store, session_id)
        if session and session.writing_progress:
            # Mantieni tutti i valori esistenti e aggiungi writing_time_minutes
            existing_progress = session.writing_progress.copy()
            existing_progress['writing_time_minutes'] = writing_time_minutes
            await update_writing_progress_async(
                session_store,
                session_id=session_id,
                current_step=existing_progress.get('current_step', 0),
                total_steps=existing_progress.get('total_steps', 0),
                current_section_name=existing_progress.get('current_section_name'),
                is_complete=existing_progress.get('is_complete', True),
                is_paused=False,
                error=existing_progress.get('error'),
            )
            # Aggiorna manualmente writing_time_minutes nel dict (update_writing_progress non lo gestisce)
            session.writing_progress['writing_time_minutes'] = writing_time_minutes
            # FileSessionStore salverà automaticamente al prossimo update o possiamo forzare il salvataggio
            if hasattr(session_store, '_save_sessions'):
                session_store._save_sessions()
        
        # Genera la copertina dopo che il libro è stato completato
        try:
            print(f"[BOOK GENERATION] Avvio generazione copertina per sessione {session_id}")
            session = await get_session_async(session_store, session_id)
            if session:
                cover_path = await generate_book_cover(
                    session_id=session_id,
                    title=draft_title or "Romanzo",
                    author=form_data.user_name or "Autore",
                    plot=validated_draft,
                    api_key=api_key,
                    cover_style=form_data.cover_style,
                )
                # Carica copertina su GCS
                try:
                    storage_service = get_storage_service()
                    user_id = session.user_id if hasattr(session, 'user_id') else None
                    cover_filename = f"{session_id}_cover.png"
                    with open(cover_path, 'rb') as f:
                        cover_data = f.read()
                    gcs_path = storage_service.upload_file(
                        data=cover_data,
                        destination_path=f"covers/{cover_filename}",
                        content_type="image/png",
                        user_id=user_id,
                    )
                    await update_cover_image_path_async(session_store, session_id, gcs_path)
                    print(f"[BOOK GENERATION] Copertina generata e caricata su GCS: {gcs_path}")
                except Exception as e:
                    print(f"[BOOK GENERATION] ERRORE nel caricamento copertina su GCS: {e}, uso path locale")
                    await update_cover_image_path_async(session_store, session_id, cover_path)
                    print(f"[BOOK GENERATION] Copertina generata e salvata: {cover_path}")
        except Exception as e:
            print(f"[BOOK GENERATION] ERRORE nella generazione copertina: {e}")
            import traceback
            traceback.print_exc()
            # Non blocchiamo il processo se la copertina fallisce
        
        # Genera la valutazione critica dopo che il libro è stato completato
        try:
            print(f"[BOOK GENERATION] Avvio valutazione critica per sessione {session_id}")
            session = await get_session_async(session_store, session_id)
            if session and session.book_chapters and len(session.book_chapters) > 0:
                # Critica: genera prima il PDF finale (e lo salva su disco), poi passa il PDF al modello multimodale.
                await update_critique_status_async(session_store, session_id, "running", error=None)
                try:
                    pdf_response = await download_book_pdf_endpoint(session_id, current_user=None)
                    pdf_bytes = getattr(pdf_response, "body", None) or getattr(pdf_response, "content", None)
                    if pdf_bytes is None:
                        # Fallback: rigenera via endpoint e prendi il body
                        pdf_bytes = pdf_response.body
                    if not isinstance(pdf_bytes, (bytes, bytearray)) or len(pdf_bytes) == 0:
                        raise ValueError("PDF bytes non disponibili per la critica.")
                except Exception as e:
                    raise RuntimeError(f"Impossibile generare/recuperare PDF per critica: {e}")

                critique = await generate_literary_critique_from_pdf(
                    title=draft_title or "Romanzo",
                    author=form_data.user_name or "Autore",
                    pdf_bytes=bytes(pdf_bytes),
                    api_key=api_key,
                )

                await update_critique_async(session_store, session_id, critique)
                print(f"[BOOK GENERATION] Valutazione critica completata: score={critique.get('score', 0)}")
        except Exception as e:
            print(f"[BOOK GENERATION] ERRORE nella valutazione critica: {e}")
            import traceback
            traceback.print_exc()
            # Niente placeholder: settiamo status failed e salviamo errore per UI (stop polling + retry).
            try:
                await update_critique_status_async(session_store, session_id, "failed", error=str(e))
            except Exception as _e:
                print(f"[BOOK GENERATION] WARNING: impossibile salvare critique_status failed: {_e}")
    except ValueError as e:
        # Errore di validazione (es. outline non valido)
        error_msg = f"Errore di validazione: {str(e)}"
        print(f"[BOOK GENERATION] ERRORE (ValueError): {error_msg}")
        import traceback
        traceback.print_exc()
        # Salva l'errore nel progresso mantenendo il total_steps se già impostato
        session = await get_session_async(session_store, session_id)
        existing_total = 0
        if session and session.writing_progress:
            existing_total = session.writing_progress.get('total_steps', 0)
        
        await update_writing_progress_async(
            session_store,
            session_id=session_id,
            current_step=0,
            total_steps=existing_total if existing_total > 0 else 1,
            current_section_name=None,
            is_complete=False,
            is_paused=False,
            error=error_msg,
        )
    except Exception as e:
        error_msg = f"Errore nella generazione: {str(e)}"
        print(f"[BOOK GENERATION] ERRORE (Exception): {error_msg}")
        import traceback
        traceback.print_exc()
        # Salva l'errore nel progresso mantenendo il total_steps se già impostato
        session = await get_session_async(session_store, session_id)
        existing_total = 0
        if session and session.writing_progress:
            existing_total = session.writing_progress.get('total_steps', 0)
        
        await update_writing_progress_async(
            session_store,
            session_id=session_id,
            current_step=0,
            total_steps=existing_total if existing_total > 0 else 1,
            current_section_name=None,
            is_complete=False,
            is_paused=False,
            error=error_msg,
        )


@app.post("/api/book/generate", response_model=BookGenerationResponse)
async def generate_book_endpoint(
    request: BookGenerationRequest,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user_optional),
):
    """Avvia la generazione del libro completo in background."""
    try:
        # Verifica che l'API key sia configurata
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="GOOGLE_API_KEY non configurata. Verifica il file .env nella root del progetto."
            )
        
        # Recupera la sessione
        session_store = get_session_store()
        user_id = current_user.id if current_user else None
        session = await get_session_async(session_store, request.session_id, user_id=user_id)
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Sessione {request.session_id} non trovata"
            )
        
        if current_user and session.user_id and session.user_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="Accesso negato: questa sessione appartiene a un altro utente"
            )
        
        if not session.current_draft or not session.validated:
            raise HTTPException(
                status_code=400,
                detail="La bozza deve essere validata prima di generare il libro."
            )
        
        if not session.current_outline:
            raise HTTPException(
                status_code=400,
                detail="La struttura del libro deve essere generata prima di iniziare la scrittura."
            )
        
        # NUOVO: Parsa l'outline e inizializza il progresso IMMEDIATAMENTE
        try:
            print(f"[BOOK GENERATION] Parsing outline per sessione {request.session_id}...")
            sections = parse_outline_sections(session.current_outline)
            total_sections = len(sections)
            
            if total_sections == 0:
                raise HTTPException(
                    status_code=400,
                    detail="Nessuna sezione trovata nella struttura. Verifica che la struttura sia in formato Markdown corretto."
                )
            
            # Inizializza il progresso PRIMA di avviare il task
            await update_writing_progress_async(
                session_store,
                session_id=request.session_id,
                current_step=0,
                total_steps=total_sections,
                current_section_name=sections[0]['title'] if sections else None,
                is_complete=False,
                is_paused=False,
            )
            print(f"[BOOK GENERATION] Progresso inizializzato: {total_sections} sezioni da scrivere")
            
        except ValueError as e:
            # Errore nel parsing
            print(f"[BOOK GENERATION] Errore nel parsing outline: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            print(f"[BOOK GENERATION] Errore imprevisto durante l'inizializzazione: {e}")
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=500,
                detail=f"Errore durante l'inizializzazione della scrittura: {str(e)}"
            )
        
        # Avvia la generazione in background
        background_tasks.add_task(
            background_book_generation,
            session_id=request.session_id,
            form_data=session.form_data,
            question_answers=session.question_answers,
            validated_draft=session.current_draft,
            draft_title=session.current_title,
            outline_text=session.current_outline,
            api_key=api_key,
        )
        
        print(f"[BOOK GENERATION] Task di generazione avviato per sessione {request.session_id}")
        
        return BookGenerationResponse(
            success=True,
            session_id=request.session_id,
            message="Generazione del libro avviata. Usa /api/book/progress per monitorare lo stato.",
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Errore nell'avvio generazione libro: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nell'avvio della generazione del libro: {str(e)}"
        )


async def background_resume_book_generation(
    session_id: str,
    api_key: str,
):
    """Funzione eseguita in background per riprendere la generazione del libro."""
    session_store = get_session_store()
    try:
        print(f"[BOOK GENERATION] Ripresa generazione libro per sessione {session_id}")
        
        # Recupera la sessione per verificare lo stato
        session = await get_session_async(session_store, session_id)
        if not session:
            raise ValueError(f"Sessione {session_id} non trovata")
        
        if not session.writing_progress:
            raise ValueError(f"Sessione {session_id} non ha uno stato di scrittura")
        
        progress = session.writing_progress
        if not progress.get("is_paused", False):
            raise ValueError(f"Sessione {session_id} non è in stato di pausa")
        
        # Recupera il timestamp di inizio se esiste, altrimenti usa quello corrente
        start_time = session.writing_start_time or datetime.now()
        if not session.writing_start_time:
            await update_writing_times_async(session_store, session_id, start_time=start_time)
        
        await resume_book_generation(
            session_id=session_id,
            api_key=api_key,
        )
        
        # Verifica se la generazione è stata completata o rimessa in pausa
        session = await get_session_async(session_store, session_id)
        if session and session.writing_progress and session.writing_progress.get('is_paused', False):
            print(f"[BOOK GENERATION] Generazione rimessa in pausa per sessione {session_id}")
            return
        
        print(f"[BOOK GENERATION] Ripresa generazione completata per sessione {session_id}")
        
        # Registra timestamp fine scrittura capitoli e calcola tempo
        end_time = datetime.now()
        await update_writing_times_async(session_store, session_id, end_time=end_time)
        writing_time_minutes = (end_time - start_time).total_seconds() / 60
        print(f"[BOOK GENERATION] Timestamp fine scrittura: {end_time.isoformat()}, tempo totale: {writing_time_minutes:.2f} minuti")
        
        # Aggiorna writing_progress con il tempo calcolato
        session = await get_session_async(session_store, session_id)
        if session and session.writing_progress:
            existing_progress = session.writing_progress.copy()
            existing_progress['writing_time_minutes'] = writing_time_minutes
            await update_writing_progress_async(
                session_store,
                session_id=session_id,
                current_step=existing_progress.get('current_step', 0),
                total_steps=existing_progress.get('total_steps', 0),
                current_section_name=existing_progress.get('current_section_name'),
                is_complete=existing_progress.get('is_complete', True),
                is_paused=False,
                error=None,
            )
            session.writing_progress['writing_time_minutes'] = writing_time_minutes
            if hasattr(session_store, '_save_sessions'):
                session_store._save_sessions()
        
        # Genera la copertina dopo che il libro è stato completato
        try:
            print(f"[BOOK GENERATION] Avvio generazione copertina per sessione {session_id}")
            session = await get_session_async(session_store, session_id)
            if session:
                cover_path = await generate_book_cover(
                    session_id=session_id,
                    title=session.current_title or "Romanzo",
                    author=session.form_data.user_name or "Autore",
                    plot=session.current_draft or "",
                    api_key=api_key,
                    cover_style=session.form_data.cover_style,
                )
                if cover_path:
                    # Carica copertina su GCS
                    try:
                        storage_service = get_storage_service()
                        user_id = session.user_id if hasattr(session, 'user_id') else None
                        cover_filename = f"{session_id}_cover.png"
                        with open(cover_path, 'rb') as f:
                            cover_data = f.read()
                        gcs_path = storage_service.upload_file(
                            data=cover_data,
                            destination_path=f"covers/{cover_filename}",
                            content_type="image/png",
                            user_id=user_id,
                        )
                        await update_cover_image_path_async(session_store, session_id, gcs_path)
                        print(f"[BOOK GENERATION] Copertina generata e caricata su GCS: {gcs_path}")
                    except Exception as e:
                        print(f"[BOOK GENERATION] ERRORE nel caricamento copertina su GCS: {e}, uso path locale")
                        await update_cover_image_path_async(session_store, session_id, cover_path)
                        print(f"[BOOK GENERATION] Copertina generata: {cover_path}")
        except Exception as e:
            print(f"[BOOK GENERATION] ERRORE nella generazione copertina: {e}")
            import traceback
            traceback.print_exc()
        
        # Genera la valutazione critica dopo che il libro è stato completato
        try:
            print(f"[BOOK GENERATION] Avvio valutazione critica per sessione {session_id}")
            session = await get_session_async(session_store, session_id)
            if session and session.book_chapters and len(session.book_chapters) > 0:
                # Critica: genera prima il PDF finale (e lo salva su disco), poi passa il PDF al modello multimodale.
                await update_critique_status_async(session_store, session_id, "running", error=None)
                try:
                    pdf_response = await download_book_pdf_endpoint(session_id, current_user=None)
                    pdf_bytes = getattr(pdf_response, "body", None) or getattr(pdf_response, "content", None)
                    if pdf_bytes is None:
                        # Fallback: rigenera via endpoint e prendi il body
                        pdf_bytes = pdf_response.body
                    if not isinstance(pdf_bytes, (bytes, bytearray)) or len(pdf_bytes) == 0:
                        raise ValueError("PDF bytes non disponibili per la critica.")
                except Exception as e:
                    raise RuntimeError(f"Impossibile generare/recuperare PDF per critica: {e}")

                critique = await generate_literary_critique_from_pdf(
                    title=session.current_title or "Romanzo",
                    author=session.form_data.user_name or "Autore",
                    pdf_bytes=bytes(pdf_bytes),
                    api_key=api_key,
                )

                await update_critique_async(session_store, session_id, critique)
                print(f"[BOOK GENERATION] Valutazione critica completata: score={critique.get('score', 0)}")
        except Exception as e:
            print(f"[BOOK GENERATION] ERRORE nella valutazione critica: {e}")
            import traceback
            traceback.print_exc()
            # Niente placeholder: settiamo status failed e salviamo errore per UI (stop polling + retry).
            try:
                await update_critique_status_async(session_store, session_id, "failed", error=str(e))
            except Exception as _e:
                print(f"[BOOK GENERATION] WARNING: impossibile salvare critique_status failed: {_e}")
    except ValueError as e:
        error_msg = f"Errore di validazione: {str(e)}"
        print(f"[BOOK GENERATION] ERRORE (ValueError): {error_msg}")
        import traceback
        traceback.print_exc()
        session = await get_session_async(session_store, session_id)
        existing_total = 0
        if session and session.writing_progress:
            existing_total = session.writing_progress.get('total_steps', 0)
        
        await update_writing_progress_async(
            session_store,
            session_id=session_id,
            current_step=0,
            total_steps=existing_total if existing_total > 0 else 1,
            current_section_name=None,
            is_complete=False,
            is_paused=False,
            error=error_msg,
        )
    except Exception as e:
        error_msg = f"Errore nella ripresa generazione: {str(e)}"
        print(f"[BOOK GENERATION] ERRORE (Exception): {error_msg}")
        import traceback
        traceback.print_exc()
        session = await get_session_async(session_store, session_id)
        existing_total = 0
        if session and session.writing_progress:
            existing_total = session.writing_progress.get('total_steps', 0)
        
        await update_writing_progress_async(
            session_store,
            session_id=session_id,
            current_step=0,
            total_steps=existing_total if existing_total > 0 else 1,
            current_section_name=None,
            is_complete=False,
            is_paused=False,
            error=error_msg,
        )


@app.post("/api/book/resume/{session_id}", response_model=BookGenerationResponse)
async def resume_book_generation_endpoint(
    session_id: str,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user_optional),
):
    """Riprende la generazione del libro dal capitolo fallito."""
    try:
        # Verifica che l'API key sia configurata
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="GOOGLE_API_KEY non configurata. Verifica il file .env nella root del progetto."
            )
        
        # Recupera la sessione
        session_store = get_session_store()
        user_id = current_user.id if current_user else None
        session = await get_session_async(session_store, session_id, user_id=user_id)
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Sessione {session_id} non trovata"
            )
        
        if current_user and session.user_id and session.user_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="Accesso negato: questa sessione appartiene a un altro utente"
            )
        
        if not session.writing_progress:
            raise HTTPException(
                status_code=400,
                detail="La sessione non ha uno stato di scrittura. Avvia prima la generazione."
            )
        
        if not session.writing_progress.get('is_paused', False):
            raise HTTPException(
                status_code=400,
                detail="La sessione non è in stato di pausa. Non è possibile riprendere."
            )
        
        # Avvia la ripresa in background
        background_tasks.add_task(
            background_resume_book_generation,
            session_id=session_id,
            api_key=api_key,
        )
        
        print(f"[BOOK GENERATION] Task di ripresa generazione avviato per sessione {session_id}")
        
        return BookGenerationResponse(
            success=True,
            session_id=session_id,
            message="Ripresa della generazione avviata. Usa /api/book/progress per monitorare lo stato.",
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Errore nell'avvio ripresa generazione libro: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nell'avvio della ripresa generazione: {str(e)}"
        )


@app.get("/api/session/{session_id}/restore", response_model=SessionRestoreResponse)
async def restore_session_endpoint(
    session_id: str,
    current_user = Depends(get_current_user_optional)
):
    """Ripristina lo stato completo di una sessione per permettere il recupero del processo interrotto."""
    try:
        session_store = get_session_store()
        user_id = current_user.id if current_user else None
        session = await get_session_async(session_store, session_id, user_id=user_id)
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Sessione {session_id} non trovata"
            )
        
        if current_user and session.user_id and session.user_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="Accesso negato: questa sessione appartiene a un altro utente"
            )
        
        # Determina lo step corrente
        current_step: Literal["questions", "draft", "summary", "writing"]
        
        # Se c'è writing_progress, siamo in writing
        if session.writing_progress:
            current_step = "writing"
        # Se c'è outline, siamo in summary
        elif session.current_outline:
            current_step = "summary"
        # Se c'è draft validato o question_answers, siamo in draft
        elif session.current_draft or (session.question_answers and len(session.question_answers) > 0):
            current_step = "draft"
        # Altrimenti siamo in questions
        else:
            current_step = "questions"
        
        # Prepara le questions (se disponibili)
        questions = None
        if session.generated_questions:
            from app.models import Question
            questions = [Question(**q) for q in session.generated_questions]
        
        # Prepara draft (se disponibile)
        draft = None
        if session.current_draft:
            draft = DraftResponse(
                success=True,
                session_id=session_id,
                draft_text=session.current_draft,
                title=session.current_title,
                version=session.current_version,
            )
        
        # Prepara writing_progress (se disponibile)
        writing_progress = None
        if session.writing_progress:
            # Usa la stessa logica di get_book_progress_endpoint per costruire BookProgress
            progress = session.writing_progress
            chapters = session.book_chapters or []
            
            # Converti i capitoli in oggetti Chapter
            completed_chapters = []
            for ch_dict in chapters:
                content = ch_dict.get('content', '')
                page_count = calculate_page_count(content)
                completed_chapters.append(Chapter(
                    title=ch_dict.get('title', ''),
                    content=content,
                    section_index=ch_dict.get('section_index', 0),
                    page_count=page_count,
                ))
            
            # Calcola total_pages se il libro è completato
            total_pages = None
            is_complete = progress.get('is_complete', False)
            if is_complete and len(completed_chapters) > 0:
                chapters_pages = sum(ch.page_count for ch in completed_chapters)
                cover_pages = 1
                app_config = get_app_config()
                toc_chapters_per_page = app_config.get("validation", {}).get("toc_chapters_per_page", 30)
                toc_pages = math.ceil(len(completed_chapters) / toc_chapters_per_page)
                total_pages = chapters_pages + cover_pages + toc_pages
            
            # Calcola writing_time_minutes
            writing_time_minutes = progress.get('writing_time_minutes')
            if writing_time_minutes is None and is_complete:
                if session.writing_start_time and session.writing_end_time:
                    delta = session.writing_end_time - session.writing_start_time
                    writing_time_minutes = delta.total_seconds() / 60.0
            
            # Calcola estimated_cost
            estimated_cost = calculate_generation_cost(session, total_pages)
            
            # Estrai critique
            critique = None
            critique_status = session.critique_status
            critique_error = session.critique_error
            if session.literary_critique:
                if isinstance(session.literary_critique, dict):
                    critique = LiteraryCritique(**session.literary_critique)
                else:
                    critique = session.literary_critique
            
            # Calcola stima tempo rimanente usando modello lineare
            estimated_time_minutes = None
            estimated_time_confidence = None
            if not is_complete:
                current_step_idx = progress.get('current_step', 0)
                total_steps = progress.get('total_steps', 0)
                
                if total_steps > 0 and current_step_idx < total_steps:
                    # Usa la stessa funzione calculate_estimated_time per coerenza
                    try:
                        estimated_time_minutes, estimated_time_confidence = await calculate_estimated_time(
                            session_id, current_step_idx, total_steps
                        )
                    except Exception as e:
                        print(f"[RESTORE_SESSION] Errore nel calcolo stima tempo: {e}")
                        # Fallback semplice se calculate_estimated_time fallisce
                        remaining = total_steps - current_step_idx
                        app_config = get_app_config()
                        current_model = session.form_data.llm_model if session.form_data else None
                        method = get_generation_method(current_model)
                        a, b = get_linear_params_for_method(method, app_config)
                        k = current_step_idx + 1
                        estimated_seconds = calculate_residual_time_linear(k, total_steps, a, b)
                        estimated_time_minutes = estimated_seconds / 60
                        estimated_time_confidence = None
            
            writing_progress = BookProgress(
                session_id=session_id,
                current_step=progress.get('current_step', 0),
                total_steps=progress.get('total_steps', 0),
                current_section_name=progress.get('current_section_name'),
                completed_chapters=completed_chapters,
                is_complete=is_complete,
                is_paused=progress.get('is_paused', False),
                error=progress.get('error'),
                total_pages=total_pages,
                writing_time_minutes=writing_time_minutes,
                estimated_cost=estimated_cost,
                critique=critique,
                critique_status=critique_status,
                critique_error=critique_error,
                estimated_time_minutes=estimated_time_minutes,
                estimated_time_confidence=estimated_time_confidence,
            )
        
        # Assicurati che outline sia sempre restituito se presente (importante per il ripristino)
        outline_text = session.current_outline if session.current_outline else None
        
        return SessionRestoreResponse(
            session_id=session_id,
            form_data=session.form_data,
            questions=questions,
            question_answers=session.question_answers or [],
            draft=draft,
            outline=outline_text,
            writing_progress=writing_progress,
            current_step=current_step,
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Errore nel ripristino sessione: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nel ripristino sessione: {str(e)}"
        )


@app.get("/api/book/progress/{session_id}", response_model=BookProgress)
async def get_book_progress_endpoint(
    session_id: str,
    current_user = Depends(get_current_user_optional),
):
    """Recupera lo stato di avanzamento della scrittura del libro."""
    try:
        session_store = get_session_store()
        user_id = current_user.id if current_user else None
        session = await get_session_async(session_store, session_id, user_id=user_id)
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Sessione {session_id} non trovata"
            )
        
        # Verifica accesso: ownership o condivisione accettata
        if current_user and session.user_id and session.user_id != current_user.id:
            # Verifica se l'utente ha accesso tramite condivisione
            from app.agent.book_share_store import get_book_share_store
            book_share_store = get_book_share_store()
            await book_share_store.connect()
            has_access = await book_share_store.check_user_has_access(
                book_session_id=session_id,
                user_id=current_user.id,
                owner_id=session.user_id,
            )
            if not has_access:
                raise HTTPException(
                    status_code=403,
                    detail="Accesso negato: questa sessione appartiene a un altro utente o non hai accesso"
                )
        
        # Costruisci la risposta dal progresso salvato
        progress = session.writing_progress or {}
        chapters = session.book_chapters or []
        
        # Converti i capitoli in oggetti Chapter
        completed_chapters = []
        for ch_dict in chapters:
            content = ch_dict.get('content', '')
            page_count = calculate_page_count(content)
            completed_chapters.append(Chapter(
                title=ch_dict.get('title', ''),
                content=content,
                section_index=ch_dict.get('section_index', 0),
                page_count=page_count,
            ))
        
        # Calcola total_pages se il libro è completato
        total_pages = None
        is_complete = progress.get('is_complete', False)
        if is_complete and len(completed_chapters) > 0:
            # Somma pagine capitoli
            chapters_pages = sum(ch.page_count for ch in completed_chapters)
            # 1 pagina per copertina
            cover_pages = 1
            # Pagine indice: 1 pagina base + 1 ogni N capitoli (da config)
            app_config = get_app_config()
            toc_chapters_per_page = app_config.get("validation", {}).get("toc_chapters_per_page", 30)
            toc_pages = math.ceil(len(completed_chapters) / toc_chapters_per_page)
            total_pages = chapters_pages + cover_pages + toc_pages
        
        # Calcola writing_time_minutes se disponibile o calcolabile
        writing_time_minutes = progress.get('writing_time_minutes')
        if writing_time_minutes is None and is_complete:
            # Backward compatibility: calcola dai timestamp se disponibili
            if session.writing_start_time and session.writing_end_time:
                delta = session.writing_end_time - session.writing_start_time
                writing_time_minutes = delta.total_seconds() / 60
        
        # Calcola costo stimato (solo se libro completo)
        estimated_cost = None
        if is_complete and total_pages:
            estimated_cost = calculate_generation_cost(session, total_pages)
        
        # Recupera la valutazione critica se disponibile
        critique = None
        if session.literary_critique:
            try:
                critique = LiteraryCritique(**session.literary_critique)
            except Exception as e:
                print(f"[GET BOOK PROGRESS] Errore nel parsing critique: {e}")

        # Backward-compat: sessioni vecchie potrebbero avere critique senza critique_status
        critique_status = session.critique_status
        critique_error = session.critique_error
        if critique_status is None:
            if critique is not None:
                critique_status = "completed"
            elif is_complete:
                critique_status = "pending"
        
        # Calcola stima tempo se il libro non è completato
        estimated_time_minutes = None
        estimated_time_confidence = None
        calculated_total_steps = None  # Variabile per salvare total_steps calcolato
        if not is_complete:
            # FIX: Casting esplicito a int per evitare errori con stringhe dal dict
            raw_current = progress.get('current_step', 0)
            raw_total = progress.get('total_steps', 0)
            
            try:
                current_step = int(raw_current)
            except (ValueError, TypeError):
                print(f"[GET BOOK PROGRESS] WARNING: current_step non è un numero valido ({raw_current}, type: {type(raw_current).__name__}), uso 0")
                current_step = 0
            
            try:
                total_steps = int(raw_total)
            except (ValueError, TypeError):
                print(f"[GET BOOK PROGRESS] WARNING: total_steps non è un numero valido ({raw_total}, type: {type(raw_total).__name__}), uso 0")
                total_steps = 0
            
            # Validazione: assicuriamoci che i valori siano validi
            if current_step < 0:
                print(f"[GET BOOK PROGRESS] WARNING: current_step negativo ({current_step}), correggo a 0")
                current_step = 0
            
            # FALLBACK: Se total_steps è 0 ma is_complete è False, prova a calcolarlo dall'outline
            if total_steps == 0:
                print(f"[GET BOOK PROGRESS] WARNING: total_steps è 0 nel progress dict, provo a calcolarlo dall'outline")
                if session.current_outline:
                    try:
                        sections = parse_outline_sections(session.current_outline)
                        total_steps = len(sections)
                        calculated_total_steps = total_steps  # Salva per uso successivo
                        print(f"[GET BOOK PROGRESS] Calcolato total_steps dall'outline: {total_steps}")
                    except Exception as e:
                        print(f"[GET BOOK PROGRESS] Errore nel parsing outline per calcolare total_steps: {e}")
                        total_steps = 0
                # Se ancora 0, usa default minimo per permettere il calcolo
                if total_steps == 0:
                    print(f"[GET BOOK PROGRESS] total_steps ancora 0, uso default 1 per permettere calcolo")
                    total_steps = 1
                    calculated_total_steps = 1  # IMPORTANTE: assegniamo anche qui per usarlo in final_total_steps
            
            print(f"[GET BOOK PROGRESS] Calcolo stima tempo: current_step={current_step}, total_steps={total_steps}")
            print(f"[GET BOOK PROGRESS] chapter_timings: {session.chapter_timings}")
            
            # Calcola SEMPRE la stima quando not is_complete (total_steps dovrebbe essere sempre > 0 grazie al fallback sopra)
            # Se total_steps è ancora 0 dopo i fallback, usiamo 1 come ultimo resort
            if total_steps <= 0:
                print(f"[GET BOOK PROGRESS] WARNING: total_steps è ancora <= 0 dopo fallback, uso 1 come ultimo resort")
                total_steps = 1
                calculated_total_steps = 1  # IMPORTANTE: assegniamo anche qui
            
            # Calcola sempre la stima
            estimated_time_minutes, estimated_time_confidence = await calculate_estimated_time(
                session_id, current_step, total_steps
            )
            print(f"[GET BOOK PROGRESS] estimated_time_minutes: {estimated_time_minutes}, confidence: {estimated_time_confidence}")
            
            # Fallback finale: se calculate_estimated_time ha restituito None nonostante remaining_chapters > 0
            if estimated_time_minutes is None:
                remaining = total_steps - current_step
                if remaining > 0:
                    print(f"[GET BOOK PROGRESS] WARNING: calculate_estimated_time ha restituito None, uso fallback finale")
                    # Leggi il fallback dalla configurazione
                    app_config = get_app_config()
                    time_config = app_config.get("time_estimation", {})
                    fallback_seconds = time_config.get("fallback_seconds_per_chapter", 45)
                    estimated_time_minutes = (remaining * fallback_seconds) / 60
                    estimated_time_confidence = "low"
                    print(f"[GET BOOK PROGRESS] Fallback finale applicato: {estimated_time_minutes:.1f} minuti")
                else:
                    print(f"[GET BOOK PROGRESS] remaining <= 0 ({remaining}), non posso calcolare stima")
        
        # Assicuriamoci che total_steps sia valido nel BookProgress
        # SEMPLIFICATO: se abbiamo calcolato total_steps (dall'outline o fallback), usiamo quello
        if not is_complete and calculated_total_steps is not None and calculated_total_steps > 0:
            final_total_steps = calculated_total_steps
            print(f"[GET BOOK PROGRESS] Usando total_steps calcolato: {final_total_steps}")
        else:
            final_total_steps = progress.get('total_steps', 0)
        
        # Ultima garanzia: se non è completo ma total_steps è ancora 0, usa 1
        if not is_complete and final_total_steps <= 0:
            print(f"[GET BOOK PROGRESS] SAFETY: final_total_steps è {final_total_steps}, uso 1 come minimo")
            final_total_steps = 1
        
        # Log finale per debug
        print(f"[GET BOOK PROGRESS] Valori finali: total_steps={final_total_steps}, estimated_time_minutes={estimated_time_minutes}, estimated_time_confidence={estimated_time_confidence}")
        
        return BookProgress(
            session_id=session_id,
            current_step=progress.get('current_step', 0),
            total_steps=final_total_steps,
            current_section_name=progress.get('current_section_name'),
            completed_chapters=completed_chapters,
            is_complete=is_complete,
            is_paused=progress.get('is_paused', False),
            error=progress.get('error'),
            total_pages=total_pages,
            writing_time_minutes=writing_time_minutes,
            estimated_cost=estimated_cost,
            critique=critique,
            critique_status=critique_status,
            critique_error=critique_error,
            estimated_time_minutes=estimated_time_minutes,
            estimated_time_confidence=estimated_time_confidence,
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Errore nel recupero del progresso: {str(e)}"
        )


@app.get("/api/book/{session_id}", response_model=BookResponse)
async def get_complete_book_endpoint(
    session_id: str,
    current_user = Depends(get_current_user_optional)
):
    """Restituisce il libro completo con tutti i capitoli."""
    try:
        print(f"[GET BOOK] Richiesta libro completo per sessione: {session_id}")
        session_store = get_session_store()
        user_id = current_user.id if current_user else None
        session = await get_session_async(session_store, session_id, user_id=user_id)
        
        if not session:
            print(f"[GET BOOK] Sessione {session_id} non trovata")
            raise HTTPException(
                status_code=404,
                detail=f"Sessione {session_id} non trovata"
            )
        
        # Verifica accesso: ownership o condivisione accettata
        if current_user and session.user_id and session.user_id != current_user.id:
            # Verifica se l'utente ha accesso tramite condivisione
            from app.agent.book_share_store import get_book_share_store
            book_share_store = get_book_share_store()
            await book_share_store.connect()
            has_access = await book_share_store.check_user_has_access(
                book_session_id=session_id,
                user_id=current_user.id,
                owner_id=session.user_id,
            )
            if not has_access:
                raise HTTPException(
                    status_code=403,
                    detail="Accesso negato: questa sessione appartiene a un altro utente o non hai accesso"
                )
        
        print(f"[GET BOOK] Sessione trovata. Progresso: {session.writing_progress}, Capitoli: {len(session.book_chapters) if session.book_chapters else 0}")
        
        if not session.writing_progress or not session.writing_progress.get('is_complete'):
            print(f"[GET BOOK] Libro non ancora completo. Progresso: {session.writing_progress}")
            raise HTTPException(
                status_code=400,
                detail="Il libro non è ancora completo. Attendi il completamento della scrittura."
            )
        
        if not session.book_chapters or len(session.book_chapters) == 0:
            print(f"[GET BOOK] Nessun capitolo trovato nella sessione")
            raise HTTPException(
                status_code=400,
                detail="Nessun capitolo trovato nel libro. La scrittura potrebbe non essere stata completata correttamente."
            )
        
        # Converti i capitoli in oggetti Chapter
        chapters = []
        for idx, ch_dict in enumerate(session.book_chapters):
            try:
                content = ch_dict.get('content', '')
                page_count = calculate_page_count(content)
                chapter = Chapter(
                    title=ch_dict.get('title', f'Capitolo {idx + 1}'),
                    content=content,
                    section_index=ch_dict.get('section_index', idx),
                    page_count=page_count,
                )
                chapters.append(chapter)
                print(f"[GET BOOK] Capitolo {idx + 1}: '{chapter.title}' - {len(chapter.content)} caratteri - {page_count} pagine")
            except Exception as e:
                print(f"[GET BOOK] Errore nel processare capitolo {idx}: {e}")
                continue
        
        if len(chapters) == 0:
            raise HTTPException(
                status_code=400,
                detail="Nessun capitolo valido trovato nel libro."
            )
        
        # Ordina per section_index
        chapters.sort(key=lambda x: x.section_index)
        
        # Calcola total_pages
        chapters_pages = sum(ch.page_count for ch in chapters)
        cover_pages = 1  # 1 pagina per copertina
        # Pagine indice: 1 pagina base + 1 ogni N capitoli (da config)
        app_config = get_app_config()
        toc_chapters_per_page = app_config.get("validation", {}).get("toc_chapters_per_page", 30)
        toc_pages = math.ceil(len(chapters) / toc_chapters_per_page)
        total_pages = chapters_pages + cover_pages + toc_pages
        
        # Calcola writing_time_minutes se disponibile o calcolabile
        writing_time_minutes = None
        progress = session.writing_progress or {}
        if progress.get('writing_time_minutes') is not None:
            writing_time_minutes = progress.get('writing_time_minutes')
        elif session.writing_start_time and session.writing_end_time:
            # Backward compatibility: calcola dai timestamp se disponibili
            delta = session.writing_end_time - session.writing_start_time
            writing_time_minutes = delta.total_seconds() / 60
        
        # Recupera la valutazione critica se disponibile
        critique = None
        if session.literary_critique:
            try:
                critique = LiteraryCritique(**session.literary_critique)
            except Exception as e:
                print(f"[GET BOOK] Errore nel parsing critique: {e}")

        # Backward-compat: sessioni vecchie potrebbero avere critique senza critique_status
        critique_status = session.critique_status
        critique_error = session.critique_error
        if critique_status is None and critique is not None:
            critique_status = "completed"
        
        book_response = BookResponse(
            title=session.current_title or "Romanzo",
            author=session.form_data.user_name or "Autore",
            chapters=chapters,
            total_pages=total_pages,
            writing_time_minutes=writing_time_minutes,
            critique=critique,
            critique_status=critique_status,
            critique_error=critique_error,
        )
        
        print(f"[GET BOOK] Libro restituito: {book_response.title} di {book_response.author}, {len(chapters)} capitoli, {total_pages} pagine totali")
        return book_response
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[GET BOOK] ERRORE nel recupero del libro completo: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nel recupero del libro completo: {str(e)}"
        )


@app.get("/api/library", response_model=LibraryResponse)
async def get_library_endpoint(
    status: Optional[str] = None,
    llm_model: Optional[str] = None,  # Retrocompatibilità: accetta ancora llm_model
    mode: Optional[str] = None,  # Nuovo parametro per modalità (Flash, Pro, Ultra)
    genre: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: Optional[str] = "created_at",
    sort_order: Optional[str] = "desc",
    skip: int = 0,
    limit: int = 20,
    current_user = Depends(get_current_user_optional),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """
    Restituisce la lista dei libri nella libreria con filtri opzionali e paginazione.
    
    Query parameters:
    - status: filtro per stato (draft, outline, writing, paused, complete, all)
    - mode: filtro per modalità (Flash, Pro, Ultra) - preferito rispetto a llm_model
    - llm_model: filtro per modello LLM (retrocompatibilità, deprecato)
    - genre: filtro per genere
    - search: ricerca in titolo/autore
    - sort_by: ordinamento (created_at, title, score, cost, total_pages, updated_at)
    - sort_order: ordine (asc, desc)
    - skip: numero di libri da saltare (per paginazione, default: 0)
    - limit: numero massimo di libri da restituire (per paginazione, default: 20)
    """
    try:
        from app.agent.session_store_helpers import get_all_sessions_async, get_session_async
        session_store = get_session_store()
        user_id = current_user.id if current_user else None
        
        # Determina il filtro per modello: se mode è fornito, convertilo in lista di modelli
        # Altrimenti usa llm_model per retrocompatibilità
        filter_llm_model = None
        if mode:
            # Converti modalità in lista di modelli
            models_for_mode = mode_to_llm_models(mode)
            if models_for_mode:
                # Per ora carichiamo tutte le sessioni e filtriamo dopo
                # (potremmo ottimizzare con $in query in futuro)
                filter_llm_model = None  # Filtriamo dopo
            else:
                filter_llm_model = None  # Modalità sconosciuta, nessun risultato
        elif llm_model:
            # Retrocompatibilità: se viene passato llm_model, convertilo in modalità
            # e poi in lista di modelli
            detected_mode = llm_model_to_mode(llm_model)
            models_for_mode = mode_to_llm_models(detected_mode)
            if models_for_mode:
                filter_llm_model = None  # Filtriamo dopo
            else:
                filter_llm_model = llm_model  # Usa il modello originale se non riconosciuto
        
        # Filtri vengono applicati nella query MongoDB (ottimizzazione performance)
        all_sessions = await get_all_sessions_async(
            session_store, 
            user_id=user_id, 
            fields=LIBRARY_ENTRY_FIELDS,
            status=status,
            llm_model=filter_llm_model,  # None se dobbiamo filtrare per modalità dopo
            genre=genre
        )
        
        # Filtra per modalità se necessario (dopo il caricamento)
        if mode:
            models_for_mode = mode_to_llm_models(mode)
            if models_for_mode:
                all_sessions = {
                    sid: sess for sid, sess in all_sessions.items()
                    if sess.form_data and sess.form_data.llm_model in models_for_mode
                }
            else:
                all_sessions = {}  # Modalità sconosciuta, nessun risultato
        elif llm_model and not filter_llm_model:
            # Retrocompatibilità: filtra per modalità se llm_model era stato convertito
            detected_mode = llm_model_to_mode(llm_model)
            models_for_mode = mode_to_llm_models(detected_mode)
            if models_for_mode:
                all_sessions = {
                    sid: sess for sid, sess in all_sessions.items()
                    if sess.form_data and sess.form_data.llm_model in models_for_mode
                }
        
        # Converti tutte le sessioni in LibraryEntry e identifica sessioni che necessitano backfill
        entries = []
        sessions_to_backfill = []  # Raccogli sessioni che necessitano backfill (total_pages o estimated_cost)
        
        for session in all_sessions.values():
            try:
                entry = session_to_library_entry(session)
                
                # Identifica sessioni complete che necessitano backfill
                if entry.status == "complete":
                    needs_pages_backfill = entry.total_pages is None
                    needs_cost_backfill = entry.estimated_cost is None and entry.total_pages is not None
                    
                    if needs_pages_backfill or needs_cost_backfill:
                        # Carica sessione completa per calcolare total_pages se mancante
                        full_session = None
                        if needs_pages_backfill:
                            try:
                                full_session = await get_session_async(session_store, session.session_id, user_id=user_id)
                                if full_session and full_session.book_chapters:
                                    # Calcola total_pages on the fly
                                    chapters_pages = sum(calculate_page_count(ch.get('content', '')) for ch in full_session.book_chapters)
                                    cover_pages = 1
                                    app_config = get_app_config()
                                    toc_chapters_per_page = app_config.get("validation", {}).get("toc_chapters_per_page", 30)
                                    toc_pages = math.ceil(len(full_session.book_chapters) / toc_chapters_per_page)
                                    calculated_pages = chapters_pages + cover_pages + toc_pages
                                    calculated_chapters_count = len(full_session.book_chapters)
                                    
                                    # Aggiorna entry con total_pages calcolato
                                    entry.total_pages = calculated_pages
                                    
                                    # Se anche estimated_cost mancava, calcolalo ora
                                    if needs_cost_backfill and calculated_pages:
                                        calculated_cost = calculate_generation_cost(full_session, calculated_pages)
                                        if calculated_cost is not None:
                                            entry.estimated_cost = calculated_cost
                                            sessions_to_backfill.append((session.session_id, calculated_pages, calculated_chapters_count, calculated_cost))
                                        else:
                                            sessions_to_backfill.append((session.session_id, calculated_pages, calculated_chapters_count, None))
                                    else:
                                        sessions_to_backfill.append((session.session_id, calculated_pages, calculated_chapters_count, None))
                            except Exception as e:
                                print(f"[LIBRARY] Errore nel caricare sessione completa per backfill {session.session_id}: {e}")
                        elif needs_cost_backfill:
                            # Solo estimated_cost mancante, usa session parziale
                            calculated_cost = calculate_generation_cost(session, entry.total_pages)
                            if calculated_cost is not None:
                                entry.estimated_cost = calculated_cost
                                sessions_to_backfill.append((session.session_id, None, None, calculated_cost))
                
                entries.append(entry)
            except Exception as e:
                print(f"[LIBRARY] Errore nel convertire sessione {session.session_id}: {e}")
                continue
        
        # Salva dati backfillati in background (total_pages e estimated_cost)
        if sessions_to_backfill:
            async def backfill_library_data():
                """Salva total_pages e estimated_cost calcolati in background."""
                from app.agent.session_store_helpers import update_writing_progress_async, set_estimated_cost_async, get_session_async
                store = get_session_store()  # Ricrea session_store nella closure
                uid = user_id  # Usa user_id dalla closure
                
                for session_id, total_pages, completed_chapters_count, estimated_cost in sessions_to_backfill:
                    try:
                        # Salva total_pages se calcolato
                        if total_pages is not None:
                            # Carica sessione per ottenere i dati di writing_progress attuali
                            full_session = await get_session_async(store, session_id, user_id=uid)
                            if full_session and full_session.writing_progress:
                                current_step = full_session.writing_progress.get('current_step', 0)
                                total_steps = full_session.writing_progress.get('total_steps', 0)
                                current_section_name = full_session.writing_progress.get('current_section_name')
                                is_complete = full_session.writing_progress.get('is_complete', False)
                                is_paused = full_session.writing_progress.get('is_paused', False)
                                error = full_session.writing_progress.get('error')
                                # Usa completed_chapters_count calcolato se disponibile, altrimenti quello salvato
                                final_chapters_count = completed_chapters_count if completed_chapters_count is not None else full_session.writing_progress.get('completed_chapters_count')
                                
                                await update_writing_progress_async(
                                    store,
                                    session_id,
                                    current_step=current_step,
                                    total_steps=total_steps,
                                    current_section_name=current_section_name,
                                    is_complete=is_complete,
                                    is_paused=is_paused,
                                    error=error,
                                    total_pages=total_pages,
                                    completed_chapters_count=final_chapters_count,
                                )
                        
                        # Salva estimated_cost se calcolato
                        if estimated_cost is not None:
                            await set_estimated_cost_async(store, session_id, estimated_cost)
                    except Exception as e:
                        print(f"[LIBRARY] Errore nel backfill per sessione {session_id}: {e}")
                
                # Invalida cache stats dopo il backfill
                for cache_key in ["library_stats", "library_stats_advanced"]:
                    if cache_key in _stats_cache:
                        del _stats_cache[cache_key]
            
            background_tasks.add_task(backfill_library_data)
        
        # Recupera anche libri condivisi con l'utente (se autenticato)
        shared_entries = []
        if current_user and user_id:
            from app.agent.book_share_store import get_book_share_store
            from app.agent.user_store import get_user_store
            book_share_store = get_book_share_store()
            user_store_shared = get_user_store()
            
            try:
                await book_share_store.connect()
                # Recupera solo condivisioni ACCEPTED (accesso concesso)
                shared_books = await book_share_store.get_user_shared_books(
                    user_id=user_id,
                    status="accepted",
                    limit=100,  # Limite ragionevole per libri condivisi
                    skip=0,
                )
                
                # Popola informazioni utente per ogni condivisione
                await user_store_shared.connect()
                for share in shared_books:
                    try:
                        # Recupera sessione libro (senza verifica ownership perché è condiviso)
                        shared_session = await get_session_async(session_store, share.book_session_id, user_id=None)
                        
                        if not shared_session:
                            continue
                        
                        # Verifica che il libro sia completato (solo libri completati vengono condivisi)
                        if not shared_session.writing_progress or not shared_session.writing_progress.get('is_complete', False):
                            continue
                        
                        # Applica filtri anche ai libri condivisi
                        # Filtro status
                        if status and status != "all":
                            session_status = shared_session.get_status()
                            if session_status != status:
                                continue
                        
                        # Filtro genere
                        if genre and shared_session.form_data:
                            if shared_session.form_data.genre != genre:
                                continue
                        
                        # Filtro modalità/modello
                        if mode:
                            models_for_mode = mode_to_llm_models(mode)
                            if models_for_mode and shared_session.form_data:
                                if shared_session.form_data.llm_model not in models_for_mode:
                                    continue
                            elif not models_for_mode:
                                continue
                        elif llm_model and not filter_llm_model:
                            detected_mode = llm_model_to_mode(llm_model)
                            models_for_mode = mode_to_llm_models(detected_mode)
                            if models_for_mode and shared_session.form_data:
                                if shared_session.form_data.llm_model not in models_for_mode:
                                    continue
                        
                        # Converti in LibraryEntry
                        shared_entry = session_to_library_entry(shared_session, skip_cost_calculation=True)
                        
                        # Recupera info owner che ha condiviso
                        owner = await user_store_shared.get_user_by_id(share.owner_id)
                        
                        # Arricchisci con informazioni condivisione
                        from app.models import LibraryEntry
                        shared_entry = LibraryEntry(
                            session_id=shared_entry.session_id,
                            title=shared_entry.title,
                            author=shared_entry.author,
                            llm_model=shared_entry.llm_model,
                            genre=shared_entry.genre,
                            created_at=shared_entry.created_at,
                            updated_at=shared_entry.updated_at,
                            status=shared_entry.status,
                            total_chapters=shared_entry.total_chapters,
                            completed_chapters=shared_entry.completed_chapters,
                            total_pages=shared_entry.total_pages,
                            critique_score=shared_entry.critique_score,
                            critique_status=shared_entry.critique_status,
                            pdf_path=shared_entry.pdf_path,
                            pdf_filename=shared_entry.pdf_filename,
                            pdf_url=shared_entry.pdf_url,
                            cover_image_path=shared_entry.cover_image_path,
                            cover_url=shared_entry.cover_url,
                            writing_time_minutes=shared_entry.writing_time_minutes,
                            estimated_cost=shared_entry.estimated_cost,
                            is_shared=True,
                            shared_by_id=share.owner_id,
                            shared_by_name=owner.name if owner else None,
                        )
                        
                        shared_entries.append(shared_entry)
                    except Exception as e:
                        print(f"[LIBRARY] Errore nel processare libro condiviso {share.book_session_id}: {e}")
                        continue
            except Exception as e:
                print(f"[LIBRARY] Errore nel recupero libri condivisi: {e}")
                # Non blocchiamo il caricamento se c'è un errore con i libri condivisi
        
        # Combina libri propri e condivisi
        all_entries = entries + shared_entries
        
        # Filtri già applicati nella query MongoDB, manteniamo solo search che richiede testo
        filtered_entries = all_entries
        
        if search:
            search_lower = search.lower()
            filtered_entries = [
                e for e in filtered_entries
                if search_lower in e.title.lower() or search_lower in (e.author or "").lower()
            ]
        
        # Ordina
        reverse_order = sort_order == "desc"
        if sort_by == "title":
            filtered_entries.sort(key=lambda e: e.title.lower(), reverse=reverse_order)
        elif sort_by == "score":
            filtered_entries.sort(key=lambda e: e.critique_score or 0, reverse=reverse_order)
        elif sort_by == "cost":
            # Per il costo, i valori None vengono sempre messi alla fine
            # Usa una tupla per garantire che None sia sempre dopo i valori numerici
            if reverse_order:  # Discendente: costi alti prima, None alla fine
                filtered_entries.sort(
                    key=lambda e: (e.estimated_cost is None, -(e.estimated_cost or float('inf')))
                )
            else:  # Ascendente: costi bassi prima, None alla fine
                filtered_entries.sort(
                    key=lambda e: (e.estimated_cost is None, e.estimated_cost or float('inf'))
                )
        elif sort_by == "total_pages":
            # Per le pagine, i valori None vengono sempre messi alla fine
            # Usa una tupla per garantire che None sia sempre dopo i valori numerici
            if reverse_order:  # Discendente: più pagine prima, None alla fine
                filtered_entries.sort(
                    key=lambda e: (e.total_pages is None, -(e.total_pages or 0))
                )
            else:  # Ascendente: meno pagine prima, None alla fine
                filtered_entries.sort(
                    key=lambda e: (e.total_pages is None, e.total_pages or float('inf'))
                )
        elif sort_by == "updated_at":
            filtered_entries.sort(key=lambda e: e.updated_at, reverse=reverse_order)
        else:  # created_at default
            filtered_entries.sort(key=lambda e: e.created_at, reverse=reverse_order)
        
        # Calcola statistiche solo sui libri propri (non includere libri condivisi nelle stats)
        stats = calculate_library_stats(entries)
        
        # Applica paginazione DOPO l'ordinamento
        total_filtered = len(filtered_entries)
        start_index = skip
        end_index = skip + limit
        paginated_entries = filtered_entries[start_index:end_index]
        has_more = end_index < total_filtered
        
        return LibraryResponse(
            books=paginated_entries,
            total=total_filtered,  # Totale prima della paginazione
            has_more=has_more,
            stats=stats,
        )
    
    except Exception as e:
        print(f"[LIBRARY] Errore nel recupero libreria: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nel recupero della libreria: {str(e)}"
        )


@app.get("/api/library/stats", response_model=LibraryStats)
async def get_library_stats_endpoint(
    current_user = Depends(require_admin),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """Restituisce statistiche aggregate della libreria (solo admin, dati globali)."""
    try:
        # Controlla cache
        cache_key = "library_stats"
        cached = get_cached_stats(cache_key)
        if cached is not None:
            return cached
        
        from app.agent.session_store_helpers import get_all_sessions_async
        session_store = get_session_store()
        # Admin vede tutte le sessioni (user_id=None)
        # Usa proiezione MongoDB per caricare solo i campi necessari (ottimizzazione performance)
        all_sessions = await get_all_sessions_async(session_store, user_id=None, fields=LIBRARY_ENTRY_FIELDS)
        
        # Converti tutte le sessioni in LibraryEntry e calcola costi mancanti in memoria
        entries = []
        sessions_to_update = []  # Raccogli sessioni da aggiornare in background
        
        for session in all_sessions.values():
            try:
                entry = session_to_library_entry(session, skip_cost_calculation=True)
                
                # Se il costo manca ma è calcolabile, calcolalo in memoria per le stats
                if entry.estimated_cost is None and entry.status == "complete" and entry.total_pages:
                    # Calcola costo in memoria
                    calculated_cost = calculate_generation_cost(session, entry.total_pages)
                    if calculated_cost is not None:
                        # Aggiorna entry con costo calcolato (per le stats)
                        entry.estimated_cost = calculated_cost
                        # Raccogli per salvare in background
                        sessions_to_update.append((session.session_id, calculated_cost))
                
                entries.append(entry)
            except Exception as e:
                print(f"[LIBRARY STATS] Errore nel convertire sessione {session.session_id}: {e}")
                continue
        
        # Salva costi calcolati in background (batch)
        if sessions_to_update:
            async def backfill_costs():
                """Salva costi calcolati in background."""
                for session_id, cost in sessions_to_update:
                    try:
                        await set_estimated_cost_async(session_store, session_id, cost)
                    except Exception as e:
                        print(f"[LIBRARY STATS] Errore nel salvare costo per {session_id}: {e}")
                # Invalida cache dopo il backfill
                if cache_key in _stats_cache:
                    del _stats_cache[cache_key]
            
            background_tasks.add_task(backfill_costs)
        
        stats = calculate_library_stats(entries)
        # Salva in cache
        set_cached_stats(cache_key, stats)
        return stats
    
    except Exception as e:
        print(f"[LIBRARY STATS] Errore nel calcolo statistiche: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nel calcolo delle statistiche: {str(e)}"
        )


@app.get("/api/library/stats/advanced", response_model=AdvancedStats)
async def get_advanced_stats_endpoint(
    current_user = Depends(require_admin),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """Restituisce statistiche avanzate con analisi temporali e confronto modelli (solo admin, dati globali)."""
    try:
        # Controlla cache
        cache_key = "library_stats_advanced"
        cached = get_cached_stats(cache_key)
        if cached is not None:
            return cached
        
        from app.agent.session_store_helpers import get_all_sessions_async
        session_store = get_session_store()
        # Admin vede tutte le sessioni (user_id=None)
        # Usa proiezione MongoDB per caricare solo i campi necessari (ottimizzazione performance)
        all_sessions = await get_all_sessions_async(session_store, user_id=None, fields=LIBRARY_ENTRY_FIELDS)
        
        # Converti tutte le sessioni in LibraryEntry e calcola costi mancanti in memoria
        entries = []
        sessions_to_update = []  # Raccogli sessioni da aggiornare in background
        
        for session in all_sessions.values():
            try:
                entry = session_to_library_entry(session, skip_cost_calculation=True)
                
                # Se il costo manca ma è calcolabile, calcolalo in memoria per le stats
                if entry.estimated_cost is None and entry.status == "complete" and entry.total_pages:
                    # Calcola costo in memoria
                    calculated_cost = calculate_generation_cost(session, entry.total_pages)
                    if calculated_cost is not None:
                        # Aggiorna entry con costo calcolato (per le stats)
                        entry.estimated_cost = calculated_cost
                        # Raccogli per salvare in background
                        sessions_to_update.append((session.session_id, calculated_cost))
                
                entries.append(entry)
            except Exception as e:
                print(f"[ADVANCED STATS] Errore nel convertire sessione {session.session_id}: {e}")
                continue
        
        # Salva costi calcolati in background (batch)
        if sessions_to_update:
            async def backfill_costs():
                """Salva costi calcolati in background."""
                for session_id, cost in sessions_to_update:
                    try:
                        await set_estimated_cost_async(session_store, session_id, cost)
                    except Exception as e:
                        print(f"[ADVANCED STATS] Errore nel salvare costo per {session_id}: {e}")
                # Invalida cache dopo il backfill
                if cache_key in _stats_cache:
                    del _stats_cache[cache_key]
            
            background_tasks.add_task(backfill_costs)
        
        advanced_stats = calculate_advanced_stats(entries)
        # Salva in cache
        set_cached_stats(cache_key, advanced_stats)
        return advanced_stats
    
    except Exception as e:
        print(f"[ADVANCED STATS] Errore nel calcolo statistiche avanzate: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nel calcolo delle statistiche avanzate: {str(e)}"
        )


@app.get("/api/admin/users/stats", response_model=UsersStats)
async def get_users_stats_endpoint(
    current_user = Depends(require_admin),
):
    """Restituisce statistiche sugli utenti: totale utenti e conteggio libri per utente (solo admin)."""
    try:
        # Controlla cache
        cache_key = "admin_users_stats"
        cached = get_cached_stats(cache_key)
        if cached is not None:
            # Se la cache contiene un dict, convertilo in UsersStats
            if isinstance(cached, dict):
                return UsersStats(**cached)
            return cached
        
        from app.agent.session_store_helpers import get_all_sessions_async
        from app.agent.user_store import get_user_store
        
        user_store = get_user_store()
        session_store = get_session_store()
        
        # Assicurati che user_store sia connesso
        if user_store.client is None or user_store.users_collection is None:
            await user_store.connect()
        
        # Ottieni tutti gli utenti
        try:
            all_users = await user_store.get_all_users(skip=0, limit=10000)  # Limite alto per ottenere tutti
            total_users = len(all_users)
        except Exception as e:
            print(f"[USERS STATS] Errore nel recupero utenti: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=500,
                detail=f"Errore nel recupero degli utenti: {str(e)}"
            )
        
        # Conta libri per utente usando aggregazione MongoDB diretta con client dedicato
        books_per_user = defaultdict(int)
        
        # Usa un client MongoDB dedicato per l'aggregazione (più robusto e indipendente)
        mongo_uri = os.getenv("MONGODB_URI")
        if mongo_uri:
            from motor.motor_asyncio import AsyncIOMotorClient
            client = AsyncIOMotorClient(mongo_uri)
            try:
                db = client["narrai"]
                sessions_collection = db["sessions"]
                
                pipeline = [
                    {"$match": {"user_id": {"$ne": None, "$exists": True}}},  # Filtra prima per efficienza
                    {"$group": {
                        "_id": "$user_id",
                        "count": {"$sum": 1}
                    }}
                ]
                
                async for result in sessions_collection.aggregate(pipeline):
                    user_id = result["_id"]
                    count = result["count"]
                    books_per_user[user_id] = count
                
                print(f"[USERS STATS] Contati {sum(books_per_user.values())} libri totali da aggregazione MongoDB", file=sys.stderr)
            except Exception as e:
                print(f"[USERS STATS] Errore nell'aggregazione MongoDB: {e}")
                import traceback
                traceback.print_exc()
            finally:
                client.close()
        else:
            # Fallback: carica tutte le sessioni (meno efficiente ma funziona anche con FileSessionStore)
            print(f"[USERS STATS] WARNING: MONGODB_URI non configurato, uso fallback")
            all_sessions = await get_all_sessions_async(session_store, user_id=None)
            for session in all_sessions.values():
                if session.user_id:
                    books_per_user[session.user_id] += 1
            print(f"[USERS STATS] Contati {len(all_sessions)} sessioni totali (fallback)")
        
        # Crea lista utenti con conteggio libri
        users_with_books = []
        for user in all_users:
            try:
                books_count = books_per_user.get(user.id, 0)
                # Assicurati che tutti i valori siano serializzabili (stringhe, numeri, booleani)
                users_with_books.append({
                    "user_id": str(user.id) if user.id else "N/A",
                    "name": str(user.name) if user.name else "N/A",
                    "email": str(user.email) if user.email else "N/A",
                    "books_count": int(books_count) if books_count else 0,
                })
            except Exception as e:
                print(f"[USERS STATS] Errore nel processare utente {getattr(user, 'id', 'unknown')}: {e}", file=sys.stderr)
                continue
        
        # Rimuovi entry "__unassigned__" se presente (non è un utente reale)
        if "__unassigned__" in books_per_user:
            unassigned_count = books_per_user["__unassigned__"]
            print(f"[USERS STATS] Sessioni senza user_id (non assegnate): {unassigned_count}")
        
        # Ordina per numero di libri (decrescente)
        users_with_books.sort(key=lambda x: x["books_count"], reverse=True)
        
        # Crea oggetto UsersStats per serializzazione corretta
        try:
            result = UsersStats(
                total_users=int(total_users),
                users_with_books=[UserBookCount(**user) for user in users_with_books],
            )
        except Exception as e:
            print(f"[USERS STATS] Errore nella creazione UsersStats: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=500,
                detail=f"Errore nella serializzazione dei dati: {str(e)}"
            )
        
        # Salva in cache (converti in dict per la cache)
        try:
            set_cached_stats(cache_key, result.model_dump())
        except Exception as e:
            print(f"[USERS STATS] Errore nel salvare cache: {e}", file=sys.stderr)
        
        return result
    
    except Exception as e:
        print(f"[USERS STATS] Errore nel calcolo statistiche utenti: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nel calcolo delle statistiche utenti: {str(e)}"
        )


@app.delete("/api/library/{session_id}")
async def delete_library_entry_endpoint(
    session_id: str,
    current_user = Depends(get_current_user_optional),
):
    """Elimina un progetto dalla libreria."""
    try:
        session_store = get_session_store()
        
        user_id = current_user.id if current_user else None
        session = await get_session_async(session_store, session_id, user_id=user_id)
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Progetto {session_id} non trovato"
            )
        
        # Verifica ownership (solo owner può eliminare, non chi ha accesso tramite condivisione)
        if current_user and session.user_id and session.user_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="Accesso negato: puoi eliminare solo i tuoi libri"
            )
        
        # Elimina anche tutte le condivisioni correlate
        from app.agent.book_share_store import get_book_share_store
        book_share_store = get_book_share_store()
        try:
            await book_share_store.connect()
            deleted_shares_count = await book_share_store.delete_all_shares_for_book(
                book_session_id=session_id,
                owner_id=current_user.id if current_user else session.user_id,
            )
            if deleted_shares_count > 0:
                print(f"[LIBRARY DELETE] Eliminate {deleted_shares_count} condivisioni per libro {session_id}", file=sys.stderr)
        except Exception as e:
            print(f"[LIBRARY DELETE] Avviso: errore nell'eliminazione condivisioni: {e}", file=sys.stderr)
            # Non blocchiamo l'eliminazione del libro se fallisce l'eliminazione delle condivisioni
        
        # Elimina file associati (PDF e copertina)
        deleted_files = []
        try:
            # Elimina PDF se esiste (calcola il nome file come in session_to_library_entry)
            books_dir = Path(__file__).parent.parent / "books"
            status = session.get_status()
            if status == "complete" and books_dir.exists():
                date_prefix = session.created_at.strftime("%Y-%m-%d")
                model_abbrev = get_model_abbreviation(session.form_data.llm_model)
                title_sanitized = "".join(c for c in (session.current_title or "Romanzo") if c.isalnum() or c in (' ', '-', '_')).rstrip()
                title_sanitized = title_sanitized.replace(" ", "_")
                if not title_sanitized:
                    title_sanitized = f"Libro_{session.session_id[:8]}"
                expected_filename = f"{date_prefix}_{model_abbrev}_{title_sanitized}.pdf"
                expected_path = books_dir / expected_filename
                
                if expected_path.exists():
                    expected_path.unlink()
                    deleted_files.append(f"PDF: {expected_filename}")
                else:
                    # Cerca qualsiasi PDF che potrebbe corrispondere
                    for pdf_file in books_dir.glob("*.pdf"):
                        if session.session_id[:8] in pdf_file.stem or (title_sanitized and title_sanitized.lower() in pdf_file.stem.lower()):
                            deleted_files.append(f"PDF: {pdf_file.name}")
                            pdf_file.unlink()
                            break
            
            # Elimina copertina se esiste
            if session.cover_image_path:
                cover_path = Path(session.cover_image_path)
                if cover_path.exists():
                    cover_path.unlink()
                    deleted_files.append(f"Copertina: {cover_path.name}")
        except Exception as file_error:
            print(f"[LIBRARY DELETE] Errore nell'eliminazione file per {session_id}: {file_error}")
            # Continua comunque con l'eliminazione della sessione
        
        deleted = await delete_session_async(session_store, session_id)
        if deleted:
            response = {"success": True, "message": f"Progetto {session_id} eliminato con successo"}
            if deleted_files:
                response["deleted_files"] = deleted_files
            return response
        else:
            raise HTTPException(
                status_code=500,
                detail="Errore nell'eliminazione del progetto"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[LIBRARY DELETE] Errore nell'eliminazione: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nell'eliminazione del progetto: {str(e)}"
        )


@app.get("/api/library/pdfs", response_model=list[PdfEntry])
async def get_available_pdfs_endpoint():
    """Restituisce la lista di tutti i PDF disponibili."""
    try:
        pdf_entries = scan_pdf_directory()
        return pdf_entries
    
    except Exception as e:
        print(f"[LIBRARY PDFS] Errore nello scan PDF: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nel recupero dei PDF: {str(e)}"
        )


@app.get("/api/library/cover/{session_id}")
async def get_cover_image_endpoint(
    session_id: str,
    current_user = Depends(get_current_user_optional),
):
    """Restituisce l'immagine della copertina per una sessione."""
    try:
        session_store = get_session_store()
        user_id = current_user.id if current_user else None
        session = await get_session_async(session_store, session_id, user_id=user_id)
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Sessione {session_id} non trovata"
            )
        
        if current_user and session.user_id and session.user_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="Accesso negato: questa sessione appartiene a un altro utente"
            )
        
        if not session.cover_image_path:
            raise HTTPException(
                status_code=404,
                detail="Copertina non disponibile per questa sessione"
            )
        
        cover_path_str = session.cover_image_path
        
        # Se il path è su GCS, usa StorageService
        if cover_path_str.startswith("gs://"):
            storage_service = get_storage_service()
            
            # Genera URL firmato e redirect
            signed_url = storage_service.get_signed_url(cover_path_str, expiration_minutes=60)
            if signed_url and signed_url.startswith("http"):
                return RedirectResponse(url=signed_url)
            
            # Se non riesce a generare URL firmato, scarica e serve
            try:
                cover_data = storage_service.download_file(cover_path_str)
                if cover_data:
                    # Determina il media type dal nome file
                    suffix = Path(cover_path_str).suffix.lower()
                    media_type = 'image/png' if suffix == '.png' else 'image/jpeg'
                    return Response(content=cover_data, media_type=media_type)
            except FileNotFoundError as download_err:
                error_msg = str(download_err)
                print(f"[COVER IMAGE] Errore download da GCS: {error_msg}")
                raise HTTPException(
                    status_code=404,
                    detail=error_msg
                )
            except Exception as download_err:
                print(f"[COVER IMAGE] Errore download da GCS: {download_err}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Errore nel recupero della copertina: {str(download_err)}"
                )
        
        # Path locale
        cover_path = Path(cover_path_str)
        if not cover_path.exists():
            raise HTTPException(
                status_code=404,
                detail="File copertina non trovato"
            )
        
        # Determina il media type
        suffix = cover_path.suffix.lower()
        media_type = 'image/png' if suffix == '.png' else 'image/jpeg'
        
        return FileResponse(
            path=str(cover_path),
            media_type=media_type,
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[COVER IMAGE] Errore nel recupero copertina: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nel recupero della copertina: {str(e)}"
        )


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


@app.post("/api/library/cover/regenerate/{session_id}")
async def regenerate_cover_endpoint(
    session_id: str,
    current_user = Depends(get_current_user_optional),
):
    """Rigenera la copertina per un libro completato."""
    try:
        session_store = get_session_store()
        user_id = current_user.id if current_user else None
        session = await get_session_async(session_store, session_id, user_id=user_id)
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Sessione {session_id} non trovata"
            )
        
        if current_user and session.user_id and session.user_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="Accesso negato: questa sessione appartiene a un altro utente"
            )
        
        status = session.get_status()
        if status != "complete":
            raise HTTPException(
                status_code=400,
                detail="Il libro deve essere completato per rigenerare la copertina"
            )
        
        # Recupera API key
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="GOOGLE_API_KEY non configurata. Verifica il file .env nella root del progetto."
            )
        
        print(f"[REGENERATE COVER] Avvio rigenerazione copertina per sessione {session_id}")
        
        # Sanitizza il plot per evitare blocchi da contenuti sensibili
        original_plot = session.current_draft or ""
        sanitized_plot = sanitize_plot_for_cover(original_plot)
        print(f"[REGENERATE COVER] Plot sanitizzato: {len(original_plot)} -> {len(sanitized_plot)} caratteri")
        
        # Rigenera copertina con plot sanitizzato
        cover_path = await generate_book_cover(
            session_id=session_id,
            title=session.current_title or "Romanzo",
            author=session.form_data.user_name or "Autore",
            plot=sanitized_plot,
            api_key=api_key,
            cover_style=session.form_data.cover_style,
        )
        
        # Carica copertina su GCS
        try:
            storage_service = get_storage_service()
            user_id = session.user_id if hasattr(session, 'user_id') else None
            cover_filename = f"{session_id}_cover.png"
            with open(cover_path, 'rb') as f:
                cover_data = f.read()
            gcs_path = storage_service.upload_file(
                data=cover_data,
                destination_path=f"covers/{cover_filename}",
                content_type="image/png",
                user_id=user_id,
            )
            await update_cover_image_path_async(session_store, session_id, gcs_path)
            print(f"[REGENERATE COVER] Copertina rigenerata e caricata su GCS: {gcs_path}")
            return {"success": True, "cover_path": gcs_path}
        except Exception as e:
            print(f"[REGENERATE COVER] ERRORE nel caricamento copertina su GCS: {e}, uso path locale")
            await update_cover_image_path_async(session_store, session_id, str(cover_path))
            print(f"[REGENERATE COVER] Copertina rigenerata con successo: {cover_path}")
            return {"success": True, "cover_path": str(cover_path)}
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[REGENERATE COVER] Errore nella rigenerazione copertina: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nella rigenerazione della copertina: {str(e)}"
        )


@app.get("/api/library/missing-covers")
async def get_missing_covers_endpoint():
    """Restituisce lista di libri completati senza copertina."""
    try:
        from app.agent.session_store_helpers import get_all_sessions_async
        session_store = get_session_store()
        all_sessions = await get_all_sessions_async(session_store)
        
        missing_covers = []
        
        for session_id, session in all_sessions.items():
            status = session.get_status()
            if status == "complete":
                # Controlla se la copertina manca o il file non esiste
                has_cover = False
                if session.cover_image_path:
                    cover_path = Path(session.cover_image_path)
                    if cover_path.exists():
                        has_cover = True
                
                if not has_cover:
                    entry = session_to_library_entry(session)
                    missing_covers.append({
                        "session_id": session_id,
                        "title": entry.title,
                        "author": entry.author,
                        "created_at": entry.created_at.isoformat(),
                    })
        
        return {"missing_covers": missing_covers, "count": len(missing_covers)}
    
    except Exception as e:
        print(f"[MISSING COVERS] Errore nel recupero libri senza copertina: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nel recupero dei libri senza copertina: {str(e)}"
        )


@app.get("/api/library/cleanup/preview")
async def preview_obsolete_books_endpoint():
    """
    Restituisce la lista dei libri obsoleti che verrebbero eliminati dalla pulizia.
    I libri obsoleti sono quelli che:
    - Non hanno voto (critique_score è None) - qualsiasi stato
    - Sono completati ma senza copertina
    """
    try:
        from app.agent.session_store_helpers import get_all_sessions_async
        session_store = get_session_store()
        all_sessions = await get_all_sessions_async(session_store)
        
        # Identifica libri obsoleti
        obsolete_books = []
        
        for session_id, session in all_sessions.items():
            # Converti in LibraryEntry per ottenere status e critique_score
            try:
                entry = session_to_library_entry(session)
                # Libro obsoleto se:
                # 1. Senza voto (qualsiasi stato)
                # 2. Completato ma senza copertina
                is_obsolete = (
                    entry.critique_score is None  # Senza voto (qualsiasi stato)
                    or 
                    (entry.status == "complete" and not session.cover_image_path)  # Completato ma senza copertina
                )
                if is_obsolete:
                    obsolete_books.append({
                        "session_id": session_id,
                        "title": entry.title,
                        "author": entry.author,
                        "status": entry.status,
                        "created_at": entry.created_at.isoformat(),
                        "updated_at": entry.updated_at.isoformat(),
                        "has_pdf": entry.pdf_filename is not None,
                        "has_cover": session.cover_image_path is not None,
                        "has_score": entry.critique_score is not None,
                    })
            except Exception as e:
                print(f"[CLEANUP PREVIEW] Errore nel processare sessione {session_id}: {e}")
                continue
        
        return {
            "obsolete_books": obsolete_books,
            "count": len(obsolete_books)
        }
    
    except Exception as e:
        print(f"[CLEANUP PREVIEW] Errore: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nella preview dei libri obsoleti: {str(e)}"
        )


@app.post("/api/library/cleanup")
async def cleanup_obsolete_books_endpoint():
    """
    Elimina automaticamente tutti i libri obsoleti dalla libreria.
    I libri obsoleti sono quelli che:
    - Non hanno voto (critique_score è None) - qualsiasi stato
    - Sono completati ma senza copertina
    """
    try:
        from app.agent.session_store_helpers import get_all_sessions_async
        session_store = get_session_store()
        all_sessions = await get_all_sessions_async(session_store)
        
        # Identifica libri obsoleti
        obsolete_session_ids = []
        books_dir = Path(__file__).parent.parent / "books"
        
        for session_id, session in all_sessions.items():
            # Converti in LibraryEntry per ottenere status e critique_score
            try:
                entry = session_to_library_entry(session)
                # Libro obsoleto se:
                # 1. Senza voto (qualsiasi stato)
                # 2. Completato ma senza copertina
                is_obsolete = (
                    entry.critique_score is None  # Senza voto (qualsiasi stato)
                    or 
                    (entry.status == "complete" and not session.cover_image_path)  # Completato ma senza copertina
                )
                if is_obsolete:
                    obsolete_session_ids.append({
                        "session_id": session_id,
                        "title": entry.title,
                        "status": entry.status,
                        "has_pdf": entry.pdf_filename is not None,
                        "has_cover": session.cover_image_path is not None,
                    })
            except Exception as e:
                print(f"[CLEANUP] Errore nel processare sessione {session_id}: {e}")
                continue
        
        # Elimina i libri obsoleti
        deleted_count = 0
        deleted_files_count = 0
        errors = []
        
        for book_info in obsolete_session_ids:
            session_id = book_info["session_id"]
            try:
                session = await get_session_async(session_store, session_id)
                if not session:
                    continue
                
                # Elimina file associati
                files_deleted = 0
                session_status = session.get_status()
                try:
                    # Elimina PDF se esiste (calcola il nome file come in session_to_library_entry)
                    if session_status == "complete" and books_dir.exists():
                        date_prefix = session.created_at.strftime("%Y-%m-%d")
                        model_abbrev = get_model_abbreviation(session.form_data.llm_model)
                        title_sanitized = "".join(c for c in (session.current_title or "Romanzo") if c.isalnum() or c in (' ', '-', '_')).rstrip()
                        title_sanitized = title_sanitized.replace(" ", "_")
                        if not title_sanitized:
                            title_sanitized = f"Libro_{session.session_id[:8]}"
                        expected_filename = f"{date_prefix}_{model_abbrev}_{title_sanitized}.pdf"
                        expected_path = books_dir / expected_filename
                        
                        if expected_path.exists():
                            expected_path.unlink()
                            files_deleted += 1
                        else:
                            # Cerca qualsiasi PDF che potrebbe corrispondere
                            for pdf_file in books_dir.glob("*.pdf"):
                                if session.session_id[:8] in pdf_file.stem or (title_sanitized and title_sanitized.lower() in pdf_file.stem.lower()):
                                    pdf_file.unlink()
                                    files_deleted += 1
                                    break
                    
                    # Elimina copertina se esiste
                    if session.cover_image_path:
                        cover_path = Path(session.cover_image_path)
                        if cover_path.exists():
                            cover_path.unlink()
                            files_deleted += 1
                except Exception as file_error:
                    errors.append(f"Errore eliminazione file per {book_info['title']}: {file_error}")
                
                # Elimina sessione
                if await delete_session_async(session_store, session_id):
                    deleted_count += 1
                    deleted_files_count += files_deleted
                else:
                    errors.append(f"Errore eliminazione sessione {session_id}")
                    
            except Exception as e:
                errors.append(f"Errore durante eliminazione {book_info['title']}: {e}")
                print(f"[CLEANUP] Errore eliminando {session_id}: {e}")
        
        return {
            "success": True,
            "obsolete_books_found": len(obsolete_session_ids),
            "deleted_sessions": deleted_count,
            "deleted_files": deleted_files_count,
            "errors": errors if errors else None,
            "message": f"Eliminati {deleted_count} libri obsoleti e {deleted_files_count} file associati"
        }
    
    except Exception as e:
        print(f"[CLEANUP] Errore nella pulizia: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nella pulizia dei libri obsoleti: {str(e)}"
        )


def is_gemini_2_5(model_name: Optional[str]) -> bool:
    """Verifica se un modello è una versione 2.5 di Gemini."""
    if not model_name:
        return False
    return "gemini-2.5" in model_name.lower()


@app.get("/api/admin/books/gemini-2.5/stats")
async def get_gemini_2_5_stats_endpoint(
    current_user = Depends(require_admin),
):
    """Restituisce statistiche sui libri generati con Gemini 2.5 (solo admin)."""
    try:
        from app.agent.session_store_helpers import get_all_sessions_async
        session_store = get_session_store()
        all_sessions = await get_all_sessions_async(session_store, user_id=None)
        
        # Filtra sessioni con modelli 2.5
        gemini_2_5_sessions = {}
        for session_id, session in all_sessions.items():
            if session.form_data and is_gemini_2_5(session.form_data.llm_model):
                gemini_2_5_sessions[session_id] = session
        
        # Raggruppa per modello
        by_model = defaultdict(int)
        by_status = defaultdict(int)
        with_pdf = 0
        with_cover = 0
        books_list = []
        
        books_dir = Path(__file__).parent.parent / "books"
        
        for session_id, session in gemini_2_5_sessions.items():
            model = session.form_data.llm_model
            by_model[model] += 1
            
            # Converti in LibraryEntry per ottenere status
            try:
                entry = session_to_library_entry(session, skip_cost_calculation=True)
                status = entry.status
                by_status[status] += 1
                
                # Verifica PDF
                has_pdf = False
                if entry.pdf_filename:
                    has_pdf = True
                elif status == "complete" and books_dir.exists():
                    # Cerca PDF locale
                    date_prefix = session.created_at.strftime("%Y-%m-%d")
                    model_abbrev = get_model_abbreviation(session.form_data.llm_model)
                    title_sanitized = "".join(c for c in (session.current_title or "Romanzo") if c.isalnum() or c in (' ', '-', '_')).rstrip()
                    title_sanitized = title_sanitized.replace(" ", "_")
                    if not title_sanitized:
                        title_sanitized = f"Libro_{session.session_id[:8]}"
                    expected_filename = f"{date_prefix}_{model_abbrev}_{title_sanitized}.pdf"
                    expected_path = books_dir / expected_filename
                    if expected_path.exists():
                        has_pdf = True
                    elif entry.pdf_path and entry.pdf_path.startswith("gs://"):
                        has_pdf = True
                
                if has_pdf:
                    with_pdf += 1
                
                # Verifica copertina
                has_cover = False
                if session.cover_image_path:
                    if session.cover_image_path.startswith("gs://"):
                        has_cover = True
                    else:
                        cover_path = Path(session.cover_image_path)
                        if cover_path.exists():
                            has_cover = True
                
                if has_cover:
                    with_cover += 1
                
                books_list.append({
                    "session_id": session_id,
                    "title": entry.title,
                    "model": model,
                    "status": status,
                    "has_pdf": has_pdf,
                    "has_cover": has_cover,
                    "created_at": session.created_at.isoformat(),
                })
            except Exception as e:
                print(f"[GEMINI-2.5-STATS] Errore nel processare sessione {session_id}: {e}")
                continue
        
        return {
            "total_books": len(gemini_2_5_sessions),
            "by_model": dict(by_model),
            "by_status": dict(by_status),
            "with_pdf": with_pdf,
            "with_cover": with_cover,
            "books": books_list,
        }
    
    except Exception as e:
        print(f"[GEMINI-2.5-STATS] Errore: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nel calcolo delle statistiche Gemini 2.5: {str(e)}"
        )


@app.get("/api/admin/books/gemini-2.5/preview")
async def preview_gemini_2_5_books_endpoint(
    current_user = Depends(require_admin),
):
    """Restituisce lista dettagliata di tutti i libri Gemini 2.5 da eliminare (solo admin)."""
    try:
        from app.agent.session_store_helpers import get_all_sessions_async
        session_store = get_session_store()
        all_sessions = await get_all_sessions_async(session_store, user_id=None)
        
        # Filtra sessioni con modelli 2.5
        gemini_2_5_books = []
        books_dir = Path(__file__).parent.parent / "books"
        
        for session_id, session in all_sessions.items():
            if session.form_data and is_gemini_2_5(session.form_data.llm_model):
                try:
                    entry = session_to_library_entry(session, skip_cost_calculation=True)
                    
                    # Verifica file associati
                    pdf_path = None
                    cover_path = None
                    
                    if entry.pdf_path:
                        pdf_path = entry.pdf_path
                    elif entry.status == "complete" and books_dir.exists():
                        date_prefix = session.created_at.strftime("%Y-%m-%d")
                        model_abbrev = get_model_abbreviation(session.form_data.llm_model)
                        title_sanitized = "".join(c for c in (session.current_title or "Romanzo") if c.isalnum() or c in (' ', '-', '_')).rstrip()
                        title_sanitized = title_sanitized.replace(" ", "_")
                        if not title_sanitized:
                            title_sanitized = f"Libro_{session.session_id[:8]}"
                        expected_filename = f"{date_prefix}_{model_abbrev}_{title_sanitized}.pdf"
                        expected_path = books_dir / expected_filename
                        if expected_path.exists():
                            pdf_path = str(expected_path)
                    
                    if session.cover_image_path:
                        cover_path = session.cover_image_path
                    
                    gemini_2_5_books.append({
                        "session_id": session_id,
                        "title": entry.title,
                        "author": entry.author,
                        "model": session.form_data.llm_model,
                        "status": entry.status,
                        "created_at": session.created_at.isoformat(),
                        "updated_at": session.updated_at.isoformat(),
                        "pdf_path": pdf_path,
                        "cover_path": cover_path,
                        "has_pdf": pdf_path is not None,
                        "has_cover": cover_path is not None,
                    })
                except Exception as e:
                    print(f"[GEMINI-2.5-PREVIEW] Errore nel processare sessione {session_id}: {e}")
                    continue
        
        return {
            "total_books": len(gemini_2_5_books),
            "books": gemini_2_5_books,
        }
    
    except Exception as e:
        print(f"[GEMINI-2.5-PREVIEW] Errore: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nel preview dei libri Gemini 2.5: {str(e)}"
        )


@app.post("/api/admin/books/gemini-2.5/delete")
async def delete_gemini_2_5_books_endpoint(
    dry_run: bool = False,
    model_filter: Optional[str] = None,
    status_filter: Optional[str] = None,
    current_user = Depends(require_admin),
):
    """
    Elimina tutti i libri generati con Gemini 2.5 (solo admin).
    
    Args:
        dry_run: Se True, simula l'eliminazione senza eliminare realmente
        model_filter: Filtra per modello specifico ("gemini-2.5-flash" o "gemini-2.5-pro")
        status_filter: Filtra per stato specifico (draft, outline, writing, paused, complete)
    """
    try:
        from app.agent.session_store_helpers import get_all_sessions_async, get_session_async
        session_store = get_session_store()
        all_sessions = await get_all_sessions_async(session_store, user_id=None)
        
        # Filtra sessioni con modelli 2.5
        gemini_2_5_sessions = {}
        for session_id, session in all_sessions.items():
            if session.form_data and is_gemini_2_5(session.form_data.llm_model):
                # Applica filtri opzionali
                if model_filter and session.form_data.llm_model != model_filter:
                    continue
                if status_filter:
                    entry = session_to_library_entry(session, skip_cost_calculation=True)
                    if entry.status != status_filter:
                        continue
                gemini_2_5_sessions[session_id] = session
        
        deleted_sessions = 0
        deleted_pdfs = 0
        deleted_covers = 0
        errors = []
        details = []
        
        books_dir = Path(__file__).parent.parent / "books"
        storage_service = get_storage_service()
        
        for session_id, session in gemini_2_5_sessions.items():
            try:
                entry = session_to_library_entry(session, skip_cost_calculation=True)
                detail = {
                    "session_id": session_id,
                    "title": entry.title,
                    "model": session.form_data.llm_model,
                    "status": entry.status,
                    "pdf_deleted": False,
                    "cover_deleted": False,
                    "session_deleted": False,
                }
                
                if not dry_run:
                    # Elimina PDF
                    pdf_deleted = False
                    try:
                        if entry.pdf_path:
                            if entry.pdf_path.startswith("gs://"):
                                # Elimina da GCS
                                try:
                                    storage_service.delete_file(entry.pdf_path)
                                    pdf_deleted = True
                                except Exception as e:
                                    errors.append(f"Errore eliminazione PDF GCS {entry.pdf_path}: {e}")
                            else:
                                # Elimina locale
                                pdf_path = Path(entry.pdf_path)
                                if pdf_path.exists():
                                    pdf_path.unlink()
                                    pdf_deleted = True
                        elif entry.status == "complete" and books_dir.exists():
                            # Cerca PDF locale
                            date_prefix = session.created_at.strftime("%Y-%m-%d")
                            model_abbrev = get_model_abbreviation(session.form_data.llm_model)
                            title_sanitized = "".join(c for c in (session.current_title or "Romanzo") if c.isalnum() or c in (' ', '-', '_')).rstrip()
                            title_sanitized = title_sanitized.replace(" ", "_")
                            if not title_sanitized:
                                title_sanitized = f"Libro_{session.session_id[:8]}"
                            expected_filename = f"{date_prefix}_{model_abbrev}_{title_sanitized}.pdf"
                            expected_path = books_dir / expected_filename
                            
                            if expected_path.exists():
                                expected_path.unlink()
                                pdf_deleted = True
                            else:
                                # Cerca qualsiasi PDF che potrebbe corrispondere
                                for pdf_file in books_dir.glob("*.pdf"):
                                    if session.session_id[:8] in pdf_file.stem or (title_sanitized and title_sanitized.lower() in pdf_file.stem.lower()):
                                        pdf_file.unlink()
                                        pdf_deleted = True
                                        break
                        
                        if pdf_deleted:
                            deleted_pdfs += 1
                            detail["pdf_deleted"] = True
                    except Exception as e:
                        errors.append(f"Errore eliminazione PDF per {entry.title}: {e}")
                    
                    # Elimina copertina
                    cover_deleted = False
                    try:
                        if session.cover_image_path:
                            if session.cover_image_path.startswith("gs://"):
                                # Elimina da GCS
                                try:
                                    storage_service.delete_file(session.cover_image_path)
                                    cover_deleted = True
                                except Exception as e:
                                    errors.append(f"Errore eliminazione copertina GCS {session.cover_image_path}: {e}")
                            else:
                                # Elimina locale
                                cover_path = Path(session.cover_image_path)
                                if cover_path.exists():
                                    cover_path.unlink()
                                    cover_deleted = True
                            
                            if cover_deleted:
                                deleted_covers += 1
                                detail["cover_deleted"] = True
                    except Exception as e:
                        errors.append(f"Errore eliminazione copertina per {entry.title}: {e}")
                    
                    # Elimina sessione
                    if await delete_session_async(session_store, session_id):
                        deleted_sessions += 1
                        detail["session_deleted"] = True
                    else:
                        errors.append(f"Errore eliminazione sessione {session_id}")
                else:
                    # Dry run: simula eliminazione
                    detail["pdf_deleted"] = entry.pdf_path is not None or (entry.status == "complete" and books_dir.exists())
                    detail["cover_deleted"] = session.cover_image_path is not None
                    detail["session_deleted"] = True
                
                details.append(detail)
            except Exception as e:
                errors.append(f"Errore durante eliminazione {session_id}: {e}")
                print(f"[GEMINI-2.5-DELETE] Errore eliminando {session_id}: {e}")
                import traceback
                traceback.print_exc()
        
        return {
            "success": True,
            "dry_run": dry_run,
            "total_found": len(gemini_2_5_sessions),
            "deleted_sessions": deleted_sessions if not dry_run else len(gemini_2_5_sessions),
            "deleted_pdfs": deleted_pdfs if not dry_run else sum(1 for d in details if d["pdf_deleted"]),
            "deleted_covers": deleted_covers if not dry_run else sum(1 for d in details if d["cover_deleted"]),
            "errors": errors if errors else None,
            "details": details,
        }
    
    except Exception as e:
        print(f"[GEMINI-2.5-DELETE] Errore: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nell'eliminazione dei libri Gemini 2.5: {str(e)}"
        )


@app.get("/api/library/pdf/{filename:path}")
async def download_pdf_by_filename_endpoint(filename: str):
    """Scarica un PDF specifico per nome file."""
    try:
        books_dir = Path(__file__).parent.parent / "books"
        pdf_path = books_dir / filename
        
        # Validazione sicurezza: assicurati che il file sia dentro la directory books
        try:
            pdf_path.resolve().relative_to(books_dir.resolve())
        except ValueError:
            raise HTTPException(
                status_code=403,
                detail="Accesso non consentito a questo file"
            )
        
        if not pdf_path.exists() or not pdf_path.is_file():
            raise HTTPException(
                status_code=404,
                detail=f"PDF {filename} non trovato"
            )
        
        with open(pdf_path, 'rb') as f:
            pdf_content = f.read()
        
        return Response(
            content=pdf_content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[LIBRARY PDF DOWNLOAD] Errore nel download: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nel download del PDF: {str(e)}"
        )


@app.post("/api/critique/analyze-pdf", response_model=LiteraryCritique)
async def analyze_external_pdf(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    author: Optional[str] = Form(None),
):
    """
    Analizza un PDF esterno con l'agente critico letterario.
    I risultati non vengono salvati e servono come benchmark.
    """
    try:
        # Validazione file
        if file.content_type not in ["application/pdf"]:
            # Controlla anche l'estensione come fallback
            if not file.filename or not file.filename.lower().endswith(".pdf"):
                raise HTTPException(
                    status_code=400,
                    detail="Il file deve essere un PDF (application/pdf)"
                )
        
        # Limite dimensione: 50MB
        MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB in bytes
        
        # Leggi il contenuto del file
        pdf_bytes = await file.read()
        
        # Controlla dimensione
        if len(pdf_bytes) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File troppo grande. Dimensione massima: {MAX_FILE_SIZE / (1024 * 1024):.0f}MB"
            )
        
        if len(pdf_bytes) == 0:
            raise HTTPException(
                status_code=400,
                detail="Il file PDF è vuoto"
            )
        
        # Verifica che l'API key sia configurata
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="GOOGLE_API_KEY non configurata. Verifica il file .env nella root del progetto."
            )
        
        # Usa titolo e autore forniti, altrimenti usa valori di default
        book_title = title or (file.filename and file.filename.replace(".pdf", "") or "Libro")
        book_author = author or "Autore Sconosciuto"
        
        print(f"[EXTERNAL PDF CRITIQUE] Analisi PDF: {file.filename}, Titolo: {book_title}, Autore: {book_author}")
        print(f"[EXTERNAL PDF CRITIQUE] Dimensione PDF: {len(pdf_bytes) / (1024 * 1024):.2f} MB")
        
        # Genera la critica usando la funzione esistente
        # Questa operazione può richiedere diversi minuti per PDF grandi
        try:
            print(f"[EXTERNAL PDF CRITIQUE] Avvio analisi con modello critico...")
            critique_dict = await generate_literary_critique_from_pdf(
                title=book_title,
                author=book_author,
                pdf_bytes=pdf_bytes,
                api_key=api_key,
            )
            print(f"[EXTERNAL PDF CRITIQUE] Analisi modello completata")
        except Exception as critique_error:
            print(f"[EXTERNAL PDF CRITIQUE] ERRORE durante analisi modello: {critique_error}")
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=500,
                detail=f"Errore durante l'analisi del PDF da parte del modello: {str(critique_error)}"
            )
        
        # Converti il dizionario in LiteraryCritique
        try:
            critique = LiteraryCritique(
                score=critique_dict.get("score", 0.0),
                pros=critique_dict.get("pros", []),
                cons=critique_dict.get("cons", []),
                summary=critique_dict.get("summary", ""),
            )
            print(f"[EXTERNAL PDF CRITIQUE] Analisi completata: score={critique.score}")
        except Exception as validation_error:
            print(f"[EXTERNAL PDF CRITIQUE] ERRORE nella validazione risposta: {validation_error}")
            raise HTTPException(
                status_code=500,
                detail=f"Errore nella validazione della risposta del critico: {str(validation_error)}"
            )
        
        return critique
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[EXTERNAL PDF CRITIQUE] Errore nell'analisi: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nell'analisi del PDF: {str(e)}"
        )


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


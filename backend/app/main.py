import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_config, reload_config
from app.models import (
    ConfigResponse, 
    SubmissionRequest, 
    SubmissionResponse,
    QuestionGenerationRequest,
    QuestionsResponse,
    AnswersRequest,
    AnswersResponse,
    DraftGenerationRequest,
    DraftResponse,
    DraftModificationRequest,
    DraftValidationRequest,
    DraftValidationResponse,
)
from app.agent.question_generator import generate_questions
from app.agent.draft_generator import generate_draft
from app.agent.session_store import get_session_store

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

# CORS per sviluppo locale
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Vite default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/config", response_model=ConfigResponse)
async def get_config_endpoint():
    """Restituisce la configurazione degli input."""
    try:
        # Ricarica sempre la config per permettere modifiche al YAML senza riavviare
        return reload_config()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore nel caricamento della configurazione: {str(e)}")


@app.post("/api/submissions", response_model=SubmissionResponse)
async def submit_form(data: SubmissionRequest):
    """Riceve e valida i dati del form."""
    config = get_config()
    
    # Valida il modello LLM
    if data.llm_model not in config.llm_models:
        raise HTTPException(
            status_code=400,
            detail=f"Modello LLM non valido: {data.llm_model}. Modelli disponibili: {', '.join(config.llm_models)}"
        )
    
    # Valida i campi select opzionali contro le opzioni configurate
    field_map = {field.id: field for field in config.fields}
    
    for field_id, value in data.model_dump(exclude={"llm_model", "plot"}).items():
        if value is not None and field_id in field_map:
            field = field_map[field_id]
            if field.type == "select" and field.options:
                valid_values = [opt.value for opt in field.options]
                if value not in valid_values:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Valore non valido per '{field.label}': {value}"
                    )
    
    return SubmissionResponse(
        success=True,
        message="Submission ricevuta con successo",
        data=data,
    )


@app.post("/api/questions/generate", response_model=QuestionsResponse)
async def generate_questions_endpoint(request: QuestionGenerationRequest):
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
        return response
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Errore nella generazione delle domande: {str(e)}"
        )


@app.post("/api/questions/answers", response_model=AnswersResponse)
async def submit_answers(data: AnswersRequest):
    """Riceve le risposte alle domande e continua il flusso."""
    try:
        # Per ora semplicemente conferma la ricezione
        # In futuro qui si continuerà il flusso LangGraph
        return AnswersResponse(
            success=True,
            message="Risposte ricevute con successo. Pronto per la fase di scrittura.",
            session_id=data.session_id,
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Errore nell'elaborazione delle risposte: {str(e)}"
        )


@app.post("/api/draft/generate", response_model=DraftResponse)
async def generate_draft_endpoint(request: DraftGenerationRequest):
    """Genera una bozza estesa della trama."""
    try:
        # Verifica che l'API key sia configurata
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="GOOGLE_API_KEY non configurata. Verifica il file .env nella root del progetto."
            )
        
        # Crea o recupera la sessione
        session_store = get_session_store()
        session = session_store.get_session(request.session_id)
        
        if not session:
            # Crea nuova sessione
            session = session_store.create_session(
                session_id=request.session_id,
                form_data=request.form_data,
                question_answers=request.question_answers,
            )
        
        # Genera la bozza
        draft_text, version = await generate_draft(
            form_data=request.form_data,
            question_answers=request.question_answers,
            session_id=request.session_id,
            api_key=api_key,
        )
        
        # Salva la bozza nella sessione
        session_store.update_draft(request.session_id, draft_text, version)
        
        return DraftResponse(
            success=True,
            session_id=request.session_id,
            draft_text=draft_text,
            version=version,
            message="Bozza generata con successo",
        )
    
    except Exception as e:
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
        session = session_store.get_session(request.session_id)
        
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
        draft_text, version = await generate_draft(
            form_data=session.form_data,
            question_answers=session.question_answers,
            session_id=request.session_id,
            api_key=api_key,
            previous_draft=session.current_draft,
            user_feedback=request.user_feedback,
        )
        
        # Salva la nuova versione
        session_store.update_draft(request.session_id, draft_text, version)
        
        return DraftResponse(
            success=True,
            session_id=request.session_id,
            draft_text=draft_text,
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
        session = session_store.get_session(request.session_id)
        
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
        session = session_store.get_session(session_id)
        
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


@app.get("/health")
async def health():
    """Endpoint di health check."""
    return {"status": "ok"}


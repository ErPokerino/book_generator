"""Router per gli endpoint delle domande."""
import os
import uuid
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from app.models import (
    QuestionGenerationRequest,
    QuestionsResponse,
    AnswersRequest,
    AnswersResponse,
    ProcessStartResponse,
    ProcessProgress,
)
from app.agent.question_generator import generate_questions
from app.agent.session_store import get_session_store, FileSessionStore
from app.agent.session_store_helpers import (
    create_session_async,
    save_generated_questions_async,
    get_session_async,
    update_questions_progress_async,
)
from app.middleware.auth import get_current_user_optional
from app.services.generation_service import background_generate_questions

router = APIRouter(prefix="/api/questions", tags=["questions"])


@router.post("/generate", response_model=QuestionsResponse)
async def generate_questions_endpoint(
    request: QuestionGenerationRequest,
    current_user = Depends(get_current_user_optional)
):
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
        session_store = get_session_store()
        try:
            questions_dict = [q.model_dump() for q in response.questions]
            user_id = current_user.id if current_user else None
            await create_session_async(
                session_store=session_store,
                session_id=response.session_id,
                form_data=request.form_data,
                question_answers=[],
                user_id=user_id,
            )
            await save_generated_questions_async(
                session_store=session_store,
                session_id=response.session_id,
                questions=questions_dict,
            )
            print(f"[DEBUG] Sessione {response.session_id} creata nel session store dopo generazione domande")
        except Exception as session_error:
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


@router.post("/answers", response_model=AnswersResponse)
async def submit_answers(
    data: AnswersRequest,
    current_user = Depends(get_current_user_optional)
):
    """Riceve le risposte alle domande e continua il flusso."""
    print(f"[SUBMIT ANSWERS] Ricevute risposte per sessione {data.session_id}")
    print(f"[SUBMIT ANSWERS] Numero di risposte: {len(data.answers)}")
    try:
        session_store = get_session_store()
        user_id = current_user.id if current_user else None
        session = await get_session_async(session_store, data.session_id, user_id=user_id)
        
        if not session:
            print(f"[SUBMIT ANSWERS] ERRORE: Sessione {data.session_id} NON trovata!")
            raise HTTPException(
                status_code=404,
                detail=f"Sessione {data.session_id} non trovata. Ricarica la pagina e riprova."
            )
        
        # Verifica ownership se autenticato
        if current_user and session.user_id and session.user_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="Accesso negato: questa sessione appartiene a un altro utente"
            )
        
        print(f"[SUBMIT ANSWERS] Sessione trovata, aggiorno le risposte...")
        session.question_answers = data.answers
        print(f"[SUBMIT ANSWERS] Aggiornate {len(data.answers)} risposte nella sessione")
        
        # Salva la sessione aggiornata
        if isinstance(session_store, FileSessionStore):
            print(f"[SUBMIT ANSWERS] Salvataggio sessioni su file...")
            try:
                session_store._save_sessions()
                print(f"[SUBMIT ANSWERS] Sessioni salvate con successo")
            except Exception as save_error:
                print(f"[WARNING] Errore nel salvataggio sessioni: {save_error}")
        elif hasattr(session_store, 'save_session'):
            # MongoSessionStore
            await session_store.save_session(session)
        
        return AnswersResponse(
            success=True,
            message="Risposte salvate con successo",
            session_id=data.session_id,
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Errore nel salvataggio delle risposte: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nel salvataggio delle risposte: {str(e)}"
        )


@router.post("/generate/start", response_model=ProcessStartResponse)
async def start_questions_generation_endpoint(
    request: QuestionGenerationRequest,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user_optional),
):
    """Avvia la generazione delle domande in background."""
    try:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="GOOGLE_API_KEY non configurata."
            )
        
        # Ottieni user_id dall'utente corrente (se autenticato)
        user_id = current_user.id if current_user else None
        
        # Log per debug autenticazione
        print(f"[QUESTIONS GENERATION] user_id: {user_id}, current_user: {current_user.email if current_user else 'None'}")
        
        # Nota: I crediti vengono consumati quando si avvia la generazione del libro, non qui
        
        # Genera session_id
        session_id = str(uuid.uuid4())
        
        # Crea la sessione con user_id
        session_store = get_session_store()
        await create_session_async(
            session_store,
            session_id=session_id,
            form_data=request.form_data,
            question_answers=[],
            user_id=user_id,
        )
        
        # Inizializza progresso: pending
        await update_questions_progress_async(
            session_store,
            session_id,
            {
                "status": "pending",
                "current_step": 0,
                "total_steps": 1,
                "progress_percentage": 0.0,
            }
        )
        
        # Avvia il task in background
        background_tasks.add_task(
            background_generate_questions,
            session_id=session_id,
            form_data=request.form_data,
            api_key=api_key,
        )
        
        print(f"[QUESTIONS GENERATION] Task di generazione domande avviato per sessione {session_id}")
        
        return ProcessStartResponse(
            success=True,
            session_id=session_id,
            message="Generazione delle domande avviata. Usa /api/questions/progress/{session_id} per monitorare lo stato.",
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Errore nell'avvio generazione domande: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nell'avvio della generazione delle domande: {str(e)}"
        )


@router.get("/progress/{session_id}", response_model=ProcessProgress)
async def get_questions_progress_endpoint(session_id: str):
    """Restituisce lo stato di avanzamento della generazione domande."""
    try:
        session_store = get_session_store()
        session = await get_session_async(session_store, session_id)
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Sessione {session_id} non trovata"
            )
        
        progress = session.questions_progress
        if not progress:
            # Nessun progresso = processo non avviato
            return ProcessProgress(
                status="pending",
                current_step=0,
                total_steps=1,
                progress_percentage=0.0,
            )
        
        return ProcessProgress(**progress)
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Errore nel recupero progresso domande: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Errore nel recupero del progresso: {str(e)}"
        )

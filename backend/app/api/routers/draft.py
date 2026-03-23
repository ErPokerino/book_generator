"""Router per gli endpoint delle bozze."""
import os
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from app.models import (
    DraftGenerationRequest,
    DraftResponse,
    DraftModificationRequest,
    DraftManualUpdateRequest,
    DraftValidationRequest,
    DraftValidationResponse,
    ProcessProgress,
    ProcessStartResponse,
)
from app.agent.draft_generator import generate_draft
from app.agent.session_store import get_session_store
from app.agent.session_store_helpers import (
    get_session_async,
    create_session_async,
    update_draft_async,
    validate_session_async,
    update_token_usage_async,
)
from app.core.logging import get_logger
from app.middleware.auth import get_current_user_optional
from app.services.generation_service import background_generate_draft
from app.services.process_job_service import (
    begin_process_job_async,
    mark_process_completed_async,
    mark_process_failed_async,
    mark_process_running_async,
)

router = APIRouter(prefix="/api/draft", tags=["draft"])
logger = get_logger("draft-router")


@router.post("/generate", response_model=DraftResponse)
async def generate_draft_endpoint(
    request: DraftGenerationRequest,
    current_user = Depends(get_current_user_optional)
):
    """Genera una bozza estesa della trama."""
    session_store = get_session_store()
    try:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="GOOGLE_API_KEY non configurata. Verifica il file .env nella root del progetto."
            )
        
        user_id = current_user.id if current_user else None
        session = await get_session_async(session_store, request.session_id, user_id=user_id)
        
        if not session:
            session = await create_session_async(
                session_store=session_store,
                session_id=request.session_id,
                form_data=request.form_data,
                question_answers=request.question_answers,
                user_id=user_id,
            )
        elif current_user and session.user_id and session.user_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="Accesso negato: questa sessione appartiene a un altro utente"
            )
        
        await mark_process_running_async(
            session_store,
            request.session_id,
            "draft",
            current_step=0,
            total_steps=1,
            progress_percentage=0.0,
        )

        draft_text, title, version, token_usage, character_profiles = await generate_draft(
            form_data=request.form_data,
            question_answers=request.question_answers,
            session_id=request.session_id,
            api_key=api_key,
        )
        
        await update_draft_async(session_store, request.session_id, draft_text, version, title, character_profiles)
        
        # Salva token usage per la fase draft
        await update_token_usage_async(
            session_store=session_store,
            session_id=request.session_id,
            phase="draft",
            input_tokens=token_usage.get("input_tokens", 0),
            output_tokens=token_usage.get("output_tokens", 0),
            model=token_usage.get("model", "gemini-3.1-pro-preview"),
        )

        await mark_process_completed_async(
            session_store,
            request.session_id,
            "draft",
            current_step=1,
            total_steps=1,
            progress_percentage=100.0,
            result={
                "success": True,
                "session_id": request.session_id,
                "draft_text": draft_text,
                "title": title,
                "version": version,
                "message": "Bozza generata con successo",
            },
        )
        
        return DraftResponse(
            success=True,
            session_id=request.session_id,
            draft_text=draft_text,
            title=title,
            version=version,
            message="Bozza generata con successo",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Errore critico in generate_draft_endpoint", context={"session_id": request.session_id})
        await mark_process_failed_async(
            session_store,
            request.session_id,
            "draft",
            f"Errore nella generazione della bozza: {str(e)}",
            recoverable=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Errore nella generazione della bozza: {str(e)}"
        )


@router.post("/generate/start", response_model=ProcessStartResponse)
async def start_draft_generation_endpoint(
    request: DraftGenerationRequest,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user_optional),
):
    """Avvia la generazione della bozza in background in modo idempotente."""
    try:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="GOOGLE_API_KEY non configurata. Verifica il file .env nella root del progetto."
            )

        session_store = get_session_store()
        user_id = current_user.id if current_user else None
        session = await get_session_async(session_store, request.session_id, user_id=user_id)

        if not session:
            session = await create_session_async(
                session_store=session_store,
                session_id=request.session_id,
                form_data=request.form_data,
                question_answers=request.question_answers,
                user_id=user_id,
            )
        elif current_user and session.user_id and session.user_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="Accesso negato: questa sessione appartiene a un altro utente"
            )

        started, job = await begin_process_job_async(
            session_store,
            request.session_id,
            "draft",
            total_steps=1,
        )
        if not started:
            return ProcessStartResponse(
                success=True,
                session_id=request.session_id,
                message="Generazione della bozza già in corso.",
                job_id=job.get("job_id"),
                job_type="draft",
                already_running=True,
            )

        background_tasks.add_task(
            background_generate_draft,
            session_id=request.session_id,
            form_data=request.form_data,
            question_answers=request.question_answers,
            api_key=api_key,
        )

        return ProcessStartResponse(
            success=True,
            session_id=request.session_id,
            message="Generazione della bozza avviata. Usa /api/draft/progress/{session_id} per monitorare lo stato.",
            job_id=job.get("job_id"),
            job_type="draft",
            already_running=False,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Errore nell'avvio generazione bozza", context={"session_id": request.session_id})
        raise HTTPException(
            status_code=500,
            detail=f"Errore nell'avvio della generazione della bozza: {str(e)}"
        )


@router.post("/modify", response_model=DraftResponse)
async def modify_draft_endpoint(
    request: DraftModificationRequest,
    current_user = Depends(get_current_user_optional)
):
    """Rigenera la bozza con le modifiche richieste dall'utente."""
    try:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="GOOGLE_API_KEY non configurata. Verifica il file .env nella root del progetto."
            )
        
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
        
        if not session.current_draft:
            raise HTTPException(
                status_code=400,
                detail="Nessuna bozza esistente da modificare"
            )
        
        draft_text, title, version, token_usage, character_profiles = await generate_draft(
            form_data=session.form_data,
            question_answers=session.question_answers,
            session_id=request.session_id,
            api_key=api_key,
            previous_draft=session.current_draft,
            user_feedback=request.user_feedback,
        )
        
        await update_draft_async(session_store, request.session_id, draft_text, version, title, character_profiles)
        
        # Salva token usage per la fase draft (rigenerazione)
        await update_token_usage_async(
            session_store=session_store,
            session_id=request.session_id,
            phase="draft",
            input_tokens=token_usage.get("input_tokens", 0),
            output_tokens=token_usage.get("output_tokens", 0),
            model=token_usage.get("model", "gemini-3.1-pro-preview"),
        )
        
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


@router.post("/update", response_model=DraftResponse)
async def update_draft_manually_endpoint(
    request: DraftManualUpdateRequest,
    current_user = Depends(get_current_user_optional)
):
    """Salva le modifiche manuali alla bozza senza passare dall'LLM."""
    try:
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
        
        if not session.current_draft:
            raise HTTPException(
                status_code=400,
                detail="Nessuna bozza esistente da modificare"
            )
        
        # Incrementa la versione
        new_version = session.current_version + 1
        
        # Usa il titolo fornito o mantieni quello esistente
        new_title = request.title if request.title else session.current_title
        
        # Salva direttamente senza passare dall'LLM
        await update_draft_async(
            session_store, 
            request.session_id, 
            request.draft_text, 
            new_version, 
            new_title
        )
        
        logger.info(
            "Bozza aggiornata manualmente",
            context={"session_id": request.session_id, "version": new_version},
        )
        
        return DraftResponse(
            success=True,
            session_id=request.session_id,
            draft_text=request.draft_text,
            title=new_title,
            version=new_version,
            message="Bozza aggiornata manualmente con successo",
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Errore nel salvataggio manuale della bozza: {str(e)}"
        )


@router.post("/validate", response_model=DraftValidationResponse)
async def validate_draft_endpoint(
    request: DraftValidationRequest,
    current_user = Depends(get_current_user_optional)
):
    """Valida la bozza finale."""
    try:
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
        
        if not session.current_draft:
            raise HTTPException(
                status_code=400,
                detail="Nessuna bozza da validare"
            )
        
        if request.validated:
            await validate_session_async(session_store, request.session_id)
            logger.info(
                "Bozza validata",
                context={
                    "session_id": request.session_id,
                    "has_draft": bool(session.current_draft),
                    "title": session.current_title or "",
                },
            )
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


@router.get("/{session_id}", response_model=DraftResponse)
async def get_draft_endpoint(
    session_id: str,
    current_user = Depends(get_current_user_optional)
):
    """Recupera la bozza corrente di una sessione."""
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


@router.get("/progress/{session_id}", response_model=ProcessProgress)
async def get_draft_progress_endpoint(session_id: str):
    """Restituisce lo stato di avanzamento della generazione bozza."""
    try:
        session_store = get_session_store()
        session = await get_session_async(session_store, session_id)
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Sessione {session_id} non trovata"
            )
        
        progress = session.draft_progress
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
        logger.exception("Errore nel recupero progresso bozza", context={"session_id": session_id})
        raise HTTPException(
            status_code=500,
            detail=f"Errore nel recupero del progresso: {str(e)}"
        )

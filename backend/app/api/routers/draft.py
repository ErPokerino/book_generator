"""Router per gli endpoint delle bozze."""
import os
from fastapi import APIRouter, HTTPException, Depends
from app.models import (
    DraftGenerationRequest,
    DraftResponse,
    DraftModificationRequest,
    DraftValidationRequest,
    DraftValidationResponse,
    ProcessProgress,
)
from app.agent.draft_generator import generate_draft
from app.agent.session_store import get_session_store
from app.agent.session_store_helpers import (
    get_session_async,
    create_session_async,
    update_draft_async,
    validate_session_async,
)
from app.middleware.auth import get_current_user_optional

router = APIRouter(prefix="/api/draft", tags=["draft"])


@router.post("/generate", response_model=DraftResponse)
async def generate_draft_endpoint(
    request: DraftGenerationRequest,
    current_user = Depends(get_current_user_optional)
):
    """Genera una bozza estesa della trama."""
    print(f"[DEBUG] Generazione bozza per sessione {request.session_id}")
    try:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            print("[DEBUG] GOOGLE_API_KEY mancante!")
            raise HTTPException(
                status_code=500,
                detail="GOOGLE_API_KEY non configurata. Verifica il file .env nella root del progetto."
            )
        
        session_store = get_session_store()
        user_id = current_user.id if current_user else None
        session = await get_session_async(session_store, request.session_id, user_id=user_id)
        
        if not session:
            print(f"[DEBUG] Sessione {request.session_id} non trovata, creazione nuova...")
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
        
        print("[DEBUG] Chiamata a generate_draft...")
        draft_text, title, version = await generate_draft(
            form_data=request.form_data,
            question_answers=request.question_answers,
            session_id=request.session_id,
            api_key=api_key,
        )
        
        print(f"[DEBUG] Bozza generata: {title}, v{version}")
        await update_draft_async(session_store, request.session_id, draft_text, version, title)
        
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
        
        draft_text, title, version = await generate_draft(
            form_data=session.form_data,
            question_answers=session.question_answers,
            session_id=request.session_id,
            api_key=api_key,
            previous_draft=session.current_draft,
            user_feedback=request.user_feedback,
        )
        
        await update_draft_async(session_store, request.session_id, draft_text, version, title)
        
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
        print(f"[ERROR] Errore nel recupero progresso bozza: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Errore nel recupero del progresso: {str(e)}"
        )

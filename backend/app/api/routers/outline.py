"""Router per gli endpoint degli outline."""
import os
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from app.models import OutlineGenerateRequest, OutlineResponse, OutlineUpdateRequest, ProcessStartResponse
from app.agent.outline_generator import generate_outline
from app.agent.writer_generator import regenerate_outline_markdown
from app.agent.session_store import get_session_store
from app.agent.session_store_helpers import (
    get_session_async,
    update_outline_async,
    update_outline_progress_async,
    update_token_usage_async,
)
from app.middleware.auth import get_current_user_optional
from app.services.generation_service import background_generate_outline

router = APIRouter(prefix="/api/outline", tags=["outline"])


@router.post("/generate", response_model=OutlineResponse)
async def generate_outline_endpoint(
    request: OutlineGenerateRequest,
    current_user = Depends(get_current_user_optional)
):
    """Genera la struttura/indice del libro basandosi sulla bozza validata."""
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
                detail="Nessuna bozza validata disponibile. Valida prima la bozza estesa."
            )
        
        if not session.validated:
            raise HTTPException(
                status_code=400,
                detail="La bozza deve essere validata prima di generare la struttura."
            )
        
        print(f"[DEBUG OUTLINE] Inizio generazione outline per sessione {request.session_id}")
        print(f"[DEBUG OUTLINE] Draft length: {len(session.current_draft) if session.current_draft else 0}")
        print(f"[DEBUG OUTLINE] Titolo: {session.current_title}")
        
        outline_text, token_usage = await generate_outline(
            form_data=session.form_data,
            question_answers=session.question_answers,
            validated_draft=session.current_draft,
            session_id=request.session_id,
            draft_title=session.current_title,
            api_key=api_key,
        )
        
        print(f"[DEBUG OUTLINE] Outline generato, length: {len(outline_text) if outline_text else 0}")
        print(f"[DEBUG OUTLINE] Preview: {outline_text[:200] if outline_text else 'None'}...")
        
        await update_outline_async(session_store, request.session_id, outline_text)
        
        # Salva token usage per la fase outline
        await update_token_usage_async(
            session_store=session_store,
            session_id=request.session_id,
            phase="outline",
            input_tokens=token_usage.get("input_tokens", 0),
            output_tokens=token_usage.get("output_tokens", 0),
            model=token_usage.get("model", "gemini-3-pro-preview"),
        )
        
        session = await get_session_async(session_store, request.session_id)  # Re-fetch per versione aggiornata
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


@router.get("/{session_id}", response_model=OutlineResponse)
async def get_outline_endpoint(
    session_id: str,
    current_user = Depends(get_current_user_optional)
):
    """Recupera la struttura corrente di una sessione."""
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


@router.post("/update", response_model=OutlineResponse)
async def update_outline_endpoint(
    request: OutlineUpdateRequest,
    current_user = Depends(get_current_user_optional)
):
    """Aggiorna l'outline con sezioni modificate dall'utente."""
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
            await update_outline_async(session_store, request.session_id, updated_outline_text, allow_if_writing=False)
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


@router.post("/generate/start", response_model=ProcessStartResponse)
async def start_outline_generation_endpoint(
    request: OutlineGenerateRequest,
    background_tasks: BackgroundTasks,
):
    """Avvia la generazione dell'outline in background."""
    try:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="GOOGLE_API_KEY non configurata."
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
        
        # Inizializza progresso: pending
        await update_outline_progress_async(
            session_store,
            request.session_id,
            {
                "status": "pending",
                "current_step": 0,
                "total_steps": 1,
                "progress_percentage": 0.0,
            }
        )
        
        # Avvia il task in background
        background_tasks.add_task(
            background_generate_outline,
            session_id=request.session_id,
            api_key=api_key,
        )
        
        print(f"[OUTLINE GENERATION] Task di generazione outline avviato per sessione {request.session_id}")
        
        return ProcessStartResponse(
            success=True,
            session_id=request.session_id,
            message="Generazione della struttura avviata. Usa /api/outline/progress/{session_id} per monitorare lo stato.",
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Errore nell'avvio generazione outline: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nell'avvio della generazione della struttura: {str(e)}"
        )

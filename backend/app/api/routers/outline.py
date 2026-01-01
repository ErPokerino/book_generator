"""Router per gli endpoint degli outline."""
import os
from fastapi import APIRouter, HTTPException
from app.models import OutlineGenerateRequest, OutlineResponse, OutlineUpdateRequest
from app.agent.outline_generator import generate_outline
from app.agent.writer_generator import regenerate_outline_markdown
from app.agent.session_store import get_session_store

router = APIRouter(prefix="/api/outline", tags=["outline"])


@router.post("/generate", response_model=OutlineResponse)
async def generate_outline_endpoint(request: OutlineGenerateRequest):
    """Genera la struttura/indice del libro basandosi sulla bozza validata."""
    try:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="GOOGLE_API_KEY non configurata. Verifica il file .env nella root del progetto."
            )
        
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


@router.get("/{session_id}", response_model=OutlineResponse)
async def get_outline_endpoint(session_id: str):
    """Recupera la struttura corrente di una sessione."""
    try:
        session_store = get_session_store()
        session = session_store.get_session(session_id)
        
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


@router.post("/update", response_model=OutlineResponse)
async def update_outline_endpoint(request: OutlineUpdateRequest):
    """Aggiorna l'outline con sezioni modificate dall'utente."""
    try:
        session_store = get_session_store()
        session = session_store.get_session(request.session_id)
        
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
        session = session_store.get_session(request.session_id)
        
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

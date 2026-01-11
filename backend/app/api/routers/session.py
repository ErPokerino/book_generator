"""Router per gli endpoint delle sessioni."""
import math
from typing import Literal
from fastapi import APIRouter, HTTPException, Depends

from app.models import SessionRestoreResponse, DraftResponse, BookProgress, Chapter, Question, LiteraryCritique
from app.agent.session_store import get_session_store
from app.agent.session_store_helpers import get_session_async
from app.middleware.auth import get_current_user_optional
from app.services.stats_service import (
    calculate_page_count,
    calculate_generation_cost,
)
from app.core.config import get_app_config

router = APIRouter(prefix="/api/session", tags=["session"])


@router.get("/{session_id}/restore", response_model=SessionRestoreResponse)
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
        
        if session.writing_progress:
            current_step = "writing"
        elif session.current_outline:
            current_step = "summary"
        elif session.current_draft or (session.question_answers and len(session.question_answers) > 0):
            current_step = "draft"
        else:
            current_step = "questions"
        
        # Prepara le questions (se disponibili)
        questions = None
        if session.generated_questions:
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
            progress = session.writing_progress
            chapters = session.book_chapters or []
            
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
            
            total_pages = None
            is_complete = progress.get('is_complete', False)
            if is_complete and len(completed_chapters) > 0:
                chapters_pages = sum(ch.page_count for ch in completed_chapters)
                cover_pages = 1
                app_config = get_app_config()
                toc_chapters_per_page = app_config.get("validation", {}).get("toc_chapters_per_page", 30)
                toc_pages = math.ceil(len(completed_chapters) / toc_chapters_per_page)
                total_pages = chapters_pages + cover_pages + toc_pages
            
            writing_time_minutes = progress.get('writing_time_minutes')
            if writing_time_minutes is None and is_complete:
                if session.writing_start_time and session.writing_end_time:
                    delta = session.writing_end_time - session.writing_start_time
                    writing_time_minutes = delta.total_seconds() / 60.0
            
            estimated_cost = calculate_generation_cost(session, total_pages)
            
            critique = None
            critique_status = session.critique_status
            critique_error = session.critique_error
            if session.literary_critique:
                if isinstance(session.literary_critique, dict):
                    critique = LiteraryCritique(**session.literary_critique)
                else:
                    critique = session.literary_critique
            
            estimated_time_minutes = None
            estimated_time_confidence = None
            if not is_complete:
                current_step_idx = progress.get('current_step', 0)
                total_steps = progress.get('total_steps', 0)
                
                if total_steps > 0 and current_step_idx < total_steps:
                    try:
                        from app.main import calculate_estimated_time
                        estimated_time_minutes, estimated_time_confidence = await calculate_estimated_time(
                            session_id, current_step_idx, total_steps
                        )
                    except Exception as e:
                        print(f"[RESTORE_SESSION] Errore nel calcolo stima tempo: {e}")
                        remaining = total_steps - current_step_idx
                        app_config = get_app_config()
                        current_model = session.form_data.llm_model if session.form_data else None
                        from app.analytics.estimate_linear_params import get_generation_method, get_linear_params_for_method, calculate_residual_time_linear
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

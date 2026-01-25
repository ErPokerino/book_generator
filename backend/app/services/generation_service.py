"""Service per la generazione asincrona di domande, bozze e outline."""
import sys
import asyncio
from typing import Optional

from app.models import SubmissionRequest, QuestionAnswer
from app.agent.question_generator import generate_questions
from app.agent.draft_generator import generate_draft
from app.agent.outline_generator import generate_outline
from app.agent.session_store import get_session_store
from app.agent.session_store_helpers import (
    update_questions_progress_async,
    update_draft_progress_async,
    update_outline_progress_async,
    save_generated_questions_async,
    update_draft_async,
    update_outline_async,
    get_session_async,
    update_token_usage_async,
)
from app.core.config import get_app_config


async def background_generate_questions(
    session_id: str,
    form_data: SubmissionRequest,
    api_key: str,
):
    """Funzione eseguita in background per generare le domande."""
    session_store = get_session_store()
    app_config = get_app_config()
    retry_config = app_config.get("retry", {}).get("questions_generation", {})
    max_retries = retry_config.get("max_retries", 2)
    
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                print(f"[QUESTIONS GENERATION] Retry {attempt}/{max_retries - 1} per sessione {session_id}", file=sys.stderr)
            
            print(f"[QUESTIONS GENERATION] Avvio generazione domande per sessione {session_id} (tentativo {attempt + 1}/{max_retries})", file=sys.stderr)
            
            # Aggiorna progresso: running
            await update_questions_progress_async(
                session_store,
                session_id,
                {
                    "status": "running",
                    "current_step": 0,
                    "total_steps": 1,
                    "progress_percentage": 0.0,
                }
            )
            
            # Genera le domande
            response, token_usage = await generate_questions(form_data, api_key=api_key, session_id=session_id)
            
            # Salva le domande nella sessione
            questions_dict = [q.model_dump() for q in response.questions]
            await save_generated_questions_async(session_store, session_id, questions_dict)
            
            # Salva token usage per la fase questions
            await update_token_usage_async(
                session_store,
                session_id,
                phase="questions",
                input_tokens=token_usage.get("input_tokens", 0),
                output_tokens=token_usage.get("output_tokens", 0),
                model=token_usage.get("model", "gemini-3-pro-preview"),
            )
            
            # Aggiorna progresso: completed
            await update_questions_progress_async(
                session_store,
                session_id,
                {
                    "status": "completed",
                    "current_step": 1,
                    "total_steps": 1,
                    "progress_percentage": 100.0,
                    "result": {
                        "success": response.success,
                        "session_id": response.session_id,
                        "questions": questions_dict,
                        "message": response.message,
                    }
                }
            )
            
            print(f"[QUESTIONS GENERATION] Generazione domande completata per sessione {session_id}", file=sys.stderr)
            return  # Successo, esci dal loop
            
        except Exception as e:
            error_msg = f"Errore nella generazione delle domande: {str(e)}"
            print(f"[QUESTIONS GENERATION] ERRORE (tentativo {attempt + 1}/{max_retries}): {error_msg}", file=sys.stderr)
            
            if attempt < max_retries - 1:
                print(f"[QUESTIONS GENERATION] Retry tra 2 secondi...", file=sys.stderr)
                await asyncio.sleep(2)
                continue
            else:
                # Ultimo tentativo fallito
                import traceback
                traceback.print_exc()
                
                # Aggiorna progresso: failed
                await update_questions_progress_async(
                    session_store,
                    session_id,
                    {
                        "status": "failed",
                        "error": error_msg,
                    }
                )


async def background_generate_draft(
    session_id: str,
    form_data: SubmissionRequest,
    question_answers: list[QuestionAnswer],
    api_key: str,
):
    """Funzione eseguita in background per generare la bozza."""
    session_store = get_session_store()
    try:
        print(f"[DRAFT GENERATION] Avvio generazione bozza per sessione {session_id}", file=sys.stderr)
        
        # Aggiorna progresso: running
        await update_draft_progress_async(
            session_store,
            session_id,
            {
                "status": "running",
                "current_step": 0,
                "total_steps": 1,
                "progress_percentage": 0.0,
            }
        )
        
        # Genera la bozza
        draft_text, title, version, token_usage = await generate_draft(
            form_data=form_data,
            question_answers=question_answers,
            session_id=session_id,
            api_key=api_key,
        )
        
        # Salva la bozza nella sessione
        await update_draft_async(session_store, session_id, draft_text, version, title=title)
        
        # Salva token usage per la fase draft
        await update_token_usage_async(
            session_store,
            session_id,
            phase="draft",
            input_tokens=token_usage.get("input_tokens", 0),
            output_tokens=token_usage.get("output_tokens", 0),
            model=token_usage.get("model", "gemini-3-pro-preview"),
        )
        
        # Aggiorna progresso: completed
        await update_draft_progress_async(
            session_store,
            session_id,
            {
                "status": "completed",
                "current_step": 1,
                "total_steps": 1,
                "progress_percentage": 100.0,
                "result": {
                    "success": True,
                    "session_id": session_id,
                    "draft_text": draft_text,
                    "title": title,
                    "version": version,
                    "message": "Bozza generata con successo",
                }
            }
        )
        
        print(f"[DRAFT GENERATION] Generazione bozza completata per sessione {session_id}", file=sys.stderr)
        
    except Exception as e:
        error_msg = f"Errore nella generazione della bozza: {str(e)}"
        print(f"[DRAFT GENERATION] ERRORE: {error_msg}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        
        # Aggiorna progresso: failed
        await update_draft_progress_async(
            session_store,
            session_id,
            {
                "status": "failed",
                "error": error_msg,
            }
        )


async def background_generate_outline(
    session_id: str,
    api_key: str,
):
    """Funzione eseguita in background per generare l'outline."""
    session_store = get_session_store()
    app_config = get_app_config()
    retry_config = app_config.get("retry", {}).get("outline_generation", {})
    max_retries = retry_config.get("max_retries", 2)
    
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                print(f"[OUTLINE GENERATION] Retry {attempt}/{max_retries - 1} per sessione {session_id}", file=sys.stderr)
            
            print(f"[OUTLINE GENERATION] Avvio generazione outline per sessione {session_id} (tentativo {attempt + 1}/{max_retries})", file=sys.stderr)
            
            # Recupera la sessione
            session = await get_session_async(session_store, session_id)
            if not session:
                raise ValueError(f"Sessione {session_id} non trovata")
            
            if not session.current_draft:
                raise ValueError("Nessuna bozza validata disponibile")
            
            if not session.validated:
                raise ValueError("La bozza deve essere validata prima di generare la struttura")
            
            # Aggiorna progresso: running
            await update_outline_progress_async(
                session_store,
                session_id,
                {
                    "status": "running",
                    "current_step": 0,
                    "total_steps": 1,
                    "progress_percentage": 0.0,
                }
            )
            
            # Genera l'outline
            outline_text, token_usage = await generate_outline(
                form_data=session.form_data,
                question_answers=session.question_answers,
                validated_draft=session.current_draft,
                session_id=session_id,
                draft_title=session.current_title,
                api_key=api_key,
            )
            
            # Salva l'outline nella sessione
            await update_outline_async(session_store, session_id, outline_text)
            
            # Salva token usage per la fase outline
            await update_token_usage_async(
                session_store,
                session_id,
                phase="outline",
                input_tokens=token_usage.get("input_tokens", 0),
                output_tokens=token_usage.get("output_tokens", 0),
                model=token_usage.get("model", "gemini-3-pro-preview"),
            )
            
            # Recupera la sessione aggiornata per avere la versione corretta
            session = await get_session_async(session_store, session_id)
            
            # Aggiorna progresso: completed
            await update_outline_progress_async(
                session_store,
                session_id,
                {
                    "status": "completed",
                    "current_step": 1,
                    "total_steps": 1,
                    "progress_percentage": 100.0,
                    "result": {
                        "success": True,
                        "session_id": session_id,
                        "outline_text": outline_text,
                        "version": session.outline_version,
                        "message": "Struttura generata con successo",
                    }
                }
            )
            
            print(f"[OUTLINE GENERATION] Generazione outline completata per sessione {session_id}", file=sys.stderr)
            return  # Successo, esci dal loop
            
        except Exception as e:
            error_msg = f"Errore nella generazione dell'outline: {str(e)}"
            print(f"[OUTLINE GENERATION] ERRORE (tentativo {attempt + 1}/{max_retries}): {error_msg}", file=sys.stderr)
            
            if attempt < max_retries - 1:
                print(f"[OUTLINE GENERATION] Retry tra 3 secondi...", file=sys.stderr)
                await asyncio.sleep(3)
                continue
            else:
                # Ultimo tentativo fallito
                import traceback
                traceback.print_exc()
                
                # Aggiorna progresso: failed
                await update_outline_progress_async(
                    session_store,
                    session_id,
                    {
                        "status": "failed",
                        "error": error_msg,
                    }
                )

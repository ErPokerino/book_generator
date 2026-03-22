"""Service per la generazione asincrona di domande, bozze e outline."""
import asyncio

from app.models import SubmissionRequest, QuestionAnswer
from app.agent.question_generator import generate_questions
from app.agent.draft_generator import generate_draft
from app.agent.outline_generator import generate_outline
from app.agent.session_store import get_session_store
from app.agent.session_store_helpers import (
    save_generated_questions_async,
    update_draft_async,
    update_outline_async,
    get_session_async,
    update_token_usage_async,
)
from app.core.config import get_app_config
from app.core.logging import get_logger
from app.services.process_job_service import (
    mark_process_completed_async,
    mark_process_failed_async,
    mark_process_running_async,
)


logger = get_logger("generation-service")


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
                logger.warning(
                    "Retry generazione domande",
                    context={"session_id": session_id, "attempt": attempt + 1, "max_retries": max_retries},
                )

            logger.info(
                "Avvio generazione domande",
                context={"session_id": session_id, "attempt": attempt + 1, "max_retries": max_retries},
            )
            await mark_process_running_async(
                session_store,
                session_id,
                "questions",
                current_step=0,
                total_steps=1,
                progress_percentage=0.0,
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
                model=token_usage.get("model", "gemini-3.1-pro-preview"),
            )
            
            await mark_process_completed_async(
                session_store,
                session_id,
                "questions",
                current_step=1,
                total_steps=1,
                progress_percentage=100.0,
                result={
                    "success": response.success,
                    "session_id": response.session_id,
                    "questions": questions_dict,
                    "message": response.message,
                },
            )
            
            logger.info("Generazione domande completata", context={"session_id": session_id})
            return  # Successo, esci dal loop
            
        except Exception as e:
            error_msg = f"Errore nella generazione delle domande: {str(e)}"
            logger.exception(
                "Errore nella generazione delle domande",
                context={"session_id": session_id, "attempt": attempt + 1, "max_retries": max_retries},
            )
            
            if attempt < max_retries - 1:
                await asyncio.sleep(2)
                continue

            await mark_process_failed_async(
                session_store,
                session_id,
                "questions",
                error_msg,
                recoverable=True,
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
        logger.info("Avvio generazione bozza", context={"session_id": session_id})

        await mark_process_running_async(
            session_store,
            session_id,
            "draft",
            current_step=0,
            total_steps=1,
            progress_percentage=0.0,
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
            model=token_usage.get("model", "gemini-3.1-pro-preview"),
        )
        
        await mark_process_completed_async(
            session_store,
            session_id,
            "draft",
            current_step=1,
            total_steps=1,
            progress_percentage=100.0,
            result={
                "success": True,
                "session_id": session_id,
                "draft_text": draft_text,
                "title": title,
                "version": version,
                "message": "Bozza generata con successo",
            },
        )
        
        logger.info("Generazione bozza completata", context={"session_id": session_id})
        
    except Exception as e:
        error_msg = f"Errore nella generazione della bozza: {str(e)}"
        logger.exception("Errore nella generazione della bozza", context={"session_id": session_id})
        await mark_process_failed_async(
            session_store,
            session_id,
            "draft",
            error_msg,
            recoverable=True,
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
                logger.warning(
                    "Retry generazione outline",
                    context={"session_id": session_id, "attempt": attempt + 1, "max_retries": max_retries},
                )

            logger.info(
                "Avvio generazione outline",
                context={"session_id": session_id, "attempt": attempt + 1, "max_retries": max_retries},
            )
            
            # Recupera la sessione
            session = await get_session_async(session_store, session_id)
            if not session:
                raise ValueError(f"Sessione {session_id} non trovata")
            
            if not session.current_draft:
                raise ValueError("Nessuna bozza validata disponibile")
            
            if not session.validated:
                raise ValueError("La bozza deve essere validata prima di generare la struttura")
            
            await mark_process_running_async(
                session_store,
                session_id,
                "outline",
                current_step=0,
                total_steps=1,
                progress_percentage=0.0,
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
                model=token_usage.get("model", "gemini-3.1-pro-preview"),
            )
            
            # Recupera la sessione aggiornata per avere la versione corretta
            session = await get_session_async(session_store, session_id)
            
            await mark_process_completed_async(
                session_store,
                session_id,
                "outline",
                current_step=1,
                total_steps=1,
                progress_percentage=100.0,
                result={
                    "success": True,
                    "session_id": session_id,
                    "outline_text": outline_text,
                    "version": session.outline_version,
                    "message": "Struttura generata con successo",
                },
            )
            
            logger.info("Generazione outline completata", context={"session_id": session_id})
            return  # Successo, esci dal loop
            
        except Exception as e:
            error_msg = f"Errore nella generazione dell'outline: {str(e)}"
            logger.exception(
                "Errore nella generazione outline",
                context={"session_id": session_id, "attempt": attempt + 1, "max_retries": max_retries},
            )
            
            if attempt < max_retries - 1:
                await asyncio.sleep(3)
                continue

            await mark_process_failed_async(
                session_store,
                session_id,
                "outline",
                error_msg,
                recoverable=True,
            )

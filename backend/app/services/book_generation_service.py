"""Service per la generazione di libri in background."""
import os
from datetime import datetime
from pathlib import Path
from typing import Optional
from app.models import SubmissionRequest, QuestionAnswer
from app.agent.writer_generator import generate_full_book, parse_outline_sections, resume_book_generation
from app.agent.cover_generator import generate_book_cover
from app.agent.literary_critic import generate_literary_critique_from_pdf
from app.agent.session_store import get_session_store
from app.agent.session_store_helpers import (
    get_session_async,
    update_writing_progress_async,
    update_writing_times_async,
    update_cover_image_path_async,
    update_critique_async,
    update_critique_status_async,
    update_token_usage_async,
    set_real_cost_async,
)
from app.core.logging import get_logger
from app.services.storage_service import get_storage_service
from app.services.cost_service import calculate_real_generation_cost
from app.services.process_job_service import (
    mark_process_completed_async,
    mark_process_failed_async,
    mark_process_paused_async,
    mark_process_running_async,
    refresh_process_metrics_async,
)


logger = get_logger("book-generation-service")


def _resolve_book_artifact_context(
    session,
    *,
    title_fallback: Optional[str] = None,
    author_fallback: Optional[str] = None,
    plot_fallback: Optional[str] = None,
) -> tuple[str, str, str, Optional[str]]:
    """Ricava titolo/autore/trama/stile per post-processing usando la sessione come fonte primaria."""
    form_data = getattr(session, "form_data", None)
    title = getattr(session, "current_title", None) or title_fallback or "Romanzo"
    author = getattr(form_data, "user_name", None) or author_fallback or "Autore"
    plot = getattr(session, "current_draft", None) or plot_fallback or ""
    cover_style = getattr(form_data, "cover_style", None)
    return title, author, plot, cover_style


async def _send_book_completed_notification(
    session_store,
    session_id: str,
    *,
    title_fallback: Optional[str] = None,
) -> None:
    """Invia la notifica di completamento libro senza bloccare la pipeline principale."""
    try:
        session = await get_session_async(session_store, session_id)
        if session and session.user_id:
            from app.agent.notification_store import get_notification_store

            notification_store = get_notification_store()
            await notification_store.connect()
            book_title = getattr(session, "current_title", None) or title_fallback or "Il tuo libro"
            await notification_store.create_notification(
                user_id=session.user_id,
                type="book_completed",
                title="📚 Libro completato!",
                message=f'"{book_title}" è pronto per la lettura!',
                data={
                    "session_id": session_id,
                    "book_title": book_title,
                },
            )
            logger.info(
                "Notifica completamento inviata",
                context={"session_id": session_id, "user_id": session.user_id},
            )
    except Exception as notif_err:
        logger.warning(
            "Errore non bloccante nell'invio notifica completamento",
            context={"session_id": session_id, "error": str(notif_err)},
        )


async def _persist_writing_completion(
    session_store,
    session_id: str,
    *,
    writing_time_minutes: float,
) -> None:
    """Persistenza unificata del completamento scrittura senza mutation manuali sul dict."""
    session = await get_session_async(session_store, session_id)
    if not session or not session.writing_progress:
        return

    progress = session.writing_progress.copy()
    await update_writing_progress_async(
        session_store,
        session_id=session_id,
        current_step=progress.get("current_step", 0),
        total_steps=progress.get("total_steps", 0),
        current_section_name=progress.get("current_section_name"),
        is_complete=progress.get("is_complete", True),
        is_paused=False,
        error=None,
        total_pages=progress.get("total_pages"),
        completed_chapters_count=progress.get("completed_chapters_count"),
        writing_time_minutes=writing_time_minutes,
    )


async def _store_cover_path(
    session_store,
    session_id: str,
    *,
    cover_path: str,
    session,
) -> None:
    """Carica la copertina su storage e salva il path finale, con fallback locale."""
    try:
        storage_service = get_storage_service()
        user_id = session.user_id if hasattr(session, "user_id") else None
        cover_filename = f"{session_id}_cover.png"
        with open(cover_path, "rb") as handle:
            cover_data = handle.read()
        gcs_path = storage_service.upload_file(
            data=cover_data,
            destination_path=f"covers/{cover_filename}",
            content_type="image/png",
            user_id=user_id,
        )
        await update_cover_image_path_async(session_store, session_id, gcs_path)
        logger.info(
            "Copertina caricata su storage",
            context={"session_id": session_id, "cover_path": gcs_path},
        )
    except Exception as exc:
        logger.warning(
            "Caricamento copertina su storage fallito, uso file locale",
            context={"session_id": session_id, "error": str(exc)},
        )
        await update_cover_image_path_async(session_store, session_id, cover_path)
        logger.info(
            "Copertina salvata localmente",
            context={"session_id": session_id, "cover_path": cover_path},
        )


async def _generate_cover_artifact(
    session_store,
    session_id: str,
    *,
    api_key: str,
    title_fallback: Optional[str] = None,
    author_fallback: Optional[str] = None,
    plot_fallback: Optional[str] = None,
) -> None:
    """Genera e persiste la copertina del libro in modo uniforme per start/resume."""
    logger.info("Avvio generazione copertina", context={"session_id": session_id})
    session = await get_session_async(session_store, session_id)
    if not session:
        return

    title, author, plot, cover_style = _resolve_book_artifact_context(
        session,
        title_fallback=title_fallback,
        author_fallback=author_fallback,
        plot_fallback=plot_fallback,
    )
    cover_path = await generate_book_cover(
        session_id=session_id,
        title=title,
        author=author,
        plot=plot,
        api_key=api_key,
        cover_style=cover_style,
    )
    if cover_path:
        await _store_cover_path(
            session_store,
            session_id,
            cover_path=cover_path,
            session=session,
        )


async def _resolve_pdf_bytes(session_id: str, generate_pdf_callback=None) -> bytes:
    """Recupera il PDF finale del libro, usando callback o fallback router."""
    try:
        if generate_pdf_callback:
            pdf_response = await generate_pdf_callback(session_id)
        else:
            from app.api.routers.book import generate_book_pdf

            pdf_response = await generate_book_pdf(session_id, current_user=None)

        pdf_bytes = getattr(pdf_response, "body", None) or getattr(pdf_response, "content", None)
        if pdf_bytes is None:
            pdf_bytes = pdf_response.body
        if not isinstance(pdf_bytes, (bytes, bytearray)) or len(pdf_bytes) == 0:
            raise ValueError("PDF bytes non disponibili per la critica.")
        return bytes(pdf_bytes)
    except Exception as exc:
        raise RuntimeError(f"Impossibile generare/recuperare PDF per critica: {exc}") from exc


async def _generate_critique_artifact(
    session_store,
    session_id: str,
    *,
    api_key: Optional[str] = None,
    title_fallback: Optional[str] = None,
    author_fallback: Optional[str] = None,
    generate_pdf_callback=None,
) -> None:
    """Genera la critica finale con selezione provider/API key coerente tra start e resume."""
    logger.info("Avvio valutazione critica", context={"session_id": session_id})
    session = await get_session_async(session_store, session_id)
    if not session or not session.book_chapters:
        return

    await update_critique_status_async(session_store, session_id, "running", error=None)
    try:
        pdf_bytes = await _resolve_pdf_bytes(session_id, generate_pdf_callback=generate_pdf_callback)
        title, author, _plot, _cover_style = _resolve_book_artifact_context(
            session,
            title_fallback=title_fallback,
            author_fallback=author_fallback,
        )
        critique, token_usage = await generate_literary_critique_from_pdf(
            title=title,
            author=author,
            pdf_bytes=pdf_bytes,
            api_key=None,
            google_api_key=api_key,
        )

        await update_critique_async(session_store, session_id, critique)
        await update_critique_status_async(session_store, session_id, "completed", error=None)
        await update_token_usage_async(
            session_store,
            session_id,
            phase="critique",
            input_tokens=token_usage.get("input_tokens", 0),
            output_tokens=token_usage.get("output_tokens", 0),
            model=token_usage.get("model", "gemini-3.1-pro-preview"),
        )
        logger.info(
            "Valutazione critica completata",
            context={"session_id": session_id, "score": critique.get("score", 0)},
        )
    except Exception as exc:
        logger.exception("Errore non bloccante nella valutazione critica", context={"session_id": session_id})
        try:
            await update_critique_status_async(session_store, session_id, "failed", error=str(exc))
        except Exception as status_exc:
            logger.warning(
                "Impossibile salvare critique_status failed",
                context={"session_id": session_id, "error": str(status_exc)},
            )


async def _refresh_book_process_cost(session_store, session_id: str) -> None:
    """Ricalcola il costo reale complessivo e aggiorna le metriche del job."""
    try:
        session = await get_session_async(session_store, session_id)
        if session:
            real_cost = calculate_real_generation_cost(session)
            if real_cost is not None:
                await set_real_cost_async(session_store, session_id, real_cost)
                await refresh_process_metrics_async(session_store, session_id, "book")
                logger.info(
                    "Costo reale calcolato e metriche job aggiornate",
                    context={"session_id": session_id, "real_cost_eur": round(real_cost, 6)},
                )
    except Exception as cost_err:
        logger.warning(
            "Errore non bloccante nel calcolo costo reale",
            context={"session_id": session_id, "error": str(cost_err)},
        )


async def _run_post_book_completion_pipeline(
    session_store,
    session_id: str,
    *,
    writing_time_minutes: float,
    api_key: str,
    title_fallback: Optional[str] = None,
    author_fallback: Optional[str] = None,
    plot_fallback: Optional[str] = None,
    generate_pdf_callback=None,
) -> None:
    """Pipeline condivisa eseguita una sola volta quando i capitoli sono completi."""
    await _send_book_completed_notification(
        session_store,
        session_id,
        title_fallback=title_fallback,
    )
    await _persist_writing_completion(
        session_store,
        session_id,
        writing_time_minutes=writing_time_minutes,
    )
    await mark_process_completed_async(
        session_store,
        session_id,
        "book",
        recoverable=False,
    )

    try:
        await _generate_cover_artifact(
            session_store,
            session_id,
            api_key=api_key,
            title_fallback=title_fallback,
            author_fallback=author_fallback,
            plot_fallback=plot_fallback,
        )
    except Exception:
        logger.exception("Errore non bloccante nella generazione copertina", context={"session_id": session_id})

    await _generate_critique_artifact(
        session_store,
        session_id,
        api_key=api_key,
        title_fallback=title_fallback,
        author_fallback=author_fallback,
        generate_pdf_callback=generate_pdf_callback,
    )
    await _refresh_book_process_cost(session_store, session_id)


async def background_book_generation(
    session_id: str,
    form_data: SubmissionRequest,
    question_answers: list[QuestionAnswer],
    validated_draft: str,
    draft_title: Optional[str],
    outline_text: str,
    api_key: str,
    generate_pdf_callback=None,  # Callback per generare PDF (per evitare dipendenza circolare)
):
    """
    Funzione eseguita in background per generare il libro completo.
    
    Args:
        session_id: ID della sessione
        form_data: Dati del form di submission
        question_answers: Risposte alle domande
        validated_draft: Bozza validata
        draft_title: Titolo del libro
        outline_text: Testo dell'outline
        api_key: API key per Gemini
        generate_pdf_callback: Funzione opzionale per generare PDF (evita dipendenza circolare)
    """
    session_store = get_session_store()
    try:
        logger.info("Avvio generazione libro", context={"session_id": session_id})
        
        # Verifica che il progresso sia stato inizializzato
        session = await get_session_async(session_store, session_id)
        if not session or not session.writing_progress:
            logger.warning("Progresso scrittura non inizializzato, applico fallback", context={"session_id": session_id})
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

        await mark_process_running_async(
            session_store,
            session_id,
            "book",
            recoverable=False,
            error=None,
        )
        
        # Registra timestamp inizio scrittura capitoli
        start_time = datetime.now()
        await update_writing_times_async(session_store, session_id, start_time=start_time)
        logger.info("Timestamp inizio scrittura registrato", context={"session_id": session_id, "started_at": start_time.isoformat()})
        
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
            logger.warning("Generazione libro messa in pausa", context={"session_id": session_id})
            await mark_process_paused_async(
                session_store,
                session_id,
                "book",
                session.writing_progress.get("error") or "Generazione temporaneamente in pausa.",
            )
            # Non continuare con copertina e critica se è in pausa
            return
        
        logger.info("Generazione capitoli completata", context={"session_id": session_id})
        
        # Registra timestamp fine scrittura capitoli e calcola tempo
        end_time = datetime.now()
        await update_writing_times_async(session_store, session_id, end_time=end_time)
        writing_time_minutes = (end_time - start_time).total_seconds() / 60
        logger.info(
            "Timestamp fine scrittura registrato",
            context={
                "session_id": session_id,
                "completed_at": end_time.isoformat(),
                "writing_time_minutes": round(writing_time_minutes, 2),
            },
        )

        await _run_post_book_completion_pipeline(
            session_store,
            session_id,
            writing_time_minutes=writing_time_minutes,
            api_key=api_key,
            title_fallback=draft_title or "Romanzo",
            author_fallback=form_data.user_name or "Autore",
            plot_fallback=validated_draft,
            generate_pdf_callback=generate_pdf_callback,
        )
    except ValueError as e:
        # Errore di validazione (es. outline non valido)
        error_msg = f"Errore di validazione: {str(e)}"
        logger.exception("Errore di validazione nella generazione libro", context={"session_id": session_id})
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
        await mark_process_failed_async(session_store, session_id, "book", error_msg, recoverable=True)
    except Exception as e:
        error_msg = f"Errore nella generazione: {str(e)}"
        logger.exception("Errore inatteso nella generazione libro", context={"session_id": session_id})
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
        await mark_process_failed_async(session_store, session_id, "book", error_msg, recoverable=True)


async def background_resume_book_generation(
    session_id: str,
    api_key: str,
    generate_pdf_callback=None,  # Callback per generare PDF
):
    """
    Funzione eseguita in background per riprendere la generazione del libro.
    
    Args:
        session_id: ID della sessione
        api_key: API key per Gemini
        generate_pdf_callback: Funzione opzionale per generare PDF
    """
    session_store = get_session_store()
    try:
        logger.info("Avvio ripresa generazione libro", context={"session_id": session_id})
        
        # Recupera la sessione per verificare lo stato
        session = await get_session_async(session_store, session_id)
        if not session:
            raise ValueError(f"Sessione {session_id} non trovata")
        
        if not session.writing_progress:
            raise ValueError(f"Sessione {session_id} non ha uno stato di scrittura")
        
        progress = session.writing_progress
        if not progress.get("is_paused", False):
            raise ValueError(f"Sessione {session_id} non è in stato di pausa")

        await mark_process_running_async(
            session_store,
            session_id,
            "book",
            recoverable=False,
            error=None,
        )
        
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
            logger.warning("Generazione libro nuovamente in pausa", context={"session_id": session_id})
            await mark_process_paused_async(
                session_store,
                session_id,
                "book",
                session.writing_progress.get("error") or "Generazione nuovamente in pausa.",
            )
            return
        
        logger.info("Ripresa generazione capitoli completata", context={"session_id": session_id})
        
        # Registra timestamp fine scrittura capitoli e calcola tempo
        end_time = datetime.now()
        await update_writing_times_async(session_store, session_id, end_time=end_time)
        writing_time_minutes = (end_time - start_time).total_seconds() / 60
        logger.info(
            "Timestamp fine ripresa registrato",
            context={
                "session_id": session_id,
                "completed_at": end_time.isoformat(),
                "writing_time_minutes": round(writing_time_minutes, 2),
            },
        )

        await _run_post_book_completion_pipeline(
            session_store,
            session_id,
            writing_time_minutes=writing_time_minutes,
            api_key=api_key,
            title_fallback="Romanzo",
            author_fallback="Autore",
            plot_fallback="",
            generate_pdf_callback=generate_pdf_callback,
        )
    except ValueError as e:
        error_msg = f"Errore di validazione: {str(e)}"
        logger.exception("Errore di validazione nella ripresa generazione libro", context={"session_id": session_id})
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
        await mark_process_failed_async(session_store, session_id, "book", error_msg, recoverable=True)
    except Exception as e:
        error_msg = f"Errore nella ripresa generazione: {str(e)}"
        logger.exception("Errore inatteso nella ripresa generazione libro", context={"session_id": session_id})
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
        await mark_process_failed_async(session_store, session_id, "book", error_msg, recoverable=True)

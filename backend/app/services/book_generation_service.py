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
)
from app.services.storage_service import get_storage_service


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
        print(f"[BOOK GENERATION] Avvio generazione libro per sessione {session_id}")
        
        # Verifica che il progresso sia stato inizializzato
        session = await get_session_async(session_store, session_id)
        if not session or not session.writing_progress:
            print(f"[BOOK GENERATION] WARNING: Progresso non inizializzato per sessione {session_id}, inizializzo ora...")
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
        
        # Registra timestamp inizio scrittura capitoli
        start_time = datetime.now()
        await update_writing_times_async(session_store, session_id, start_time=start_time)
        print(f"[BOOK GENERATION] Timestamp inizio scrittura: {start_time.isoformat()}")
        
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
            print(f"[BOOK GENERATION] Generazione messa in pausa per sessione {session_id}")
            # Non continuare con copertina e critica se è in pausa
            return
        
        print(f"[BOOK GENERATION] Generazione completata per sessione {session_id}")
        
        # Registra timestamp fine scrittura capitoli e calcola tempo
        end_time = datetime.now()
        await update_writing_times_async(session_store, session_id, end_time=end_time)
        writing_time_minutes = (end_time - start_time).total_seconds() / 60
        print(f"[BOOK GENERATION] Timestamp fine scrittura: {end_time.isoformat()}, tempo totale: {writing_time_minutes:.2f} minuti")
        
        # Invia notifica di completamento libro (subito dopo la scrittura)
        try:
            session = await get_session_async(session_store, session_id)
            if session and session.user_id:
                from app.agent.notification_store import get_notification_store
                notification_store = get_notification_store()
                await notification_store.connect()
                
                book_title = session.current_title or draft_title or "Il tuo libro"
                
                await notification_store.create_notification(
                    user_id=session.user_id,
                    type="book_completed",
                    title="📚 Libro completato!",
                    message=f'"{book_title}" è pronto per la lettura!',
                    data={
                        "session_id": session_id,
                        "book_title": book_title,
                    }
                )
                print(f"[BOOK GENERATION] Notifica di completamento inviata a utente {session.user_id}")
        except Exception as notif_err:
            print(f"[BOOK GENERATION] WARNING: Errore nell'invio notifica: {notif_err}")
        
        # Aggiorna writing_progress con il tempo calcolato
        session = await get_session_async(session_store, session_id)
        if session and session.writing_progress:
            # Mantieni tutti i valori esistenti e aggiungi writing_time_minutes
            existing_progress = session.writing_progress.copy()
            existing_progress['writing_time_minutes'] = writing_time_minutes
            await update_writing_progress_async(
                session_store,
                session_id=session_id,
                current_step=existing_progress.get('current_step', 0),
                total_steps=existing_progress.get('total_steps', 0),
                current_section_name=existing_progress.get('current_section_name'),
                is_complete=existing_progress.get('is_complete', True),
                is_paused=False,
                error=existing_progress.get('error'),
            )
            # Aggiorna manualmente writing_time_minutes nel dict (update_writing_progress non lo gestisce)
            session.writing_progress['writing_time_minutes'] = writing_time_minutes
            # FileSessionStore salverà automaticamente al prossimo update o possiamo forzare il salvataggio
            if hasattr(session_store, '_save_sessions'):
                session_store._save_sessions()
        
        # Genera la copertina dopo che il libro è stato completato
        try:
            print(f"[BOOK GENERATION] Avvio generazione copertina per sessione {session_id}")
            session = await get_session_async(session_store, session_id)
            if session:
                cover_path = await generate_book_cover(
                    session_id=session_id,
                    title=draft_title or "Romanzo",
                    author=form_data.user_name or "Autore",
                    plot=validated_draft,
                    api_key=api_key,
                    cover_style=form_data.cover_style,
                )
                # Carica copertina su GCS
                try:
                    storage_service = get_storage_service()
                    user_id = session.user_id if hasattr(session, 'user_id') else None
                    cover_filename = f"{session_id}_cover.png"
                    with open(cover_path, 'rb') as f:
                        cover_data = f.read()
                    gcs_path = storage_service.upload_file(
                        data=cover_data,
                        destination_path=f"covers/{cover_filename}",
                        content_type="image/png",
                        user_id=user_id,
                    )
                    await update_cover_image_path_async(session_store, session_id, gcs_path)
                    print(f"[BOOK GENERATION] Copertina generata e caricata su GCS: {gcs_path}")
                except Exception as e:
                    print(f"[BOOK GENERATION] ERRORE nel caricamento copertina su GCS: {e}, uso path locale")
                    await update_cover_image_path_async(session_store, session_id, cover_path)
                    print(f"[BOOK GENERATION] Copertina generata e salvata: {cover_path}")
        except Exception as e:
            print(f"[BOOK GENERATION] ERRORE nella generazione copertina: {e}")
            import traceback
            traceback.print_exc()
            # Non blocchiamo il processo se la copertina fallisce
        
        # Genera la valutazione critica dopo che il libro è stato completato
        try:
            print(f"[BOOK GENERATION] Avvio valutazione critica per sessione {session_id}")
            session = await get_session_async(session_store, session_id)
            if session and session.book_chapters and len(session.book_chapters) > 0:
                # Critica: genera prima il PDF finale (e lo salva su disco), poi passa il PDF al modello multimodale.
                await update_critique_status_async(session_store, session_id, "running", error=None)
                try:
                    # Usa il callback se fornito, altrimenti importa direttamente (per retrocompatibilità)
                    if generate_pdf_callback:
                        pdf_response = await generate_pdf_callback(session_id)
                    else:
                        # Fallback: importa direttamente (crea dipendenza circolare ma funziona)
                        from app.api.routers.book import generate_book_pdf
                        pdf_response = await generate_book_pdf(session_id, current_user=None)
                    
                    pdf_bytes = getattr(pdf_response, "body", None) or getattr(pdf_response, "content", None)
                    if pdf_bytes is None:
                        # Fallback: rigenera via endpoint e prendi il body
                        pdf_bytes = pdf_response.body
                    if not isinstance(pdf_bytes, (bytes, bytearray)) or len(pdf_bytes) == 0:
                        raise ValueError("PDF bytes non disponibili per la critica.")
                except Exception as e:
                    raise RuntimeError(f"Impossibile generare/recuperare PDF per critica: {e}")

                critique = await generate_literary_critique_from_pdf(
                    title=draft_title or "Romanzo",
                    author=form_data.user_name or "Autore",
                    pdf_bytes=bytes(pdf_bytes),
                    api_key=api_key,
                )

                await update_critique_async(session_store, session_id, critique)
                await update_critique_status_async(session_store, session_id, "completed", error=None)
                print(f"[BOOK GENERATION] Valutazione critica completata: score={critique.get('score', 0)}")
        except Exception as e:
            print(f"[BOOK GENERATION] ERRORE nella valutazione critica: {e}")
            import traceback
            traceback.print_exc()
            # Niente placeholder: settiamo status failed e salviamo errore per UI (stop polling + retry).
            try:
                await update_critique_status_async(session_store, session_id, "failed", error=str(e))
            except Exception as _e:
                print(f"[BOOK GENERATION] WARNING: impossibile salvare critique_status failed: {_e}")
    except ValueError as e:
        # Errore di validazione (es. outline non valido)
        error_msg = f"Errore di validazione: {str(e)}"
        print(f"[BOOK GENERATION] ERRORE (ValueError): {error_msg}")
        import traceback
        traceback.print_exc()
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
    except Exception as e:
        error_msg = f"Errore nella generazione: {str(e)}"
        print(f"[BOOK GENERATION] ERRORE (Exception): {error_msg}")
        import traceback
        traceback.print_exc()
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
        print(f"[BOOK GENERATION] Ripresa generazione libro per sessione {session_id}")
        
        # Recupera la sessione per verificare lo stato
        session = await get_session_async(session_store, session_id)
        if not session:
            raise ValueError(f"Sessione {session_id} non trovata")
        
        if not session.writing_progress:
            raise ValueError(f"Sessione {session_id} non ha uno stato di scrittura")
        
        progress = session.writing_progress
        if not progress.get("is_paused", False):
            raise ValueError(f"Sessione {session_id} non è in stato di pausa")
        
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
            print(f"[BOOK GENERATION] Generazione rimessa in pausa per sessione {session_id}")
            return
        
        print(f"[BOOK GENERATION] Ripresa generazione completata per sessione {session_id}")
        
        # Registra timestamp fine scrittura capitoli e calcola tempo
        end_time = datetime.now()
        await update_writing_times_async(session_store, session_id, end_time=end_time)
        writing_time_minutes = (end_time - start_time).total_seconds() / 60
        print(f"[BOOK GENERATION] Timestamp fine scrittura: {end_time.isoformat()}, tempo totale: {writing_time_minutes:.2f} minuti")
        
        # Invia notifica di completamento libro (subito dopo la scrittura)
        try:
            session = await get_session_async(session_store, session_id)
            if session and session.user_id:
                from app.agent.notification_store import get_notification_store
                notification_store = get_notification_store()
                await notification_store.connect()
                
                book_title = session.current_title or "Il tuo libro"
                
                await notification_store.create_notification(
                    user_id=session.user_id,
                    type="book_completed",
                    title="📚 Libro completato!",
                    message=f'"{book_title}" è pronto per la lettura!',
                    data={
                        "session_id": session_id,
                        "book_title": book_title,
                    }
                )
                print(f"[BOOK GENERATION] Notifica di completamento inviata a utente {session.user_id}")
        except Exception as notif_err:
            print(f"[BOOK GENERATION] WARNING: Errore nell'invio notifica: {notif_err}")
        
        # Aggiorna writing_progress con il tempo calcolato
        session = await get_session_async(session_store, session_id)
        if session and session.writing_progress:
            existing_progress = session.writing_progress.copy()
            existing_progress['writing_time_minutes'] = writing_time_minutes
            await update_writing_progress_async(
                session_store,
                session_id=session_id,
                current_step=existing_progress.get('current_step', 0),
                total_steps=existing_progress.get('total_steps', 0),
                current_section_name=existing_progress.get('current_section_name'),
                is_complete=existing_progress.get('is_complete', True),
                is_paused=False,
                error=None,
            )
            session.writing_progress['writing_time_minutes'] = writing_time_minutes
            if hasattr(session_store, '_save_sessions'):
                session_store._save_sessions()
        
        # Genera la copertina dopo che il libro è stato completato
        try:
            print(f"[BOOK GENERATION] Avvio generazione copertina per sessione {session_id}")
            session = await get_session_async(session_store, session_id)
            if session:
                cover_path = await generate_book_cover(
                    session_id=session_id,
                    title=session.current_title or "Romanzo",
                    author=session.form_data.user_name or "Autore",
                    plot=session.current_draft or "",
                    api_key=api_key,
                    cover_style=session.form_data.cover_style,
                )
                if cover_path:
                    # Carica copertina su GCS
                    try:
                        storage_service = get_storage_service()
                        user_id = session.user_id if hasattr(session, 'user_id') else None
                        cover_filename = f"{session_id}_cover.png"
                        with open(cover_path, 'rb') as f:
                            cover_data = f.read()
                        gcs_path = storage_service.upload_file(
                            data=cover_data,
                            destination_path=f"covers/{cover_filename}",
                            content_type="image/png",
                            user_id=user_id,
                        )
                        await update_cover_image_path_async(session_store, session_id, gcs_path)
                        print(f"[BOOK GENERATION] Copertina generata e caricata su GCS: {gcs_path}")
                    except Exception as e:
                        print(f"[BOOK GENERATION] ERRORE nel caricamento copertina su GCS: {e}, uso path locale")
                        await update_cover_image_path_async(session_store, session_id, cover_path)
                        print(f"[BOOK GENERATION] Copertina generata: {cover_path}")
        except Exception as e:
            print(f"[BOOK GENERATION] ERRORE nella generazione copertina: {e}")
            import traceback
            traceback.print_exc()
        
        # Genera la valutazione critica dopo che il libro è stato completato
        try:
            print(f"[BOOK GENERATION] Avvio valutazione critica per sessione {session_id}")
            session = await get_session_async(session_store, session_id)
            if session and session.book_chapters and len(session.book_chapters) > 0:
                # Critica: genera prima il PDF finale (e lo salva su disco), poi passa il PDF al modello multimodale.
                await update_critique_status_async(session_store, session_id, "running", error=None)
                try:
                    # Usa il callback se fornito
                    if generate_pdf_callback:
                        pdf_response = await generate_pdf_callback(session_id)
                    else:
                        # Fallback: importa direttamente dalla funzione helper
                        from app.api.routers.book import generate_book_pdf
                        pdf_response = await generate_book_pdf(session_id, current_user=None)
                    
                    pdf_bytes = getattr(pdf_response, "body", None) or getattr(pdf_response, "content", None)
                    if pdf_bytes is None:
                        pdf_bytes = pdf_response.body
                    if not isinstance(pdf_bytes, (bytes, bytearray)) or len(pdf_bytes) == 0:
                        raise ValueError("PDF bytes non disponibili per la critica.")
                except Exception as e:
                    raise RuntimeError(f"Impossibile generare/recuperare PDF per critica: {e}")

                # La funzione gestisce automaticamente quale API key usare (Gemini o OpenAI)
                critique = await generate_literary_critique_from_pdf(
                    title=session.current_title or "Romanzo",
                    author=session.form_data.user_name or "Autore",
                    pdf_bytes=bytes(pdf_bytes),
                    api_key=None,  # None = auto-detect da env in base al provider configurato
                )

                await update_critique_async(session_store, session_id, critique)
                await update_critique_status_async(session_store, session_id, "completed", error=None)
                print(f"[BOOK GENERATION] Valutazione critica completata: score={critique.get('score', 0)}")
        except Exception as e:
            print(f"[BOOK GENERATION] ERRORE nella valutazione critica: {e}")
            import traceback
            traceback.print_exc()
            # Niente placeholder: settiamo status failed e salviamo errore per UI (stop polling + retry).
            try:
                await update_critique_status_async(session_store, session_id, "failed", error=str(e))
            except Exception as _e:
                print(f"[BOOK GENERATION] WARNING: impossibile salvare critique_status failed: {_e}")
    except ValueError as e:
        error_msg = f"Errore di validazione: {str(e)}"
        print(f"[BOOK GENERATION] ERRORE (ValueError): {error_msg}")
        import traceback
        traceback.print_exc()
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
    except Exception as e:
        error_msg = f"Errore nella ripresa generazione: {str(e)}"
        print(f"[BOOK GENERATION] ERRORE (Exception): {error_msg}")
        import traceback
        traceback.print_exc()
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

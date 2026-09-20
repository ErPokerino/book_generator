"""Router per gli endpoint dei libri."""
from app.services.durable_worker import schedule_generation
import os
import asyncio
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import Response
import math

from app.models import (
    BookGenerationRequest,
    BookGenerationResponse,
    BookProgress,
    BookResponse,
    Chapter,
    LiteraryCritique,
)
from app.agent.writer_generator import parse_outline_sections
from app.agent.session_store import get_session_store
from app.agent.session_store_helpers import (
    get_session_async,
    save_session_async,
    update_writing_progress_async,
    update_critique_async,
    update_critique_status_async,
    update_token_usage_async,
)
from app.services.pdf_service import generate_complete_book_pdf, calculate_page_count
from app.services.export_service import generate_epub, generate_docx
from app.services.storage_service import get_storage_service
from app.services.book_generation_service import (
    background_book_generation,
    background_resume_book_generation,
)
from app.core.config import get_app_config
from app.services.process_job_service import begin_process_job_async
from app.services.cost_service import calculate_real_generation_cost
from app.services.stats_service import calculate_estimated_time
from app.utils.downloads import attachment_header

router = APIRouter(prefix="/api/book", tags=["book"])


async def generate_book_pdf(session_id: str) -> Response:
    """
    Helper function per generare PDF del libro.
    Può essere chiamata sia dall'endpoint che dal service.
    """
    session_store = get_session_store()
    session = await get_session_async(session_store, session_id)

    if not session:
        raise HTTPException(status_code=404, detail=f"Sessione {session_id} non trovata")

    if not session.writing_progress or not session.writing_progress.get('is_complete'):
        raise HTTPException(
            status_code=400,
            detail="Il libro non è ancora completo. Attendi il completamento della scrittura."
        )
    
    if not session.book_chapters or len(session.book_chapters) == 0:
        raise HTTPException(status_code=400, detail="Nessun capitolo trovato nel libro.")
    
    pdf_content, filename = await asyncio.to_thread(generate_complete_book_pdf, session)
    await save_session_async(session_store, session)
    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers={"Content-Disposition": attachment_header(filename)},
    )


@router.post("/generate", response_model=BookGenerationResponse)
async def generate_book_endpoint(
    request: BookGenerationRequest,
    background_tasks: BackgroundTasks,
):
    """Avvia la generazione del libro completo in background."""
    try:
        api_key = os.getenv("GOOGLE_API_KEY") or None

        # Recupera la sessione
        session_store = get_session_store()
        session = await get_session_async(session_store, request.session_id)

        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Sessione {request.session_id} non trovata"
            )

        if not session.current_draft or not session.validated:
            raise HTTPException(
                status_code=400,
                detail="La bozza deve essere validata prima di generare il libro."
            )
        
        if not session.current_outline:
            raise HTTPException(
                status_code=400,
                detail="La struttura del libro deve essere generata prima di iniziare la scrittura."
            )

        if session.book_chapters and (session.writing_progress or {}).get("status") not in {"pending", "running"}:
            raise HTTPException(status_code=409, detail="Il libro contiene già capitoli salvati. Usa la ripresa per continuare la scrittura.")
        
        # Parsa l'outline e inizializza il progresso IMMEDIATAMENTE
        try:
            print(f"[BOOK GENERATION] Parsing outline per sessione {request.session_id}...")
            sections = parse_outline_sections(session.current_outline)
            total_sections = len(sections)
            
            if total_sections == 0:
                raise HTTPException(
                    status_code=400,
                    detail="Nessuna sezione trovata nella struttura. Verifica che la struttura sia in formato Markdown corretto."
                )
            
            started, job = await begin_process_job_async(
                session_store,
                request.session_id,
                "book",
                total_steps=total_sections,
                current_section_name=sections[0]['title'] if sections else None,
            )
            if not started:
                return BookGenerationResponse(
                    success=True,
                    session_id=request.session_id,
                    message="Generazione del libro già in corso. Usa /api/book/progress per monitorare lo stato.",
                    job_id=job.get("job_id"),
                    job_type="book",
                    already_running=True,
                )

            # Inizializza il progresso PRIMA di avviare il task
            await update_writing_progress_async(
                session_store,
                session_id=request.session_id,
                current_step=0,
                total_steps=total_sections,
                current_section_name=sections[0]['title'] if sections else None,
                is_complete=False,
                is_paused=False,
            )
            print(f"[BOOK GENERATION] Progresso inizializzato: {total_sections} sezioni da scrivere")
            
        except HTTPException:
            raise
        except ValueError as e:
            print(f"[BOOK GENERATION] Errore nel parsing outline: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            print(f"[BOOK GENERATION] Errore imprevisto durante l'inizializzazione: {e}")
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=500,
                detail=f"Errore durante l'inizializzazione della scrittura: {str(e)}"
            )
        
        # Avvia la generazione in background con callback per PDF
        schedule_generation(
            background_tasks, session_store, background_book_generation,
            session_id=request.session_id,
            form_data=session.form_data,
            question_answers=session.question_answers,
            validated_draft=session.current_draft,
            draft_title=session.current_title,
            outline_text=session.current_outline,
            api_key=api_key,
            generate_pdf_callback=lambda sid: generate_book_pdf(sid),
        )
        
        print(f"[BOOK GENERATION] Task di generazione avviato per sessione {request.session_id}")
        
        return BookGenerationResponse(
            success=True,
            session_id=request.session_id,
            message="Generazione del libro avviata. Usa /api/book/progress per monitorare lo stato.",
            job_id=job.get("job_id"),
            job_type="book",
            already_running=False,
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Errore nell'avvio generazione libro: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nell'avvio della generazione del libro: {str(e)}"
        )


@router.post("/resume/{session_id}", response_model=BookGenerationResponse)
async def resume_book_generation_endpoint(
    session_id: str,
    background_tasks: BackgroundTasks,
):
    """Riprende la generazione del libro dal capitolo fallito."""
    try:
        api_key = os.getenv("GOOGLE_API_KEY") or None

        # Recupera la sessione
        session_store = get_session_store()
        session = await get_session_async(session_store, session_id)

        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Sessione {session_id} non trovata"
            )

        if not session.writing_progress:
            raise HTTPException(
                status_code=400,
                detail="La sessione non ha uno stato di scrittura. Avvia prima la generazione."
            )

        if not session.current_draft or not session.current_outline:
            raise HTTPException(status_code=400, detail="Bozza o struttura mancanti: impossibile riprendere la scrittura.")
        
        if not session.writing_progress.get('is_paused', False):
            current_status = session.writing_progress.get("status")
            if current_status in {"pending", "running"}:
                return BookGenerationResponse(
                    success=True,
                    session_id=session_id,
                    message="Ripresa già in corso. Usa /api/book/progress per monitorare lo stato.",
                    job_id=session.writing_progress.get("job_id"),
                    job_type="book",
                    already_running=True,
                )
            raise HTTPException(
                status_code=400,
                detail="La sessione non è in stato di pausa. Non è possibile riprendere."
            )

        started, job = await begin_process_job_async(
            session_store,
            session_id,
            "book",
            total_steps=session.writing_progress.get("total_steps", 1),
            current_step=session.writing_progress.get("current_step", 0),
            current_section_name=session.writing_progress.get("current_section_name"),
        )
        if not started:
            return BookGenerationResponse(
                success=True,
                session_id=session_id,
                message="Ripresa già in corso. Usa /api/book/progress per monitorare lo stato.",
                job_id=job.get("job_id"),
                job_type="book",
                already_running=True,
            )
        
        # Avvia la ripresa in background con callback per PDF
        schedule_generation(
            background_tasks, session_store, background_resume_book_generation,
            session_id=session_id,
            api_key=api_key,
            generate_pdf_callback=lambda sid: generate_book_pdf(sid),
        )
        
        print(f"[BOOK GENERATION] Task di ripresa generazione avviato per sessione {session_id}")
        
        return BookGenerationResponse(
            success=True,
            session_id=session_id,
            message="Ripresa della generazione avviata. Usa /api/book/progress per monitorare lo stato.",
            job_id=job.get("job_id"),
            job_type="book",
            already_running=False,
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Errore nell'avvio ripresa generazione libro: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nell'avvio della ripresa generazione: {str(e)}"
        )


@router.get("/progress/{session_id}", response_model=BookProgress)
async def get_book_progress_endpoint(
    session_id: str,
):
    """Recupera lo stato di avanzamento della scrittura del libro."""
    try:
        session_store = get_session_store()
        session = await get_session_async(session_store, session_id)
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Sessione {session_id} non trovata"
            )
        
        
        # Costruisci la risposta dal progresso salvato
        progress = session.writing_progress or {}
        chapters = session.book_chapters or []
        
        # Converti i capitoli in oggetti Chapter
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
        
        # Calcola total_pages se il libro è completato
        total_pages = None
        is_complete = progress.get('is_complete', False)
        if is_complete and len(completed_chapters) > 0:
            chapters_pages = sum(ch.page_count for ch in completed_chapters)
            cover_pages = 1
            app_config = get_app_config()
            toc_chapters_per_page = app_config.get("validation", {}).get("toc_chapters_per_page", 30)
            toc_pages = math.ceil(len(completed_chapters) / toc_chapters_per_page)
            total_pages = chapters_pages + cover_pages + toc_pages
        
        # Tempo trascorso dall'inizio della scrittura, anche mentre è in corso
        writing_time_minutes = progress.get('writing_time_minutes')
        start_time = session.writing_start_time
        end_time = session.writing_end_time
        if start_time:
            elapsed_end = end_time or datetime.now()
            writing_time_minutes = max(0.0, (elapsed_end - start_time).total_seconds() / 60)
        elif writing_time_minutes is None and is_complete:
            writing_time_minutes = None
        
        # Costo reale dai token già usati (anche a metà generazione)
        estimated_cost = calculate_real_generation_cost(session)
        
        # Recupera la valutazione critica se disponibile
        critique = None
        if session.literary_critique:
            try:
                critique = LiteraryCritique(**session.literary_critique)
            except Exception as e:
                print(f"[GET BOOK PROGRESS] Errore nel parsing critique: {e}")

        # Backward-compat: sessioni vecchie potrebbero avere critique senza critique_status
        critique_status = session.critique_status
        critique_error = session.critique_error
        if critique_status is None:
            if critique is not None:
                critique_status = "completed"
            elif is_complete:
                critique_status = "pending"
        
        # Calcola stima tempo se il libro non è completato
        estimated_time_minutes = None
        estimated_time_confidence = None
        calculated_total_steps = None
        if not is_complete:
            raw_current = progress.get('current_step', 0)
            raw_total = progress.get('total_steps', 0)
            
            try:
                current_step = int(raw_current)
            except (ValueError, TypeError):
                print(f"[GET BOOK PROGRESS] WARNING: current_step non è un numero valido ({raw_current}), uso 0")
                current_step = 0
            
            try:
                total_steps = int(raw_total)
            except (ValueError, TypeError):
                print(f"[GET BOOK PROGRESS] WARNING: total_steps non è un numero valido ({raw_total}), uso 0")
                total_steps = 0
            
            if current_step < 0:
                print(f"[GET BOOK PROGRESS] WARNING: current_step negativo ({current_step}), correggo a 0")
                current_step = 0
            
            # FALLBACK: Se total_steps è 0 ma is_complete è False, prova a calcolarlo dall'outline
            if total_steps == 0:
                print(f"[GET BOOK PROGRESS] WARNING: total_steps è 0 nel progress dict, provo a calcolarlo dall'outline")
                if session.current_outline:
                    try:
                        sections = parse_outline_sections(session.current_outline)
                        total_steps = len(sections)
                        calculated_total_steps = total_steps
                        print(f"[GET BOOK PROGRESS] Calcolato total_steps dall'outline: {total_steps}")
                    except Exception as e:
                        print(f"[GET BOOK PROGRESS] Errore nel parsing outline per calcolare total_steps: {e}")
                        total_steps = 0
                if total_steps == 0:
                    print(f"[GET BOOK PROGRESS] total_steps ancora 0, uso default 1 per permettere calcolo")
                    total_steps = 1
                    calculated_total_steps = 1
            
            print(f"[GET BOOK PROGRESS] Calcolo stima tempo: current_step={current_step}, total_steps={total_steps}")
            print(f"[GET BOOK PROGRESS] chapter_timings: {session.chapter_timings}")
            
            if total_steps <= 0:
                print(f"[GET BOOK PROGRESS] WARNING: total_steps è ancora <= 0 dopo fallback, uso 1 come ultimo resort")
                total_steps = 1
                calculated_total_steps = 1
            
            # Calcola sempre la stima
            estimated_time_minutes, estimated_time_confidence = await calculate_estimated_time(
                session_id, current_step, total_steps
            )
            print(f"[GET BOOK PROGRESS] estimated_time_minutes: {estimated_time_minutes}, confidence: {estimated_time_confidence}")
            
            # Fallback finale
            if estimated_time_minutes is None:
                remaining = total_steps - current_step
                if remaining > 0:
                    print(f"[GET BOOK PROGRESS] WARNING: calculate_estimated_time ha restituito None, uso fallback finale")
                    app_config = get_app_config()
                    time_config = app_config.get("time_estimation", {})
                    fallback_seconds = time_config.get("fallback_seconds_per_chapter", 45)
                    estimated_time_minutes = (remaining * fallback_seconds) / 60
                    estimated_time_confidence = "low"
                    print(f"[GET BOOK PROGRESS] Fallback finale applicato: {estimated_time_minutes:.1f} minuti")
        
        # Assicuriamoci che total_steps sia valido nel BookProgress
        if not is_complete and calculated_total_steps is not None and calculated_total_steps > 0:
            final_total_steps = calculated_total_steps
            print(f"[GET BOOK PROGRESS] Usando total_steps calcolato: {final_total_steps}")
        else:
            final_total_steps = progress.get('total_steps', 0)
        
        # Ultima garanzia
        if not is_complete and final_total_steps <= 0:
            print(f"[GET BOOK PROGRESS] SAFETY: final_total_steps è {final_total_steps}, uso 1 come minimo")
            final_total_steps = 1
        
        print(f"[GET BOOK PROGRESS] Valori finali: total_steps={final_total_steps}, estimated_time_minutes={estimated_time_minutes}, estimated_time_confidence={estimated_time_confidence}")
        
        return BookProgress(
            session_id=session_id,
            status=progress.get('status'),
            job_id=progress.get('job_id'),
            job_type=progress.get('job_type'),
            recoverable=progress.get('recoverable', False),
            attempt=progress.get('attempt'),
            updated_at=progress.get('updated_at'),
            queued_at=progress.get('queued_at'),
            started_at=progress.get('started_at'),
            completed_at=progress.get('completed_at'),
            job_metrics=progress.get('job_metrics'),
            current_step=progress.get('current_step', 0),
            total_steps=final_total_steps,
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
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Errore nel recupero del progresso: {str(e)}"
        )


@router.get("/{session_id}", response_model=BookResponse)
async def get_complete_book_endpoint(
    session_id: str,
):
    """Restituisce il libro completo con tutti i capitoli."""
    try:
        print(f"[GET BOOK] Richiesta libro completo per sessione: {session_id}")
        session_store = get_session_store()
        session = await get_session_async(session_store, session_id)
        
        if not session:
            print(f"[GET BOOK] Sessione {session_id} non trovata")
            raise HTTPException(
                status_code=404,
                detail=f"Sessione {session_id} non trovata"
            )
        
        
        print(f"[GET BOOK] Sessione trovata. Progresso: {session.writing_progress}, Capitoli: {len(session.book_chapters) if session.book_chapters else 0}")
        
        if not session.writing_progress or not session.writing_progress.get('is_complete'):
            print(f"[GET BOOK] Libro non ancora completo. Progresso: {session.writing_progress}")
            raise HTTPException(
                status_code=400,
                detail="Il libro non è ancora completo. Attendi il completamento della scrittura."
            )
        
        if not session.book_chapters or len(session.book_chapters) == 0:
            print(f"[GET BOOK] Nessun capitolo trovato nella sessione")
            raise HTTPException(
                status_code=400,
                detail="Nessun capitolo trovato nel libro. La scrittura potrebbe non essere stata completata correttamente."
            )
        
        # Converti i capitoli in oggetti Chapter
        chapters = []
        for idx, ch_dict in enumerate(session.book_chapters):
            try:
                content = ch_dict.get('content', '')
                page_count = calculate_page_count(content)
                chapter = Chapter(
                    title=ch_dict.get('title', f'Capitolo {idx + 1}'),
                    content=content,
                    section_index=ch_dict.get('section_index', idx),
                    page_count=page_count,
                )
                chapters.append(chapter)
                print(f"[GET BOOK] Capitolo {idx + 1}: '{chapter.title}' - {len(chapter.content)} caratteri - {page_count} pagine")
            except Exception as e:
                print(f"[GET BOOK] Errore nel processare capitolo {idx}: {e}")
                continue
        
        if len(chapters) == 0:
            raise HTTPException(
                status_code=400,
                detail="Nessun capitolo valido trovato nel libro."
            )
        
        # Ordina per section_index
        chapters.sort(key=lambda x: x.section_index)
        
        # Calcola total_pages
        chapters_pages = sum(ch.page_count for ch in chapters)
        cover_pages = 1
        app_config = get_app_config()
        toc_chapters_per_page = app_config.get("validation", {}).get("toc_chapters_per_page", 30)
        toc_pages = math.ceil(len(chapters) / toc_chapters_per_page)
        total_pages = chapters_pages + cover_pages + toc_pages
        
        # Calcola writing_time_minutes
        writing_time_minutes = None
        progress = session.writing_progress or {}
        if progress.get('writing_time_minutes') is not None:
            writing_time_minutes = progress.get('writing_time_minutes')
        elif session.writing_start_time and session.writing_end_time:
            delta = session.writing_end_time - session.writing_start_time
            writing_time_minutes = delta.total_seconds() / 60
        
        # Recupera la valutazione critica
        critique = None
        if session.literary_critique:
            try:
                critique = LiteraryCritique(**session.literary_critique)
            except Exception as e:
                print(f"[GET BOOK] Errore nel parsing critique: {e}")

        critique_status = session.critique_status
        critique_error = session.critique_error
        if critique_status is None and critique is not None:
            critique_status = "completed"
        
        book_response = BookResponse(
            title=session.current_title or "Romanzo",
            author=session.form_data.user_name or "Autore",
            chapters=chapters,
            total_pages=total_pages,
            writing_time_minutes=writing_time_minutes,
            critique=critique,
            critique_status=critique_status,
            critique_error=critique_error,
        )
        
        print(f"[GET BOOK] Libro restituito: {book_response.title} di {book_response.author}, {len(chapters)} capitoli, {total_pages} pagine totali")
        return book_response
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[GET BOOK] ERRORE nel recupero del libro completo: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nel recupero del libro completo: {str(e)}"
        )


@router.get("/pdf/{session_id}")
async def download_book_pdf_endpoint(
    session_id: str,
):
    """Genera e scarica un PDF del libro completo con titolo, indice e capitoli usando WeasyPrint."""
    return await generate_book_pdf(session_id)


@router.get("/audio/{session_id}/{chapter_index}")
async def get_chapter_audio_endpoint(
    session_id: str,
    chapter_index: int,
    voice_name: Optional[str] = None,
):
    """
    Restituisce l'audio (Text-to-Speech) di un capitolo specifico.
    """
    from app.services.tts_service import generate_chapter_audio
    
    session_store = get_session_store()
    session = await get_session_async(session_store, session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail=f"Sessione {session_id} non trovata")
        
    try:
        audio_content = await generate_chapter_audio(session_id, chapter_index, voice_name)
        return Response(
            content=audio_content,
            media_type="audio/wav",
            headers={
                "Content-Disposition": f'attachment; filename="chapter_{chapter_index}.wav"'
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"[CHAPTER AUDIO] Errore: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export/{session_id}")
async def export_book_endpoint(
    session_id: str,
    format: str = "pdf",
):
    """
    Genera e scarica il libro in diversi formati: PDF, EPUB o DOCX.
    
    Args:
        session_id: ID della sessione del libro
        format: Formato di export ("pdf", "epub", "docx"), default "pdf"
    
    Returns:
        File Response con il libro nel formato richiesto
    """
    try:
        print(f"[BOOK EXPORT] Richiesta export {format} per sessione: {session_id}")
        session_store = get_session_store()
        session = await get_session_async(session_store, session_id)
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Sessione {session_id} non trovata"
            )
        
        
        if not session.writing_progress or not session.writing_progress.get('is_complete'):
            raise HTTPException(
                status_code=400,
                detail="Il libro non è ancora completo. Attendi il completamento della scrittura."
            )
        
        if not session.book_chapters or len(session.book_chapters) == 0:
            raise HTTPException(
                status_code=400,
                detail="Nessun capitolo trovato nel libro."
            )
        
        format_lower = format.lower()
        
        # Genera il file nel formato richiesto
        if format_lower == "pdf":
            file_content, filename = await asyncio.to_thread(generate_complete_book_pdf, session)
            await save_session_async(session_store, session)
            media_type = "application/pdf"
        elif format_lower == "epub":
            file_content, filename = await asyncio.to_thread(generate_epub, session)
            media_type = "application/epub+zip"
        elif format_lower == "docx":
            file_content, filename = await asyncio.to_thread(generate_docx, session)
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Formato non supportato: {format}. Formati supportati: pdf, epub, docx"
            )
        
        print(f"[BOOK EXPORT] File {format} generato con successo: {filename}")
        
        return Response(
            content=file_content,
            media_type=media_type,
            headers={
                "Content-Disposition": attachment_header(filename)
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[BOOK EXPORT] ERRORE nella generazione del file {format}: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nella generazione del file {format}: {str(e)}"
        )


@router.post("/critique/{session_id}")
async def regenerate_book_critique_endpoint(
    session_id: str,
):
    """
    Rigenera la valutazione critica usando come input il PDF finale del libro.
    Utile per test e per rigenerare in caso di errore.
    """
    session_store = get_session_store()
    session = await get_session_async(session_store, session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Sessione {session_id} non trovata")

    if not session.writing_progress or not session.writing_progress.get("is_complete"):
        raise HTTPException(status_code=400, detail="Il libro non è ancora completo.")

    # Genera/recupera PDF
    try:
        await update_critique_status_async(session_store, session_id, "running", error=None)
        pdf_response = await generate_book_pdf(session_id)
        pdf_bytes = getattr(pdf_response, "body", None) or getattr(pdf_response, "content", None)
        if not isinstance(pdf_bytes, (bytes, bytearray)) or len(pdf_bytes) == 0:
            raise ValueError("PDF bytes non disponibili.")
    except Exception as e:
        await update_critique_status_async(session_store, session_id, "failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Errore nel generare il PDF per la critica: {e}")

    from app.core.config import get_literary_critic_config
    from app.agent.literary_critic import generate_literary_critique_from_pdf
    from app.llm.model_routing import get_stage_model
    
    critic_cfg = get_literary_critic_config()
    model_name = get_stage_model("critique", form_data=session.form_data) or critic_cfg.get("default_model")
    print(f"[REGENERATE_CRITIQUE] Endpoint chiamato per sessione {session_id}", file=sys.stderr)
    print(f"[REGENERATE_CRITIQUE] Configurazione critico: modello={model_name}, provider=GEMINI", file=sys.stderr)
    
    api_key = None  # Passiamo None, la funzione leggerà GOOGLE_API_KEY da env
    try:
        critique, token_usage = await generate_literary_critique_from_pdf(
            session_id=session_id,
            title=session.current_title or "Romanzo",
            author=session.form_data.user_name or "Autore",
            pdf_bytes=bytes(pdf_bytes),
            api_key=api_key,  # None = auto-detect da env
            model_name=model_name,
        )
    except Exception as e:
        await update_critique_status_async(session_store, session_id, "failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Errore nella generazione della critica: {e}")

    await update_critique_async(session_store, session_id, critique)
    await update_critique_status_async(session_store, session_id, "completed", error=None)
    
    # Salva token usage per la fase critique
    await update_token_usage_async(
        session_store=session_store,
        session_id=session_id,
        phase="critique",
        input_tokens=token_usage.get("input_tokens", 0),
        output_tokens=token_usage.get("output_tokens", 0),
        model=token_usage.get("model", "gemini-3.1-pro-preview"),
    )
    
    return critique

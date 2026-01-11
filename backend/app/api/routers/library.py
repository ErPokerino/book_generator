"""Router per gli endpoint della libreria."""
import os
import sys
import math
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from fastapi.responses import Response, FileResponse, RedirectResponse

from app.models import (
    LibraryResponse,
    LibraryStats,
    AdvancedStats,
    PdfEntry,
)
from app.agent.session_store import get_session_store
from app.agent.session_store_helpers import (
    get_all_sessions_async,
    get_session_async,
    delete_session_async,
    update_writing_progress_async,
    set_estimated_cost_async,
    update_cover_image_path_async,
)
from app.agent.cover_generator import generate_book_cover
from app.middleware.auth import get_current_user_optional, require_admin
from app.services.storage_service import get_storage_service
from app.services.stats_service import (
    get_cached_stats,
    set_cached_stats,
    invalidate_cache,
    session_to_library_entry,
    calculate_library_stats,
    calculate_advanced_stats,
    scan_pdf_directory,
    calculate_page_count,
    get_model_abbreviation,
    llm_model_to_mode,
    mode_to_llm_models,
    calculate_generation_cost,
    LIBRARY_ENTRY_FIELDS,
)
from app.core.config import get_app_config

router = APIRouter(prefix="/api/library", tags=["library"])


def sanitize_plot_for_cover(plot: str) -> str:
    """Sanitizza il plot creando un riassunto molto generico con solo elementi atmosferici e visivi."""
    if not plot:
        return ""
    
    import re
    
    plot_lower = plot.lower()
    
    places = []
    if 'villa' in plot_lower:
        places.append('villa')
    if 'vienna' in plot_lower:
        places.append('Vienna')
    if 'new york' in plot_lower or 'newyork' in plot_lower:
        places.append('New York')
    if 'roma' in plot_lower:
        places.append('Roma')
    if 'parigi' in plot_lower or 'paris' in plot_lower:
        places.append('Parigi')
    if 'ligure' in plot_lower or 'liguria' in plot_lower:
        places.append('costa ligure')
    
    atmosphere = []
    if 'estate' in plot_lower:
        atmosphere.append('estate')
    if 'neve' in plot_lower:
        atmosphere.append('neve')
    if 'mare' in plot_lower:
        atmosphere.append('mare')
    if 'caldo' in plot_lower:
        atmosphere.append('caldo opprimente')
    if 'luce' in plot_lower or 'tramonto' in plot_lower:
        atmosphere.append('luce del tramonto')
    
    themes = []
    if 'architettura' in plot_lower:
        themes.append('architettura')
    if 'musica' in plot_lower or 'violoncello' in plot_lower:
        themes.append('musica')
    if 'tempo' in plot_lower or 'memoria' in plot_lower:
        themes.append('tempo e memoria')
    if 'spazio' in plot_lower:
        themes.append('spazio')
    
    visual_elements = []
    if 'serra' in plot_lower:
        visual_elements.append('serra')
    if 'giardino' in plot_lower:
        visual_elements.append('giardino')
    if 'stanza' in plot_lower or 'camera' in plot_lower:
        visual_elements.append('stanza')
    
    sanitized_parts = []
    
    if places:
        sanitized_parts.append(f"Ambientato in {', '.join(set(places[:3]))}")
    
    if atmosphere:
        sanitized_parts.append(f"Atmosfera: {', '.join(set(atmosphere[:3]))}")
    
    if themes:
        sanitized_parts.append(f"Temi: {', '.join(set(themes[:3]))}")
    
    if visual_elements:
        sanitized_parts.append(f"Elementi visivi: {', '.join(set(visual_elements[:3]))}")
    
    if sanitized_parts:
        sanitized = "Romanzo " + ". ".join(sanitized_parts) + "."
    else:
        sentences = re.split(r'[.!?]', plot)
        first_safe_sentences = []
        for sent in sentences[:3]:
            sent_clean = sent.strip()
            if len(sent_clean) > 20 and len(sent_clean) < 200:
                sent_lower = sent_clean.lower()
                if not any(word in sent_lower for word in ['amore', 'bacio', 'corpo', 'intim', 'fisic', 'nud']):
                    first_safe_sentences.append(sent_clean)
        if first_safe_sentences:
            sanitized = ". ".join(first_safe_sentences) + "."
        else:
            sanitized = "Romanzo con temi di architettura, musica e memoria. Ambientato in luoghi che variano nel tempo."
    
    if len(sanitized) > 500:
        sanitized = sanitized[:500]
    
    return sanitized


@router.get("", response_model=LibraryResponse)
async def get_library_endpoint(
    status: Optional[str] = None,
    llm_model: Optional[str] = None,
    mode: Optional[str] = None,
    genre: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: Optional[str] = "created_at",
    sort_order: Optional[str] = "desc",
    skip: int = 0,
    limit: int = 20,
    current_user = Depends(get_current_user_optional),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """Restituisce la lista dei libri nella libreria con filtri opzionali e paginazione."""
    try:
        session_store = get_session_store()
        user_id = current_user.id if current_user else None
        
        # Determina il filtro per modello
        filter_llm_model = None
        if mode:
            models_for_mode = mode_to_llm_models(mode)
            if models_for_mode:
                filter_llm_model = None  # Filtriamo dopo
            else:
                filter_llm_model = None
        elif llm_model:
            detected_mode = llm_model_to_mode(llm_model)
            models_for_mode = mode_to_llm_models(detected_mode)
            if models_for_mode:
                filter_llm_model = None
            else:
                filter_llm_model = llm_model
        
        # Filtri vengono applicati nella query MongoDB
        all_sessions = await get_all_sessions_async(
            session_store, 
            user_id=user_id, 
            fields=LIBRARY_ENTRY_FIELDS,
            status=status,
            llm_model=filter_llm_model,
            genre=genre
        )
        
        # Filtra per modalità se necessario
        if mode:
            models_for_mode = mode_to_llm_models(mode)
            if models_for_mode:
                all_sessions = {
                    sid: sess for sid, sess in all_sessions.items()
                    if sess.form_data and sess.form_data.llm_model in models_for_mode
                }
            else:
                all_sessions = {}
        elif llm_model and not filter_llm_model:
            detected_mode = llm_model_to_mode(llm_model)
            models_for_mode = mode_to_llm_models(detected_mode)
            if models_for_mode:
                all_sessions = {
                    sid: sess for sid, sess in all_sessions.items()
                    if sess.form_data and sess.form_data.llm_model in models_for_mode
                }
        
        # Converti tutte le sessioni in LibraryEntry
        entries = []
        sessions_to_backfill = []
        
        for session in all_sessions.values():
            try:
                entry = session_to_library_entry(session)
                
                if entry.status == "complete":
                    needs_pages_backfill = entry.total_pages is None
                    needs_cost_backfill = entry.estimated_cost is None and entry.total_pages is not None
                    
                    if needs_pages_backfill or needs_cost_backfill:
                        full_session = None
                        if needs_pages_backfill:
                            try:
                                full_session = await get_session_async(session_store, session.session_id, user_id=user_id)
                                if full_session and full_session.book_chapters:
                                    chapters_pages = sum(calculate_page_count(ch.get('content', '')) for ch in full_session.book_chapters)
                                    cover_pages = 1
                                    app_config = get_app_config()
                                    toc_chapters_per_page = app_config.get("validation", {}).get("toc_chapters_per_page", 30)
                                    toc_pages = math.ceil(len(full_session.book_chapters) / toc_chapters_per_page)
                                    calculated_pages = chapters_pages + cover_pages + toc_pages
                                    calculated_chapters_count = len(full_session.book_chapters)
                                    
                                    entry.total_pages = calculated_pages
                                    
                                    if needs_cost_backfill and calculated_pages:
                                        calculated_cost = calculate_generation_cost(full_session, calculated_pages)
                                        if calculated_cost is not None:
                                            entry.estimated_cost = calculated_cost
                                            sessions_to_backfill.append((session.session_id, calculated_pages, calculated_chapters_count, calculated_cost))
                                        else:
                                            sessions_to_backfill.append((session.session_id, calculated_pages, calculated_chapters_count, None))
                                    else:
                                        sessions_to_backfill.append((session.session_id, calculated_pages, calculated_chapters_count, None))
                            except Exception as e:
                                print(f"[LIBRARY] Errore nel caricare sessione completa per backfill {session.session_id}: {e}")
                        elif needs_cost_backfill:
                            calculated_cost = calculate_generation_cost(session, entry.total_pages)
                            if calculated_cost is not None:
                                entry.estimated_cost = calculated_cost
                                sessions_to_backfill.append((session.session_id, None, None, calculated_cost))
                
                entries.append(entry)
            except Exception as e:
                print(f"[LIBRARY] Errore nel convertire sessione {session.session_id}: {e}")
                continue
        
        # Salva dati backfillati in background
        if sessions_to_backfill:
            async def backfill_library_data():
                """Salva total_pages e estimated_cost calcolati in background."""
                store = get_session_store()
                uid = user_id
                
                for session_id, total_pages, completed_chapters_count, estimated_cost in sessions_to_backfill:
                    try:
                        if total_pages is not None:
                            full_session = await get_session_async(store, session_id, user_id=uid)
                            if full_session and full_session.writing_progress:
                                current_step = full_session.writing_progress.get('current_step', 0)
                                total_steps = full_session.writing_progress.get('total_steps', 0)
                                current_section_name = full_session.writing_progress.get('current_section_name')
                                is_complete = full_session.writing_progress.get('is_complete', False)
                                is_paused = full_session.writing_progress.get('is_paused', False)
                                error = full_session.writing_progress.get('error')
                                final_chapters_count = completed_chapters_count if completed_chapters_count is not None else full_session.writing_progress.get('completed_chapters_count')
                                
                                await update_writing_progress_async(
                                    store,
                                    session_id,
                                    current_step=current_step,
                                    total_steps=total_steps,
                                    current_section_name=current_section_name,
                                    is_complete=is_complete,
                                    is_paused=is_paused,
                                    error=error,
                                    total_pages=total_pages,
                                    completed_chapters_count=final_chapters_count,
                                )
                        
                        if estimated_cost is not None:
                            await set_estimated_cost_async(store, session_id, estimated_cost)
                    except Exception as e:
                        print(f"[LIBRARY] Errore nel backfill per sessione {session_id}: {e}")
                
                # Invalida cache stats dopo il backfill
                invalidate_cache("library_stats")
                invalidate_cache("library_stats_advanced")
            
            background_tasks.add_task(backfill_library_data)
        
        # Recupera anche libri condivisi con l'utente (se autenticato)
        shared_entries = []
        if current_user and user_id:
            from app.agent.book_share_store import get_book_share_store
            from app.agent.user_store import get_user_store
            book_share_store = get_book_share_store()
            user_store_shared = get_user_store()
            
            try:
                await book_share_store.connect()
                shared_books = await book_share_store.get_user_shared_books(
                    user_id=user_id,
                    status="accepted",
                    limit=100,
                    skip=0,
                )
                
                await user_store_shared.connect()
                for share in shared_books:
                    try:
                        shared_session = await get_session_async(session_store, share.book_session_id, user_id=None)
                        
                        if not shared_session:
                            continue
                        
                        if not shared_session.writing_progress or not shared_session.writing_progress.get('is_complete', False):
                            continue
                        
                        # Applica filtri anche ai libri condivisi
                        if status and status != "all":
                            session_status = shared_session.get_status()
                            if session_status != status:
                                continue
                        
                        if genre and shared_session.form_data:
                            if shared_session.form_data.genre != genre:
                                continue
                        
                        if mode:
                            models_for_mode = mode_to_llm_models(mode)
                            if models_for_mode and shared_session.form_data:
                                if shared_session.form_data.llm_model not in models_for_mode:
                                    continue
                            elif not models_for_mode:
                                continue
                        elif llm_model and not filter_llm_model:
                            detected_mode = llm_model_to_mode(llm_model)
                            models_for_mode = mode_to_llm_models(detected_mode)
                            if models_for_mode and shared_session.form_data:
                                if shared_session.form_data.llm_model not in models_for_mode:
                                    continue
                        
                        shared_entry = session_to_library_entry(shared_session, skip_cost_calculation=True)
                        
                        owner = await user_store_shared.get_user_by_id(share.owner_id)
                        
                        from app.models import LibraryEntry
                        shared_entry = LibraryEntry(
                            session_id=shared_entry.session_id,
                            title=shared_entry.title,
                            author=shared_entry.author,
                            llm_model=shared_entry.llm_model,
                            genre=shared_entry.genre,
                            created_at=shared_entry.created_at,
                            updated_at=shared_entry.updated_at,
                            status=shared_entry.status,
                            total_chapters=shared_entry.total_chapters,
                            completed_chapters=shared_entry.completed_chapters,
                            total_pages=shared_entry.total_pages,
                            critique_score=shared_entry.critique_score,
                            critique_status=shared_entry.critique_status,
                            pdf_path=shared_entry.pdf_path,
                            pdf_filename=shared_entry.pdf_filename,
                            pdf_url=shared_entry.pdf_url,
                            cover_image_path=shared_entry.cover_image_path,
                            cover_url=shared_entry.cover_url,
                            writing_time_minutes=shared_entry.writing_time_minutes,
                            estimated_cost=shared_entry.estimated_cost,
                            is_shared=True,
                            shared_by_id=share.owner_id,
                            shared_by_name=owner.name if owner else None,
                        )
                        
                        shared_entries.append(shared_entry)
                    except Exception as e:
                        print(f"[LIBRARY] Errore nel processare libro condiviso {share.book_session_id}: {e}")
                        continue
            except Exception as e:
                print(f"[LIBRARY] Errore nel recupero libri condivisi: {e}")
        
        # Combina libri propri e condivisi
        all_entries = entries + shared_entries
        
        # Filtri già applicati nella query MongoDB, manteniamo solo search
        filtered_entries = all_entries
        
        if search:
            search_lower = search.lower()
            filtered_entries = [
                e for e in filtered_entries
                if search_lower in e.title.lower() or search_lower in (e.author or "").lower()
            ]
        
        # Ordina
        reverse_order = sort_order == "desc"
        if sort_by == "title":
            filtered_entries.sort(key=lambda e: e.title.lower(), reverse=reverse_order)
        elif sort_by == "score":
            filtered_entries.sort(key=lambda e: e.critique_score or 0, reverse=reverse_order)
        elif sort_by == "cost":
            if reverse_order:
                filtered_entries.sort(
                    key=lambda e: (e.estimated_cost is None, -(e.estimated_cost or float('inf')))
                )
            else:
                filtered_entries.sort(
                    key=lambda e: (e.estimated_cost is None, e.estimated_cost or float('inf'))
                )
        elif sort_by == "total_pages":
            if reverse_order:
                filtered_entries.sort(
                    key=lambda e: (e.total_pages is None, -(e.total_pages or 0))
                )
            else:
                filtered_entries.sort(
                    key=lambda e: (e.total_pages is None, e.total_pages or float('inf'))
                )
        elif sort_by == "updated_at":
            filtered_entries.sort(key=lambda e: e.updated_at, reverse=reverse_order)
        else:  # created_at default
            filtered_entries.sort(key=lambda e: e.created_at, reverse=reverse_order)
        
        # Calcola statistiche solo sui libri propri
        stats = calculate_library_stats(entries)
        
        # Applica paginazione DOPO l'ordinamento
        total_filtered = len(filtered_entries)
        start_index = skip
        end_index = skip + limit
        paginated_entries = filtered_entries[start_index:end_index]
        has_more = end_index < total_filtered
        
        return LibraryResponse(
            books=paginated_entries,
            total=total_filtered,
            has_more=has_more,
            stats=stats,
        )
    
    except Exception as e:
        print(f"[LIBRARY] Errore nel recupero libreria: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nel recupero della libreria: {str(e)}"
        )


@router.get("/stats", response_model=LibraryStats)
async def get_library_stats_endpoint(
    current_user = Depends(require_admin),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """Restituisce statistiche aggregate della libreria (solo admin, dati globali)."""
    try:
        cache_key = "library_stats"
        cached = get_cached_stats(cache_key)
        if cached is not None:
            return cached
        
        session_store = get_session_store()
        all_sessions = await get_all_sessions_async(session_store, user_id=None, fields=LIBRARY_ENTRY_FIELDS)
        
        entries = []
        sessions_to_update = []
        
        for session in all_sessions.values():
            try:
                entry = session_to_library_entry(session, skip_cost_calculation=True)
                
                if entry.estimated_cost is None and entry.status == "complete" and entry.total_pages:
                    calculated_cost = calculate_generation_cost(session, entry.total_pages)
                    if calculated_cost is not None:
                        entry.estimated_cost = calculated_cost
                        sessions_to_update.append((session.session_id, calculated_cost))
                
                entries.append(entry)
            except Exception as e:
                print(f"[LIBRARY STATS] Errore nel convertire sessione {session.session_id}: {e}")
                continue
        
        # Salva costi calcolati in background
        if sessions_to_update:
            async def backfill_costs():
                """Salva costi calcolati in background."""
                for session_id, cost in sessions_to_update:
                    try:
                        await set_estimated_cost_async(session_store, session_id, cost)
                    except Exception as e:
                        print(f"[LIBRARY STATS] Errore nel salvare costo per {session_id}: {e}")
                invalidate_cache(cache_key)
            
            background_tasks.add_task(backfill_costs)
        
        stats = calculate_library_stats(entries)
        set_cached_stats(cache_key, stats)
        return stats
    
    except Exception as e:
        print(f"[LIBRARY STATS] Errore nel calcolo statistiche: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nel calcolo delle statistiche: {str(e)}"
        )


@router.get("/stats/advanced", response_model=AdvancedStats)
async def get_advanced_stats_endpoint(
    current_user = Depends(require_admin),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """Restituisce statistiche avanzate con analisi temporali e confronto modelli (solo admin, dati globali)."""
    try:
        cache_key = "library_stats_advanced"
        cached = get_cached_stats(cache_key)
        if cached is not None:
            return cached
        
        session_store = get_session_store()
        all_sessions = await get_all_sessions_async(session_store, user_id=None, fields=LIBRARY_ENTRY_FIELDS)
        
        entries = []
        sessions_to_update = []
        
        for session in all_sessions.values():
            try:
                entry = session_to_library_entry(session, skip_cost_calculation=True)
                
                if entry.estimated_cost is None and entry.status == "complete" and entry.total_pages:
                    calculated_cost = calculate_generation_cost(session, entry.total_pages)
                    if calculated_cost is not None:
                        entry.estimated_cost = calculated_cost
                        sessions_to_update.append((session.session_id, calculated_cost))
                
                entries.append(entry)
            except Exception as e:
                print(f"[ADVANCED STATS] Errore nel convertire sessione {session.session_id}: {e}")
                continue
        
        # Salva costi calcolati in background
        if sessions_to_update:
            async def backfill_costs():
                """Salva costi calcolati in background."""
                for session_id, cost in sessions_to_update:
                    try:
                        await set_estimated_cost_async(session_store, session_id, cost)
                    except Exception as e:
                        print(f"[ADVANCED STATS] Errore nel salvare costo per {session_id}: {e}")
                invalidate_cache(cache_key)
            
            background_tasks.add_task(backfill_costs)
        
        advanced_stats = calculate_advanced_stats(entries)
        set_cached_stats(cache_key, advanced_stats)
        return advanced_stats
    
    except Exception as e:
        print(f"[ADVANCED STATS] Errore nel calcolo statistiche avanzate: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nel calcolo delle statistiche avanzate: {str(e)}"
        )


@router.delete("/{session_id}")
async def delete_library_entry_endpoint(
    session_id: str,
    current_user = Depends(get_current_user_optional),
):
    """Elimina un progetto dalla libreria."""
    try:
        session_store = get_session_store()
        
        user_id = current_user.id if current_user else None
        session = await get_session_async(session_store, session_id, user_id=user_id)
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Progetto {session_id} non trovato"
            )
        
        # Verifica ownership
        if current_user and session.user_id and session.user_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="Accesso negato: puoi eliminare solo i tuoi libri"
            )
        
        # Elimina anche tutte le condivisioni correlate
        from app.agent.book_share_store import get_book_share_store
        book_share_store = get_book_share_store()
        try:
            await book_share_store.connect()
            deleted_shares_count = await book_share_store.delete_all_shares_for_book(
                book_session_id=session_id,
                owner_id=current_user.id if current_user else session.user_id,
            )
            if deleted_shares_count > 0:
                print(f"[LIBRARY DELETE] Eliminate {deleted_shares_count} condivisioni per libro {session_id}", file=sys.stderr)
        except Exception as e:
            print(f"[LIBRARY DELETE] Avviso: errore nell'eliminazione condivisioni: {e}", file=sys.stderr)
        
        # Elimina file associati (PDF e copertina)
        deleted_files = []
        try:
            books_dir = Path(__file__).parent.parent.parent / "books"
            status = session.get_status()
            if status == "complete" and books_dir.exists():
                date_prefix = session.created_at.strftime("%Y-%m-%d")
                model_abbrev = get_model_abbreviation(session.form_data.llm_model)
                title_sanitized = "".join(c for c in (session.current_title or "Romanzo") if c.isalnum() or c in (' ', '-', '_')).rstrip()
                title_sanitized = title_sanitized.replace(" ", "_")
                if not title_sanitized:
                    title_sanitized = f"Libro_{session.session_id[:8]}"
                expected_filename = f"{date_prefix}_{model_abbrev}_{title_sanitized}.pdf"
                expected_path = books_dir / expected_filename
                
                if expected_path.exists():
                    expected_path.unlink()
                    deleted_files.append(f"PDF: {expected_filename}")
                else:
                    for pdf_file in books_dir.glob("*.pdf"):
                        if session.session_id[:8] in pdf_file.stem or (title_sanitized and title_sanitized.lower() in pdf_file.stem.lower()):
                            deleted_files.append(f"PDF: {pdf_file.name}")
                            pdf_file.unlink()
                            break
            
            if session.cover_image_path:
                cover_path = Path(session.cover_image_path)
                if cover_path.exists():
                    cover_path.unlink()
                    deleted_files.append(f"Copertina: {cover_path.name}")
        except Exception as file_error:
            print(f"[LIBRARY DELETE] Errore nell'eliminazione file per {session_id}: {file_error}")
        
        deleted = await delete_session_async(session_store, session_id)
        if deleted:
            response = {"success": True, "message": f"Progetto {session_id} eliminato con successo"}
            if deleted_files:
                response["deleted_files"] = deleted_files
            return response
        else:
            raise HTTPException(
                status_code=500,
                detail="Errore nell'eliminazione del progetto"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[LIBRARY DELETE] Errore nell'eliminazione: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nell'eliminazione del progetto: {str(e)}"
        )


@router.get("/pdfs", response_model=list[PdfEntry])
async def get_available_pdfs_endpoint():
    """Restituisce la lista di tutti i PDF disponibili."""
    try:
        pdf_entries = scan_pdf_directory()
        return pdf_entries
    
    except Exception as e:
        print(f"[LIBRARY PDFS] Errore nello scan PDF: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nel recupero dei PDF: {str(e)}"
        )


@router.get("/cover/{session_id}")
async def get_cover_image_endpoint(
    session_id: str,
    current_user = Depends(get_current_user_optional),
):
    """Restituisce l'immagine della copertina per una sessione."""
    try:
        session_store = get_session_store()
        session = await get_session_async(session_store, session_id, user_id=None)
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Sessione {session_id} non trovata"
            )
        
        # Verifica accesso: ownership o condivisione accettata
        if current_user and session.user_id and session.user_id != current_user.id:
            from app.agent.book_share_store import get_book_share_store
            book_share_store = get_book_share_store()
            await book_share_store.connect()
            has_access = await book_share_store.check_user_has_access(
                book_session_id=session_id,
                user_id=current_user.id,
                owner_id=session.user_id,
            )
            if not has_access:
                raise HTTPException(
                    status_code=403,
                    detail="Accesso negato: questa sessione appartiene a un altro utente o non hai accesso"
                )
        
        if not session.cover_image_path:
            raise HTTPException(
                status_code=404,
                detail="Copertina non disponibile per questa sessione"
            )
        
        cover_path_str = session.cover_image_path
        
        # Se il path è su GCS, usa StorageService
        if cover_path_str.startswith("gs://"):
            storage_service = get_storage_service()
            
            signed_url = storage_service.get_signed_url(cover_path_str, expiration_minutes=60)
            if signed_url and signed_url.startswith("http"):
                return RedirectResponse(url=signed_url)
            
            try:
                cover_data = storage_service.download_file(cover_path_str)
                if cover_data:
                    suffix = Path(cover_path_str).suffix.lower()
                    media_type = 'image/png' if suffix == '.png' else 'image/jpeg'
                    return Response(content=cover_data, media_type=media_type)
            except FileNotFoundError as download_err:
                error_msg = str(download_err)
                print(f"[COVER IMAGE] Errore download da GCS: {error_msg}")
                raise HTTPException(
                    status_code=404,
                    detail=error_msg
                )
            except Exception as download_err:
                print(f"[COVER IMAGE] Errore download da GCS: {download_err}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Errore nel recupero della copertina: {str(download_err)}"
                )
        
        # Path locale
        cover_path = Path(cover_path_str)
        if not cover_path.exists():
            raise HTTPException(
                status_code=404,
                detail="File copertina non trovato"
            )
        
        suffix = cover_path.suffix.lower()
        media_type = 'image/png' if suffix == '.png' else 'image/jpeg'
        
        return FileResponse(
            path=str(cover_path),
            media_type=media_type,
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[COVER IMAGE] Errore nel recupero copertina: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nel recupero della copertina: {str(e)}"
        )


@router.post("/cover/regenerate/{session_id}")
async def regenerate_cover_endpoint(
    session_id: str,
    current_user = Depends(get_current_user_optional),
):
    """Rigenera la copertina per un libro completato."""
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
        
        status = session.get_status()
        if status != "complete":
            raise HTTPException(
                status_code=400,
                detail="Il libro deve essere completato per rigenerare la copertina"
            )
        
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="GOOGLE_API_KEY non configurata. Verifica il file .env nella root del progetto."
            )
        
        print(f"[REGENERATE COVER] Avvio rigenerazione copertina per sessione {session_id}")
        
        original_plot = session.current_draft or ""
        sanitized_plot = sanitize_plot_for_cover(original_plot)
        print(f"[REGENERATE COVER] Plot sanitizzato: {len(original_plot)} -> {len(sanitized_plot)} caratteri")
        
        cover_path = await generate_book_cover(
            session_id=session_id,
            title=session.current_title or "Romanzo",
            author=session.form_data.user_name or "Autore",
            plot=sanitized_plot,
            api_key=api_key,
            cover_style=session.form_data.cover_style,
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
            print(f"[REGENERATE COVER] Copertina rigenerata e caricata su GCS: {gcs_path}")
            return {"success": True, "cover_path": gcs_path}
        except Exception as e:
            print(f"[REGENERATE COVER] ERRORE nel caricamento copertina su GCS: {e}, uso path locale")
            await update_cover_image_path_async(session_store, session_id, str(cover_path))
            print(f"[REGENERATE COVER] Copertina rigenerata con successo: {cover_path}")
            return {"success": True, "cover_path": str(cover_path)}
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[REGENERATE COVER] Errore nella rigenerazione copertina: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nella rigenerazione della copertina: {str(e)}"
        )


@router.get("/missing-covers")
async def get_missing_covers_endpoint():
    """Restituisce lista di libri completati senza copertina."""
    try:
        session_store = get_session_store()
        all_sessions = await get_all_sessions_async(session_store)
        
        missing_covers = []
        
        for session_id, session in all_sessions.items():
            status = session.get_status()
            if status == "complete":
                has_cover = False
                if session.cover_image_path:
                    cover_path = Path(session.cover_image_path)
                    if cover_path.exists():
                        has_cover = True
                
                if not has_cover:
                    entry = session_to_library_entry(session)
                    missing_covers.append({
                        "session_id": session_id,
                        "title": entry.title,
                        "author": entry.author,
                        "created_at": entry.created_at.isoformat(),
                    })
        
        return {"missing_covers": missing_covers, "count": len(missing_covers)}
    
    except Exception as e:
        print(f"[MISSING COVERS] Errore nel recupero libri senza copertina: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nel recupero dei libri senza copertina: {str(e)}"
        )


@router.get("/cleanup/preview")
async def preview_obsolete_books_endpoint():
    """Restituisce la lista dei libri obsoleti che verrebbero eliminati dalla pulizia."""
    try:
        session_store = get_session_store()
        all_sessions = await get_all_sessions_async(session_store)
        
        obsolete_books = []
        
        for session_id, session in all_sessions.items():
            try:
                entry = session_to_library_entry(session)
                is_obsolete = (
                    entry.critique_score is None
                    or 
                    (entry.status == "complete" and not session.cover_image_path)
                )
                if is_obsolete:
                    obsolete_books.append({
                        "session_id": session_id,
                        "title": entry.title,
                        "author": entry.author,
                        "status": entry.status,
                        "created_at": entry.created_at.isoformat(),
                        "updated_at": entry.updated_at.isoformat(),
                        "has_pdf": entry.pdf_filename is not None,
                        "has_cover": session.cover_image_path is not None,
                        "has_score": entry.critique_score is not None,
                    })
            except Exception as e:
                print(f"[CLEANUP PREVIEW] Errore nel processare sessione {session_id}: {e}")
                continue
        
        return {
            "obsolete_books": obsolete_books,
            "count": len(obsolete_books)
        }
    
    except Exception as e:
        print(f"[CLEANUP PREVIEW] Errore: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nella preview dei libri obsoleti: {str(e)}"
        )


@router.post("/cleanup")
async def cleanup_obsolete_books_endpoint():
    """Elimina automaticamente tutti i libri obsoleti dalla libreria."""
    try:
        session_store = get_session_store()
        all_sessions = await get_all_sessions_async(session_store)
        
        obsolete_session_ids = []
        books_dir = Path(__file__).parent.parent.parent / "books"
        
        for session_id, session in all_sessions.items():
            try:
                entry = session_to_library_entry(session)
                is_obsolete = (
                    entry.critique_score is None
                    or 
                    (entry.status == "complete" and not session.cover_image_path)
                )
                if is_obsolete:
                    obsolete_session_ids.append({
                        "session_id": session_id,
                        "title": entry.title,
                        "status": entry.status,
                        "has_pdf": entry.pdf_filename is not None,
                        "has_cover": session.cover_image_path is not None,
                    })
            except Exception as e:
                print(f"[CLEANUP] Errore nel processare sessione {session_id}: {e}")
                continue
        
        # Elimina i libri obsoleti
        deleted_count = 0
        deleted_files_count = 0
        errors = []
        
        for book_info in obsolete_session_ids:
            session_id = book_info["session_id"]
            try:
                session = await get_session_async(session_store, session_id)
                if not session:
                    continue
                
                files_deleted = 0
                session_status = session.get_status()
                try:
                    if session_status == "complete" and books_dir.exists():
                        date_prefix = session.created_at.strftime("%Y-%m-%d")
                        model_abbrev = get_model_abbreviation(session.form_data.llm_model)
                        title_sanitized = "".join(c for c in (session.current_title or "Romanzo") if c.isalnum() or c in (' ', '-', '_')).rstrip()
                        title_sanitized = title_sanitized.replace(" ", "_")
                        if not title_sanitized:
                            title_sanitized = f"Libro_{session.session_id[:8]}"
                        expected_filename = f"{date_prefix}_{model_abbrev}_{title_sanitized}.pdf"
                        expected_path = books_dir / expected_filename
                        
                        if expected_path.exists():
                            expected_path.unlink()
                            files_deleted += 1
                        else:
                            for pdf_file in books_dir.glob("*.pdf"):
                                if session.session_id[:8] in pdf_file.stem or (title_sanitized and title_sanitized.lower() in pdf_file.stem.lower()):
                                    pdf_file.unlink()
                                    files_deleted += 1
                                    break
                    
                    if session.cover_image_path:
                        cover_path = Path(session.cover_image_path)
                        if cover_path.exists():
                            cover_path.unlink()
                            files_deleted += 1
                except Exception as file_error:
                    errors.append(f"Errore eliminazione file per {book_info['title']}: {file_error}")
                
                if await delete_session_async(session_store, session_id):
                    deleted_count += 1
                    deleted_files_count += files_deleted
                else:
                    errors.append(f"Errore eliminazione sessione {session_id}")
                    
            except Exception as e:
                errors.append(f"Errore durante eliminazione {book_info['title']}: {e}")
                print(f"[CLEANUP] Errore eliminando {session_id}: {e}")
        
        return {
            "deleted_count": deleted_count,
            "deleted_files_count": deleted_files_count,
            "errors": errors if errors else None,
        }
    
    except Exception as e:
        print(f"[CLEANUP] Errore: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nella pulizia dei libri obsoleti: {str(e)}"
        )


@router.get("/pdf/{filename:path}")
async def download_pdf_by_filename_endpoint(filename: str):
    """Scarica un PDF specifico per nome file."""
    try:
        books_dir = Path(__file__).parent.parent.parent / "books"
        pdf_path = books_dir / filename
        
        # Validazione sicurezza
        try:
            pdf_path.resolve().relative_to(books_dir.resolve())
        except ValueError:
            raise HTTPException(
                status_code=403,
                detail="Accesso non consentito a questo file"
            )
        
        if not pdf_path.exists() or not pdf_path.is_file():
            raise HTTPException(
                status_code=404,
                detail=f"PDF {filename} non trovato"
            )
        
        with open(pdf_path, 'rb') as f:
            pdf_content = f.read()
        
        return Response(
            content=pdf_content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[LIBRARY PDF DOWNLOAD] Errore nel download: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nel download del PDF: {str(e)}"
        )

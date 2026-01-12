"""Router per gli endpoint dei libri."""
import os
import sys
from pathlib import Path
from typing import Optional
from io import BytesIO
from datetime import datetime
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from fastapi.responses import Response
from PIL import Image as PILImage
import markdown
import base64
import math
from xhtml2pdf import pisa

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
    update_writing_progress_async,
    update_critique_async,
    update_critique_status_async,
)
from app.middleware.auth import get_current_user_optional
from app.services.pdf_service import generate_complete_book_pdf, calculate_page_count
from app.services.export_service import generate_epub, generate_docx
from app.services.storage_service import get_storage_service
from app.services.book_generation_service import (
    background_book_generation,
    background_resume_book_generation,
)
from app.core.config import get_app_config
from app.services.stats_service import llm_model_to_mode

# Helper functions (temporarily defined here, will be moved to utils later)
def get_model_abbreviation(model_name: str) -> str:
    """Converte il nome completo del modello in una versione abbreviata per il nome del PDF."""
    model_lower = model_name.lower()
    if "gemini-2.5-flash" in model_lower:
        return "g25f"
    elif "gemini-2.5-pro" in model_lower:
        return "g25p"
    elif "gemini-3-flash" in model_lower:
        return "g3f"
    elif "gemini-3-pro" in model_lower:
        return "g3p"
    else:
        return model_name.replace("gemini-", "g").replace("-", "").replace("_", "")[:6]


def escape_html(text: str) -> str:
    """Escapa caratteri speciali per HTML."""
    if not text:
        return ""
    return (text.replace("&", "&amp;")
              .replace("<", "&lt;")
              .replace(">", "&gt;")
              .replace('"', "&quot;")
              .replace("'", "&#39;"))


def markdown_to_html(text: str) -> str:
    """Converte markdown base a HTML."""
    if not text:
        return ""
    html = markdown.markdown(text, extensions=['nl2br', 'fenced_code'])
    return html


def calculate_generation_cost(session, total_pages: Optional[int]) -> Optional[float]:
    """Calcola il costo stimato di generazione dei capitoli del libro."""
    if not total_pages or total_pages <= 0:
        return None
    
    try:
        from app.core.config import (
            get_tokens_per_page,
            get_model_pricing,
            get_exchange_rate_usd_to_eur,
        )
        from app.agent.writer_generator import map_model_name
        
        tokens_per_page = get_tokens_per_page()
        model_name = session.form_data.llm_model if session.form_data else None
        if not model_name:
            return None
        
        gemini_model = map_model_name(model_name)
        pricing = get_model_pricing(gemini_model)
        input_cost_per_million = pricing["input_cost_per_million"]
        output_cost_per_million = pricing["output_cost_per_million"]
        
        from app.core.config import get_token_estimates
        token_estimates = get_token_estimates()
        context_base_tokens = token_estimates.get("context_base", 8000)
        
        # Calcola usando formula chiusa O(1)
        chapters = session.book_chapters or []
        num_chapters = len(chapters)
        if num_chapters == 0:
            return None
        
        avg_pages_per_chapter = total_pages / num_chapters if num_chapters > 0 else 0
        chapters_pages = total_pages - 1  # Escludi copertina
        
        # Formula chiusa: sum(i=1 to N) di (i-1) = N * (N-1) / 2
        cumulative_pages_sum = (num_chapters * (num_chapters - 1) / 2) * avg_pages_per_chapter
        
        chapters_input = num_chapters * context_base_tokens
        chapters_input += cumulative_pages_sum * tokens_per_page
        
        chapters_output = chapters_pages * tokens_per_page
        
        cost_usd = (chapters_input * input_cost_per_million / 1_000_000) + (chapters_output * output_cost_per_million / 1_000_000)
        
        exchange_rate = get_exchange_rate_usd_to_eur()
        cost_eur = cost_usd * exchange_rate
        
        return round(cost_eur, 4)
    except Exception as e:
        print(f"[CALCULATE_COST] Errore nel calcolo costo: {e}")
        return None


async def calculate_estimated_time(session_id: str, current_step: int, total_steps: int) -> tuple[Optional[float], Optional[str]]:
    """Calcola la stima del tempo rimanente per completare il libro usando modello lineare."""
    try:
        try:
            current_step = int(current_step)
        except (ValueError, TypeError):
            print(f"[CALCULATE_ESTIMATED_TIME] WARNING: current_step non è un numero valido ({current_step}), uso 0")
            current_step = 0
        
        try:
            total_steps = int(total_steps)
        except (ValueError, TypeError):
            print(f"[CALCULATE_ESTIMATED_TIME] WARNING: total_steps non è un numero valido ({total_steps}), uso 0")
            total_steps = 0
        
        if total_steps <= 0:
            return None, None
        
        remaining_chapters = total_steps - current_step
        if remaining_chapters <= 0:
            return None, None
        
        app_config = get_app_config()
        session_store = get_session_store()
        session = await get_session_async(session_store, session_id)
        
        current_model = session.form_data.llm_model if session and session.form_data else None
        
        from app.utils.stats_utils import get_generation_method, get_linear_params_for_method, calculate_residual_time_linear
        method = get_generation_method(current_model)
        a, b = get_linear_params_for_method(method, app_config)
        
        k = current_step + 1
        N = total_steps
        
        estimated_seconds = calculate_residual_time_linear(k, N, a, b)
        estimated_minutes = estimated_seconds / 60
        
        return round(estimated_minutes, 1), None
        
    except Exception as e:
        print(f"[CALCULATE_ESTIMATED_TIME] ERRORE nel calcolo stima tempo: {e}")
        import traceback
        traceback.print_exc()
        return None, None

router = APIRouter(prefix="/api/book", tags=["book"])


async def generate_book_pdf(session_id: str, current_user=None) -> Response:
    """
    Helper function per generare PDF del libro.
    Può essere chiamata sia dall'endpoint che dal service.
    """
    from app.agent.book_share_store import get_book_share_store
    
    session_store = get_session_store()
    session = await get_session_async(session_store, session_id, user_id=None)
    
    if not session:
        raise HTTPException(status_code=404, detail=f"Sessione {session_id} non trovata")
    
    # Verifica accesso se current_user è fornito
    if current_user and session.user_id and session.user_id != current_user.id:
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
    
    if not session.writing_progress or not session.writing_progress.get('is_complete'):
        raise HTTPException(
            status_code=400,
            detail="Il libro non è ancora completo. Attendi il completamento della scrittura."
        )
    
    if not session.book_chapters or len(session.book_chapters) == 0:
        raise HTTPException(status_code=400, detail="Nessun capitolo trovato nel libro.")
    
    book_title = session.current_title or "Romanzo"
    book_author = session.form_data.user_name or "Autore"
    
    print(f"[BOOK PDF] Generazione PDF con WeasyPrint per: {book_title}")
    
    # Leggi il file CSS
    css_path = Path(__file__).parent.parent.parent / "static" / "book_styles.css"
    if not css_path.exists():
        raise Exception(f"File CSS non trovato: {css_path}")
    
    with open(css_path, 'r', encoding='utf-8') as f:
        css_content = f.read()
    
    print(f"[BOOK PDF] CSS caricato da: {css_path}")
    
    # Prepara immagine copertina
    cover_image_data = None
    cover_image_mime = None
    cover_image_style = None
    
    print(f"[BOOK PDF] Verifica copertina - cover_image_path nella sessione: {session.cover_image_path}")
    
    if session.cover_image_path:
        try:
            storage_service = get_storage_service()
            print(f"[BOOK PDF] Caricamento copertina da: {session.cover_image_path}")
            image_bytes = storage_service.download_file(session.cover_image_path)
            print(f"[BOOK PDF] Immagine copertina caricata: {len(image_bytes)} bytes")
            
            with PILImage.open(BytesIO(image_bytes)) as img:
                cover_image_width, cover_image_height = img.size
                print(f"[BOOK PDF] Dimensioni originali immagine: {cover_image_width} x {cover_image_height}")
            
            cover_path_str = session.cover_image_path.lower()
            if '.png' in cover_path_str:
                cover_image_mime = 'image/png'
            elif '.jpg' in cover_path_str or '.jpeg' in cover_path_str:
                cover_image_mime = 'image/jpeg'
            else:
                cover_image_mime = 'image/png'
            
            a4_width_pt = 595.276
            a4_height_pt = 841.890
            a4_ratio = a4_height_pt / a4_width_pt
            image_ratio = cover_image_height / cover_image_width
            
            if image_ratio > a4_ratio:
                cover_image_style = "width: auto; height: 100%;"
            else:
                cover_image_style = "width: 100%; height: auto;"
            
            cover_image_data = base64.b64encode(image_bytes).decode('utf-8')
            print(f"[BOOK PDF] Immagine copertina caricata, MIME: {cover_image_mime}")
        except Exception as e:
            print(f"[BOOK PDF] Errore nel caricamento copertina: {e}")
            import traceback
            traceback.print_exc()
    
    # Ordina i capitoli per section_index
    sorted_chapters = sorted(session.book_chapters, key=lambda x: x.get('section_index', 0))
    
    # Prepara HTML per indice
    toc_items = []
    for idx, chapter in enumerate(sorted_chapters, 1):
        chapter_title = chapter.get('title', f'Capitolo {idx}')
        toc_items.append(f'<div class="toc-item">{idx}. {escape_html(chapter_title)}</div>')
    
    toc_html = '\n            '.join(toc_items)
    
    # Prepara HTML per capitoli
    chapters_html = []
    for idx, chapter in enumerate(sorted_chapters, 1):
        chapter_title = chapter.get('title', f'Capitolo {idx}')
        chapter_content = chapter.get('content', '')
        content_html = markdown_to_html(chapter_content)
        
        chapters_html.append(f'''    <div class="chapter">
        <h1 class="chapter-title">{escape_html(chapter_title)}</h1>
        <div class="chapter-content">
            {content_html}
        </div>
    </div>''')
    
    chapters_html_str = '\n\n'.join(chapters_html)
    
    # Genera HTML completo
    cover_section = ''
    image_style = cover_image_style or "width: 100%; height: auto;"
    container_style = "width: 595.276pt; height: 841.890pt; margin: 0; padding: 0; position: relative; overflow: hidden; display: flex; align-items: center; justify-content: center;"
    
    if cover_image_data and cover_image_mime:
        cover_section = f'''    <!-- Copertina -->
    <div class="cover-page" style="{container_style}">
        <img src="data:{cover_image_mime};base64,{cover_image_data}" class="cover-image" alt="Copertina" style="{image_style} margin: 0; padding: 0; display: block;">
    </div>
    <div style="page-break-after: always;"></div>'''
        print(f"[BOOK PDF] Copertina aggiunta con base64, stile: {image_style}")
    
    html_content = f'''<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{escape_html(book_title)}</title>
    <style>
        {css_content}
    </style>
</head>
<body>
    <div class="content-wrapper">
{cover_section}
        
        <!-- Indice -->
        <div class="table-of-contents">
            <h1>Indice</h1>
            <div class="toc-list">
                {toc_html}
            </div>
        </div>
        
        <!-- Capitoli -->
{chapters_html_str}
    </div>
</body>
</html>'''
    
    print(f"[BOOK PDF] HTML generato, lunghezza: {len(html_content)} caratteri")
    
    # Genera PDF con xhtml2pdf
    print(f"[BOOK PDF] Generazione PDF con xhtml2pdf...")
    buffer = BytesIO()
    
    try:
        result = pisa.CreatePDF(
            src=html_content,
            dest=buffer,
            encoding='utf-8'
        )
        
        if result.err:
            raise Exception(f"Errore nella generazione PDF: {result.err}")
        
        print(f"[BOOK PDF] PDF generato con successo")
    except Exception as e:
        print(f"[BOOK PDF] Errore nella generazione PDF con xhtml2pdf: {e}")
        import traceback
        traceback.print_exc()
        raise
    
    buffer.seek(0)
    pdf_content = buffer.getvalue()
    
    # Nome file con data, modello e titolo
    date_prefix = datetime.now().strftime("%Y-%m-%d")
    model_abbrev = get_model_abbreviation(session.form_data.llm_model)
    title_sanitized = "".join(c for c in book_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
    title_sanitized = title_sanitized.replace(" ", "_")
    if not title_sanitized:
        title_sanitized = f"Libro_{session_id[:8]}"
    filename = f"{date_prefix}_{model_abbrev}_{title_sanitized}.pdf"
    
    # Salva PDF su GCS o locale tramite StorageService
    try:
        storage_service = get_storage_service()
        user_id = session.user_id if hasattr(session, 'user_id') else None
        gcs_path = storage_service.upload_file(
            data=pdf_content,
            destination_path=f"books/{filename}",
            content_type="application/pdf",
            user_id=user_id,
        )
        print(f"[BOOK PDF] PDF salvato: {gcs_path}")
    except Exception as e:
        print(f"[BOOK PDF] Errore nel salvataggio PDF: {e}")
        import traceback
        traceback.print_exc()
    
    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@router.post("/generate", response_model=BookGenerationResponse)
async def generate_book_endpoint(
    request: BookGenerationRequest,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user_optional),
):
    """Avvia la generazione del libro completo in background."""
    try:
        # Verifica che l'API key sia configurata
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="GOOGLE_API_KEY non configurata. Verifica il file .env nella root del progetto."
            )
        
        # Recupera la sessione
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
        
        # Verifica e consuma crediti (solo per utenti autenticati)
        if current_user:
            from app.agent.user_store import get_user_store
            
            # Estrai la modalità dal form_data della sessione
            llm_model = session.form_data.llm_model if session.form_data and session.form_data.llm_model else "gemini-3-flash"
            mode = llm_model_to_mode(llm_model).lower()  # flash, pro, ultra
            
            print(f"[BOOK GENERATION] Tentativo consumo credito {mode} per utente {current_user.id}")
            
            # Verifica crediti disponibili e consuma
            user_store = get_user_store()
            success, message, updated_credits = await user_store.consume_credit(current_user.id, mode)
            
            print(f"[BOOK GENERATION] Risultato consumo credito: success={success}, message={message}, credits={updated_credits}")
            
            if not success:
                # Crediti esauriti - ritorna errore HTTP
                _, _, next_reset = await user_store.get_user_credits(current_user.id)
                raise HTTPException(
                    status_code=402,  # Payment Required
                    detail={
                        "error_type": "credits_exhausted",
                        "message": message,
                        "mode": mode.capitalize(),
                        "next_reset_at": next_reset.isoformat(),
                    }
                )
        else:
            print(f"[BOOK GENERATION] ATTENZIONE: Utente non autenticato, crediti NON consumati")
        
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
        background_tasks.add_task(
            background_book_generation,
            session_id=request.session_id,
            form_data=session.form_data,
            question_answers=session.question_answers,
            validated_draft=session.current_draft,
            draft_title=session.current_title,
            outline_text=session.current_outline,
            api_key=api_key,
            generate_pdf_callback=lambda sid: generate_book_pdf(sid, current_user=None),
        )
        
        print(f"[BOOK GENERATION] Task di generazione avviato per sessione {request.session_id}")
        
        return BookGenerationResponse(
            success=True,
            session_id=request.session_id,
            message="Generazione del libro avviata. Usa /api/book/progress per monitorare lo stato.",
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
    current_user = Depends(get_current_user_optional),
):
    """Riprende la generazione del libro dal capitolo fallito."""
    try:
        # Verifica che l'API key sia configurata
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="GOOGLE_API_KEY non configurata. Verifica il file .env nella root del progetto."
            )
        
        # Recupera la sessione
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
        
        if not session.writing_progress:
            raise HTTPException(
                status_code=400,
                detail="La sessione non ha uno stato di scrittura. Avvia prima la generazione."
            )
        
        if not session.writing_progress.get('is_paused', False):
            raise HTTPException(
                status_code=400,
                detail="La sessione non è in stato di pausa. Non è possibile riprendere."
            )
        
        # Avvia la ripresa in background con callback per PDF
        background_tasks.add_task(
            background_resume_book_generation,
            session_id=session_id,
            api_key=api_key,
            generate_pdf_callback=lambda sid: generate_book_pdf(sid, current_user=None),
        )
        
        print(f"[BOOK GENERATION] Task di ripresa generazione avviato per sessione {session_id}")
        
        return BookGenerationResponse(
            success=True,
            session_id=session_id,
            message="Ripresa della generazione avviata. Usa /api/book/progress per monitorare lo stato.",
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
    current_user = Depends(get_current_user_optional),
):
    """Recupera lo stato di avanzamento della scrittura del libro."""
    try:
        session_store = get_session_store()
        # Recupera sessione senza filtro user_id per permettere accesso a libri condivisi
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
        
        # Calcola writing_time_minutes se disponibile o calcolabile
        writing_time_minutes = progress.get('writing_time_minutes')
        if writing_time_minutes is None and is_complete:
            if session.writing_start_time and session.writing_end_time:
                delta = session.writing_end_time - session.writing_start_time
                writing_time_minutes = delta.total_seconds() / 60
        
        # Calcola costo stimato (solo se libro completo)
        estimated_cost = None
        if is_complete and total_pages:
            estimated_cost = calculate_generation_cost(session, total_pages)
        
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
    current_user = Depends(get_current_user_optional)
):
    """Restituisce il libro completo con tutti i capitoli."""
    try:
        print(f"[GET BOOK] Richiesta libro completo per sessione: {session_id}")
        session_store = get_session_store()
        session = await get_session_async(session_store, session_id, user_id=None)
        
        if not session:
            print(f"[GET BOOK] Sessione {session_id} non trovata")
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
    current_user = Depends(get_current_user_optional),
):
    """Genera e scarica un PDF del libro completo con titolo, indice e capitoli usando WeasyPrint."""
    return await generate_book_pdf(session_id, current_user)


@router.get("/export/{session_id}")
async def export_book_endpoint(
    session_id: str,
    format: str = "pdf",
    current_user = Depends(get_current_user_optional),
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
            file_content, filename = generate_complete_book_pdf(session)
            media_type = "application/pdf"
        elif format_lower == "epub":
            file_content, filename = generate_epub(session)
            media_type = "application/epub+zip"
        elif format_lower == "docx":
            file_content, filename = generate_docx(session)
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
                "Content-Disposition": f'attachment; filename="{filename}"'
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
    current_user = Depends(get_current_user_optional),
):
    """
    Rigenera la valutazione critica usando come input il PDF finale del libro.
    Utile per test e per rigenerare in caso di errore.
    """
    session_store = get_session_store()
    session = await get_session_async(session_store, session_id, user_id=None)
    if not session:
        raise HTTPException(status_code=404, detail=f"Sessione {session_id} non trovata")
    
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

    if not session.writing_progress or not session.writing_progress.get("is_complete"):
        raise HTTPException(status_code=400, detail="Il libro non è ancora completo.")

    # Genera/recupera PDF
    try:
        await update_critique_status_async(session_store, session_id, "running", error=None)
        pdf_response = await generate_book_pdf(session_id, current_user=None)
        pdf_bytes = getattr(pdf_response, "body", None) or getattr(pdf_response, "content", None)
        if not isinstance(pdf_bytes, (bytes, bytearray)) or len(pdf_bytes) == 0:
            raise ValueError("PDF bytes non disponibili.")
    except Exception as e:
        await update_critique_status_async(session_store, session_id, "failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Errore nel generare il PDF per la critica: {e}")

    # La funzione generate_literary_critique_from_pdf gestisce automaticamente
    # quale API key usare in base al provider configurato (Gemini o OpenAI)
    from app.core.config import get_literary_critic_config, detect_critic_provider, normalize_critic_model_name
    from app.agent.literary_critic import generate_literary_critique_from_pdf
    
    critic_cfg = get_literary_critic_config()
    model_name = normalize_critic_model_name(critic_cfg.get("default_model", "gemini-3-pro-preview"))
    provider = detect_critic_provider(model_name)
    print(f"[REGENERATE_CRITIQUE] Endpoint chiamato per sessione {session_id}", file=sys.stderr)
    print(f"[REGENERATE_CRITIQUE] Configurazione critico: modello={model_name}, provider={provider.upper()}", file=sys.stderr)
    
    api_key = None  # Passiamo None, la funzione leggerà da env appropriato
    try:
        critique = await generate_literary_critique_from_pdf(
            title=session.current_title or "Romanzo",
            author=session.form_data.user_name or "Autore",
            pdf_bytes=bytes(pdf_bytes),
            api_key=api_key,  # None = auto-detect da env
        )
    except Exception as e:
        await update_critique_status_async(session_store, session_id, "failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Errore nella generazione della critica: {e}")

    await update_critique_async(session_store, session_id, critique)
    await update_critique_status_async(session_store, session_id, "completed", error=None)
    return critique

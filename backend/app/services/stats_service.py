"""Service per il calcolo delle statistiche della libreria."""
import math
from datetime import datetime
from collections import defaultdict
from pathlib import Path
from typing import Optional

from app.models import LibraryEntry, LibraryStats, AdvancedStats, ModelComparisonEntry
from app.agent.session_store import get_session_store
from app.services.storage_service import get_storage_service
from app.core.config import get_app_config

# Campi da recuperare per le entry della libreria (ottimizzazione performance)
# Escludiamo campi pesanti come book_chapters e current_outline
LIBRARY_ENTRY_FIELDS = [
    "_id",
    "user_id",
    "session_id",
    "current_title",
    "form_data",
    "question_answers",  # Necessario per SessionData.from_dict()
    "created_at",
    "updated_at",
    # book_chapters RIMOSSO - troppo pesante, usa writing_progress.total_pages
    "writing_progress",
    # current_outline RIMOSSO - usa writing_progress.total_steps per conteggio sezioni
    "literary_critique",
    "cover_image_path",
    "writing_start_time",
    "writing_end_time",
    "critique_status",
    "real_cost_eur",  # Costo reale basato su token effettivi
]

# Cache in memoria per statistiche (TTL: 30 secondi)
_stats_cache = {}
_stats_cache_ttl = 30  # secondi


def get_cached_stats(cache_key: str):
    """Recupera statistiche dalla cache se valide."""
    if cache_key in _stats_cache:
        data, timestamp = _stats_cache[cache_key]
        if (datetime.now() - timestamp).total_seconds() < _stats_cache_ttl:
            return data
        else:
            # Cache scaduta, rimuovi
            del _stats_cache[cache_key]
    return None


def set_cached_stats(cache_key: str, data):
    """Salva statistiche nella cache."""
    _stats_cache[cache_key] = (data, datetime.now())


def invalidate_cache(cache_key: Optional[str] = None):
    """Invalida la cache. Se cache_key è None, invalida tutta la cache."""
    if cache_key:
        if cache_key in _stats_cache:
            del _stats_cache[cache_key]
    else:
        _stats_cache.clear()


def calculate_page_count(content: str) -> int:
    """Calcola il numero di pagine basato sul contenuto (parole/250 arrotondato per eccesso)."""
    if not content:
        return 0
    try:
        app_config = get_app_config()
        words_per_page = app_config.get("validation", {}).get("words_per_page", 250)
        
        # Conta le parole dividendo per spazi
        words = content.split()
        word_count = len(words)
        # Calcola pagine: parole/words_per_page arrotondato per eccesso
        pages = math.ceil(word_count / words_per_page)
        return pages
    except Exception as e:
        print(f"[CALCULATE_PAGE_COUNT] Errore: {e}")
        return 0


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


def llm_model_to_mode(model_name: Optional[str]) -> str:
    """Converte il nome del modello LLM in modalità (Flash, Pro, Ultra)."""
    if not model_name:
        return "Sconosciuto"
    
    model_lower = model_name.lower()
    if "ultra" in model_lower:
        return "Ultra"
    elif "flash" in model_lower:
        return "Flash"
    elif "pro" in model_lower:
        return "Pro"
    else:
        return "Sconosciuto"


def mode_to_llm_models(mode: str) -> list[str]:
    """Converte una modalità in lista di modelli LLM corrispondenti."""
    mode_lower = mode.lower()
    if mode_lower == "flash":
        return ["gemini-2.5-flash", "gemini-3-flash"]
    elif mode_lower == "pro":
        return ["gemini-2.5-pro", "gemini-3-pro"]
    elif mode_lower == "ultra":
        return ["gemini-3-ultra"]
    else:
        return []


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


def session_to_library_entry(session, skip_cost_calculation: bool = False) -> LibraryEntry:
    """Converte una SessionData in una LibraryEntry."""
    import math
    
    status = session.get_status()
    
    # Ottimizzazione: usa valori pre-calcolati da writing_progress
    total_chapters = 0
    completed_chapters = 0
    total_pages = None
    
    if session.writing_progress:
        total_chapters = session.writing_progress.get('total_steps', 0)
        completed_chapters = session.writing_progress.get('completed_chapters_count', 
                                                           session.writing_progress.get('current_step', 0))
        total_pages = session.writing_progress.get('total_pages')
    
    # Fallback per libri che non hanno valori pre-calcolati
    if completed_chapters == 0 and session.book_chapters:
        completed_chapters = len(session.book_chapters)
    
    # Per total_pages, usiamo il valore pre-calcolato
    if total_pages is None and status == "complete" and session.book_chapters:
        chapters_pages = sum(calculate_page_count(ch.get('content', '')) for ch in session.book_chapters)
        cover_pages = 1
        app_config = get_app_config()
        toc_chapters_per_page = app_config.get("validation", {}).get("toc_chapters_per_page", 30)
        toc_pages = math.ceil(len(session.book_chapters) / toc_chapters_per_page)
        total_pages = chapters_pages + cover_pages + toc_pages
    
    # Estrai critique_score
    critique_score = None
    if session.literary_critique and isinstance(session.literary_critique, dict):
        critique_score = session.literary_critique.get('score')
    elif session.literary_critique:
        critique_score = getattr(session.literary_critique, 'score', None)
    
    # Cerca PDF collegato
    pdf_path = None
    pdf_filename = None
    pdf_url = None
    cover_url = None
    
    storage_service = get_storage_service()
    
    if status == "complete":
        # Prova a costruire il path atteso
        date_prefix = session.created_at.strftime("%Y-%m-%d")
        model_abbrev = get_model_abbreviation(session.form_data.llm_model)
        title_sanitized = "".join(c for c in (session.current_title or "Romanzo") if c.isalnum() or c in (' ', '-', '_')).rstrip()
        title_sanitized = title_sanitized.replace(" ", "_")
        if not title_sanitized:
            title_sanitized = f"Libro_{session.session_id[:8]}"
        expected_filename = f"{date_prefix}_{model_abbrev}_{title_sanitized}.pdf"
        
        # Costruisci path senza verificare esistenza (verificato on-demand)
        if storage_service.gcs_enabled:
            pdf_path = f"gs://{storage_service.bucket_name}/books/{expected_filename}"
            pdf_filename = expected_filename
        else:
            # Verifica locale (veloce, no chiamate HTTP)
            local_pdf_path = Path(__file__).parent.parent.parent / "books" / expected_filename
            if local_pdf_path.exists():
                pdf_path = str(local_pdf_path)
                pdf_filename = expected_filename
    
    # Calcola writing_time_minutes
    writing_time_minutes = None
    if session.writing_progress:
        writing_time_minutes = session.writing_progress.get('writing_time_minutes')
    if writing_time_minutes is None and session.writing_start_time and session.writing_end_time:
        delta = session.writing_end_time - session.writing_start_time
        writing_time_minutes = delta.total_seconds() / 60
    
    # Usa il costo reale basato sui token effettivi (None per libri vecchi senza tracking)
    estimated_cost = getattr(session, 'real_cost_eur', None)
    
    # Converti il modello in modalità per la visualizzazione
    original_model = session.form_data.llm_model if session.form_data else None
    mode = llm_model_to_mode(original_model)
    
    return LibraryEntry(
        session_id=session.session_id,
        title=session.current_title or "Romanzo",
        author=session.form_data.user_name or "Autore",
        llm_model=mode,  # Ora contiene la modalità invece del nome del modello
        genre=session.form_data.genre,
        created_at=session.created_at,
        updated_at=session.updated_at,
        status=status,
        total_chapters=total_chapters,
        completed_chapters=completed_chapters,
        total_pages=total_pages,
        critique_score=critique_score,
        critique_status=session.critique_status,
        pdf_path=pdf_path,
        pdf_filename=pdf_filename,
        pdf_url=pdf_url,
        cover_image_path=session.cover_image_path,
        cover_url=cover_url,
        writing_time_minutes=writing_time_minutes,
        estimated_cost=estimated_cost,
    )


def calculate_library_stats(entries: list[LibraryEntry]) -> LibraryStats:
    """Calcola statistiche aggregate dalla lista di LibraryEntry."""
    if not entries:
        return LibraryStats(
            total_books=0,
            completed_books=0,
            in_progress_books=0,
            average_score=None,
            average_pages=0.0,
            average_writing_time_minutes=0.0,
            books_by_model={},
            books_by_genre={},
            score_distribution={},
            average_score_by_model={},
            average_writing_time_by_model={},
            average_time_per_page_by_model={},
            average_pages_by_model={},
            average_cost_by_model={},
            average_cost_per_page_by_model={},
        )
    
    completed = [e for e in entries if e.status == "complete"]
    in_progress = [e for e in entries if e.status in ["draft", "outline", "writing", "paused"]]
    
    # Calcola voto medio solo sui libri completati con voto
    scores = [e.critique_score for e in completed if e.critique_score is not None]
    average_score = sum(scores) / len(scores) if scores else None
    
    # Calcola pagine medie (solo libri completati con pagine)
    pages_list = [e.total_pages for e in completed if e.total_pages is not None and e.total_pages > 0]
    average_pages = sum(pages_list) / len(pages_list) if pages_list else 0.0
    
    # Calcola tempo medio scrittura
    time_list = [e.writing_time_minutes for e in entries if e.writing_time_minutes is not None and e.writing_time_minutes > 0]
    average_writing_time_minutes = sum(time_list) / len(time_list) if time_list else 0.0
    
    # Distribuzione per modalità
    books_by_mode = defaultdict(int)
    for e in entries:
        books_by_mode[e.llm_model] += 1
    
    # Distribuzione per genere
    books_by_genre = defaultdict(int)
    for e in entries:
        if e.genre:
            books_by_genre[e.genre] += 1
    
    # Distribuzione voti (0-2, 2-4, 4-6, 6-8, 8-10)
    score_distribution = defaultdict(int)
    for e in completed:
        if e.critique_score is not None:
            score = e.critique_score
            if score < 2:
                score_distribution["0-2"] += 1
            elif score < 4:
                score_distribution["2-4"] += 1
            elif score < 6:
                score_distribution["4-6"] += 1
            elif score < 8:
                score_distribution["6-8"] += 1
            else:
                score_distribution["8-10"] += 1
    
    # Calcola voto medio per modalità
    mode_scores = defaultdict(list)
    for e in completed:
        if e.critique_score is not None:
            mode_scores[e.llm_model].append(e.critique_score)
    
    average_score_by_model = {}
    for mode, scores_list in mode_scores.items():
        if scores_list:
            average_score_by_model[mode] = round(sum(scores_list) / len(scores_list), 2)
    
    # Calcola tempo medio di generazione per modalità
    mode_times = defaultdict(list)
    for e in completed:
        if e.writing_time_minutes is not None and e.writing_time_minutes > 0:
            mode_times[e.llm_model].append(e.writing_time_minutes)
    
    average_writing_time_by_model = {}
    for mode, times_list in mode_times.items():
        if times_list:
            average_writing_time_by_model[mode] = round(sum(times_list) / len(times_list), 1)
    
    # Calcola tempo medio per pagina per modalità (MEDIA PESATA)
    mode_time_sum_minutes = defaultdict(float)
    mode_pages_sum_for_time = defaultdict(float)
    for e in completed:
        if (
            e.writing_time_minutes is not None
            and e.writing_time_minutes > 0
            and e.total_pages is not None
            and e.total_pages > 0
        ):
            mode_time_sum_minutes[e.llm_model] += float(e.writing_time_minutes)
            mode_pages_sum_for_time[e.llm_model] += float(e.total_pages)

    average_time_per_page_by_model = {}
    for mode in set(list(mode_time_sum_minutes.keys()) + list(mode_pages_sum_for_time.keys())):
        pages_sum = mode_pages_sum_for_time.get(mode, 0.0)
        if pages_sum > 0:
            average_time_per_page_by_model[mode] = round(mode_time_sum_minutes.get(mode, 0.0) / pages_sum, 2)
    
    # Calcola pagine medie per modalità
    mode_pages = defaultdict(list)
    for e in completed:
        if e.total_pages is not None and e.total_pages > 0:
            mode_pages[e.llm_model].append(e.total_pages)
    
    average_pages_by_model = {}
    for mode, pages_list in mode_pages.items():
        if pages_list:
            average_pages_by_model[mode] = round(sum(pages_list) / len(pages_list), 1)
    
    # Calcola costo medio per libro per modalità
    mode_costs = defaultdict(list)
    for e in completed:
        if e.estimated_cost is not None and e.estimated_cost > 0:
            mode_costs[e.llm_model].append(e.estimated_cost)
    
    average_cost_by_model = {}
    for mode, costs_list in mode_costs.items():
        if costs_list:
            average_cost_by_model[mode] = round(sum(costs_list) / len(costs_list), 4)
    
    # Calcola costo medio per pagina per modalità
    mode_costs_per_page = defaultdict(list)
    for e in completed:
        if (e.estimated_cost is not None and e.estimated_cost > 0 and
            e.total_pages is not None and e.total_pages > 0):
            cost_per_page = e.estimated_cost / e.total_pages
            mode_costs_per_page[e.llm_model].append(cost_per_page)
    
    average_cost_per_page_by_model = {}
    for mode, costs_per_page_list in mode_costs_per_page.items():
        if costs_per_page_list:
            average_cost_per_page_by_model[mode] = round(sum(costs_per_page_list) / len(costs_per_page_list), 4)
    
    return LibraryStats(
        total_books=len(entries),
        completed_books=len(completed),
        in_progress_books=len(in_progress),
        average_score=round(average_score, 2) if average_score else None,
        average_pages=round(average_pages, 1),
        average_writing_time_minutes=round(average_writing_time_minutes, 1),
        books_by_model=dict(books_by_mode),
        books_by_genre=dict(books_by_genre),
        score_distribution=dict(score_distribution),
        average_score_by_model=average_score_by_model,
        average_writing_time_by_model=average_writing_time_by_model,
        average_time_per_page_by_model=average_time_per_page_by_model,
        average_pages_by_model=average_pages_by_model,
        average_cost_by_model=average_cost_by_model,
        average_cost_per_page_by_model=average_cost_per_page_by_model,
    )


def calculate_advanced_stats(entries: list[LibraryEntry]) -> AdvancedStats:
    """Calcola statistiche avanzate con analisi temporali e confronto modelli."""
    if not entries:
        return AdvancedStats(
            books_over_time={},
            score_trend_over_time={},
            model_comparison=[],
        )
    
    completed = [e for e in entries if e.status == "complete"]
    
    # Calcola libri creati nel tempo (raggruppati per giorno)
    books_over_time = defaultdict(int)
    for entry in entries:
        date_str = entry.created_at.strftime("%Y-%m-%d")
        books_over_time[date_str] += 1
    
    # Ordina per data
    books_over_time_sorted = dict(sorted(books_over_time.items()))
    
    # Calcola trend voto nel tempo (voto medio per giorno)
    score_by_date = defaultdict(list)
    for entry in completed:
        if entry.critique_score is not None:
            date_str = entry.created_at.strftime("%Y-%m-%d")
            score_by_date[date_str].append(entry.critique_score)
    
    score_trend_over_time = {}
    for date_str, scores in sorted(score_by_date.items()):
        score_trend_over_time[date_str] = round(sum(scores) / len(scores), 2)
    
    # Calcola confronto dettagliato per ogni modalità
    mode_comparison_data = defaultdict(lambda: {
        'total': 0,
        'completed': 0,
        'scores': [],
        'pages': [],
        'costs': [],
        'writing_times': [],
        'time_sum_minutes_for_pages': 0.0,
        'pages_sum_for_time': 0.0,
        'score_distribution': defaultdict(int),
    })
    
    for entry in entries:
        mode = entry.llm_model
        mode_comparison_data[mode]['total'] += 1
        if entry.status == "complete":
            mode_comparison_data[mode]['completed'] += 1
            
            if entry.critique_score is not None:
                mode_comparison_data[mode]['scores'].append(entry.critique_score)
                # Distribuzione voti per modalità
                score = entry.critique_score
                if score < 2:
                    mode_comparison_data[mode]['score_distribution']["0-2"] += 1
                elif score < 4:
                    mode_comparison_data[mode]['score_distribution']["2-4"] += 1
                elif score < 6:
                    mode_comparison_data[mode]['score_distribution']["4-6"] += 1
                elif score < 8:
                    mode_comparison_data[mode]['score_distribution']["6-8"] += 1
                else:
                    mode_comparison_data[mode]['score_distribution']["8-10"] += 1
            
            if entry.total_pages is not None and entry.total_pages > 0:
                mode_comparison_data[mode]['pages'].append(entry.total_pages)
            
            if entry.estimated_cost is not None and entry.estimated_cost > 0:
                mode_comparison_data[mode]['costs'].append(entry.estimated_cost)
            
            if entry.writing_time_minutes is not None and entry.writing_time_minutes > 0:
                mode_comparison_data[mode]['writing_times'].append(entry.writing_time_minutes)
                if entry.total_pages is not None and entry.total_pages > 0:
                    mode_comparison_data[mode]['time_sum_minutes_for_pages'] += float(entry.writing_time_minutes)
                    mode_comparison_data[mode]['pages_sum_for_time'] += float(entry.total_pages)
    
    # Crea lista ModelComparisonEntry
    model_comparison = []
    for mode, data in sorted(mode_comparison_data.items()):
        avg_score = None
        if data['scores']:
            avg_score = round(sum(data['scores']) / len(data['scores']), 2)
        
        avg_pages = 0.0
        if data['pages']:
            avg_pages = round(sum(data['pages']) / len(data['pages']), 1)
        
        avg_cost = None
        if data['costs']:
            avg_cost = round(sum(data['costs']) / len(data['costs']), 1)
        
        avg_writing_time = 0.0
        if data['writing_times']:
            avg_writing_time = round(sum(data['writing_times']) / len(data['writing_times']), 1)
        
        avg_time_per_page = 0.0
        pages_sum = float(data.get('pages_sum_for_time', 0.0) or 0.0)
        if pages_sum > 0:
            avg_time_per_page = round(float(data.get('time_sum_minutes_for_pages', 0.0) or 0.0) / pages_sum, 2)
        
        model_comparison.append(ModelComparisonEntry(
            model=mode,
            total_books=data['total'],
            completed_books=data['completed'],
            average_score=avg_score,
            average_pages=avg_pages,
            average_cost=avg_cost,
            average_writing_time=avg_writing_time,
            average_time_per_page=avg_time_per_page,
            score_range=dict(data['score_distribution']),
        ))
    
    return AdvancedStats(
        books_over_time=books_over_time_sorted,
        score_trend_over_time=score_trend_over_time,
        model_comparison=model_comparison,
    )


def scan_pdf_directory() -> list:
    """Scansiona la directory books/ e restituisce lista di PDF disponibili."""
    from app.models import PdfEntry
    
    books_dir = Path(__file__).parent.parent.parent / "books"
    pdf_entries = []
    
    if not books_dir.exists():
        return pdf_entries
    
    session_store = get_session_store()
    
    for pdf_file in sorted(books_dir.glob("*.pdf"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            filename = pdf_file.name
            stem = pdf_file.stem
            
            parts = stem.split('_', 2)
            created_date = None
            if len(parts) >= 1:
                try:
                    created_date = datetime.strptime(parts[0], "%Y-%m-%d")
                except:
                    pass
            
            session_id = None
            title = None
            author = None
            
            # Prova a cercare nelle sessioni per matchare il PDF
            if hasattr(session_store, '_sessions'):
                for sid, session in session_store._sessions.items():
                    if session.current_title:
                        date_prefix = session.created_at.strftime("%Y-%m-%d")
                        model_abbrev = get_model_abbreviation(session.form_data.llm_model)
                        title_sanitized = "".join(c for c in session.current_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                        title_sanitized = title_sanitized.replace(" ", "_")
                        expected_filename = f"{date_prefix}_{model_abbrev}_{title_sanitized}.pdf"
                        
                        if filename == expected_filename:
                            session_id = sid
                            title = session.current_title
                            author = session.form_data.user_name
                            break
            
            if not title and len(parts) >= 3:
                title = parts[2].replace('_', ' ')
            
            size_bytes = pdf_file.stat().st_size
            
            pdf_entries.append(PdfEntry(
                filename=filename,
                session_id=session_id,
                title=title,
                author=author,
                created_date=created_date,
                size_bytes=size_bytes,
            ))
        except Exception as e:
            print(f"[SCAN PDF] Errore nel processare {pdf_file.name}: {e}")
            continue
    
    return pdf_entries

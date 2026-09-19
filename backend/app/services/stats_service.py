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
    "content_type",
    "current_title",
    "form_data",
    "question_answers",  # Necessario per SessionData.from_dict()
    "created_at",
    "updated_at",
    # book_chapters RIMOSSO - troppo pesante, usa writing_progress.total_pages
    "writing_progress",
    "manga_form_data",
    "manga_pages",
    "manga_progress",
    "manga_cost_eur",
    # current_outline RIMOSSO - usa writing_progress.total_steps per conteggio sezioni
    "literary_critique",
    "cover_image_path",
    "pdf_path",
    "pdf_filename",
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
    elif "gemini-3.1-pro" in model_lower:
        return "g31p"
    elif "gemini-3-pro" in model_lower:
        return "g3p"
    else:
        return model_name.replace("gemini-", "g").replace("-", "").replace("_", "")[:6]


def llm_model_to_mode(model_name: Optional[str], generation_mode: Optional[str] = None) -> str:
    """Converte il nome del modello LLM in modalità (Standard, Ultra)."""
    from app.llm.model_routing import resolve_generation_mode

    resolved = resolve_generation_mode(model_name, generation_mode)
    return "Ultra" if resolved == "ultra" else "Standard"


def mode_to_llm_models(mode: str) -> list[str]:
    """Converte una modalità in lista di modelli LLM corrispondenti (legacy filter)."""
    mode_lower = mode.lower()
    if mode_lower in {"standard", "flash", "pro"}:
        return [
            "gemini-3.8-flash",
            "gemini-3.5-flash-lite",
            "gemini-2.5-flash",
            "gemini-3-flash",
            "gemini-2.5-pro",
            "gemini-3-pro",
            "gemini-3.1-pro",
        ]
    if mode_lower == "ultra":
        return ["gemini-3-ultra"]
    return []


def calculate_generation_cost(session, total_pages: Optional[int]) -> Optional[float]:
    """Delega al cost_service allineato a story bible + ultimi N capitoli."""
    from app.services.cost_service import calculate_generation_cost as _calculate
    return _calculate(session, total_pages)


async def calculate_estimated_time(session_id: str, current_step: int, total_steps: int) -> tuple[Optional[float], Optional[str]]:
    """Stima il tempo rimanente con il modello lineare t(i) = a*i + b."""
    from app.agent.session_store_helpers import get_session_async
    from app.utils.stats_utils import (
        calculate_residual_time_linear,
        get_generation_method,
        get_linear_params_for_method,
    )

    try:
        try:
            current_step = int(current_step)
        except (ValueError, TypeError):
            current_step = 0
        try:
            total_steps = int(total_steps)
        except (ValueError, TypeError):
            total_steps = 0

        if total_steps <= 0 or current_step >= total_steps:
            return None, None

        app_config = get_app_config()
        session = await get_session_async(get_session_store(), session_id)
        current_model = session.form_data.llm_model if session and session.form_data else None
        method = get_generation_method(
            current_model,
            getattr(session.form_data, "generation_mode", None) if session and session.form_data else None,
        )
        a, b = get_linear_params_for_method(method, app_config)
        estimated_seconds = calculate_residual_time_linear(current_step + 1, total_steps, a, b)
        return round(estimated_seconds / 60, 1), None
    except Exception as e:
        print(f"[CALCULATE_ESTIMATED_TIME] Errore nel calcolo stima tempo: {e}")
        return None, None


def _sanitize_title_for_filename(title: Optional[str], fallback_prefix: str, session_id: str) -> str:
    title_sanitized = "".join(c for c in (title or fallback_prefix) if c.isalnum() or c in (" ", "-", "_")).rstrip()
    title_sanitized = title_sanitized.replace(" ", "_")
    if not title_sanitized:
        title_sanitized = f"{fallback_prefix}_{session_id[:8]}"
    return title_sanitized


def _build_book_pdf_info(session, status: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    pdf_path = None
    pdf_filename = None
    pdf_url = None
    storage_service = get_storage_service()

    if status != "complete":
        return pdf_path, pdf_filename, pdf_url

    date_prefix = session.created_at.strftime("%Y-%m-%d")
    model_abbrev = get_model_abbreviation(session.form_data.llm_model)
    title_sanitized = _sanitize_title_for_filename(session.current_title, "Libro", session.session_id)
    expected_filename = f"{date_prefix}_{model_abbrev}_{title_sanitized}.pdf"

    destination = f"books/{expected_filename}"
    if storage_service.exists(destination):
        pdf_path = str(Path(__file__).resolve().parent.parent.parent / "books" / expected_filename)
        pdf_filename = expected_filename

    return pdf_path, pdf_filename, pdf_url


def _parse_optional_datetime(value) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _build_book_library_entry(session, status: str) -> LibraryEntry:
    total_chapters = 0
    completed_chapters = 0
    total_pages = None

    if session.writing_progress:
        total_chapters = session.writing_progress.get("total_steps", 0)
        completed_chapters = session.writing_progress.get(
            "completed_chapters_count",
            session.writing_progress.get("current_step", 0),
        )
        total_pages = session.writing_progress.get("total_pages")

    if completed_chapters == 0 and session.book_chapters:
        completed_chapters = len(session.book_chapters)

    if total_pages is None and status == "complete" and session.book_chapters:
        chapters_pages = sum(calculate_page_count(ch.get("content", "")) for ch in session.book_chapters)
        cover_pages = 1
        app_config = get_app_config()
        toc_chapters_per_page = app_config.get("validation", {}).get("toc_chapters_per_page", 30)
        toc_pages = math.ceil(len(session.book_chapters) / toc_chapters_per_page)
        total_pages = chapters_pages + cover_pages + toc_pages

    critique_score = None
    if session.literary_critique and isinstance(session.literary_critique, dict):
        critique_score = session.literary_critique.get("score")
    elif session.literary_critique:
        critique_score = getattr(session.literary_critique, "score", None)

    pdf_path, pdf_filename, pdf_url = _build_book_pdf_info(session, status)

    writing_time_minutes = None
    if session.writing_progress:
        writing_time_minutes = session.writing_progress.get("writing_time_minutes")
    if writing_time_minutes is None and session.writing_start_time and session.writing_end_time:
        delta = session.writing_end_time - session.writing_start_time
        writing_time_minutes = delta.total_seconds() / 60

    estimated_cost = getattr(session, "real_cost_eur", None)
    original_model = session.form_data.llm_model if session.form_data else None
    mode = llm_model_to_mode(
        original_model,
        getattr(session.form_data, "generation_mode", None) if session.form_data else None,
    )

    return LibraryEntry(
        session_id=session.session_id,
        content_type="book",
        title=session.current_title or "Romanzo",
        author=session.form_data.user_name or "Autore",
        llm_model=mode,
        genre=session.form_data.genre,
        manga_type=None,
        created_at=session.created_at,
        updated_at=session.updated_at,
        status=status,
        total_chapters=total_chapters,
        completed_chapters=completed_chapters,
        completed_pages=None,
        total_pages=total_pages,
        critique_score=critique_score,
        critique_status=session.critique_status,
        pdf_path=pdf_path,
        pdf_filename=pdf_filename,
        pdf_url=pdf_url,
        cover_image_path=session.cover_image_path,
        cover_url=None,
        writing_time_minutes=writing_time_minutes,
        estimated_cost=estimated_cost,
    )


def _build_manga_library_entry(session, status: str) -> LibraryEntry:
    manga_form_data = getattr(session, "manga_form_data", None) or {}
    manga_progress = getattr(session, "manga_progress", None) or {}
    manga_plan = getattr(session, "manga_plan", None) or {}
    manga_pages = getattr(session, "manga_pages", None) or []
    sorted_pages = sorted(manga_pages, key=lambda page: int(page.get("page_number", 0) or 0))
    planned_pages = manga_plan.get("page_plans", []) if isinstance(manga_plan, dict) else []

    total_pages = int(
        len(planned_pages)
        or manga_progress.get("planned_total_pages")
        or manga_progress.get("total_steps")
        or len(manga_pages)
        or manga_form_data.get("max_pages")
        or get_app_config().get("manga_generation", {}).get("page_count", 10)
        or 10
    )
    completed_pages = len(manga_pages)
    current_title = getattr(session, "current_title", None) or manga_form_data.get("title") or "Mini manga"
    manga_type = manga_form_data.get("manga_type")

    writing_time_minutes = None
    started_at = _parse_optional_datetime(manga_progress.get("started_at"))
    completed_at = _parse_optional_datetime(manga_progress.get("completed_at"))
    if started_at and completed_at:
        writing_time_minutes = (completed_at - started_at).total_seconds() / 60

    original_model = session.form_data.llm_model if session.form_data else None
    mode = llm_model_to_mode(
        original_model,
        getattr(session.form_data, "generation_mode", None) if session.form_data else None,
    )
    estimated_cost = getattr(session, "manga_cost_eur", None) or manga_progress.get("estimated_cost")
    cover_url = None
    if session.cover_image_path:
        cover_url = f"/api/library/cover/{session.session_id}"
    elif sorted_pages and sorted_pages[0].get("image_path"):
        cover_url = f"/api/manga/{session.session_id}/pages/{int(sorted_pages[0].get('page_number', 1) or 1)}/image"

    return LibraryEntry(
        session_id=session.session_id,
        content_type="manga",
        title=current_title,
        author="NarrAI",
        llm_model=mode,
        genre="Manga",
        manga_type=manga_type,
        created_at=session.created_at,
        updated_at=session.updated_at,
        status=status,
        total_chapters=0,
        completed_chapters=0,
        completed_pages=completed_pages,
        total_pages=total_pages,
        critique_score=None,
        critique_status=None,
        pdf_path=getattr(session, "pdf_path", None),
        pdf_filename=getattr(session, "pdf_filename", None),
        pdf_url=None,
        cover_image_path=session.cover_image_path,
        cover_url=cover_url,
        writing_time_minutes=writing_time_minutes,
        estimated_cost=estimated_cost,
    )


def session_to_library_entry(session, skip_cost_calculation: bool = False) -> LibraryEntry:
    """Converte una SessionData in una LibraryEntry."""
    _ = skip_cost_calculation
    content_type = getattr(session, "content_type", "book")
    status = session.get_status()

    if content_type == "manga":
        return _build_manga_library_entry(session, status)
    return _build_book_library_entry(session, status)


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

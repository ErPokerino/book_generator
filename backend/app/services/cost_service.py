"""Servizio per il calcolo dei costi di generazione."""
import math
from typing import Optional
from app.agent.session_store import SessionData
from app.core.config import (
    get_tokens_per_page,
    get_model_pricing,
    get_exchange_rate_usd_to_eur,
    get_token_estimates,
    get_app_config,
)


def calculate_generation_cost(
    session: SessionData,
    total_pages: Optional[int],
) -> Optional[float]:
    """
    Calcola il costo stimato di generazione dei capitoli del libro.
    
    Considera solo il costo di generazione dei capitoli (processo autoregressivo),
    escludendo bozza, outline, critica e copertina.
    
    Args:
        session: SessionData object
        total_pages: Numero totale di pagine del libro (None se non disponibile)
    
    Returns:
        Costo stimato in EUR, o None se non calcolabile
    """
    # Calcola solo se il libro è completo e abbiamo total_pages
    if not total_pages or total_pages <= 0:
        return None
    
    try:
        # Recupera configurazione costi
        tokens_per_page = get_tokens_per_page()
        model_name = session.form_data.llm_model if session.form_data else None
        if not model_name:
            return None
        
        # Mappa il nome del modello al nome API
        from app.agent.writer_generator import map_model_name
        gemini_model = map_model_name(model_name)
        
        # Recupera pricing del modello
        pricing = get_model_pricing(gemini_model)
        input_cost_per_million = pricing["input_cost_per_million"]
        output_cost_per_million = pricing["output_cost_per_million"]
        
        # Recupera stime token
        token_estimates = get_token_estimates()
        
        # Calcola pagine capitoli (escludendo copertina e TOC)
        chapters_pages = total_pages - 1  # -1 per copertina
        app_config = get_app_config()
        toc_chapters_per_page = app_config.get("validation", {}).get("toc_chapters_per_page", 30)
        completed_chapters = len(session.book_chapters) if session.book_chapters else 0
        toc_pages = math.ceil(completed_chapters / toc_chapters_per_page) if completed_chapters > 0 else 0
        chapters_pages = chapters_pages - toc_pages  # Rimuovi anche TOC
        
        if chapters_pages <= 0:
            chapters_pages = max(1, total_pages - 1)  # Fallback minimo
        
        if completed_chapters == 0:
            print(f"[COST CALCULATION] Nessun capitolo completato per sessione {session.session_id}")
            return None  # Nessun capitolo, non calcolabile
        
        print(f"[COST CALCULATION] Calcolo costo per: modello={gemini_model}, capitoli={completed_chapters}, pagine={chapters_pages}")
        
        # Calcolo costo Capitoli (processo autoregressivo)
        num_chapters = completed_chapters
        context_base = token_estimates.get("chapter", {}).get("context_base", 8000)
        avg_pages_per_chapter = chapters_pages / num_chapters if num_chapters > 0 else chapters_pages
        
        # Input totale per tutti i capitoli
        chapters_input = num_chapters * context_base
        
        for i in range(1, num_chapters + 1):
            previous_pages = (i - 1) * avg_pages_per_chapter
            chapters_input += previous_pages * tokens_per_page
        
        # Output totale
        chapters_output = chapters_pages * tokens_per_page
        
        # Calcola costo
        chapters_cost_usd = (
            (chapters_input * input_cost_per_million / 1_000_000) +
            (chapters_output * output_cost_per_million / 1_000_000)
        )
        
        # Converti USD -> EUR
        exchange_rate = get_exchange_rate_usd_to_eur()
        total_cost_eur = chapters_cost_usd * exchange_rate
        
        print(f"[COST CALCULATION] Risultato: ${chapters_cost_usd:.6f} USD = €{total_cost_eur:.4f} EUR")
        
        return round(total_cost_eur, 4)
        
    except Exception as e:
        print(f"[COST CALCULATION] Errore nel calcolo costo: {e}")
        import traceback
        traceback.print_exc()
        return None

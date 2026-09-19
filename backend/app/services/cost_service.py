"""Servizio per il calcolo dei costi di generazione."""
import math
from typing import Optional, Dict, Any
from app.agent.session_store import SessionData
from app.core.config import (
    get_tokens_per_page,
    get_model_pricing,
    get_exchange_rate_usd_to_eur,
    get_token_estimates,
    get_app_config,
)
from app.utils.token_tracker import calculate_total_cost


def calculate_generation_cost(
    session: SessionData,
    total_pages: Optional[int],
) -> Optional[float]:
    """
    Stima il costo di generazione dei capitoli.

    Allineato alla pipeline live: prompt writer + story bible euristica
    + ultimi N capitoli integrali (non tutto il testo precedente).
    Ultra conta 2 chiamate writer per capitolo. Review/revise Pro-Ultra
    non è incluso: in UI preferire `real_cost_eur` quando disponibile.
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
        from app.llm.model_routing import map_book_model_name
        gemini_model = map_book_model_name(model_name)
        
        # Recupera pricing del modello
        pricing = get_model_pricing(gemini_model)
        input_cost_per_million = pricing["input_cost_per_million"]
        output_cost_per_million = pricing["output_cost_per_million"]
        
        token_estimates = get_token_estimates()
        chapter_estimates = token_estimates.get("chapter", {})

        chapters_pages = total_pages - 1
        app_config = get_app_config()
        toc_chapters_per_page = app_config.get("validation", {}).get("toc_chapters_per_page", 30)
        completed_chapters = len(session.book_chapters) if session.book_chapters else 0
        toc_pages = math.ceil(completed_chapters / toc_chapters_per_page) if completed_chapters > 0 else 0
        chapters_pages = chapters_pages - toc_pages

        if chapters_pages <= 0:
            chapters_pages = max(1, total_pages - 1)

        if completed_chapters == 0:
            print(f"[COST CALCULATION] Nessun capitolo completato per sessione {session.session_id}")
            return None

        print(f"[COST CALCULATION] Calcolo costo per: modello={gemini_model}, capitoli={completed_chapters}, pagine={chapters_pages}")

        num_chapters = completed_chapters
        writer_prompt_tokens = int(chapter_estimates.get("writer_prompt_tokens", 2800))
        story_bible_tokens = int(chapter_estimates.get("story_bible_tokens", 3400))
        recent_full_chapters = int(chapter_estimates.get("recent_full_chapters", 1))
        fixed_input = writer_prompt_tokens + story_bible_tokens
        avg_pages_per_chapter = chapters_pages / num_chapters if num_chapters > 0 else chapters_pages
        avg_chapter_tokens = avg_pages_per_chapter * tokens_per_page

        from app.llm.model_routing import get_writer_split_calls
        split_calls = get_writer_split_calls(
            model_name,
            getattr(session.form_data, "generation_mode", None) if session.form_data else None,
        )

        chapters_input = 0.0
        for i in range(num_chapters):
            full_prev = min(i, recent_full_chapters)
            chapters_input += (fixed_input + full_prev * avg_chapter_tokens) * split_calls

        chapters_output = chapters_pages * tokens_per_page
        
        # Calcola costo
        chapters_cost_usd = (
            (chapters_input * input_cost_per_million / 1_000_000) +
            (chapters_output * output_cost_per_million / 1_000_000)
        )
        
        # Converti USD -> EUR
        exchange_rate = get_exchange_rate_usd_to_eur()
        total_cost_eur = chapters_cost_usd * exchange_rate
        
        print(f"[COST CALCULATION] Risultato stimato: ${chapters_cost_usd:.6f} USD = €{total_cost_eur:.4f} EUR")
        
        return round(total_cost_eur, 4)
        
    except Exception as e:
        print(f"[COST CALCULATION] Errore nel calcolo costo: {e}")
        import traceback
        traceback.print_exc()
        return None


def calculate_real_generation_cost(session: SessionData) -> Optional[float]:
    """
    Calcola il costo REALE di generazione basandosi sui token effettivamente usati.
    
    Questo metodo usa i dati raccolti in session.token_usage per calcolare
    il costo effettivo in EUR per tutte le fasi di generazione.
    
    Args:
        session: SessionData object con token_usage popolato
    
    Returns:
        Costo reale in EUR, o None se token_usage non disponibile
    """
    # Verifica che token_usage esista e abbia dati
    token_usage = getattr(session, 'token_usage', None)
    if not token_usage:
        print(f"[REAL COST CALCULATION] Nessun token_usage per sessione {session.session_id}")
        return None
    
    # Verifica che ci siano token registrati
    total = token_usage.get("total", {})
    total_input = total.get("input_tokens", 0) or 0
    total_output = total.get("output_tokens", 0) or 0
    
    if total_input == 0 and total_output == 0:
        print(f"[REAL COST CALCULATION] Nessun token registrato per sessione {session.session_id}")
        return None
    
    try:
        # Usa la funzione di calcolo dal token_tracker
        real_cost = calculate_total_cost(token_usage)
        
        print(f"[REAL COST CALCULATION] Sessione {session.session_id}:")
        print(f"  Token totali: {total_input:,} input + {total_output:,} output = {total_input + total_output:,}")
        print(f"  Costo reale: €{real_cost:.6f} EUR")
        
        # Log dettaglio per fase
        for phase in ["questions", "draft", "outline", "chapters", "critique"]:
            phase_data = token_usage.get(phase, {})
            phase_in = phase_data.get("input_tokens", 0) or 0
            phase_out = phase_data.get("output_tokens", 0) or 0
            if phase_in > 0 or phase_out > 0:
                calls = phase_data.get("calls", 1)
                model = phase_data.get("model", "N/A")
                calls_str = f" ({calls} calls)" if calls > 1 else ""
                print(f"  {phase.capitalize()}{calls_str}: {phase_in:,} in + {phase_out:,} out [{model}]")
        
        return round(real_cost, 6)
        
    except Exception as e:
        print(f"[REAL COST CALCULATION] Errore nel calcolo costo reale: {e}")
        import traceback
        traceback.print_exc()
        return None


def get_cost_summary(session: SessionData, total_pages: Optional[int] = None) -> Dict[str, Any]:
    """
    Restituisce un riepilogo completo dei costi (stimati e reali).
    
    Args:
        session: SessionData object
        total_pages: Numero totale di pagine (per stima)
    
    Returns:
        Dict con estimated_cost, real_cost, token_usage summary
    """
    estimated_cost = calculate_generation_cost(session, total_pages)
    real_cost = calculate_real_generation_cost(session)
    
    token_usage = getattr(session, 'token_usage', None)
    total_tokens = None
    if token_usage:
        total = token_usage.get("total", {})
        total_tokens = {
            "input": total.get("input_tokens", 0) or 0,
            "output": total.get("output_tokens", 0) or 0,
            "total": (total.get("input_tokens", 0) or 0) + (total.get("output_tokens", 0) or 0),
        }
    
    return {
        "estimated_cost_eur": estimated_cost,
        "real_cost_eur": real_cost,
        "token_usage": total_tokens,
        "phases": {
            phase: {
                "input_tokens": (token_usage.get(phase, {}).get("input_tokens", 0) or 0) if token_usage else 0,
                "output_tokens": (token_usage.get(phase, {}).get("output_tokens", 0) or 0) if token_usage else 0,
                "model": token_usage.get(phase, {}).get("model") if token_usage else None,
                "calls": token_usage.get(phase, {}).get("calls", 1) if token_usage and phase in ["draft", "chapters"] else None,
            }
            for phase in ["questions", "draft", "outline", "chapters", "critique"]
        } if token_usage else None,
    }

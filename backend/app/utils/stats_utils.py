"""Utility functions for statistics and analytics."""
from typing import Optional


def get_generation_method(model_name: str) -> str:
    """
    Determina il metodo di generazione in base al modello.
    
    Args:
        model_name: Nome del modello (es. "gemini-3-ultra", "gemini-3-flash")
    
    Returns:
        'flash', 'pro', 'ultra', o 'default'
    """
    if not model_name:
        return "default"
    model_lower = model_name.lower()
    if "ultra" in model_lower:
        return "ultra"
    elif "pro" in model_lower:
        return "pro"
    elif "flash" in model_lower:
        return "flash"
    return "default"


def estimate_linear_params_from_history(sessions: list, method: str) -> Optional[tuple[float, float]]:
    """
    Stima i parametri a e b del modello lineare t(i) = a*i + b dai dati storici.
    
    Args:
        sessions: Lista di sessioni con chapter_timings
        method: Metodo di generazione ('flash', 'pro', 'ultra')
    
    Returns:
        Tupla (a, b) o None se non ci sono abbastanza dati
    """
    
    # Raccogli tutti i punti (indice_capitolo, tempo_misurato)
    data_points = []
    
    for session in sessions:
        if not session.chapter_timings or len(session.chapter_timings) == 0:
            continue
        
        # Verifica che il metodo della sessione corrisponda
        session_method = get_generation_method(session.form_data.llm_model if session.form_data else None)
        if session_method != method:
            continue
        
        # Aggiungi coppie (indice_capitolo, tempo)
        for idx, timing in enumerate(session.chapter_timings, start=1):
            data_points.append((idx, timing))
    
    if len(data_points) < 2:
        # Serve almeno 2 punti per regressione lineare
        return None
    
    # Regressione lineare: y = ax + b
    # Formula minimi quadrati:
    # a = (n*Σ(xy) - Σ(x)*Σ(y)) / (n*Σ(x²) - (Σ(x))²)
    # b = (Σ(y) - a*Σ(x)) / n
    
    n = len(data_points)
    sum_x = sum(x for x, y in data_points)
    sum_y = sum(y for x, y in data_points)
    sum_xy = sum(x * y for x, y in data_points)
    sum_x2 = sum(x * x for x, y in data_points)
    
    denominator = n * sum_x2 - sum_x * sum_x
    if abs(denominator) < 1e-10:  # Evita divisione per zero
        return None
    
    a = (n * sum_xy - sum_x * sum_y) / denominator
    b = (sum_y - a * sum_x) / n
    
    # Verifica che i parametri siano ragionevoli
    if a < 0 or b < 0:
        return None
    
    return (a, b)


def get_linear_params_for_method(method: str, app_config: dict) -> tuple[float, float]:
    """
    Ottiene i parametri a, b del modello lineare dal config per il metodo specificato.
    
    Args:
        method: Metodo di generazione ('flash', 'pro', 'ultra', 'default')
        app_config: Dizionario di configurazione dell'applicazione
    
    Returns:
        Tupla (a, b) dove t(i) = a*i + b rappresenta il tempo per il capitolo i
    """
    time_est = app_config.get("time_estimation", {})
    linear_params = time_est.get("linear_model_params", {})
    params = linear_params.get(method, linear_params.get("default", {}))
    a = params.get("a", 0.2)
    b = params.get("b", 40.0)
    return (a, b)


def calculate_residual_time_linear(k: int, N: int, a: float, b: float) -> float:
    """
    Calcola il tempo residuo stimato con modello lineare.
    
    Il tempo per il capitolo i è t(i) = a*i + b.
    Il tempo residuo è la somma: sum_{i=k}^{N} (a*i + b)
    
    Args:
        k: Indice del prossimo capitolo da generare (1-based)
        N: Numero totale di capitoli
        a: Coefficiente angolare del modello lineare (secondi/capitolo)
        b: Intercetta del modello lineare (secondi)
    
    Returns:
        Tempo residuo stimato in secondi
    """
    if k > N:
        return 0.0
    
    # Somma aritmetica: sum(a*i + b) per i da k a N
    # = a * sum(i) + b * (N - k + 1)
    # = a * (k + k+1 + ... + N) + b * (N - k + 1)
    # = a * (N - k + 1) * (k + N) / 2 + b * (N - k + 1)
    chapters_remaining = N - k + 1
    sum_indices = chapters_remaining * (k + N) / 2
    return a * sum_indices + b * chapters_remaining

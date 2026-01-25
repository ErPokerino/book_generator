"""
Utility per il tracciamento dei token e calcolo dei costi di generazione.

Estrae token usage dalle risposte LangChain/Gemini e calcola i costi
basandosi sui prezzi configurati in app.yaml.
"""
from typing import Any, Dict, Optional
from app.core.config import get_model_pricing, get_exchange_rate_usd_to_eur


def extract_token_usage(response: Any) -> Dict[str, int]:
    """
    Estrae input_tokens e output_tokens dalla risposta LangChain.
    
    Supporta:
    - ChatGoogleGenerativeAI (Gemini): response.usage_metadata
    - ChatOpenAI: response.response_metadata["token_usage"]
    
    Args:
        response: Risposta del modello LLM (AIMessage)
    
    Returns:
        Dict con "input_tokens" e "output_tokens"
    """
    # Default se non troviamo token usage
    result = {"input_tokens": 0, "output_tokens": 0}
    
    if response is None:
        return result
    
    # Metodo 1: usage_metadata (LangChain ChatGoogleGenerativeAI per Gemini)
    usage_metadata = getattr(response, 'usage_metadata', None)
    if usage_metadata:
        # usage_metadata può essere un dict o un oggetto
        if isinstance(usage_metadata, dict):
            result["input_tokens"] = usage_metadata.get("input_tokens", 0) or 0
            result["output_tokens"] = usage_metadata.get("output_tokens", 0) or 0
        else:
            result["input_tokens"] = getattr(usage_metadata, 'input_tokens', 0) or 0
            result["output_tokens"] = getattr(usage_metadata, 'output_tokens', 0) or 0
        return result
    
    # Metodo 2: response_metadata (LangChain ChatOpenAI)
    response_metadata = getattr(response, 'response_metadata', None)
    if response_metadata and isinstance(response_metadata, dict):
        token_usage = response_metadata.get("token_usage", {})
        if token_usage:
            result["input_tokens"] = token_usage.get("prompt_tokens", 0) or 0
            result["output_tokens"] = token_usage.get("completion_tokens", 0) or 0
            return result
    
    return result


def calculate_cost_from_tokens(
    input_tokens: int,
    output_tokens: int,
    model_name: str,
    currency: str = "EUR",
) -> float:
    """
    Calcola il costo in EUR (o altra valuta) basandosi sui token e prezzi del modello.
    
    Args:
        input_tokens: Numero di token in input
        output_tokens: Numero di token in output
        model_name: Nome del modello (es: "gemini-3-pro-preview")
        currency: Valuta di output (default: "EUR")
    
    Returns:
        Costo calcolato nella valuta specificata
    """
    # Ottieni pricing del modello
    pricing = get_model_pricing(model_name)
    input_cost_per_million = pricing["input_cost_per_million"]
    output_cost_per_million = pricing["output_cost_per_million"]
    
    # Calcola costo in USD
    cost_usd = (
        (input_tokens * input_cost_per_million / 1_000_000) +
        (output_tokens * output_cost_per_million / 1_000_000)
    )
    
    # Converti in EUR se richiesto
    if currency.upper() == "EUR":
        exchange_rate = get_exchange_rate_usd_to_eur()
        return cost_usd * exchange_rate
    
    return cost_usd


def calculate_total_cost(token_usage: Dict[str, Any]) -> float:
    """
    Calcola il costo totale da un dict token_usage completo.
    
    Il token_usage deve contenere le chiavi per fase (questions, draft, outline, chapters, critique)
    e ogni fase deve avere input_tokens, output_tokens e model.
    
    Args:
        token_usage: Dict con token usage per fase
    
    Returns:
        Costo totale in EUR
    """
    if not token_usage:
        return 0.0
    
    total_cost = 0.0
    
    # Fasi da considerare
    phases = ["questions", "draft", "outline", "chapters", "critique"]
    
    for phase in phases:
        phase_data = token_usage.get(phase, {})
        input_tokens = phase_data.get("input_tokens", 0) or 0
        output_tokens = phase_data.get("output_tokens", 0) or 0
        model = phase_data.get("model")
        
        if input_tokens > 0 or output_tokens > 0:
            if model:
                phase_cost = calculate_cost_from_tokens(input_tokens, output_tokens, model)
            else:
                # Fallback a modello default se non specificato
                phase_cost = calculate_cost_from_tokens(input_tokens, output_tokens, "gemini-3-pro-preview")
            total_cost += phase_cost
    
    return round(total_cost, 6)


def format_token_usage_summary(token_usage: Dict[str, Any]) -> str:
    """
    Formatta un riepilogo leggibile del token usage.
    
    Args:
        token_usage: Dict con token usage per fase
    
    Returns:
        Stringa con riepilogo formattato
    """
    if not token_usage:
        return "Nessun dato token disponibile"
    
    lines = ["Token Usage Summary:"]
    
    total = token_usage.get("total", {})
    total_input = total.get("input_tokens", 0) or 0
    total_output = total.get("output_tokens", 0) or 0
    
    lines.append(f"  Total: {total_input:,} input + {total_output:,} output = {total_input + total_output:,} tokens")
    lines.append("")
    
    phases = ["questions", "draft", "outline", "chapters", "critique"]
    for phase in phases:
        phase_data = token_usage.get(phase, {})
        input_t = phase_data.get("input_tokens", 0) or 0
        output_t = phase_data.get("output_tokens", 0) or 0
        model = phase_data.get("model", "N/A")
        calls = phase_data.get("calls", 1)
        
        if input_t > 0 or output_t > 0:
            calls_str = f" ({calls} calls)" if calls > 1 else ""
            lines.append(f"  {phase.capitalize()}{calls_str}: {input_t:,} in + {output_t:,} out [{model}]")
    
    return "\n".join(lines)

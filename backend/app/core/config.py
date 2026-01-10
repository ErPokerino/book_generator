import os
import yaml
from pathlib import Path
from typing import Any, TypedDict, Optional, Literal
from app.models import ConfigResponse, FieldConfig, FieldOption


class LiteraryCriticConfig(TypedDict, total=False):
    default_model: str
    fallback_model: str
    temperature: float
    max_retries: int
    response_mime_type: str
    system_prompt: str
    user_prompt: str


def load_config() -> ConfigResponse:
    """Carica la configurazione dal file YAML."""
    # In locale: __file__ = backend/app/core/config.py -> root = .parent.parent.parent.parent
    # Nel container: __file__ = /app/app/core/config.py -> root = .parent.parent.parent
    # Prova prima il path locale, poi quello del container
    base_path = Path(__file__).parent.parent.parent
    config_path = base_path / "config" / "inputs.yaml"
    
    # Se non esiste, prova un livello sopra (per ambiente locale)
    if not config_path.exists():
        base_path = base_path.parent
        config_path = base_path / "config" / "inputs.yaml"
    
    if not config_path.exists():
        raise FileNotFoundError(f"File di configurazione non trovato: {config_path}")
    
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    
    # Converte i dati YAML in ConfigResponse
    fields = []
    for field_data in data.get("fields", []):
        options = None
        if field_data.get("type") == "select" and "options" in field_data:
            options = [
                FieldOption(value=opt if isinstance(opt, str) else opt["value"], 
                          label=opt.get("label") if isinstance(opt, dict) else None)
                for opt in field_data["options"]
            ]
        
        mode_availability = field_data.get("mode_availability")
        
        field = FieldConfig(
            id=field_data["id"],
            label=field_data["label"],
            type=field_data["type"],
            required=field_data.get("required", False),
            options=options,
            placeholder=field_data.get("placeholder"),
            description=field_data.get("description"),
            mode_availability=mode_availability,
        )
        fields.append(field)
    
    return ConfigResponse(
        llm_models=data.get("llm_models", []),
        fields=fields,
    )


# Cache della configurazione caricata all'avvio
_config: ConfigResponse | None = None


def get_config() -> ConfigResponse:
    """Restituisce la configurazione (cached)."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reload_config() -> ConfigResponse:
    """Ricarica la configurazione (utile per sviluppo)."""
    global _config
    _config = load_config()
    return _config


# --- Literary critic config ---
_critic_config: Optional[LiteraryCriticConfig] = None


def load_literary_critic_config() -> LiteraryCriticConfig:
    """Carica la configurazione del critico letterario dal file YAML."""
    # In locale: __file__ = backend/app/core/config.py -> root = .parent.parent.parent.parent
    # Nel container: __file__ = /app/app/core/config.py -> root = .parent.parent.parent
    # Prova prima il path locale, poi quello del container
    base_path = Path(__file__).parent.parent.parent
    config_path = base_path / "config" / "literary_critic.yaml"
    
    # Se non esiste, prova un livello sopra (per ambiente locale)
    if not config_path.exists():
        base_path = base_path.parent
        config_path = base_path / "config" / "literary_critic.yaml"
    
    if not config_path.exists():
        raise FileNotFoundError(f"File di configurazione non trovato: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    # Normalizza valori base e default minimi
    return {
        "default_model": data.get("default_model", "gemini-3-pro-preview"),
        "fallback_model": data.get("fallback_model", "gemini-3-flash-preview"),
        "temperature": float(data.get("temperature", 0.3)),
        "max_retries": int(data.get("max_retries", 2)),
        "response_mime_type": data.get("response_mime_type"),
        "system_prompt": data.get("system_prompt", ""),
        "user_prompt": data.get("user_prompt", ""),
    }


def get_literary_critic_config() -> LiteraryCriticConfig:
    """Restituisce la configurazione del critico letterario (cached)."""
    global _critic_config
    if _critic_config is None:
        _critic_config = load_literary_critic_config()
    return _critic_config


def reload_literary_critic_config() -> LiteraryCriticConfig:
    """Ricarica la configurazione del critico letterario (utile per sviluppo)."""
    global _critic_config
    _critic_config = load_literary_critic_config()
    return _critic_config


# --- App config ---
class AppConfig(TypedDict, total=False):
    api_timeouts: dict[str, int]
    retry: dict[str, Any]
    validation: dict[str, Any]
    frontend: dict[str, int]
    time_estimation: dict[str, Any]
    cover_generation: dict[str, Any]
    cost_estimation: dict[str, Any]


_app_config: Optional[AppConfig] = None


def load_app_config() -> AppConfig:
    """Carica la configurazione dell'applicazione dal file YAML."""
    # In locale: __file__ = backend/app/core/config.py -> root = .parent.parent.parent.parent
    # Nel container: __file__ = /app/app/core/config.py -> root = .parent.parent.parent
    # Prova prima il path locale, poi quello del container
    base_path = Path(__file__).parent.parent.parent
    config_path = base_path / "config" / "app.yaml"
    
    # Se non esiste, prova un livello sopra (per ambiente locale)
    if not config_path.exists():
        base_path = base_path.parent
        config_path = base_path / "config" / "app.yaml"
    
    if not config_path.exists():
        # Valori di default se il file non esiste
        print(f"[CONFIG] File app.yaml non trovato, uso valori di default")
        return {
            "api_timeouts": {
                "submit_form": 30000,
                "generate_questions": 60000,
                "submit_answers": 30000,
                "generate_draft": 120000,
                "generate_outline": 120000,
                "download_pdf": 300000,
            },
            "retry": {
                "chapter_generation": {
                    "max_retries": 2,
                    "min_chapter_length": 50,
                }
            },
            "validation": {
                "min_chapter_length": 50,
                "words_per_page": 250,
                "toc_chapters_per_page": 30,
            },
            "frontend": {
                "polling_interval": 2000,
                "polling_interval_critique": 5000,
            },
            "time_estimation": {
                "min_chapters_for_reliable_avg": 3,
                "use_session_avg_if_available": True,
            },
            "temperature": {},
            "cost_estimation": {},
        }
    
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    
    # Normalizza e valida i valori
    return {
        "api_timeouts": data.get("api_timeouts", {}),
        "retry": data.get("retry", {}),
        "validation": data.get("validation", {}),
        "frontend": data.get("frontend", {}),
        "time_estimation": data.get("time_estimation", {}),
        "cover_generation": data.get("cover_generation", {}),
        "temperature": data.get("temperature", {}),
        "cost_estimation": data.get("cost_estimation", {}),
    }


def get_app_config() -> AppConfig:
    """Restituisce la configurazione dell'applicazione (cached)."""
    global _app_config
    if _app_config is None:
        _app_config = load_app_config()
    return _app_config


def reload_app_config() -> AppConfig:
    """Ricarica la configurazione dell'applicazione (utile per sviluppo)."""
    global _app_config
    _app_config = load_app_config()
    return _app_config


def get_temperature_for_agent(agent_name: str, model_name: str) -> float:
    """
    Determina la temperatura per un agente basandosi su:
    1. Configurazione esplicita in app.yaml per l'agente
    2. Regola basata su versione modello (2.5 → 0.0, 3.0 → 1.0)
    
    Args:
        agent_name: Nome dell'agente (es: "writer_generator", "draft_generator", etc.)
        model_name: Nome del modello Gemini (es: "gemini-2.5-flash", "gemini-3-pro-preview")
    
    Returns:
        Temperatura da utilizzare (float tra 0.0 e 1.0)
    """
    app_config = get_app_config()
    # Gestisce il caso in cui temperature sia None o non esista
    temperature_config = app_config.get("temperature")
    if temperature_config is None or not isinstance(temperature_config, dict):
        temperature_config = {}
    agent_temps = temperature_config.get("agents", {})
    
    # Se agent_temps non è un dict, usa un dict vuoto
    if not isinstance(agent_temps, dict):
        agent_temps = {}
    
    # Se c'è configurazione esplicita per l'agente, usala
    if agent_name in agent_temps:
        return float(agent_temps[agent_name])
    
    # Altrimenti, determina dalla versione modello
    # Gestisce il caso in cui model_name sia None
    if model_name is None:
        model_name = ""
    model_lower = model_name.lower()
    if "2.5" in model_lower:
        return 0.0
    elif "3" in model_lower:
        return 1.0
    else:
        # Default conservativo se non si riesce a determinare la versione
        return 0.0


def get_tokens_per_page() -> int:
    """Restituisce il numero di token stimati per pagina."""
    app_config = get_app_config()
    cost_config = app_config.get("cost_estimation", {})
    return int(cost_config.get("tokens_per_page", 350))


def get_model_pricing(model_name: str) -> dict[str, float]:
    """
    Restituisce i costi per input/output per il modello specificato.
    
    Args:
        model_name: Nome del modello (es: "gemini-2.5-flash", "gemini-3-pro-preview", "gpt-5.2")
    
    Returns:
        Dizionario con 'input_cost_per_million' e 'output_cost_per_million' in USD
    """
    app_config = get_app_config()
    cost_config = app_config.get("cost_estimation", {})
    model_costs = cost_config.get("model_costs", {})
    
    # Normalizza il nome del modello per il lookup
    model_normalized = model_name.lower().replace("_", "-")
    
    # Prova prima il nome esatto, poi varianti comuni
    if model_normalized in model_costs:
        costs = model_costs[model_normalized]
    elif "gemini-2.5-flash" in model_normalized:
        costs = model_costs.get("gemini-2.5-flash", {})
    elif "gemini-2.5-pro" in model_normalized:
        costs = model_costs.get("gemini-2.5-pro", {})
    elif "gemini-3-flash" in model_normalized:
        costs = model_costs.get("gemini-3-flash-preview", {})
    elif "gemini-3-pro" in model_normalized:
        costs = model_costs.get("gemini-3-pro-preview", {})
    # OpenAI GPT 5.2 models
    elif "gpt-5.2-pro" in model_normalized:
        costs = model_costs.get("gpt-5.2-pro", {})
    elif "gpt-5.2-chat" in model_normalized or "gpt-5.2-instant" in model_normalized:
        costs = model_costs.get("gpt-5.2-chat-latest", {})
    elif "gpt-5.2" in model_normalized:
        costs = model_costs.get("gpt-5.2", {})
    elif "gpt-4o-mini" in model_normalized:
        costs = model_costs.get("gpt-4o-mini", {})
    elif "gpt-4o" in model_normalized:
        costs = model_costs.get("gpt-4o", {})
    elif "gpt-4-turbo" in model_normalized:
        costs = model_costs.get("gpt-4-turbo", {})
    elif "gpt-4" in model_normalized:
        costs = model_costs.get("gpt-4", {})
    else:
        # Fallback a default
        costs = model_costs.get("default", {})
    
    return {
        "input_cost_per_million": float(costs.get("input_cost_per_million", 1.0)),
        "output_cost_per_million": float(costs.get("output_cost_per_million", 3.0)),
    }


def get_image_generation_cost() -> float:
    """Restituisce il costo per generazione immagine copertina in USD."""
    app_config = get_app_config()
    cost_config = app_config.get("cost_estimation", {})
    return float(cost_config.get("image_generation_cost", 0.02))


def get_cost_currency() -> str:
    """Restituisce la valuta di visualizzazione."""
    app_config = get_app_config()
    cost_config = app_config.get("cost_estimation", {})
    return str(cost_config.get("currency", "EUR"))


def get_exchange_rate_usd_to_eur() -> float:
    """Restituisce il tasso di cambio USD->EUR."""
    app_config = get_app_config()
    cost_config = app_config.get("cost_estimation", {})
    return float(cost_config.get("exchange_rate_usd_to_eur", 0.92))


def get_token_estimates() -> dict[str, Any]:
    """Restituisce le stime di token per le varie fasi."""
    app_config = get_app_config()
    cost_config = app_config.get("cost_estimation", {})
    return cost_config.get("token_estimates", {
        "draft": {"input_base": 800, "output_per_page": 12},
        "outline": {"input_base": 3000, "output_base": 2000},
        "chapter": {"context_base": 8000},
        "critique": {"input_multiplier": 1.2, "output_base": 1200},
    })


# --- Literary Critic Provider Support (Gemini + OpenAI) ---

def detect_critic_provider(model_name: str) -> Literal["google", "openai"]:
    """
    Rileva il provider LLM dal nome del modello per l'agente critico.
    
    Args:
        model_name: Nome del modello (es: "gemini-3-pro-preview", "gpt-5.2", "gpt-5.2-pro")
    
    Returns:
        "google" per modelli Gemini, "openai" per modelli OpenAI
    """
    if not model_name:
        return "google"  # Default per retrocompatibilità
    
    model_lower = model_name.lower()
    if model_lower.startswith(("gpt", "o1", "o3")):
        return "openai"
    elif model_lower.startswith(("gemini", "claude")):
        return "google"
    else:
        # Default: assume Gemini per retrocompatibilità
        return "google"


def normalize_critic_model_name(model_name: str) -> str:
    """
    Normalizza il nome del modello per l'API corretta dell'agente critico.
    
    Args:
        model_name: Nome del modello dall'utente/config
    
    Returns:
        Nome modello normalizzato per l'API (Gemini o OpenAI)
    """
    if not model_name:
        return "gemini-3-pro-preview"  # Default
    
    model_lower = model_name.lower()
    
    # Mapping modelli Gemini (mantiene formato esistente)
    if "gemini-3-pro" in model_lower or model_lower == "gemini-3-pro-preview":
        return "gemini-3-pro-preview"
    elif "gemini-3-flash" in model_lower or model_lower == "gemini-3-flash-preview":
        return "gemini-3-flash-preview"
    elif "gemini-3-ultra" in model_lower:
        return "gemini-3-ultra-preview"
    elif "gemini-2.5-pro" in model_lower:
        return "gemini-2.5-pro"
    elif "gemini-2.5-flash" in model_lower:
        return "gemini-2.5-flash"
    
    # Mapping modelli OpenAI GPT 5.2
    if "gpt-5.2-pro" in model_lower or model_lower == "gpt-5.2-pro":
        return "gpt-5.2-pro"
    elif "gpt-5.2-thinking" in model_lower or model_lower == "gpt-5.2":
        return "gpt-5.2"
    elif "gpt-5.2-instant" in model_lower or "gpt-5.2-chat" in model_lower:
        return "gpt-5.2-chat-latest"
    elif "gpt-4o" in model_lower:
        # Mantiene il nome completo (es: gpt-4o, gpt-4o-mini, gpt-4o-2024-08-06)
        return model_name
    elif "gpt-4-turbo" in model_lower:
        return "gpt-4-turbo"
    elif "gpt-4" in model_lower:
        return "gpt-4"
    
    # Default: restituisce il nome originale (per modelli futuri o già normalizzati)
    return model_name


# --- Literary Critic Provider Support (Gemini + OpenAI) ---

def detect_critic_provider(model_name: str) -> Literal["google", "openai"]:
    """
    Rileva il provider LLM dal nome del modello per l'agente critico.
    
    Args:
        model_name: Nome del modello (es: "gemini-3-pro-preview", "gpt-5.2", "gpt-5.2-pro")
    
    Returns:
        "google" per modelli Gemini, "openai" per modelli OpenAI
    """
    if not model_name:
        return "google"  # Default per retrocompatibilità
    
    model_lower = model_name.lower()
    if model_lower.startswith(("gpt", "o1", "o3")):
        return "openai"
    elif model_lower.startswith(("gemini", "claude")):
        return "google"
    else:
        # Default: assume Gemini per retrocompatibilità
        return "google"


def normalize_critic_model_name(model_name: str) -> str:
    """
    Normalizza il nome del modello per l'API corretta dell'agente critico.
    
    Args:
        model_name: Nome del modello dall'utente/config
    
    Returns:
        Nome modello normalizzato per l'API (Gemini o OpenAI)
    """
    if not model_name:
        return "gemini-3-pro-preview"  # Default
    
    model_lower = model_name.lower()
    
    # Mapping modelli Gemini (mantiene formato esistente)
    if "gemini-3-pro" in model_lower or model_lower == "gemini-3-pro-preview":
        return "gemini-3-pro-preview"
    elif "gemini-3-flash" in model_lower or model_lower == "gemini-3-flash-preview":
        return "gemini-3-flash-preview"
    elif "gemini-3-ultra" in model_lower:
        return "gemini-3-ultra-preview"
    elif "gemini-2.5-pro" in model_lower:
        return "gemini-2.5-pro"
    elif "gemini-2.5-flash" in model_lower:
        return "gemini-2.5-flash"
    
    # Mapping modelli OpenAI GPT 5.2
    if "gpt-5.2-pro" in model_lower or model_lower == "gpt-5.2-pro":
        return "gpt-5.2-pro"
    elif "gpt-5.2-thinking" in model_lower or model_lower == "gpt-5.2":
        return "gpt-5.2"
    elif "gpt-5.2-instant" in model_lower or "gpt-5.2-chat" in model_lower:
        return "gpt-5.2-chat-latest"
    elif "gpt-4o" in model_lower:
        # Mantiene il nome completo (es: gpt-4o, gpt-4o-mini, gpt-4o-2024-08-06)
        return model_name
    elif "gpt-4-turbo" in model_lower:
        return "gpt-4-turbo"
    elif "gpt-4" in model_lower:
        return "gpt-4"
    
    # Default: restituisce il nome originale (per modelli futuri o già normalizzati)
    return model_name

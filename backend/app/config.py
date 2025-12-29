import yaml
from pathlib import Path
from typing import Any, TypedDict, Optional
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
    config_path = Path(__file__).parent.parent.parent / "config" / "inputs.yaml"
    
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
        
        field = FieldConfig(
            id=field_data["id"],
            label=field_data["label"],
            type=field_data["type"],
            required=field_data.get("required", False),
            options=options,
            placeholder=field_data.get("placeholder"),
            description=field_data.get("description"),
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
    config_path = Path(__file__).parent.parent.parent / "config" / "literary_critic.yaml"
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


_app_config: Optional[AppConfig] = None


def load_app_config() -> AppConfig:
    """Carica la configurazione dell'applicazione dal file YAML."""
    config_path = Path(__file__).parent.parent.parent / "config" / "app.yaml"
    
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


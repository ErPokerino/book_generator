import yaml
from pathlib import Path
from typing import Any
from app.models import ConfigResponse, FieldConfig, FieldOption


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


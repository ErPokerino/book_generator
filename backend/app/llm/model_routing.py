"""Routing centralizzato dei modelli e dei limiti di output."""

from __future__ import annotations

from app.core.config import get_app_config

DEFAULT_STAGE_MODEL_OVERRIDES = {
    "questions": "gemini-3.1-pro-preview",
    "draft": "gemini-3.1-pro-preview",
    "outline": "gemini-3.1-pro-preview",
}


def map_book_model_name(model_name: str | None) -> str:
    """Mappa il nome del modello scelto dall'utente verso quello effettivo per Gemini API."""
    model_lower = (model_name or "").lower()
    if "gemini-2.5-flash" in model_lower:
        return "gemini-2.5-flash"
    if "gemini-2.5-pro" in model_lower:
        return "gemini-2.5-pro"
    if "gemini-3-flash" in model_lower:
        return "gemini-3-flash-preview"
    if "gemini-3-pro" in model_lower or "gemini-3.1-pro" in model_lower:
        return "gemini-3.1-pro-preview"
    if "gemini-3-ultra" in model_lower:
        return "gemini-3.1-pro-preview"
    return "gemini-2.5-flash"


def get_stage_model(stage_name: str, requested_model: str | None = None) -> str:
    """Restituisce il modello da usare per uno stadio specifico della pipeline."""
    app_config = get_app_config()
    overrides = app_config.get("llm_models", {}).get("stage_model_overrides", {})
    stage_override = overrides.get(stage_name, DEFAULT_STAGE_MODEL_OVERRIDES.get(stage_name))
    if stage_override:
        return stage_override
    return map_book_model_name(requested_model)


def resolve_generation_mode(model_name: str | None) -> str:
    """Converte il nome del modello in una modalità prodotto usata dalla UI e dai review gate."""
    model_lower = (model_name or "").lower()
    if "ultra" in model_lower:
        return "ultra"
    if "pro" in model_lower:
        return "pro"
    return "flash"


def get_max_output_tokens(model_name: str | None) -> int:
    """Determina il limite output in base al modello normalizzato."""
    app_config = get_app_config()
    tokens_config = app_config.get("llm_models", {}).get("max_output_tokens", {})
    normalized = (model_name or "").lower()
    if "gemini-2.5-flash" in normalized:
        return int(tokens_config.get("gemini_2_5_flash", 8192))
    return int(tokens_config.get("default", 65536))


def get_structured_output_method() -> str:
    """Metodo nativo di structured output da usare per i modelli compatibili."""
    app_config = get_app_config()
    method = app_config.get("llm_models", {}).get("structured_output_method", "json_schema")
    return str(method or "json_schema")

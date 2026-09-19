"""Routing centralizzato dei modelli e dei limiti di output."""

from __future__ import annotations

from typing import Any, Mapping

from app.core.config import get_app_config

TEXT_PURPOSE = "text"
IMAGE_PURPOSE = "image"
TTS_PURPOSE = "tts"

DEFAULT_TEXT_MODEL = "gemini-3.8-flash"
DEFAULT_IMAGE_MODEL = "gemini-3.1-flash-lite-image"
DEFAULT_COVER_IMAGE_MODEL = "gemini-3.1-flash-image"
DEFAULT_TTS_MODEL = "gemini-3.1-flash-tts-preview"

ALLOWED_TEXT_MODELS = ("gemini-3.8-flash", "gemini-3.5-flash-lite")
ALLOWED_IMAGE_MODELS = ("gemini-3.1-flash-lite-image", "gemini-3.1-flash-image")
ALLOWED_TTS_MODELS = (DEFAULT_TTS_MODEL,)

TEXT_STAGES = frozenset(
    {
        "questions",
        "draft",
        "outline",
        "chapters",
        "book",
        "critique",
        "manga_planning",
        "manga_localization",
    }
)
IMAGE_STAGES = frozenset(
    {
        "cover",
        "manga_pages",
        "manga_cover",
        "manga_back_cover",
    }
)
TTS_STAGES = frozenset({"tts"})

DEFAULT_STAGE_MODEL_OVERRIDES = {
    "questions": "gemini-3.5-flash-lite",
    "draft": DEFAULT_TEXT_MODEL,
    "outline": DEFAULT_TEXT_MODEL,
    "chapters": DEFAULT_TEXT_MODEL,
    "critique": DEFAULT_TEXT_MODEL,
    "cover": DEFAULT_COVER_IMAGE_MODEL,
    "manga_planning": DEFAULT_TEXT_MODEL,
    "manga_localization": DEFAULT_TEXT_MODEL,
    "manga_pages": DEFAULT_IMAGE_MODEL,
    "manga_cover": DEFAULT_COVER_IMAGE_MODEL,
    "manga_back_cover": DEFAULT_COVER_IMAGE_MODEL,
    "tts": DEFAULT_TTS_MODEL,
}

_LEGACY_API_IDS = {
    "gemini-2.5-flash": "gemini-3.5-flash-lite",
    "gemini-2.5-pro": DEFAULT_TEXT_MODEL,
    "gemini-3-flash": DEFAULT_TEXT_MODEL,
    "gemini-3-flash-preview": DEFAULT_TEXT_MODEL,
    "gemini-3-pro": DEFAULT_TEXT_MODEL,
    "gemini-3.1-pro-preview": DEFAULT_TEXT_MODEL,
    "gemini-3-ultra": DEFAULT_TEXT_MODEL,
    "gemini-3.1-flash-image-preview": DEFAULT_COVER_IMAGE_MODEL,
    "gemini-2.5-flash-image": DEFAULT_IMAGE_MODEL,
}


def get_model_catalog() -> dict[str, dict[str, Any]]:
    """Catalogo alias → id API / purpose / label da config/app.yaml."""
    catalog = get_app_config().get("llm_models", {}).get("catalog", {}) or {}
    return catalog if isinstance(catalog, dict) else {}


def lookup_model_catalog_entry(model_name: str | None) -> dict[str, Any] | None:
    """Trova la voce di catalogo per un alias UI o un id API."""
    catalog = get_model_catalog()
    if not model_name:
        return None
    key = model_name.strip().lower()
    if key in catalog and isinstance(catalog[key], dict):
        return catalog[key]
    for alias, entry in catalog.items():
        if not isinstance(entry, dict):
            continue
        api_id = str(entry.get("api_id") or "").lower()
        if api_id and (key == api_id or api_id in key or key in alias):
            return entry
        if alias in key:
            return entry
    return None


def _family_default(purpose: str) -> str:
    defaults = get_app_config().get("llm_models", {}).get("defaults", {}) or {}
    if purpose == IMAGE_PURPOSE:
        return str(defaults.get("image") or DEFAULT_IMAGE_MODEL)
    if purpose == TTS_PURPOSE:
        return str(defaults.get("tts") or DEFAULT_TTS_MODEL)
    return str(defaults.get("text") or DEFAULT_TEXT_MODEL)


def stage_purpose(stage_name: str) -> str:
    stage = (stage_name or "").strip().lower()
    if stage in IMAGE_STAGES:
        return IMAGE_PURPOSE
    if stage in TTS_STAGES:
        return TTS_PURPOSE
    return TEXT_PURPOSE


def allowed_models_for_purpose(purpose: str) -> tuple[str, ...]:
    if purpose == IMAGE_PURPOSE:
        return ALLOWED_IMAGE_MODELS
    if purpose == TTS_PURPOSE:
        return ALLOWED_TTS_MODELS
    return ALLOWED_TEXT_MODELS


def is_known_text_model(model_name: str | None) -> bool:
    if not model_name:
        return False
    key = model_name.strip().lower()
    if key in ALLOWED_TEXT_MODELS or key in _LEGACY_API_IDS:
        return True
    entry = lookup_model_catalog_entry(key)
    return bool(entry and str(entry.get("purpose") or TEXT_PURPOSE) == TEXT_PURPOSE)


def map_book_model_name(model_name: str | None) -> str:
    """Mappa il nome del modello scelto dall'utente verso quello effettivo per Gemini API."""
    if not model_name:
        return DEFAULT_TEXT_MODEL

    entry = lookup_model_catalog_entry(model_name)
    if entry and entry.get("api_id"):
        return str(entry["api_id"])

    model_lower = model_name.strip().lower()
    if model_lower in ALLOWED_TEXT_MODELS or model_lower in ALLOWED_IMAGE_MODELS or model_lower in ALLOWED_TTS_MODELS:
        return model_lower
    if model_lower in _LEGACY_API_IDS:
        return _LEGACY_API_IDS[model_lower]
    for alias, api_id in _LEGACY_API_IDS.items():
        if alias in model_lower:
            return api_id
    if "flash-lite-image" in model_lower:
        return DEFAULT_IMAGE_MODEL
    if "flash-image" in model_lower:
        return DEFAULT_COVER_IMAGE_MODEL
    if "tts" in model_lower:
        return DEFAULT_TTS_MODEL
    if "lite" in model_lower:
        return "gemini-3.5-flash-lite"
    return DEFAULT_TEXT_MODEL


def image_size_for_model(model_name: str | None) -> str:
    """Dimensione immagine Gemini supportata dal modello scelto.

    `gemini-3.1-flash-lite-image` non accetta 2K.
    """
    mapped = map_book_model_name(model_name) if model_name else DEFAULT_IMAGE_MODEL
    if "lite" in mapped.lower():
        return "1K"
    return "2K"


def _coerce_override(value: Any, purpose: str) -> str | None:
    if not value:
        return None
    mapped = map_book_model_name(str(value))
    allowed = allowed_models_for_purpose(purpose)
    if mapped in allowed:
        return mapped
    return None


def _collect_overrides(
    *,
    form_data: Any = None,
    overrides: Mapping[str, str] | None = None,
) -> dict[str, str]:
    merged: dict[str, str] = {}
    sources = []
    if form_data is not None:
        sources.append(getattr(form_data, "model_overrides", None))
    if overrides:
        sources.append(overrides)
    for source in sources:
        if not isinstance(source, Mapping):
            continue
        for key, value in source.items():
            if value:
                merged[str(key)] = str(value)
    return merged


def get_stage_model(
    stage_name: str,
    requested_model: str | None = None,
    *,
    form_data: Any = None,
    overrides: Mapping[str, str] | None = None,
) -> str:
    """Restituisce il modello da usare per uno stadio specifico della pipeline.

    Priorità: override di fase nella richiesta → override di famiglia (text/image)
    → modello richiesto dall'utente (se compatibile) → default YAML di fase → default famiglia.
    """
    purpose = stage_purpose(stage_name)
    request_overrides = _collect_overrides(form_data=form_data, overrides=overrides)

    stage_key = (stage_name or "").strip().lower()
    stage_from_request = _coerce_override(request_overrides.get(stage_key), purpose)
    if stage_from_request:
        return stage_from_request

    family_from_request = _coerce_override(request_overrides.get(purpose), purpose)
    if family_from_request:
        return family_from_request

    requested = _coerce_override(requested_model, purpose)
    if requested:
        return requested

    if form_data is not None and purpose == TEXT_PURPOSE:
        requested = _coerce_override(getattr(form_data, "llm_model", None), purpose)
        if requested:
            return requested

    app_config = get_app_config()
    yaml_overrides = app_config.get("llm_models", {}).get("stage_model_overrides", {}) or {}
    yaml_stage = yaml_overrides.get(stage_key, DEFAULT_STAGE_MODEL_OVERRIDES.get(stage_key))
    mapped_yaml = _coerce_override(yaml_stage, purpose)
    if mapped_yaml:
        return mapped_yaml

    return _family_default(purpose)


def resolve_generation_mode(
    model_name: str | None = None,
    generation_mode: str | None = None,
    *,
    form_data: Any = None,
) -> str:
    """Converte scelta utente / alias legacy in `standard` o `ultra`."""
    if form_data is not None:
        generation_mode = generation_mode or getattr(form_data, "generation_mode", None)
        model_name = model_name or getattr(form_data, "llm_model", None)

    mode = (generation_mode or "").strip().lower()
    if mode == "ultra":
        return "ultra"
    if mode in {"standard", "flash", "pro"}:
        return "standard"

    entry = lookup_model_catalog_entry(model_name)
    if entry and entry.get("mode"):
        catalog_mode = str(entry["mode"]).lower()
        if catalog_mode == "ultra":
            return "ultra"
        return "standard"

    model_lower = (model_name or "").lower()
    if "ultra" in model_lower:
        return "ultra"
    return "standard"


def get_writer_split_calls(
    model_name: str | None = None,
    generation_mode: str | None = None,
    *,
    form_data: Any = None,
) -> int:
    """Quante chiamate writer per capitolo (Ultra = 2)."""
    return 2 if resolve_generation_mode(model_name, generation_mode, form_data=form_data) == "ultra" else 1


def get_max_output_tokens(model_name: str | None) -> int:
    """Determina il limite output in base al modello normalizzato."""
    app_config = get_app_config()
    tokens_config = app_config.get("llm_models", {}).get("max_output_tokens", {})
    normalized = (model_name or "").lower()
    if "gemini-2.5-flash" in normalized or "flash-lite" in normalized:
        return int(tokens_config.get("gemini_2_5_flash", tokens_config.get("lite", 8192)))
    return int(tokens_config.get("default", 65536))


def get_structured_output_method() -> str:
    """Metodo nativo di structured output da usare per i modelli compatibili."""
    app_config = get_app_config()
    method = app_config.get("llm_models", {}).get("structured_output_method", "json_schema")
    return str(method or "json_schema")


def public_llm_catalog() -> dict[str, Any]:
    """Sottoinsieme del catalogo esposto al frontend."""
    catalog = get_model_catalog()
    defaults = get_app_config().get("llm_models", {}).get("defaults", {}) or {}
    stage_overrides = get_app_config().get("llm_models", {}).get("stage_model_overrides", {}) or {}
    return {
        "catalog": catalog,
        "defaults": {
            "text": defaults.get("text") or DEFAULT_TEXT_MODEL,
            "image": defaults.get("image") or DEFAULT_IMAGE_MODEL,
            "cover_image": defaults.get("cover_image") or DEFAULT_COVER_IMAGE_MODEL,
            "tts": defaults.get("tts") or DEFAULT_TTS_MODEL,
        },
        "stage_model_overrides": stage_overrides or DEFAULT_STAGE_MODEL_OVERRIDES,
        "text_models": list(ALLOWED_TEXT_MODELS),
        "image_models": list(ALLOWED_IMAGE_MODELS),
        "tts_model": DEFAULT_TTS_MODEL,
        "generation_modes": ["standard", "ultra"],
    }

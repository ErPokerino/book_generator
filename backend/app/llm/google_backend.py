"""Configurazione condivisa del backend Google LLM (Vertex o Gemini API)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from google import genai
from google.genai import types

from app.core.config import get_app_config

GoogleBackendProvider = Literal["vertex", "developer_api"]
DEFAULT_VERTEX_LOCATION = "global"


@dataclass(frozen=True, slots=True)
class GoogleBackendConfig:
    provider: GoogleBackendProvider
    project: str | None = None
    location: str | None = None
    api_key: str | None = None


def _env_flag(name: str) -> bool | None:
    raw = os.getenv(name)
    if raw is None:
        return None
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def get_google_backend_config(api_key: str | None = None) -> GoogleBackendConfig:
    """Risoluzione centralizzata del backend Google da usare per i modelli Gemini."""
    app_config = get_app_config()
    google_cfg = app_config.get("google_llm", {})
    explicit_provider = os.getenv("GOOGLE_LLM_PROVIDER")
    explicit_vertex_flag = _env_flag("GOOGLE_GENAI_USE_VERTEXAI")

    provider_raw = (
        explicit_provider
        or google_cfg.get("provider")
        or ("vertex" if explicit_vertex_flag else None)
    )
    provider = str(provider_raw or "").strip().lower()

    explicit_api_key = api_key or os.getenv("GOOGLE_API_KEY")
    has_vertex_settings = bool(
        os.getenv("GOOGLE_CLOUD_PROJECT")
        or os.getenv("GCLOUD_PROJECT")
        or google_cfg.get("project")
    )

    if provider not in {"vertex", "developer_api"}:
        provider = "vertex" if has_vertex_settings else "developer_api"

    if provider == "vertex":
        project = (
            os.getenv("GOOGLE_CLOUD_PROJECT")
            or os.getenv("GCLOUD_PROJECT")
            or google_cfg.get("project")
        )
        location = (
            os.getenv("GOOGLE_CLOUD_LOCATION")
            or os.getenv("VERTEX_AI_LOCATION")
            or google_cfg.get("location")
            or DEFAULT_VERTEX_LOCATION
        )
        if not project:
            if explicit_api_key and explicit_provider is None and explicit_vertex_flag is not True:
                return GoogleBackendConfig(provider="developer_api", api_key=explicit_api_key)
            raise ValueError(
                "Vertex AI non configurato: imposta GOOGLE_CLOUD_PROJECT "
                "(o google_llm.project in app.yaml) e GOOGLE_CLOUD_LOCATION."
            )
        return GoogleBackendConfig(
            provider="vertex",
            project=str(project),
            location=str(location),
        )

    if not explicit_api_key:
        raise ValueError(
            "Provider Google non configurato: manca GOOGLE_API_KEY e non risultano attive impostazioni Vertex AI."
        )
    return GoogleBackendConfig(provider="developer_api", api_key=explicit_api_key)


def uses_vertex_ai(api_key: str | None = None) -> bool:
    """True se il backend Google risolto usa Vertex AI."""
    return get_google_backend_config(api_key=api_key).provider == "vertex"


def get_google_structured_output_method(api_key: str | None = None) -> str:
    """Metodo di structured output adatto al backend Google attivo."""
    if uses_vertex_ai(api_key=api_key):
        return "json_mode"
    app_config = get_app_config()
    configured = app_config.get("llm_models", {}).get("structured_output_method", "json_schema")
    return str(configured or "json_schema")


def build_google_genai_client(api_key: str | None = None) -> genai.Client:
    """Client google-genai configurato per Vertex AI o Gemini Developer API."""
    backend = get_google_backend_config(api_key=api_key)
    if backend.provider == "vertex":
        return genai.Client(
            vertexai=True,
            project=backend.project,
            location=backend.location,
            http_options=types.HttpOptions(api_version="v1"),
        )
    return genai.Client(api_key=backend.api_key)

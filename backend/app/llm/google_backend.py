"""Configurazione del backend Google LLM (solo Gemini Developer API, uso locale)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from google import genai

from app.core.config import get_app_config

GoogleBackendProvider = Literal["developer_api"]


@dataclass(frozen=True, slots=True)
class GoogleBackendConfig:
    provider: GoogleBackendProvider = "developer_api"
    api_key: str | None = None


def get_google_backend_config(api_key: str | None = None) -> GoogleBackendConfig:
    """Restituisce la configurazione del backend Gemini Developer API."""
    resolved_api_key = api_key or os.getenv("GOOGLE_API_KEY")
    if not resolved_api_key:
        raise ValueError(
            "GOOGLE_API_KEY non configurata. Aggiungi GOOGLE_API_KEY=... al file .env "
            "nella root del progetto."
        )
    return GoogleBackendConfig(provider="developer_api", api_key=resolved_api_key)


def get_google_structured_output_method() -> str:
    """Metodo di structured output per la Gemini Developer API."""
    app_config = get_app_config()
    configured = app_config.get("llm_models", {}).get("structured_output_method", "json_schema")
    return str(configured or "json_schema")


def build_google_genai_client(api_key: str | None = None) -> genai.Client:
    """Client google-genai configurato per la Gemini Developer API."""
    backend = get_google_backend_config(api_key=api_key)
    return genai.Client(api_key=backend.api_key)

"""Tracing persistente per le invocazioni LLM e i passaggi di parsing."""

from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.config import get_app_config


DEFAULT_TRACE_SETTINGS = {
    "enabled": True,
    "sample_rate": 1.0,
    "schema_version": 2,
    "preview_char_limit": 0,
    "record_message_previews": False,
    "record_response_previews": False,
    "redact_text": True,
    "export_target": "jsonl",
}


def _trace_root() -> Path:
    configured = os.getenv("LLM_TRACE_DIR")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parent.parent.parent / ".llm_traces"


def _sanitize_component(value: str | None, fallback: str) -> str:
    raw = (value or fallback).strip().replace(" ", "-").replace(":", "-")
    return "".join(char for char in raw if char.isalnum() or char in {"-", "_"}) or fallback


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _clamp_sample_rate(value: Any) -> float:
    try:
        sample_rate = float(value)
    except (TypeError, ValueError):
        return 1.0
    return max(0.0, min(1.0, sample_rate))


def _safe_int(value: Any, *, default: int, minimum: int | None = None) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    if minimum is not None:
        parsed = max(minimum, parsed)
    return parsed


def _load_trace_settings() -> dict[str, Any]:
    settings = DEFAULT_TRACE_SETTINGS.copy()
    settings.update(get_app_config().get("llm_tracing", {}))
    settings["enabled"] = _env_flag("LLM_TRACE_ENABLED", bool(settings["enabled"]))
    settings["record_message_previews"] = _env_flag(
        "LLM_TRACE_RECORD_MESSAGE_PREVIEWS",
        bool(settings["record_message_previews"]),
    )
    settings["record_response_previews"] = _env_flag(
        "LLM_TRACE_RECORD_RESPONSE_PREVIEWS",
        bool(settings["record_response_previews"]),
    )
    settings["redact_text"] = _env_flag("LLM_TRACE_REDACT_TEXT", bool(settings["redact_text"]))
    settings["sample_rate"] = _clamp_sample_rate(os.getenv("LLM_TRACE_SAMPLE_RATE", settings["sample_rate"]))
    settings["schema_version"] = _safe_int(
        os.getenv("LLM_TRACE_SCHEMA_VERSION", settings["schema_version"]),
        default=int(settings["schema_version"]),
        minimum=1,
    )
    settings["preview_char_limit"] = _safe_int(
        os.getenv("LLM_TRACE_PREVIEW_CHAR_LIMIT", settings["preview_char_limit"]),
        default=int(settings["preview_char_limit"]),
        minimum=0,
    )
    settings["export_target"] = str(os.getenv("LLM_TRACE_EXPORT_TARGET", settings["export_target"]))
    return settings


def _safe_serialize(value: Any, *, max_length: int = 4000) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value if len(value) <= max_length else f"{value[:max_length]}...<truncated>"
    if isinstance(value, dict):
        return {
            str(key): _safe_serialize(item, max_length=max_length)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_safe_serialize(item, max_length=max_length) for item in value]
    if isinstance(value, tuple):
        return [_safe_serialize(item, max_length=max_length) for item in value]
    if hasattr(value, "model_dump"):
        return _safe_serialize(value.model_dump(), max_length=max_length)
    return _safe_serialize(str(value), max_length=max_length)


@dataclass(slots=True)
class LLMTraceRecorder:
    """Appender leggero che salva eventi JSONL per debug offline."""

    stage: str
    session_id: str | None = None
    request_id: str | None = None
    trace_id: str = field(default_factory=lambda: uuid4().hex)
    file_path: Path = field(init=False)
    enabled: bool = field(init=False, default=True)
    sampled: bool = field(init=False, default=True)
    schema_version: int = field(init=False, default=2)
    export_target: str = field(init=False, default="jsonl")
    preview_char_limit: int = field(init=False, default=0)
    record_message_previews: bool = field(init=False, default=False)
    record_response_previews: bool = field(init=False, default=False)
    redact_text: bool = field(init=False, default=True)

    def __post_init__(self) -> None:
        settings = _load_trace_settings()
        self.enabled = bool(settings["enabled"])
        self.sampled = self.enabled and random.random() <= _clamp_sample_rate(settings["sample_rate"])
        self.schema_version = int(settings["schema_version"])
        self.export_target = str(settings["export_target"])
        self.preview_char_limit = max(0, int(settings["preview_char_limit"]))
        self.record_message_previews = bool(settings["record_message_previews"])
        self.record_response_previews = bool(settings["record_response_previews"])
        self.redact_text = bool(settings["redact_text"])
        root = _trace_root()
        root.mkdir(parents=True, exist_ok=True)
        session_component = _sanitize_component(self.session_id, "no-session")
        stage_component = _sanitize_component(self.stage, "stage")
        request_component = _sanitize_component(self.request_id, "request")
        self.file_path = root / f"{session_component}--{stage_component}--{request_component}--{self.trace_id}.jsonl"

    def preview_text(self, text: str, *, preview_kind: str) -> str | None:
        if not text:
            return ""
        allow_preview = (
            self.record_message_previews
            if preview_kind == "message"
            else self.record_response_previews
        )
        if not allow_preview or self.preview_char_limit <= 0:
            return None
        if self.redact_text:
            return f"<redacted:{len(text)} chars>"
        if len(text) <= self.preview_char_limit:
            return text
        return f"{text[:self.preview_char_limit]}...<truncated>"

    def record(self, event_type: str, **payload: Any) -> None:
        if not self.enabled or not self.sampled:
            return
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trace_id": self.trace_id,
            "schema_version": self.schema_version,
            "stage": self.stage,
            "session_id": self.session_id,
            "request_id": self.request_id,
            "export_target": self.export_target,
            "redact_text": self.redact_text,
            "event_type": event_type,
            "payload": _safe_serialize(payload),
        }
        with open(self.file_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False))
            handle.write("\n")

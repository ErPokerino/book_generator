"""Utility per logging strutturato e coerente."""
import logging
import os
from typing import Any


def configure_logging() -> None:
    """Configura il logging applicativo una sola volta."""
    if getattr(configure_logging, "_configured", False):
        return

    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    configure_logging._configured = True


class ContextLogger(logging.LoggerAdapter):
    """LoggerAdapter semplice che serializza il contesto nel messaggio."""

    def process(self, msg: str, kwargs: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        runtime_context = kwargs.pop("context", {}) or {}
        merged_context = {**self.extra, **runtime_context}
        if not merged_context:
            return msg, kwargs

        serialized = " ".join(f"{key}={value}" for key, value in merged_context.items())
        return f"{msg} | {serialized}", kwargs


def get_logger(name: str, **context: Any) -> ContextLogger:
    """Restituisce un logger con eventuale contesto preimpostato."""
    configure_logging()
    return ContextLogger(logging.getLogger(name), context)

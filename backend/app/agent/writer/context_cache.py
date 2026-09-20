"""Prefisso stabile del writer con cache implicita gestita dal provider."""

from __future__ import annotations

from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import get_temperature_for_agent
from app.llm import (
    LLMTraceRecorder,
    build_google_chat_model,
    get_max_output_tokens,
    invoke_chat_model,
)

async def generate_chapter_with_prefix_cache(
    *,
    agent_context: str,
    prefix: str,
    turn: str,
    gemini_model: str,
    api_key: Optional[str],
    current_section_title: str,
    session_id: str | None,
    request_label: str,
    response_validator,
) -> tuple[str, dict[str, int]]:
    """Prefix stabile per la cache implicita: nessun costo di storage o cache orfana."""
    llm = build_google_chat_model(
        model_name=gemini_model,
        api_key=api_key,
        temperature=get_temperature_for_agent("writer_generator", gemini_model),
        max_output_tokens=get_max_output_tokens(gemini_model),
    )
    return await invoke_chat_model(
        llm=llm,
        messages=[
            SystemMessage(content=agent_context),
            HumanMessage(content=f"{prefix}\n{turn}"),
        ],
        model_name=gemini_model,
        stage="chapter-generation",
        request_label=request_label,
        session_id=session_id,
        trace_recorder=LLMTraceRecorder(
            stage="chapter-generation",
            session_id=session_id,
            request_id=request_label,
        ),
        response_validator=response_validator,
    )

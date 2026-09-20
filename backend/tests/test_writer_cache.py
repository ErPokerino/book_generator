from unittest.mock import AsyncMock
import pytest
from app.agent.writer import context_cache

@pytest.mark.asyncio
async def test_prefix_is_sent_without_creating_billable_storage(monkeypatch):
    monkeypatch.setattr(context_cache, "build_google_chat_model", lambda **kwargs: object())
    invoke = AsyncMock(return_value=("Testo", {"input_tokens": 1, "output_tokens": 2}))
    monkeypatch.setattr(context_cache, "invoke_chat_model", invoke)
    result = await context_cache.generate_chapter_with_prefix_cache(agent_context="Regole", prefix="Memoria",
        turn="Scrivi", gemini_model="gemini-3.8-flash", api_key=None, current_section_title="Primo",
        session_id=None, request_label="test", response_validator=lambda x: x)
    assert result[0] == "Testo"
    assert invoke.call_args.kwargs["messages"][1].content == "Memoria\nScrivi"

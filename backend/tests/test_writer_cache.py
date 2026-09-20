from unittest.mock import Mock

from app.agent.writer import context_cache


def test_expired_writer_cache_is_recreated(monkeypatch):
    monkeypatch.setattr(context_cache, "_CACHE_NAMES", {})
    now = [0.0]
    monkeypatch.setattr(context_cache, "monotonic", lambda: now[0])
    create = Mock(side_effect=["cache/one", "cache/two"])
    monkeypatch.setattr(context_cache, "_create_explicit_cache", create)
    args = dict(model_name="test-model", system_prompt="Scrivi", prefix="Trama", api_key=None)
    assert context_cache.resolve_writer_cache_name(**args) == "cache/one"
    assert context_cache.resolve_writer_cache_name(**args) == "cache/one"
    assert create.call_count == 1
    now[0] = context_cache.CACHE_TTL_SECONDS + 1
    assert context_cache.resolve_writer_cache_name(**args) == "cache/two"
    assert create.call_count == 2

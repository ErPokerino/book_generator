import pytest

import app.core.config as config_module


def test_gemini_38_uses_catalog_default_not_agent_override(monkeypatch) -> None:
    monkeypatch.setattr(
        config_module,
        "get_app_config",
        lambda: {
            "llm_models": {
                "catalog": {
                    "gemini-3.8-flash": {"api_id": "gemini-3.8-flash", "temperature": 1.0},
                    "gemini-3.5-flash-lite": {"api_id": "gemini-3.5-flash-lite", "temperature": 1.0},
                }
            },
            "temperature": {"agents": {"writer_generator": 0.65, "manga_planner": 0.4}},
        },
    )

    assert config_module.get_temperature_for_agent("writer_generator", "gemini-3.8-flash") == 1.0
    assert config_module.get_temperature_for_agent("manga_planner", "gemini-3.5-flash-lite") == 1.0


def test_unknown_model_uses_temperature_default(monkeypatch) -> None:
    monkeypatch.setattr(
        config_module,
        "get_app_config",
        lambda: {
            "llm_models": {"catalog": {}},
            "temperature": {"default": 1.0, "agents": {"writer_generator": 0.65}},
        },
    )

    assert config_module.get_temperature_for_agent("writer_generator", "gemini-2.5-flash") == 1.0

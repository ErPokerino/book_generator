import app.core.config as config_module


def test_gemini_3_forces_temperature_one_even_with_agent_override(monkeypatch) -> None:
    monkeypatch.setattr(
        config_module,
        "get_app_config",
        lambda: {"temperature": {"agents": {"manga_planner": 0.4}}},
    )

    assert config_module.get_temperature_for_agent("manga_planner", "gemini-3-flash-preview") == 1.0


def test_non_gemini_3_still_uses_agent_override(monkeypatch) -> None:
    monkeypatch.setattr(
        config_module,
        "get_app_config",
        lambda: {"temperature": {"agents": {"writer_generator": 0.65}}},
    )

    assert config_module.get_temperature_for_agent("writer_generator", "gemini-2.5-flash") == 0.65

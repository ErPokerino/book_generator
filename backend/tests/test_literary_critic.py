from app.agent.literary_critic import _resolve_provider_api_key


def test_resolve_provider_api_key_prefers_provider_specific_keys(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "env-google")
    monkeypatch.setenv("OPENAI_API_KEY", "env-openai")

    assert (
        _resolve_provider_api_key(
            "google",
            api_key=None,
            google_api_key="request-google",
            openai_api_key="request-openai",
        )
        == "request-google"
    )
    assert (
        _resolve_provider_api_key(
            "openai",
            api_key=None,
            google_api_key="request-google",
            openai_api_key="request-openai",
        )
        == "request-openai"
    )


def test_resolve_provider_api_key_falls_back_to_provider_env(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "env-google")
    monkeypatch.setenv("OPENAI_API_KEY", "env-openai")

    assert _resolve_provider_api_key("google", api_key=None) == "env-google"
    assert _resolve_provider_api_key("openai", api_key=None) == "env-openai"

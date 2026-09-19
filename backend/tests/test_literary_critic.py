from app.agent.literary_critic import _resolve_provider_api_key
from app.core.config import normalize_critic_model_name


def test_resolve_provider_api_key_prefers_google_specific_key(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "env-google")

    assert (
        _resolve_provider_api_key(
            "google",
            api_key=None,
            google_api_key="request-google",
        )
        == "request-google"
    )


def test_resolve_provider_api_key_falls_back_to_google_env(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "env-google")

    assert _resolve_provider_api_key("google", api_key=None) == "env-google"


def test_normalize_critic_model_name_maps_ultra_to_gemini_38_flash() -> None:
    assert normalize_critic_model_name("gemini-3-ultra") == "gemini-3.8-flash"
    assert normalize_critic_model_name("gemini-3-ultra-preview") == "gemini-3.8-flash"
    assert normalize_critic_model_name("ultra") == "gemini-3.8-flash"
    assert normalize_critic_model_name("gemini-3.8-flash") == "gemini-3.8-flash"

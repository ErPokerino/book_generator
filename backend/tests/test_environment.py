import pytest

from app.core.environment import (
    DEFAULT_SESSION_SECRET,
    allow_detailed_diagnostics,
    get_environment,
    get_session_secret,
)


def test_get_environment_normalizes_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "Prod")

    assert get_environment() == "production"


def test_get_session_secret_requires_override_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("SESSION_SECRET", raising=False)

    with pytest.raises(RuntimeError, match="SESSION_SECRET"):
        get_session_secret()

    monkeypatch.setenv("SESSION_SECRET", "super-secret-value")
    assert get_session_secret() == "super-secret-value"
    assert DEFAULT_SESSION_SECRET != "super-secret-value"


def test_diagnostics_disabled_by_default_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("ENABLE_DIAGNOSTIC_DETAILS", raising=False)

    assert allow_detailed_diagnostics() is False

    monkeypatch.setenv("ENABLE_DIAGNOSTIC_DETAILS", "true")
    assert allow_detailed_diagnostics() is True

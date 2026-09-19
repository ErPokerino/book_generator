import pytest

from app.core.environment import allow_detailed_diagnostics, get_environment


def test_get_environment_normalizes_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "Prod")

    assert get_environment() == "production"


def test_diagnostics_disabled_by_default_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("ENABLE_DIAGNOSTIC_DETAILS", raising=False)

    assert allow_detailed_diagnostics() is False

    monkeypatch.setenv("ENABLE_DIAGNOSTIC_DETAILS", "true")
    assert allow_detailed_diagnostics() is True

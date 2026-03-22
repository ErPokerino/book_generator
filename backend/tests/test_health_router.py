import sys
from types import ModuleType

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers import health


def build_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    app = FastAPI()
    app.include_router(health.router)

    stub_main = ModuleType("app.main")
    stub_main.app = app
    monkeypatch.setitem(sys.modules, "app.main", stub_main)
    return TestClient(app)


def test_health_endpoint_returns_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    client = build_client(monkeypatch)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ping_hides_routes_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("ENABLE_DIAGNOSTIC_DETAILS", raising=False)
    client = build_client(monkeypatch)

    response = client.get("/api/ping")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "pong"
    assert payload["environment"] == "production"
    assert "routes" not in payload


def test_ping_exposes_routes_outside_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    client = build_client(monkeypatch)

    response = client.get("/api/ping")

    assert response.status_code == 200
    payload = response.json()
    assert payload["environment"] == "development"
    assert "/health" in payload["routes"]

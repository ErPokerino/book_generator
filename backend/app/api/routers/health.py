"""Router per gli endpoint di health check e diagnostica."""
from fastapi import APIRouter
from app.core.environment import allow_detailed_diagnostics, get_environment

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    """Endpoint di health check."""
    return {"status": "ok"}


@router.get("/api/ping")
async def ping():
    """Endpoint di diagnostica per verificare se il backend è attivo e aggiornato."""
    from app.main import app
    payload = {
        "status": "pong",
        "version": "0.1.1",
        "environment": get_environment(),
    }
    if allow_detailed_diagnostics():
        payload["routes"] = [route.path for route in app.routes]
    return payload

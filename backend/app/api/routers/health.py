"""Router per gli endpoint di health check e diagnostica."""
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    """Endpoint di health check."""
    return {"status": "ok"}


@router.get("/api/ping")
async def ping():
    """Endpoint di diagnostica per verificare se il backend è attivo e aggiornato."""
    from app.main import app
    return {
        "status": "pong",
        "version": "0.1.1",
        "routes": [route.path for route in app.routes]
    }

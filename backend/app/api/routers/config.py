"""Router per gli endpoint di configurazione."""
from fastapi import APIRouter, HTTPException
from app.models import ConfigResponse
from app.core.config import reload_config, get_app_config

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("", response_model=ConfigResponse)
async def get_config_endpoint():
    """Restituisce la configurazione degli input."""
    try:
        # Ricarica sempre la config per permettere modifiche al YAML senza riavviare
        return reload_config()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore nel caricamento della configurazione: {str(e)}")


@router.get("/app")
async def get_app_config_endpoint():
    """Restituisce la configurazione dell'applicazione (solo valori necessari al frontend)."""
    try:
        app_config = get_app_config()
        # Restituisci solo i valori necessari al frontend
        return {
            "api_timeouts": app_config.get("api_timeouts", {}),
            "frontend": app_config.get("frontend", {}),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore nel caricamento della configurazione app: {str(e)}")

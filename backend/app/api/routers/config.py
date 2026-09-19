"""Router per gli endpoint di configurazione."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from app.models import ConfigResponse
from app.core.config import reload_config, reload_app_config
from app.llm.model_routing import public_llm_catalog
import json

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("")
async def get_config_endpoint():
    """Restituisce la configurazione degli input."""
    try:
        # Ricarica sempre la config per permettere modifiche al YAML senza riavviare
        config = reload_config()
        result = config.model_dump(exclude_none=False)
        # Usa JSONResponse per controllare esplicitamente la serializzazione
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore nel caricamento della configurazione: {str(e)}")


@router.get("/app")
async def get_app_config_endpoint():
    """Restituisce la configurazione dell'applicazione (solo valori necessari al frontend)."""
    try:
        # Ricarica la app config per permettere modifiche al YAML senza riavviare (dev-friendly)
        app_config = reload_app_config()
        # Restituisci solo i valori necessari al frontend
        return {
            "api_timeouts": app_config.get("api_timeouts", {}),
            "frontend": app_config.get("frontend", {}),
            "manga_generation": app_config.get("manga_generation", {}),
            "llm_models": public_llm_catalog(),
            "cost_estimation": app_config.get("cost_estimation", {}),
            "time_estimation": app_config.get("time_estimation", {}),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore nel caricamento della configurazione app: {str(e)}")

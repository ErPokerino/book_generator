"""Router per gli endpoint di configurazione."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from app.models import ConfigResponse
from app.core.config import reload_config, reload_app_config
from app.llm.model_routing import public_llm_catalog
import json
from typing import Literal

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("/book-estimates")
async def get_book_estimates(model: str = "gemini-3.8-flash", length: Literal["breve", "media", "lunga"] | None = None):
    from app.agent.session_store import get_session_store
    from app.services.book_estimate_service import estimate_book_sizes
    sessions = get_session_store().get_all_sessions().values()
    return estimate_book_sizes(sessions, model=model, length=length)


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
        from app.services.usage_service import RATES, pricing_snapshot, SOURCE, VERIFIED_AT
        costs = dict(app_config.get("cost_estimation", {}))
        costs["model_costs"] = {model: {"input_cost_per_million": pricing_snapshot(model)["rates"]["input"],
            "output_cost_per_million": pricing_snapshot(model)["rates"]["output"]} for model in RATES}
        costs["image_costs"] = {"gemini-3.1-flash-lite-image": .0336, "gemini-3.1-flash-image": .1008}
        costs["pricing_source"] = SOURCE
        costs["pricing_verified_at"] = VERIFIED_AT
        # Restituisci solo i valori necessari al frontend
        return {
            "api_timeouts": app_config.get("api_timeouts", {}),
            "frontend": app_config.get("frontend", {}),
            "manga_generation": app_config.get("manga_generation", {}),
            "llm_models": public_llm_catalog(),
            "cost_estimation": costs,
            "time_estimation": app_config.get("time_estimation", {}),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore nel caricamento della configurazione app: {str(e)}")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_config, reload_config
from app.models import ConfigResponse, SubmissionRequest, SubmissionResponse

app = FastAPI(title="Scrittura Libro API", version="0.1.0")

# CORS per sviluppo locale
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Vite default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/config", response_model=ConfigResponse)
async def get_config_endpoint():
    """Restituisce la configurazione degli input."""
    try:
        # Ricarica sempre la config per permettere modifiche al YAML senza riavviare
        return reload_config()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore nel caricamento della configurazione: {str(e)}")


@app.post("/api/submissions", response_model=SubmissionResponse)
async def submit_form(data: SubmissionRequest):
    """Riceve e valida i dati del form."""
    config = get_config()
    
    # Valida il modello LLM
    if data.llm_model not in config.llm_models:
        raise HTTPException(
            status_code=400,
            detail=f"Modello LLM non valido: {data.llm_model}. Modelli disponibili: {', '.join(config.llm_models)}"
        )
    
    # Valida i campi select opzionali contro le opzioni configurate
    field_map = {field.id: field for field in config.fields}
    
    for field_id, value in data.model_dump(exclude={"llm_model", "plot"}).items():
        if value is not None and field_id in field_map:
            field = field_map[field_id]
            if field.type == "select" and field.options:
                valid_values = [opt.value for opt in field.options]
                if value not in valid_values:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Valore non valido per '{field.label}': {value}"
                    )
    
    return SubmissionResponse(
        success=True,
        message="Submission ricevuta con successo",
        data=data,
    )


@app.get("/health")
async def health():
    """Endpoint di health check."""
    return {"status": "ok"}


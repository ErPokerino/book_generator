"""Router per gli endpoint di submission."""
from fastapi import APIRouter, HTTPException
from app.models import SubmissionRequest, SubmissionResponse
from app.core.config import get_config

router = APIRouter(prefix="/api/submissions", tags=["submission"])


@router.post("", response_model=SubmissionResponse)
async def submit_form(data: SubmissionRequest):
    """Riceve e valida i dati del form."""
    try:
        print(f"[SUBMIT FORM] Ricevuta submission con llm_model={data.llm_model}")
        config = get_config()
        
        # Valida che llm_model non sia None o vuoto
        if not data.llm_model or not data.llm_model.strip():
            print(f"[SUBMIT FORM] ERRORE: Modello LLM mancante o vuoto")
            raise HTTPException(
                status_code=400,
                detail="Il modello LLM è obbligatorio. Seleziona un modello dalla lista."
            )
        
        # Valida il modello LLM
        if data.llm_model not in config.llm_models:
            print(f"[SUBMIT FORM] ERRORE: Modello LLM non valido: {data.llm_model}")
            raise HTTPException(
                status_code=400,
                detail=f"Modello LLM non valido: {data.llm_model}. Modelli disponibili: {', '.join(config.llm_models)}"
            )
        
        # Valida i campi select opzionali contro le opzioni configurate
        # Escludi llm_model e plot dalla validazione come select
        field_map = {field.id: field for field in config.fields}
        
        for field_id, value in data.model_dump(exclude={"llm_model", "plot"}).items():
            if value is not None and field_id in field_map:
                field = field_map[field_id]
                if field.type == "select" and field.options:
                    valid_values = [opt.value for opt in field.options]
                    if value not in valid_values:
                        print(f"[SUBMIT FORM] ERRORE: Valore non valido per '{field.label}': {value}")
                        raise HTTPException(
                            status_code=400,
                            detail=f"Valore non valido per '{field.label}': {value}"
                        )
        
        print(f"[SUBMIT FORM] Submission validata con successo")
        return SubmissionResponse(
            success=True,
            message="Submission ricevuta con successo",
            data=data,
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"[SUBMIT FORM] ERRORE CRITICO: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore interno nel processamento della submission: {str(e)}"
        )

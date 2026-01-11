"""Router per l'accesso ai file (PDF libri e cover images)."""
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, RedirectResponse

from app.services.storage_service import get_storage_service

router = APIRouter(prefix="/api/files", tags=["files"])


@router.get("/{tipo}/{filename}")
async def get_file_endpoint(tipo: str, filename: str):
    """
    Genera un URL firmato temporaneo per accedere a un file su GCS.
    
    Args:
        tipo: Tipo di file ("books" o "covers")
        filename: Nome del file
    
    Returns:
        Redirect all'URL firmato GCS o file locale
    """
    try:
        storage_service = get_storage_service()
        
        if tipo not in ["books", "covers"]:
            raise HTTPException(
                status_code=400,
                detail=f"Tipo non valido: {tipo}. Tipi supportati: books, covers"
            )
        
        # Costruisci il path
        if storage_service.gcs_enabled:
            gcs_path = f"gs://{storage_service.bucket_name}/{tipo}/{filename}"
        else:
            # Fallback locale
            if tipo == "books":
                local_path = Path(__file__).parent.parent.parent / "books" / filename
            else:  # covers
                local_path = Path(__file__).parent.parent.parent / "sessions" / filename
            
            if not local_path.exists():
                raise HTTPException(
                    status_code=404,
                    detail=f"File non trovato: {filename}"
                )
            
            # Per locale, restituisci il file direttamente
            return FileResponse(
                path=str(local_path),
                filename=filename,
                media_type="application/pdf" if filename.endswith(".pdf") else "image/png"
            )
        
        # Verifica che il file esista
        if not storage_service.file_exists(gcs_path):
            raise HTTPException(
                status_code=404,
                detail=f"File non trovato: {filename}"
            )
        
        # Genera URL firmato (valido 15 minuti)
        signed_url = storage_service.get_signed_url(gcs_path, expiration_minutes=15)
        
        # Redirect all'URL firmato
        return RedirectResponse(url=signed_url, status_code=307)
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[GET FILE] Errore nel recupero file: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nel recupero del file: {str(e)}"
        )

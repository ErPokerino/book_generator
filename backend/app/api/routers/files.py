"""Router per l'accesso ai file (PDF libri e cover images)."""
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.services.storage_service import get_storage_service

router = APIRouter(prefix="/api/files", tags=["files"])


@router.get("/{tipo}/{filename}")
async def get_file_endpoint(tipo: str, filename: str):
    """Serve un file locale (PDF o copertina)."""
    try:
        if tipo not in ["books", "covers"]:
            raise HTTPException(
                status_code=400,
                detail=f"Tipo non valido: {tipo}. Tipi supportati: books, covers"
            )

        storage_service = get_storage_service()
        destination = f"{tipo}/{filename}"
        if not storage_service.exists(destination):
            raise HTTPException(
                status_code=404,
                detail=f"File non trovato: {filename}"
            )

        folder = "books" if tipo == "books" else "sessions"
        local_path = storage_service.local_base_path / folder / filename
        media_type = "application/pdf" if filename.endswith(".pdf") else "image/png"
        return FileResponse(
            path=str(local_path),
            filename=Path(filename).name,
            media_type=media_type,
        )

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

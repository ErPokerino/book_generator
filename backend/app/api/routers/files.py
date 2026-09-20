"""Router per l'accesso ai file (PDF libri e cover images)."""
from pathlib import Path
from mimetypes import guess_type
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

        if not filename or filename in {".", ".."} or any(char in filename for char in "/\\:"):
            raise HTTPException(status_code=403, detail="Nome file non consentito")

        storage_service = get_storage_service()
        destination = f"{tipo}/{filename}"
        if not storage_service.exists(destination):
            raise HTTPException(
                status_code=404,
                detail=f"File non trovato: {filename}"
            )

        folder = "books" if tipo == "books" else "sessions"
        root = (storage_service.local_base_path / folder).resolve()
        local_path = (root / filename).resolve()
        if not local_path.is_relative_to(root):
            raise HTTPException(status_code=403, detail="Accesso non consentito a questo file")
        if not local_path.is_file():
            raise HTTPException(status_code=404, detail="File non trovato")
        media_type = guess_type(filename)[0] or "application/octet-stream"
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

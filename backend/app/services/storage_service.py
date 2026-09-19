"""Servizio per la gestione di file sul filesystem locale."""
from pathlib import Path
from typing import Optional


class StorageService:
    """
    Storage locale sotto backend/:
    - books/     PDF e audio
    - sessions/  copertine (destination_path covers/...)
    - manga/     pagine e copertine manga
    """

    def __init__(self):
        self.local_base_path = Path(__file__).resolve().parent.parent.parent

    def _normalize_key(self, source_path: str) -> str:
        return str(source_path).replace("\\", "/")

    def _resolve_path(self, source_path: str) -> Path:
        raw = self._normalize_key(source_path)
        path = Path(source_path) if Path(str(source_path)).is_absolute() else Path(raw)
        if path.is_absolute():
            return path

        if raw.startswith("books/"):
            return self.local_base_path / "books" / raw[len("books/") :]
        if raw.startswith("covers/"):
            return self.local_base_path / "sessions" / raw[len("covers/") :]
        if raw.startswith("sessions/"):
            return self.local_base_path / "sessions" / raw[len("sessions/") :]
        if raw.startswith("manga/"):
            return self.local_base_path / "manga" / raw[len("manga/") :]

        name = Path(raw).name
        if name.endswith(".pdf") or "books" in raw:
            return self.local_base_path / "books" / name
        if name.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            sessions_path = self.local_base_path / "sessions" / name
            covers_path = self.local_base_path / "covers" / name
            if sessions_path.exists():
                return sessions_path
            if covers_path.exists():
                return covers_path
            manga_candidate = self.local_base_path / raw
            if manga_candidate.exists():
                return manga_candidate
            return sessions_path
        return self.local_base_path / raw

    def upload_file(
        self,
        data: bytes,
        destination_path: str,
        content_type: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> str:
        """Salva un file sul filesystem locale e restituisce il path assoluto."""
        local_path = self._resolve_path(destination_path)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(data)
        print(f"[STORAGE] File salvato localmente: {local_path}")
        return str(local_path)

    def download_file(self, source_path: str) -> bytes:
        """Legge un file dal filesystem locale."""
        path = self._resolve_path(source_path)
        if not path.exists():
            raise FileNotFoundError(
                f"File non trovato localmente: {source_path} (cercato in: {path})"
            )
        return path.read_bytes()

    def exists(self, path: str) -> bool:
        """True se il file esiste in locale."""
        return self._resolve_path(path).exists()

    def delete(self, path: str) -> bool:
        """Elimina un file locale. True se rimosso."""
        resolved = self._resolve_path(path)
        if not resolved.exists():
            return False
        resolved.unlink()
        print(f"[STORAGE] File eliminato localmente: {resolved}")
        return True

    def get_url(self, path: str) -> str:
        """Restituisce un path API `/api/files/...` per books/covers, altrimenti il path locale."""
        resolved = self._resolve_path(path)
        try:
            relative = resolved.resolve().relative_to(self.local_base_path.resolve())
        except ValueError:
            return str(resolved)

        parts = relative.parts
        if not parts:
            return str(resolved)
        if parts[0] == "books":
            rest = Path(*parts[1:]).as_posix() if len(parts) > 1 else resolved.name
            return f"/api/files/books/{rest}"
        if parts[0] in ("sessions", "covers"):
            return f"/api/files/covers/{resolved.name}"
        return str(resolved)

    def file_exists(self, path: str) -> bool:
        return self.exists(path)

    def delete_file(self, path: str) -> bool:
        return self.delete(path)


_storage_service: Optional[StorageService] = None


def get_storage_service() -> StorageService:
    """Restituisce l'istanza globale del servizio storage."""
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service

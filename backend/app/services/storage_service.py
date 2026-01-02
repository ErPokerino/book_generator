"""Servizio per la gestione di file su Google Cloud Storage o locale."""
import os
from pathlib import Path
from typing import Optional
from io import BytesIO
from datetime import timedelta
from dotenv import load_dotenv

# Carica variabili d'ambiente PRIMA di qualsiasi altra operazione
# Il file .env è nella root del progetto (un livello sopra backend)
# Path(__file__) = backend/app/services/storage_service.py
# parent.parent.parent = root del progetto
env_path = Path(__file__).parent.parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
# Fallback: carica anche dalla directory corrente
load_dotenv()

# Import condizionale per GCS
try:
    from google.cloud import storage
    from google.cloud.exceptions import NotFound
    GCS_AVAILABLE = True
except ImportError:
    GCS_AVAILABLE = False
    storage = None
    NotFound = Exception


class StorageService:
    """
    Servizio per gestire upload/download file su GCS o locale.
    
    Struttura bucket GCS:
    - Con user_id: users/{user_id}/books/... e users/{user_id}/covers/...
    - Senza user_id (sessione anonima): books/... e covers/... (root)
    
    I file vengono organizzati per utente quando possibile per isolamento e gestione più semplice.
    """
    
    def __init__(self):
        self.gcs_enabled = os.getenv("GCS_ENABLED", "false").lower() == "true"
        self.bucket_name = os.getenv("GCS_BUCKET_NAME", "narrai-books-483022")
        self.client: Optional[storage.Client] = None
        self.bucket: Optional[storage.Bucket] = None
        
        # Percorsi locali di fallback
        self.local_base_path = Path(__file__).parent.parent.parent
        
        if self.gcs_enabled and GCS_AVAILABLE:
            self._init_gcs_client()
        elif self.gcs_enabled and not GCS_AVAILABLE:
            print("[STORAGE] WARN: GCS_ENABLED=true ma google-cloud-storage non installato. Usando fallback locale.")
            self.gcs_enabled = False
    
    def _init_gcs_client(self):
        """Inizializza il client GCS (lazy loading)."""
        if self.client is None:
            try:
                # Correggi path credenziali se relativo
                cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
                if cred_path and not Path(cred_path).is_absolute():
                    # Converti path relativo in assoluto rispetto alla root del progetto
                    root_dir = Path(__file__).parent.parent.parent.parent
                    abs_cred_path = (root_dir / cred_path.lstrip("./")).resolve()
                    if abs_cred_path.exists():
                        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(abs_cred_path)
                
                self.client = storage.Client()
                self.bucket = self.client.bucket(self.bucket_name)
                # Non verifichiamo exists() perché potrebbe richiedere permessi aggiuntivi
                # Verificheremo l'accesso al primo upload/download
                print(f"[STORAGE] GCS client inizializzato. Bucket: {self.bucket_name}")
            except Exception as e:
                print(f"[STORAGE] ERRORE inizializzazione GCS: {e}")
                print("[STORAGE] Fallback a storage locale")
                self.gcs_enabled = False
    
    def upload_file(
        self,
        data: bytes,
        destination_path: str,
        content_type: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> str:
        """
        Carica un file su GCS o locale.
        
        Args:
            data: Contenuto del file in bytes
            destination_path: Path di destinazione (es: "books/filename.pdf" o "covers/session_id_cover.png")
            content_type: MIME type del file (es: "application/pdf", "image/png")
            user_id: ID utente per organizzare i file per utente (opzionale)
        
        Returns:
            Path del file caricato (gs://bucket/path per GCS, path locale per fallback)
        """
        # Se user_id fornito E GCS è abilitato, organizza i file per utente
        # Struttura: users/{user_id}/books/... o users/{user_id}/covers/...
        # Se user_id non è disponibile o GCS non è abilitato, usa la struttura root: covers/... o books/...
        if user_id and self.gcs_enabled:
            if "books/" in destination_path:
                destination_path = f"users/{user_id}/books/{destination_path.split('books/')[-1]}"
            elif "covers/" in destination_path:
                destination_path = f"users/{user_id}/covers/{destination_path.split('covers/')[-1]}"
            else:
                destination_path = f"users/{user_id}/{destination_path}"
        
        if self.gcs_enabled:
            return self._upload_to_gcs(data, destination_path, content_type)
        else:
            return self._upload_to_local(data, destination_path)
    
    def _upload_to_gcs(
        self,
        data: bytes,
        destination_path: str,
        content_type: Optional[str]
    ) -> str:
        """Upload su Google Cloud Storage."""
        if self.bucket is None:
            self._init_gcs_client()
        
        blob = self.bucket.blob(destination_path)
        
        # Usa upload_from_file con BytesIO per garantire il content_type corretto
        from io import BytesIO
        data_io = BytesIO(data)
        
        # Imposta content_type prima dell'upload
        if content_type:
            blob.content_type = content_type
        
        # upload_from_file garantisce che il content_type sia rispettato
        blob.upload_from_file(data_io, content_type=content_type)
        
        gcs_path = f"gs://{self.bucket_name}/{destination_path}"
        print(f"[STORAGE] File caricato su GCS: {gcs_path} ({content_type or 'no content-type'})")
        return gcs_path
    
    def _upload_to_local(self, data: bytes, destination_path: str) -> str:
        """Upload su filesystem locale (fallback)."""
        # Determina la directory base in base al tipo
        if destination_path.startswith("books/"):
            local_dir = self.local_base_path / "books"
            relative_path = destination_path.replace("books/", "")
        elif destination_path.startswith("covers/"):
            local_dir = self.local_base_path / "sessions"
            relative_path = destination_path.replace("covers/", "")
        else:
            # Default: usa la directory base
            local_dir = self.local_base_path
            relative_path = destination_path
        
        local_dir.mkdir(parents=True, exist_ok=True)
        local_path = local_dir / relative_path
        
        with open(local_path, 'wb') as f:
            f.write(data)
        
        print(f"[STORAGE] File salvato localmente: {local_path}")
        return str(local_path)
    
    def download_file(self, source_path: str) -> bytes:
        """
        Scarica un file da GCS o locale.
        
        Args:
            source_path: Path del file (gs://bucket/path per GCS, path locale per fallback)
        
        Returns:
            Contenuto del file in bytes
        """
        # Se il path è gs://, prova sempre GCS prima (anche se gcs_enabled è False)
        # perché il file potrebbe essere stato salvato su GCS in precedenza
        if source_path.startswith("gs://"):
            if not self.gcs_enabled:
                # Prova a inizializzare GCS comunque (potrebbe essere solo un problema di config)
                try:
                    if GCS_AVAILABLE:
                        self._init_gcs_client()
                        self.gcs_enabled = self.client is not None and self.bucket is not None
                except Exception as e:
                    print(f"[STORAGE] WARN: Impossibile inizializzare GCS: {e}")
            
            if self.gcs_enabled:
                try:
                    return self._download_from_gcs(source_path)
                except Exception as e:
                    print(f"[STORAGE] Errore download da GCS: {e}")
                    # Non fare fallback locale per path GCS - il file è su GCS
                    raise FileNotFoundError(
                        f"File non trovato su GCS: {source_path}. "
                        f"Verifica che GCS_ENABLED=true e che le credenziali siano configurate."
                    )
            else:
                raise FileNotFoundError(
                    f"Path GCS richiesto ({source_path}) ma GCS non è abilitato. "
                    f"Imposta GCS_ENABLED=true nel .env"
                )
        
        # Path locale
        return self._download_from_local(source_path)
    
    def _download_from_gcs(self, gcs_path: str) -> bytes:
        """
        Download da Google Cloud Storage con retrocompatibilità.
        
        Cerca il file in diverse posizioni per gestire migrazione da struttura vecchia (covers/) 
        a struttura nuova (users/{user_id}/covers/).
        """
        if self.bucket is None:
            self._init_gcs_client()
        
        # Estrai path relativo da gs://bucket/path
        if gcs_path.startswith(f"gs://{self.bucket_name}/"):
            blob_path = gcs_path.replace(f"gs://{self.bucket_name}/", "")
        else:
            blob_path = gcs_path
        
        # Lista di path alternativi da provare (in ordine di priorità)
        paths_to_try = [blob_path]
        
        # Retrocompatibilità: se il path è users/{user_id}/covers/xxx, prova anche covers/xxx
        if blob_path.startswith("users/") and "/covers/" in blob_path:
            # Estrai solo il nome file
            filename = blob_path.split("/covers/")[-1]
            alt_path = f"covers/{filename}"
            if alt_path not in paths_to_try:
                paths_to_try.append(alt_path)
        # Retrocompatibilità: se il path è covers/xxx, prova anche users/{user_id}/covers/xxx
        # ma solo se abbiamo informazioni sull'utente (implementabile in futuro se necessario)
        elif blob_path.startswith("covers/"):
            # Manteniamo il path originale come prima scelta
            # Non proviamo in users/ perché richiederebbe di listare tutti gli utenti
            pass
        
        # Prova ogni path in ordine
        last_error = None
        for path in paths_to_try:
            try:
                blob = self.bucket.blob(path)
                if blob.exists():
                    print(f"[STORAGE] File trovato su GCS: {path} (path originale: {blob_path})")
                    return blob.download_as_bytes()
            except Exception as e:
                last_error = e
                continue
        
        # Se nessun path ha funzionato, solleva errore con informazioni utili
        if len(paths_to_try) > 1:
            raise FileNotFoundError(
                f"File non trovato su GCS: {gcs_path} (prova anche: {paths_to_try[1:]})"
            )
        else:
            raise FileNotFoundError(f"File non trovato su GCS: {gcs_path}")
    
    def _download_from_local(self, local_path: str) -> bytes:
        """Download da filesystem locale."""
        path = Path(local_path)
        
        # Se è un path relativo, prova a cercarlo nelle directory standard
        if not path.is_absolute():
            # Prova books/ o sessions/ o covers/
            if "books" in str(local_path) or local_path.endswith(".pdf"):
                path = self.local_base_path / "books" / Path(local_path).name
            elif "covers" in str(local_path) or local_path.endswith((".png", ".jpg", ".jpeg")):
                # Prova prima in sessions/, poi in covers/ se esiste
                path_sessions = self.local_base_path / "sessions" / Path(local_path).name
                path_covers = self.local_base_path / "covers" / Path(local_path).name
                if path_sessions.exists():
                    path = path_sessions
                elif path_covers.exists():
                    path = path_covers
                else:
                    path = path_sessions  # Usa questo per il messaggio di errore
        
        if not path.exists():
            raise FileNotFoundError(f"File non trovato localmente: {local_path} (cercato in: {path})")
        
        with open(path, 'rb') as f:
            return f.read()
    
    def get_signed_url(
        self,
        path: str,
        expiration_minutes: int = 15
    ) -> str:
        """
        Genera un URL firmato temporaneo per accedere a un file su GCS.
        
        Args:
            path: Path del file (gs://bucket/path o path relativo)
            expiration_minutes: Minuti di validità dell'URL (default: 15)
        
        Returns:
            URL firmato per GCS, o path locale per fallback
        """
        # Se il path è gs://, prova sempre GCS prima
        if path.startswith("gs://"):
            if not self.gcs_enabled:
                # Prova a inizializzare GCS comunque
                try:
                    if GCS_AVAILABLE:
                        self._init_gcs_client()
                        self.gcs_enabled = self.client is not None and self.bucket is not None
                except Exception as e:
                    print(f"[STORAGE] WARN: Impossibile inizializzare GCS per signed URL: {e}")
            
            if self.gcs_enabled:
                try:
                    return self._get_gcs_signed_url(path, expiration_minutes)
                except Exception as e:
                    print(f"[STORAGE] Errore generazione signed URL da GCS: {e}")
                    # Fallback: restituisci None per far gestire il download diretto
                    return None
        
        # Per locale, restituisci un path API relativo
        if path.startswith("gs://"):
            # Estrai solo il nome file
            filename = Path(path).name
            if "books" in path:
                return f"/api/files/books/{filename}"
            elif "covers" in path:
                return f"/api/files/covers/{filename}"
        return path
    
    def _get_gcs_signed_url(self, gcs_path: str, expiration_minutes: int) -> str:
        """Genera URL firmato GCS."""
        if self.bucket is None:
            self._init_gcs_client()
        
        # Estrai path relativo
        if gcs_path.startswith(f"gs://{self.bucket_name}/"):
            blob_path = gcs_path.replace(f"gs://{self.bucket_name}/", "")
        else:
            blob_path = gcs_path
        
        blob = self.bucket.blob(blob_path)
        
        # Ottimizzazione: non verifichiamo exists() qui per evitare chiamata HTTP extra
        # Se il file non esiste, l'errore verrà gestito quando si accede all'URL firmato
        url = blob.generate_signed_url(
            expiration=timedelta(minutes=expiration_minutes),
            method="GET"
        )
        return url
    
    def delete_file(self, path: str) -> bool:
        """
        Elimina un file da GCS o locale.
        
        Args:
            path: Path del file da eliminare
        
        Returns:
            True se eliminato con successo, False altrimenti
        """
        if path.startswith("gs://") and self.gcs_enabled:
            return self._delete_from_gcs(path)
        else:
            return self._delete_from_local(path)
    
    def _delete_from_gcs(self, gcs_path: str) -> bool:
        """Elimina file da GCS."""
        if self.bucket is None:
            self._init_gcs_client()
        
        # Estrai path relativo
        if gcs_path.startswith(f"gs://{self.bucket_name}/"):
            blob_path = gcs_path.replace(f"gs://{self.bucket_name}/", "")
        else:
            blob_path = gcs_path
        
        blob = self.bucket.blob(blob_path)
        
        if not blob.exists():
            return False
        
        blob.delete()
        print(f"[STORAGE] File eliminato da GCS: {gcs_path}")
        return True
    
    def _delete_from_local(self, local_path: str) -> bool:
        """Elimina file locale."""
        path = Path(local_path)
        
        if not path.is_absolute():
            # Prova a cercarlo nelle directory standard
            if "books" in str(local_path) or local_path.endswith(".pdf"):
                path = self.local_base_path / "books" / Path(local_path).name
            elif "covers" in str(local_path) or local_path.endswith((".png", ".jpg", ".jpeg")):
                path = self.local_base_path / "sessions" / Path(local_path).name
        
        if not path.exists():
            return False
        
        path.unlink()
        print(f"[STORAGE] File eliminato localmente: {local_path}")
        return True
    
    def file_exists(self, path: str) -> bool:
        """
        Verifica se un file esiste su GCS o locale.
        
        Args:
            path: Path del file da verificare
        
        Returns:
            True se il file esiste, False altrimenti
        """
        if path.startswith("gs://") and self.gcs_enabled:
            return self._gcs_file_exists(path)
        else:
            return self._local_file_exists(path)
    
    def _gcs_file_exists(self, gcs_path: str) -> bool:
        """Verifica esistenza file su GCS."""
        if self.bucket is None:
            self._init_gcs_client()
        
        # Estrai path relativo
        if gcs_path.startswith(f"gs://{self.bucket_name}/"):
            blob_path = gcs_path.replace(f"gs://{self.bucket_name}/", "")
        else:
            blob_path = gcs_path
        
        blob = self.bucket.blob(blob_path)
        return blob.exists()
    
    def _local_file_exists(self, local_path: str) -> bool:
        """Verifica esistenza file locale."""
        path = Path(local_path)
        
        if not path.is_absolute():
            # Prova a cercarlo nelle directory standard
            if "books" in str(local_path) or local_path.endswith(".pdf"):
                path = self.local_base_path / "books" / Path(local_path).name
            elif "covers" in str(local_path) or local_path.endswith((".png", ".jpg", ".jpeg")):
                path = self.local_base_path / "sessions" / Path(local_path).name
        
        return path.exists()


# Istanza globale del servizio storage
_storage_service: Optional[StorageService] = None


def get_storage_service() -> StorageService:
    """Restituisce l'istanza globale del servizio storage."""
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service

"""Script per migrare PDF e copertine esistenti da filesystem locale a Google Cloud Storage."""
import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from typing import List, Dict

# Aggiungi il percorso del backend al sys.path per importare i moduli dell'app
script_dir = Path(__file__).parent
backend_app_dir = script_dir.parent / "app"
sys.path.insert(0, str(backend_app_dir))

from app.services.storage_service import get_storage_service
from app.agent.session_store import get_session_store
from app.agent.session_store_helpers import get_all_sessions_async

# Carica variabili d'ambiente
env_path = script_dir.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)
load_dotenv()


async def migrate_pdfs(backend_dir: Path) -> Dict[str, int]:
    """Migra tutti i PDF da backend/books/ a GCS."""
    storage_service = get_storage_service()
    books_dir = backend_dir / "books"
    
    if not books_dir.exists():
        print("[MIGRATE PDFS] Directory books/ non trovata")
        return {"migrated": 0, "skipped": 0, "errors": 0}
    
    pdf_files = list(books_dir.glob("*.pdf"))
    print(f"[MIGRATE PDFS] Trovati {len(pdf_files)} PDF da migrare")
    
    migrated = 0
    skipped = 0
    errors = 0
    
    for pdf_file in pdf_files:
        try:
            filename = pdf_file.name
            gcs_path = f"gs://{storage_service.bucket_name}/books/{filename}"
            
            # Verifica se esiste già su GCS
            if storage_service.file_exists(gcs_path):
                print(f"[MIGRATE PDFS] Skip {filename} (già su GCS)")
                skipped += 1
                continue
            
            # Leggi e carica su GCS
            with open(pdf_file, 'rb') as f:
                pdf_data = f.read()
            
            uploaded_path = storage_service.upload_file(
                data=pdf_data,
                destination_path=f"books/{filename}",
                content_type="application/pdf"
            )
            
            migrated += 1
            print(f"[MIGRATE PDFS] Migrato: {filename} -> {uploaded_path}")
        
        except Exception as e:
            errors += 1
            print(f"[MIGRATE PDFS] ERRORE migrazione {pdf_file.name}: {e}")
    
    return {"migrated": migrated, "skipped": skipped, "errors": errors}


async def migrate_covers(backend_dir: Path) -> Dict[str, int]:
    """Migra tutte le copertine da backend/sessions/ a GCS."""
    storage_service = get_storage_service()
    sessions_dir = backend_dir / "sessions"
    
    if not sessions_dir.exists():
        print("[MIGRATE COVERS] Directory sessions/ non trovata")
        return {"migrated": 0, "skipped": 0, "errors": 0}
    
    cover_files = list(sessions_dir.glob("*_cover.png"))
    print(f"[MIGRATE COVERS] Trovate {len(cover_files)} copertine da migrare")
    
    migrated = 0
    skipped = 0
    errors = 0
    
    for cover_file in cover_files:
        try:
            filename = cover_file.name
            # Estrai session_id dal nome file (formato: {session_id}_cover.png)
            session_id = filename.replace("_cover.png", "")
            
            gcs_path = f"gs://{storage_service.bucket_name}/covers/{filename}"
            
            # Verifica se esiste già su GCS
            if storage_service.file_exists(gcs_path):
                print(f"[MIGRATE COVERS] Skip {filename} (già su GCS)")
                skipped += 1
                continue
            
            # Leggi e carica su GCS
            with open(cover_file, 'rb') as f:
                cover_data = f.read()
            
            uploaded_path = storage_service.upload_file(
                data=cover_data,
                destination_path=f"covers/{filename}",
                content_type="image/png"
            )
            
            migrated += 1
            print(f"[MIGRATE COVERS] Migrato: {filename} -> {uploaded_path}")
        
        except Exception as e:
            errors += 1
            print(f"[MIGRATE COVERS] ERRORE migrazione {cover_file.name}: {e}")
    
    return {"migrated": migrated, "skipped": skipped, "errors": errors}


async def update_mongodb_paths(backend_dir: Path) -> Dict[str, int]:
    """Aggiorna i path in MongoDB con i path GCS."""
    session_store = get_session_store()
    storage_service = get_storage_service()
    
    # Carica tutte le sessioni
    all_sessions = await get_all_sessions_async(session_store)
    print(f"[UPDATE PATHS] Trovate {len(all_sessions)} sessioni da aggiornare")
    
    updated_pdf = 0
    updated_covers = 0
    errors = 0
    
    for session_id, session in all_sessions.items():
        try:
            updated = False
            
            # Aggiorna path PDF se necessario
            if session.cover_image_path:
                # Se è un path locale, prova a convertirlo in GCS
                cover_path = Path(session.cover_image_path)
                if cover_path.is_absolute() or not session.cover_image_path.startswith("gs://"):
                    # È un path locale, cerca il file corrispondente su GCS
                    cover_filename = cover_path.name
                    if not cover_filename.endswith("_cover.png"):
                        # Prova a costruire il nome file atteso
                        cover_filename = f"{session_id}_cover.png"
                    
                    gcs_cover_path = f"gs://{storage_service.bucket_name}/covers/{cover_filename}"
                    
                    # Verifica che esista su GCS
                    if storage_service.file_exists(gcs_cover_path):
                        session.cover_image_path = gcs_cover_path
                        updated = True
                        updated_covers += 1
                        print(f"[UPDATE PATHS] Aggiornato cover path per {session_id}")
            
            # Per il PDF, non lo salviamo direttamente nella sessione,
            # ma viene costruito dinamicamente in session_to_library_entry
            # Quindi non serve aggiornare qui
            
            if updated:
                await session_store.save_session(session) if hasattr(session_store, 'save_session') else session_store._save_sessions()
        
        except Exception as e:
            errors += 1
            print(f"[UPDATE PATHS] ERRORE aggiornamento {session_id}: {e}")
    
    return {"updated_pdf": updated_pdf, "updated_covers": updated_covers, "errors": errors}


async def main():
    """Esegue la migrazione completa."""
    print("=" * 60)
    print("MIGRAZIONE FILE A GOOGLE CLOUD STORAGE")
    print("=" * 60)
    
    backend_dir = Path(__file__).parent.parent
    
    # Verifica configurazione GCS
    storage_service = get_storage_service()
    if not storage_service.gcs_enabled:
        print("[ERROR] GCS non abilitato. Imposta GCS_ENABLED=true nel .env")
        sys.exit(1)
    
    print(f"[INFO] Bucket: {storage_service.bucket_name}")
    print()
    
    # Migra PDF
    print("[STEP 1] Migrazione PDF...")
    pdf_stats = await migrate_pdfs(backend_dir)
    print(f"  Migrati: {pdf_stats['migrated']}")
    print(f"  Saltati: {pdf_stats['skipped']}")
    print(f"  Errori: {pdf_stats['errors']}")
    print()
    
    # Migra copertine
    print("[STEP 2] Migrazione copertine...")
    cover_stats = await migrate_covers(backend_dir)
    print(f"  Migrate: {cover_stats['migrated']}")
    print(f"  Saltate: {cover_stats['skipped']}")
    print(f"  Errori: {cover_stats['errors']}")
    print()
    
    # Aggiorna path in MongoDB
    print("[STEP 3] Aggiornamento path in MongoDB...")
    path_stats = await update_mongodb_paths(backend_dir)
    print(f"  PDF aggiornati: {path_stats['updated_pdf']}")
    print(f"  Copertine aggiornate: {path_stats['updated_covers']}")
    print(f"  Errori: {path_stats['errors']}")
    print()
    
    print("=" * 60)
    print("MIGRAZIONE COMPLETATA")
    print("=" * 60)
    print(f"Totale PDF migrati: {pdf_stats['migrated']}")
    print(f"Totale copertine migrate: {cover_stats['migrated']}")
    print(f"Totale path aggiornati: {path_stats['updated_covers']}")


if __name__ == "__main__":
    asyncio.run(main())

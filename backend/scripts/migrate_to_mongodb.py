"""Script per migrare le sessioni da FileSessionStore (JSON) a MongoDB."""
import asyncio
import os
import sys
import shutil
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Aggiungi il percorso del backend al sys.path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.agent.session_store import FileSessionStore, SessionData
from app.agent.mongo_session_store import MongoSessionStore
from pymongo.errors import BulkWriteError


async def migrate_sessions(
    source_store: FileSessionStore,
    target_store: MongoSessionStore,
    dry_run: bool = False,
) -> dict:
    """
    Migra tutte le sessioni da FileSessionStore a MongoSessionStore.
    
    Args:
        source_store: FileSessionStore da cui leggere
        target_store: MongoSessionStore in cui scrivere
        dry_run: Se True, non scrive su MongoDB, solo verifica
    
    Returns:
        Dict con statistiche della migrazione
    """
    # Connetti a MongoDB
    await target_store.connect()
    
    stats = {
        "total": len(source_store._sessions),
        "migrated": 0,
        "skipped": 0,
        "errors": 0,
        "error_details": [],
    }
    
    print(f"\n[MIGRATION] Trovate {stats['total']} sessioni da migrare")
    
    if dry_run:
        print("[MIGRATION] DRY RUN MODE - Nessun dato verrà scritto su MongoDB")
    
    for session_id, session in source_store._sessions.items():
        try:
            # Verifica se la sessione esiste già in MongoDB
            existing = await target_store.get_session(session_id)
            if existing:
                print(f"[MIGRATION] [SKIP] Sessione {session_id} già esistente in MongoDB, skip")
                stats["skipped"] += 1
                continue
            
            if not dry_run:
                # Migra la sessione
                await target_store.save_session(session)
                stats["migrated"] += 1
                print(f"[MIGRATION] [OK] Migrata sessione {session_id[:8]}... ({session.current_title or 'Senza titolo'})")
            else:
                stats["migrated"] += 1
                print(f"[MIGRATION] [DRY RUN] Sarebbe migrata sessione {session_id[:8]}... ({session.current_title or 'Senza titolo'})")
        
        except Exception as e:
            stats["errors"] += 1
            error_msg = f"Errore nella migrazione di {session_id}: {str(e)}"
            stats["error_details"].append(error_msg)
            print(f"[MIGRATION] [ERROR] {error_msg}")
    
    return stats


async def verify_migration(
    source_store: FileSessionStore,
    target_store: MongoSessionStore,
) -> dict:
    """
    Verifica che tutte le sessioni siano state migrate correttamente.
    
    Returns:
        Dict con risultati della verifica
    """
    await target_store.connect()
    
    verification = {
        "total_source": len(source_store._sessions),
        "total_target": 0,
        "matches": 0,
        "missing": [],
        "differences": [],
    }
    
    # Conta sessioni in MongoDB
    all_mongo_sessions = await target_store.get_all_sessions()
    verification["total_target"] = len(all_mongo_sessions)
    
    # Verifica ogni sessione
    for session_id, source_session in source_store._sessions.items():
        target_session = all_mongo_sessions.get(session_id)
        
        if not target_session:
            verification["missing"].append(session_id)
            continue
        
        # Verifica base: titolo, session_id
        if (source_session.current_title != target_session.current_title or
            source_session.session_id != target_session.session_id):
            verification["differences"].append({
                "session_id": session_id,
                "field": "title or session_id",
            })
            continue
        
        verification["matches"] += 1
    
    return verification


def backup_sessions_file(source_file: Path) -> Path:
    """Crea un backup del file .sessions.json."""
    if not source_file.exists():
        return None
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = source_file.parent / f".sessions.json.backup_{timestamp}"
    
    try:
        shutil.copy2(source_file, backup_path)
        print(f"[BACKUP] Backup creato: {backup_path}")
        return backup_path
    except Exception as e:
        print(f"[BACKUP] ERRORE nella creazione backup: {e}")
        return None


async def main():
    """Funzione principale dello script di migrazione."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Migra sessioni da JSON a MongoDB")
    parser.add_argument("--mongodb-uri", type=str, help="MongoDB connection string (default: da MONGODB_URI env)")
    parser.add_argument("--database", type=str, default="narrai", help="Nome database MongoDB")
    parser.add_argument("--collection", type=str, default="sessions", help="Nome collection MongoDB")
    parser.add_argument("--dry-run", action="store_true", help="Dry run: non scrive su MongoDB")
    parser.add_argument("--verify", action="store_true", help="Verifica la migrazione dopo il completamento")
    parser.add_argument("--no-backup", action="store_true", help="Non creare backup del file JSON")
    
    args = parser.parse_args()
    
    # Carica variabili d'ambiente
    env_path = Path(__file__).parent.parent.parent / ".env"
    load_dotenv(dotenv_path=env_path)
    load_dotenv()
    
    # Ottieni MongoDB URI
    mongo_uri = args.mongodb_uri or os.getenv("MONGODB_URI")
    if not mongo_uri:
        print("[ERROR] MONGODB_URI non specificata. Usa --mongodb-uri o imposta MONGODB_URI nel .env")
        sys.exit(1)
    
    print(f"[MIGRATION] MongoDB URI: {mongo_uri[:50]}...")
    print(f"[MIGRATION] Database: {args.database}, Collection: {args.collection}")
    
    # Carica sessioni da file
    print("\n[MIGRATION] Caricamento sessioni da file JSON...")
    source_store = FileSessionStore()
    print(f"[MIGRATION] Caricate {len(source_store._sessions)} sessioni da file")
    
    if len(source_store._sessions) == 0:
        print("[MIGRATION] Nessuna sessione da migrare. Uscita.")
        return
    
    # Backup del file originale (se richiesto)
    if not args.no_backup:
        source_file = source_store.file_path
        backup_path = backup_sessions_file(source_file)
        if backup_path:
            print(f"[MIGRATION] Backup disponibile in: {backup_path}")
    
    # Inizializza MongoDB store
    target_store = MongoSessionStore(mongo_uri, args.database, args.collection)
    
    try:
        # Esegui migrazione
        print("\n[MIGRATION] Avvio migrazione...")
        stats = await migrate_sessions(source_store, target_store, dry_run=args.dry_run)
        
        # Report migrazione
        print("\n" + "=" * 60)
        print("[MIGRATION] REPORT MIGRAZIONE")
        print("=" * 60)
        print(f"Totale sessioni: {stats['total']}")
        print(f"Migrate: {stats['migrated']}")
        print(f"Saltate (già esistenti): {stats['skipped']}")
        print(f"Errori: {stats['errors']}")
        
        if stats['errors'] > 0:
            print("\n[ERRORI]")
            for error in stats['error_details']:
                print(f"  - {error}")
        
        # Verifica se richiesta
        if args.verify and not args.dry_run:
            print("\n[MIGRATION] Verifica migrazione...")
            verification = await verify_migration(source_store, target_store)
            
            print("\n" + "=" * 60)
            print("[MIGRATION] REPORT VERIFICA")
            print("=" * 60)
            print(f"Sessioni nel file: {verification['total_source']}")
            print(f"Sessioni in MongoDB: {verification['total_target']}")
            print(f"Match: {verification['matches']}")
            print(f"Manche: {len(verification['missing'])}")
            print(f"Differenze: {len(verification['differences'])}")
            
            if verification['missing']:
                print("\n[MANCANTI]")
                for session_id in verification['missing'][:10]:  # Mostra max 10
                    print(f"  - {session_id}")
                if len(verification['missing']) > 10:
                    print(f"  ... e altri {len(verification['missing']) - 10}")
        
        if not args.dry_run:
            print("\n[MIGRATION] [SUCCESS] Migrazione completata con successo!")
            print(f"[MIGRATION] Le sessioni sono ora disponibili in MongoDB: {args.database}.{args.collection}")
        else:
            print("\n[MIGRATION] [SUCCESS] Dry run completato. Nessun dato modificato.")
    
    except Exception as e:
        print(f"\n[MIGRATION] [ERROR] ERRORE CRITICO: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    finally:
        # Disconnetti da MongoDB
        await target_store.disconnect()


if __name__ == "__main__":
    asyncio.run(main())

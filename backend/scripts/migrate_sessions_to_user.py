"""Script per assegnare tutte le sessioni esistenti senza user_id all'utente Marcello Gomitoni."""
import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Aggiungi il percorso del backend al sys.path per importare i moduli dell'app
script_dir = Path(__file__).parent
backend_app_dir = script_dir.parent / "app"
sys.path.insert(0, str(backend_app_dir))

from motor.motor_asyncio import AsyncIOMotorClient
from app.agent.user_store import get_user_store

# Carica variabili d'ambiente
env_path = script_dir.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)
load_dotenv()


async def migrate_sessions_to_user():
    """Assegna tutte le sessioni senza user_id all'utente Marcello Gomitoni."""
    mongo_uri = os.getenv("MONGODB_URI")
    if not mongo_uri:
        print("[ERROR] MONGODB_URI non configurato nel file .env")
        return
    
    # Trova user_id di Marcello Gomitoni
    user_store = get_user_store()
    await user_store.connect()
    
    try:
        user = await user_store.get_user_by_email("marcello.gomitoni@gmail.com")
        if not user:
            print("[ERROR] Utente marcello.gomitoni@gmail.com non trovato nel database")
            print("[INFO] Crea prima l'utente tramite registrazione")
            return
        
        user_id = user.id
        print(f"[INFO] Trovato utente: {user.email} (ID: {user_id})")
        
        # Connetti al database
        client = AsyncIOMotorClient(mongo_uri)
        db = client["narrai"]
        sessions_collection = db["sessions"]
        
        # Conta sessioni senza user_id
        count_query = {
            "$or": [
                {"user_id": {"$exists": False}},
                {"user_id": None}
            ]
        }
        
        count = await sessions_collection.count_documents(count_query)
        print(f"[INFO] Trovate {count} sessioni senza user_id da migrare")
        
        if count == 0:
            print("[INFO] Nessuna sessione da migrare")
            return
        
        # Conferma
        print(f"[INFO] Assegno {count} sessioni all'utente {user.email}")
        
        # Aggiorna tutte le sessioni senza user_id
        result = await sessions_collection.update_many(
            count_query,
            {"$set": {"user_id": user_id}}
        )
        
        print(f"[SUCCESS] Migrazione completata:")
        print(f"  - Sessioni aggiornate: {result.modified_count}")
        print(f"  - Utente proprietario: {user.email} ({user_id})")
        
        # Verifica che non ci siano più sessioni senza user_id
        remaining = await sessions_collection.count_documents(count_query)
        if remaining > 0:
            print(f"[WARNING] Rimangono {remaining} sessioni senza user_id")
        else:
            print("[SUCCESS] Tutte le sessioni hanno ora un user_id assegnato")
        
    except Exception as e:
        print(f"[ERROR] Errore durante la migrazione: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await user_store.disconnect()
        client.close()


if __name__ == "__main__":
    asyncio.run(migrate_sessions_to_user())

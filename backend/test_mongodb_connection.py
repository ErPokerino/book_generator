"""Script di test rapido per verificare la connessione MongoDB."""
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

# Carica .env dalla root del progetto
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)
load_dotenv()

async def test_mongodb():
    """Testa la connessione a MongoDB."""
    mongo_uri = os.getenv("MONGODB_URI")
    
    if not mongo_uri:
        print("[ERROR] MONGODB_URI non configurata nel .env")
        return False
    
    print(f"[TEST] Testing connessione a MongoDB...")
    print(f"       URI: {mongo_uri[:50]}...")
    
    try:
        client = AsyncIOMotorClient(mongo_uri)
        
        # Test ping
        result = await client.admin.command('ping')
        print(f"[OK] MongoDB ping OK: {result}")
        
        # Verifica database e collections
        db = client['narrai']
        collections = await db.list_collection_names()
        print(f"[OK] Database 'narrai' accessibile")
        print(f"     Collections: {collections}")
        
        # Conta documenti nella collection sessions (se esiste)
        if 'sessions' in collections:
            count = await db.sessions.count_documents({})
            print(f"[OK] Collection 'sessions' trovata: {count} documenti")
        else:
            print(f"[INFO] Collection 'sessions' non ancora creata (verrà creata al primo utilizzo)")
        
        client.close()
        print("\n[SUCCESS] Test MongoDB completato con successo!")
        return True
        
    except Exception as e:
        print(f"[ERROR] Errore nella connessione MongoDB: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    asyncio.run(test_mongodb())

"""Script per verificare lo stato degli utenti nel database."""
import asyncio
import os
import sys
from dotenv import load_dotenv

# Carica variabili d'ambiente
load_dotenv()

# Aggiungi il path del backend
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.agent.user_store import UserStore


async def check_users():
    """Verifica lo stato degli utenti specificati."""
    mongodb_uri = os.getenv("MONGODB_URI")
    
    if not mongodb_uri:
        print("[ERRORE] MONGODB_URI non configurato")
        return
    
    # Utenti da verificare
    users_to_check = [
        ("valeria echarry", "valeria.echarry@abstract.i"),
        ("valeria echarry", "valeria.echarry@abstract.it"),  # Prova anche con .it
        ("Francesco Malvezzi", "francesco.malvezzi@abstract.it"),
    ]
    
    user_store = UserStore(mongodb_uri)
    
    try:
        await user_store.connect()
        print("[OK] Connesso a MongoDB\n")
        
        for name, email in users_to_check:
            print(f"Verifica: {name} ({email})")
            print("-" * 60)
            
            user = await user_store.get_user_by_email(email)
            
            if user:
                print(f"[OK] Utente trovato!")
                print(f"   ID: {user.id}")
                print(f"   Nome: {user.name}")
                print(f"   Email: {user.email}")
                print(f"   Ruolo: {user.role}")
                print(f"   Attivo: {user.is_active}")
                print(f"   Email verificata: {'SI' if user.is_verified else 'NO'}")
                print(f"   Creato: {user.created_at}")
                print(f"   Aggiornato: {user.updated_at}")
                
                if user.verification_token:
                    print(f"   [WARN] Token di verifica presente (scade: {user.verification_expires})")
                else:
                    print(f"   Token di verifica: Nessuno")
                
                if not user.is_verified:
                    print(f"\n   [WARN] ATTENZIONE: Email NON verificata!")
                    if user.verification_token:
                        print(f"   [INFO] L'utente può richiedere un nuovo link di verifica")
            else:
                print(f"[ERRORE] Utente NON trovato nel database")
            
            print()
        
        await user_store.disconnect()
        
    except Exception as e:
        print(f"[ERRORE] {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(check_users())

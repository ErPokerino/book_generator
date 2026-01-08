#!/usr/bin/env python3
"""
Script per promuovere un utente ad admin.
Uso: python promote_user_to_admin.py <email>
"""
import os
import sys
from pathlib import Path

# Aggiungi il path del backend al PYTHONPATH
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv
load_dotenv()

from app.agent.user_store import get_user_store


async def promote_user_to_admin(email: str):
    """Promuove un utente ad admin."""
    user_store = get_user_store()
    
    # Connetti al database
    await user_store.connect()
    
    try:
        # Cerca l'utente per email
        user = await user_store.get_user_by_email(email)
        if not user:
            print(f"❌ Utente con email '{email}' non trovato.", file=sys.stderr)
            return False
        
        print(f"📧 Utente trovato: {user.name} ({user.email})", file=sys.stderr)
        print(f"   Ruolo attuale: {user.role}", file=sys.stderr)
        
        if user.role == "admin":
            print(f"✅ L'utente è già admin.", file=sys.stderr)
            return True
        
        # Aggiorna il ruolo
        success = await user_store.update_user(user.id, {"role": "admin"})
        if success:
            print(f"✅ Utente promosso ad admin con successo!", file=sys.stderr)
            return True
        else:
            print(f"❌ Errore nell'aggiornamento del ruolo.", file=sys.stderr)
            return False
    
    finally:
        await user_store.disconnect()


if __name__ == "__main__":
    import asyncio
    
    if len(sys.argv) < 2:
        print("Uso: python promote_user_to_admin.py <email>", file=sys.stderr)
        sys.exit(1)
    
    email = sys.argv[1].strip().lower()
    
    print(f"🔄 Promozione utente '{email}' ad admin...", file=sys.stderr)
    
    success = asyncio.run(promote_user_to_admin(email))
    
    if success:
        sys.exit(0)
    else:
        sys.exit(1)

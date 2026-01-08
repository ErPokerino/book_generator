#!/usr/bin/env python3
"""Script per verificare il conteggio libri per utente."""
import os
import sys
import asyncio
from pathlib import Path
from collections import defaultdict

backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv
load_dotenv()

from motor.motor_asyncio import AsyncIOMotorClient
from app.agent.user_store import get_user_store


async def debug_user_books():
    """Verifica il conteggio libri per utente."""
    mongo_uri = os.getenv("MONGODB_URI")
    if not mongo_uri:
        print("❌ MONGODB_URI non configurato", file=sys.stderr)
        return
    
    client = AsyncIOMotorClient(mongo_uri)
    db = client["narrai"]
    sessions_collection = db["sessions"]
    users_collection = db["users"]
    
    try:
        # Ottieni tutti gli utenti
        users = {}
        async for user_doc in users_collection.find({}):
            users[user_doc["_id"]] = {
                "name": user_doc.get("name", "N/A"),
                "email": user_doc.get("email", "N/A")
            }
        
        print(f"📊 Utenti trovati: {len(users)}", file=sys.stderr)
        for user_id, user_info in users.items():
            print(f"   - {user_id[:8]}... | {user_info['name']} | {user_info['email']}", file=sys.stderr)
        
        # Aggregazione MongoDB per contare libri per utente
        print(f"\n📚 Conto libri per utente con aggregazione MongoDB:", file=sys.stderr)
        pipeline = [
            {"$group": {
                "_id": "$user_id",
                "count": {"$sum": 1}
            }},
            {"$match": {"_id": {"$ne": None}}}
        ]
        
        books_per_user = {}
        async for result in sessions_collection.aggregate(pipeline):
            user_id = result["_id"]
            count = result["count"]
            books_per_user[user_id] = count
            user_info = users.get(user_id, {"name": "N/A", "email": "N/A"})
            print(f"   - {user_id[:8]}... | {user_info['name']} | {user_info['email']} | {count} libri", file=sys.stderr)
        
        print(f"\n📊 Riepilogo:", file=sys.stderr)
        print(f"   Utenti totali: {len(users)}", file=sys.stderr)
        print(f"   Utenti con libri: {len(books_per_user)}", file=sys.stderr)
        print(f"   Libri totali: {sum(books_per_user.values())}", file=sys.stderr)
        
        # Verifica sessioni senza user_id
        total_sessions = await sessions_collection.count_documents({})
        sessions_with_user = sum(books_per_user.values())
        sessions_without_user = total_sessions - sessions_with_user
        print(f"   Sessioni totali: {total_sessions}", file=sys.stderr)
        print(f"   Sessioni senza user_id: {sessions_without_user}", file=sys.stderr)
        
        # Mostra alcuni user_id dalle sessioni per debug
        print(f"\n🔍 Esempi di user_id nelle sessioni:", file=sys.stderr)
        async for doc in sessions_collection.find({}, {"_id": 1, "user_id": 1}).limit(5):
            print(f"   - Sessione {doc['_id'][:8]}... | user_id: {doc.get('user_id', 'None')}", file=sys.stderr)
    
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(debug_user_books())

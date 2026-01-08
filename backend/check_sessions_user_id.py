#!/usr/bin/env python3
"""Script per verificare quante sessioni hanno user_id."""
import os
import sys
import asyncio
from pathlib import Path

backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv
load_dotenv()

from motor.motor_asyncio import AsyncIOMotorClient


async def check_sessions():
    """Verifica quante sessioni hanno user_id."""
    mongo_uri = os.getenv("MONGODB_URI")
    if not mongo_uri:
        print("❌ MONGODB_URI non configurato", file=sys.stderr)
        return
    
    client = AsyncIOMotorClient(mongo_uri)
    db = client["narrai"]
    sessions_collection = db["sessions"]
    
    try:
        total = await sessions_collection.count_documents({})
        with_user = await sessions_collection.count_documents({
            "user_id": {"$exists": True, "$ne": None}
        })
        without_user = total - with_user
        
        print(f"📊 Statistiche Sessioni:", file=sys.stderr)
        print(f"   Totali: {total}", file=sys.stderr)
        print(f"   Con user_id: {with_user}", file=sys.stderr)
        print(f"   Senza user_id: {without_user}", file=sys.stderr)
        
        # Mostra alcuni esempi di sessioni senza user_id
        if without_user > 0:
            print(f"\n📋 Esempi di sessioni senza user_id:", file=sys.stderr)
            async for doc in sessions_collection.find(
                {"user_id": {"$exists": False}},
                {"_id": 1, "current_title": 1, "created_at": 1}
            ).limit(5):
                title = doc.get("current_title", "N/A")
                created = doc.get("created_at", "N/A")
                print(f"   - {doc['_id'][:8]}... | {title} | {created}", file=sys.stderr)
    
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(check_sessions())

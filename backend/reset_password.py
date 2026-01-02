"""Script per resettare password utente."""
import asyncio
import os
import sys
from passlib.context import CryptContext
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def reset_password(email: str, new_password: str):
    """Resetta la password di un utente."""
    new_hash = pwd_context.hash(new_password)
    
    client = AsyncIOMotorClient(os.getenv("MONGODB_URI"))
    db = client["narrai"]
    users = db["users"]
    
    result = await users.update_one(
        {"email": email.lower().strip()},
        {"$set": {"password_hash": new_hash}}
    )
    
    if result.modified_count > 0:
        print(f"Password aggiornata per: {email}")
    else:
        print(f"Utente non trovato: {email}")
    
    client.close()


if __name__ == "__main__":
    email = "marcello.gomitoni@gmail.com"
    new_password = "warhammer"
    
    asyncio.run(reset_password(email, new_password))

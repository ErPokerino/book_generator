"""Middleware per autenticazione e autorizzazione."""
import os
import sys
from typing import Optional
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status, Request, Cookie
from fastapi.security import HTTPBearer
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from app.agent.user_store import get_user_store, UserStore
from app.models import User

# Serializer per session token
SESSION_SECRET = os.getenv("SESSION_SECRET", "change-me-in-production-secret-key")
SESSION_EXPIRE_DAYS = int(os.getenv("SESSION_EXPIRE_DAYS", "7"))

serializer = URLSafeTimedSerializer(SESSION_SECRET)
security = HTTPBearer(auto_error=False)

# MongoDB collection per sessioni auth
_auth_sessions_collection = None


async def get_auth_sessions_collection():
    """Ottiene la collection per le sessioni auth."""
    global _auth_sessions_collection
    if _auth_sessions_collection is None:
        from motor.motor_asyncio import AsyncIOMotorClient
        mongo_uri = os.getenv("MONGODB_URI")
        if not mongo_uri:
            raise ValueError("MONGODB_URI non configurato")
        client = AsyncIOMotorClient(mongo_uri)
        db = client.get_database("narrai")
        _auth_sessions_collection = db["sessions_auth"]
    return _auth_sessions_collection


async def create_session(user_id: str) -> str:
    """
    Crea una nuova sessione per l'utente.
    
    Returns:
        session_id (token da mettere nel cookie)
    """
    import uuid
    session_id = str(uuid.uuid4())
    expires_at = datetime.utcnow() + timedelta(days=SESSION_EXPIRE_DAYS)
    
    sessions_collection = await get_auth_sessions_collection()
    await sessions_collection.insert_one({
        "session_id": session_id,
        "user_id": user_id,
        "created_at": datetime.utcnow(),
        "expires_at": expires_at,
    })
    
    return session_id


async def get_user_from_session(auth_session_id: Optional[str] = Cookie(None, alias="session_id")) -> Optional[User]:
    """
    Recupera l'utente dalla sessione.
    
    Returns:
        User se sessione valida, None altrimenti
    """
    if not auth_session_id:
        return None
    
    sessions_collection = await get_auth_sessions_collection()
    session_doc = await sessions_collection.find_one({
        "session_id": auth_session_id,
        "expires_at": {"$gt": datetime.utcnow()}
    })
    
    if not session_doc:
        return None
    
    user_store = get_user_store()
    user = await user_store.get_user_by_id(session_doc["user_id"])
    return user


async def delete_session(session_id: str):
    """Elimina una sessione."""
    sessions_collection = await get_auth_sessions_collection()
    await sessions_collection.delete_one({"session_id": session_id})


async def get_current_user(
    auth_session_id: Optional[str] = Cookie(None, alias="session_id")
) -> User:
    """
    Dependency FastAPI per ottenere l'utente corrente.
    Solleva HTTPException se non autenticato.
    """
    user = await get_user_from_session(auth_session_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Non autenticato",
            headers={"WWW-Authenticate": "Cookie"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Utente disattivato",
        )
    return user


async def get_current_user_optional(
    auth_session_id: Optional[str] = Cookie(None, alias="session_id")
) -> Optional[User]:
    """
    Dependency FastAPI per ottenere l'utente corrente (opzionale).
    Restituisce None se non autenticato (non solleva eccezione).
    """
    return await get_user_from_session(auth_session_id)


async def require_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency per verificare che l'utente sia admin.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accesso negato: richiesto ruolo admin",
        )
    return current_user

"""Dipendenze comuni per i router API."""
from app.agent.session_store import get_session_store

def get_session_store_dep():
    """Dependency per ottenere il session store."""
    return get_session_store()

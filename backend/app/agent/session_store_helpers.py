"""Helper functions per gestire session_store in modo compatibile sync/async."""
from typing import Optional, Dict, TYPE_CHECKING
from app.agent.session_store import SessionStore, SessionData
from app.models import SubmissionRequest, QuestionAnswer

if TYPE_CHECKING:
    from app.agent.mongo_session_store import MongoSessionStore


async def get_session_async(session_store: SessionStore, session_id: str, user_id: Optional[str] = None) -> Optional[SessionData]:
    """Helper per ottenere una sessione in modo async-compatibile."""
    if hasattr(session_store, 'get_session') and callable(getattr(session_store, 'get_session', None)):
        # Se è MongoSessionStore, usa await con user_id
        if hasattr(session_store, 'connect'):
            return await session_store.get_session(session_id, user_id)
        # Altrimenti è FileSessionStore, chiamata sync (non supporta user_id per ora)
        session = session_store.get_session(session_id)
        # Verifica ownership manualmente per FileSessionStore
        if session and user_id and session.user_id != user_id:
            return None
        return session
    return None


async def create_session_async(
    session_store: SessionStore,
    session_id: str,
    form_data: SubmissionRequest,
    question_answers: list[QuestionAnswer],
    user_id: Optional[str] = None,
) -> SessionData:
    """Helper per creare una sessione in modo async-compatibile."""
    if hasattr(session_store, 'connect'):
        # MongoSessionStore
        return await session_store.create_session(session_id, form_data, question_answers, user_id=user_id)
    else:
        # FileSessionStore (user_id gestito nel costruttore)
        session = session_store.create_session(session_id, form_data, question_answers)
        if user_id:
            session.user_id = user_id
        return session


async def update_draft_async(
    session_store: SessionStore,
    session_id: str,
    draft_text: str,
    version: Optional[int] = None,
    title: Optional[str] = None,
) -> SessionData:
    """Helper per aggiornare una bozza in modo async-compatibile."""
    if hasattr(session_store, 'connect'):
        return await session_store.update_draft(session_id, draft_text, version, title)
    else:
        return session_store.update_draft(session_id, draft_text, version, title)


async def validate_session_async(session_store: SessionStore, session_id: str) -> SessionData:
    """Helper per validare una sessione in modo async-compatibile."""
    if hasattr(session_store, 'connect'):
        return await session_store.validate_session(session_id)
    else:
        return session_store.validate_session(session_id)


async def save_generated_questions_async(
    session_store: SessionStore,
    session_id: str,
    questions: list,
) -> SessionData:
    """Helper per salvare domande generate in modo async-compatibile."""
    if hasattr(session_store, 'connect'):
        return await session_store.save_generated_questions(session_id, questions)
    else:
        return session_store.save_generated_questions(session_id, questions)


async def update_outline_async(
    session_store: SessionStore,
    session_id: str,
    outline_text: str,
    allow_if_writing: bool = False,
    version: Optional[int] = None,
) -> SessionData:
    """Helper per aggiornare outline in modo async-compatibile."""
    if hasattr(session_store, 'connect'):
        return await session_store.update_outline(session_id, outline_text, allow_if_writing, version)
    else:
        return session_store.update_outline(session_id, outline_text, allow_if_writing, version)


async def get_all_sessions_async(session_store: SessionStore, user_id: Optional[str] = None) -> Dict[str, SessionData]:
    """Helper per ottenere tutte le sessioni in modo async-compatibile."""
    if hasattr(session_store, 'get_all_sessions'):
        # MongoSessionStore
        return await session_store.get_all_sessions(user_id=user_id)
    else:
        # FileSessionStore - _sessions è un dict normale, filtra per user_id
        all_sessions = session_store._sessions
        if user_id:
            return {sid: sess for sid, sess in all_sessions.items() if sess.user_id == user_id}
        return all_sessions

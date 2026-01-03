"""Helper functions per gestire session_store in modo compatibile sync/async."""
from typing import Optional, Dict, TYPE_CHECKING, Any
from datetime import datetime
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


async def update_writing_progress_async(
    session_store: SessionStore,
    session_id: str,
    current_step: int,
    total_steps: int,
    current_section_name: Optional[str] = None,
    is_complete: bool = False,
    is_paused: bool = False,
    error: Optional[str] = None,
    total_pages: Optional[int] = None,
    completed_chapters_count: Optional[int] = None,
) -> SessionData:
    """Helper per aggiornare il progresso della scrittura in modo async-compatibile."""
    if hasattr(session_store, 'connect'):
        # MongoSessionStore - metodo async
        return await session_store.update_writing_progress(
            session_id, current_step, total_steps, current_section_name, is_complete, is_paused, error,
            total_pages=total_pages, completed_chapters_count=completed_chapters_count
        )
    else:
        # FileSessionStore - metodo sync
        return session_store.update_writing_progress(
            session_id, current_step, total_steps, current_section_name, is_complete, is_paused, error,
            total_pages=total_pages, completed_chapters_count=completed_chapters_count
        )


async def start_chapter_timing_async(
    session_store: SessionStore,
    session_id: str,
    start_time: Optional[datetime] = None,
) -> SessionData:
    """Helper per iniziare il tracciamento del tempo capitolo in modo async-compatibile."""
    if hasattr(session_store, 'connect'):
        # MongoSessionStore - metodo async
        return await session_store.start_chapter_timing(session_id, start_time)
    else:
        # FileSessionStore - metodo sync
        return session_store.start_chapter_timing(session_id, start_time)


async def end_chapter_timing_async(
    session_store: SessionStore,
    session_id: str,
    end_time: Optional[datetime] = None,
) -> SessionData:
    """Helper per terminare il tracciamento del tempo capitolo in modo async-compatibile."""
    if hasattr(session_store, 'connect'):
        # MongoSessionStore - metodo async
        return await session_store.end_chapter_timing(session_id, end_time)
    else:
        # FileSessionStore - metodo sync
        return session_store.end_chapter_timing(session_id, end_time)


async def update_critique_async(
    session_store: SessionStore,
    session_id: str,
    critique: Dict,
) -> SessionData:
    """Helper per aggiornare la critica in modo async-compatibile."""
    if hasattr(session_store, 'connect'):
        # MongoSessionStore - metodo async
        return await session_store.update_critique(session_id, critique)
    else:
        # FileSessionStore - metodo sync
        return session_store.update_critique(session_id, critique)


async def update_critique_status_async(
    session_store: SessionStore,
    session_id: str,
    status: str,
    error: Optional[str] = None,
) -> SessionData:
    """Helper per aggiornare lo stato della critica in modo async-compatibile."""
    if hasattr(session_store, 'connect'):
        # MongoSessionStore - metodo async
        return await session_store.update_critique_status(session_id, status, error)
    else:
        # FileSessionStore - metodo sync
        return session_store.update_critique_status(session_id, status, error)


async def update_writing_times_async(
    session_store: SessionStore,
    session_id: str,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> SessionData:
    """Helper per aggiornare i timestamp di scrittura in modo async-compatibile."""
    if hasattr(session_store, 'connect'):
        return await session_store.update_writing_times(session_id, start_time, end_time)
    else:
        return session_store.update_writing_times(session_id, start_time, end_time)


async def update_cover_image_path_async(
    session_store: SessionStore,
    session_id: str,
    cover_image_path: str,
) -> SessionData:
    """Helper per aggiornare il path della copertina in modo async-compatibile."""
    if hasattr(session_store, 'connect'):
        return await session_store.update_cover_image_path(session_id, cover_image_path)
    else:
        return session_store.update_cover_image_path(session_id, cover_image_path)


async def update_book_chapter_async(
    session_store: SessionStore,
    session_id: str,
    chapter_title: str,
    chapter_content: str,
    section_index: int,
) -> SessionData:
    """Helper per aggiornare un capitolo in modo async-compatibile."""
    if hasattr(session_store, 'connect'):
        return await session_store.update_book_chapter(session_id, chapter_title, chapter_content, section_index)
    else:
        return session_store.update_book_chapter(session_id, chapter_title, chapter_content, section_index)


async def pause_writing_async(
    session_store: SessionStore,
    session_id: str,
    current_step: int,
    total_steps: int,
    current_section_name: Optional[str],
    error_msg: str,
) -> SessionData:
    """Helper per mettere in pausa la scrittura in modo async-compatibile."""
    if hasattr(session_store, 'connect'):
        return await session_store.pause_writing(session_id, current_step, total_steps, current_section_name, error_msg)
    else:
        return session_store.pause_writing(session_id, current_step, total_steps, current_section_name, error_msg)


async def resume_writing_async(
    session_store: SessionStore,
    session_id: str,
) -> SessionData:
    """Helper per riprendere la scrittura in modo async-compatibile."""
    if hasattr(session_store, 'connect'):
        return await session_store.resume_writing(session_id)
    else:
        return session_store.resume_writing(session_id)


async def delete_session_async(
    session_store: SessionStore,
    session_id: str,
) -> bool:
    """Helper per eliminare una sessione in modo async-compatibile."""
    if hasattr(session_store, 'connect'):
        # MongoSessionStore - metodo async
        return await session_store.delete_session(session_id)
    else:
        # FileSessionStore - metodo sync
        return session_store.delete_session(session_id)


async def get_all_sessions_async(session_store: SessionStore, user_id: Optional[str] = None, 
                                 fields: Optional[list] = None, status: Optional[str] = None,
                                 llm_model: Optional[str] = None, genre: Optional[str] = None) -> Dict[str, SessionData]:
    """Helper per ottenere tutte le sessioni in modo async-compatibile."""
    if hasattr(session_store, 'get_all_sessions'):
        # MongoSessionStore
        return await session_store.get_all_sessions(user_id=user_id, fields=fields, 
                                                   status=status, llm_model=llm_model, genre=genre)
    else:
        # FileSessionStore - _sessions è un dict normale, filtra per user_id e altri filtri
        all_sessions = session_store._sessions
        result = all_sessions
        if user_id:
            result = {sid: sess for sid, sess in result.items() if sess.user_id == user_id}
        if llm_model:
            result = {sid: sess for sid, sess in result.items() 
                     if sess.form_data and sess.form_data.llm_model == llm_model}
        if genre:
            result = {sid: sess for sid, sess in result.items() 
                     if sess.form_data and sess.form_data.genre == genre}
        if status and status != "all":
            result = {sid: sess for sid, sess in result.items() if sess.get_status() == status}
        return result

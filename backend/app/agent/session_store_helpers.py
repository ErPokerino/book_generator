"""Helper async-compatibili sopra il session store sincrono su file."""
from typing import Optional, Dict, Any
from datetime import datetime
from app.agent.session_store import SessionStore, SessionData
from app.models import SubmissionRequest, QuestionAnswer


async def get_session_async(session_store: SessionStore, session_id: str, user_id: Optional[str] = None) -> Optional[SessionData]:
    """Restituisce una sessione, con verifica ownership opzionale."""
    session = session_store.get_session(session_id)
    if session and user_id and session.user_id != user_id:
        return None
    return session


async def create_session_async(
    session_store: SessionStore,
    session_id: str,
    form_data: SubmissionRequest,
    question_answers: list[QuestionAnswer],
    user_id: Optional[str] = None,
) -> SessionData:
    """Crea una nuova sessione."""
    return session_store.create_session(session_id, form_data, question_answers, user_id=user_id)


async def save_session_async(session_store: SessionStore, session: SessionData) -> SessionData:
    """Salva una sessione."""
    return session_store.save_session(session)


async def update_draft_async(
    session_store: SessionStore,
    session_id: str,
    draft_text: str,
    version: Optional[int] = None,
    title: Optional[str] = None,
    character_profiles: Optional[str] = None,
) -> SessionData:
    """Aggiorna la bozza di una sessione."""
    return session_store.update_draft(session_id, draft_text, version, title, character_profiles)


async def validate_session_async(session_store: SessionStore, session_id: str) -> SessionData:
    """Marca una sessione come validata."""
    return session_store.validate_session(session_id)


async def save_generated_questions_async(
    session_store: SessionStore,
    session_id: str,
    questions: list,
) -> SessionData:
    """Salva le domande generate per una sessione."""
    return session_store.save_generated_questions(session_id, questions)


async def update_outline_async(
    session_store: SessionStore,
    session_id: str,
    outline_text: str,
    allow_if_writing: bool = False,
    version: Optional[int] = None,
) -> SessionData:
    """Aggiorna l'outline di una sessione."""
    return session_store.update_outline(session_id, outline_text, allow_if_writing, version)


async def update_questions_progress_async(
    session_store: SessionStore,
    session_id: str,
    progress_dict: Dict[str, Any],
) -> SessionData:
    """Aggiorna il progresso generazione domande."""
    return session_store.update_questions_progress(session_id, progress_dict)


async def update_draft_progress_async(
    session_store: SessionStore,
    session_id: str,
    progress_dict: Dict[str, Any],
) -> SessionData:
    """Aggiorna il progresso generazione bozza."""
    return session_store.update_draft_progress(session_id, progress_dict)


async def update_outline_progress_async(
    session_store: SessionStore,
    session_id: str,
    progress_dict: Dict[str, Any],
) -> SessionData:
    """Aggiorna il progresso generazione outline."""
    return session_store.update_outline_progress(session_id, progress_dict)


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
    writing_time_minutes: Optional[float] = None,
) -> SessionData:
    """Aggiorna il progresso della scrittura."""
    return session_store.update_writing_progress(
        session_id, current_step, total_steps, current_section_name, is_complete, is_paused, error,
        total_pages=total_pages,
        completed_chapters_count=completed_chapters_count,
        writing_time_minutes=writing_time_minutes,
    )


async def set_estimated_cost_async(
    session_store: SessionStore,
    session_id: str,
    estimated_cost: float,
) -> bool:
    """Aggiorna estimated_cost in writing_progress."""
    return session_store.set_estimated_cost(session_id, estimated_cost)


async def start_chapter_timing_async(
    session_store: SessionStore,
    session_id: str,
    start_time: Optional[datetime] = None,
) -> SessionData:
    """Inizia il tracciamento del tempo capitolo."""
    return session_store.start_chapter_timing(session_id, start_time)


async def end_chapter_timing_async(
    session_store: SessionStore,
    session_id: str,
    end_time: Optional[datetime] = None,
) -> SessionData:
    """Termina il tracciamento del tempo capitolo."""
    return session_store.end_chapter_timing(session_id, end_time)


async def update_critique_async(
    session_store: SessionStore,
    session_id: str,
    critique: Dict,
) -> SessionData:
    """Aggiorna la critica di una sessione."""
    return session_store.update_critique(session_id, critique)


async def update_critique_status_async(
    session_store: SessionStore,
    session_id: str,
    status: str,
    error: Optional[str] = None,
) -> SessionData:
    """Aggiorna lo stato della critica."""
    return session_store.update_critique_status(session_id, status, error)


async def update_writing_times_async(
    session_store: SessionStore,
    session_id: str,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> SessionData:
    """Aggiorna i timestamp di scrittura."""
    return session_store.update_writing_times(session_id, start_time, end_time)


async def update_cover_image_path_async(
    session_store: SessionStore,
    session_id: str,
    cover_image_path: str,
) -> SessionData:
    """Aggiorna il path della copertina."""
    return session_store.update_cover_image_path(session_id, cover_image_path)


async def update_book_chapter_async(
    session_store: SessionStore,
    session_id: str,
    chapter_title: str,
    chapter_content: str,
    section_index: int,
) -> SessionData:
    """Aggiunge o aggiorna un capitolo completato."""
    return session_store.update_book_chapter(session_id, chapter_title, chapter_content, section_index)


async def pause_writing_async(
    session_store: SessionStore,
    session_id: str,
    current_step: int,
    total_steps: int,
    current_section_name: Optional[str],
    error_msg: str,
) -> SessionData:
    """Mette in pausa la scrittura."""
    return session_store.pause_writing(session_id, current_step, total_steps, current_section_name, error_msg)


async def resume_writing_async(
    session_store: SessionStore,
    session_id: str,
) -> SessionData:
    """Riprende la scrittura rimuovendo lo stato di pausa."""
    return session_store.resume_writing(session_id)


async def delete_session_async(
    session_store: SessionStore,
    session_id: str,
) -> bool:
    """Elimina una sessione."""
    return session_store.delete_session(session_id)


async def update_token_usage_async(
    session_store: SessionStore,
    session_id: str,
    phase: str,
    input_tokens: int,
    output_tokens: int,
    model: str,
) -> bool:
    """Aggiorna il conteggio token per una fase."""
    return session_store.update_token_usage(session_id, phase, input_tokens, output_tokens, model)


async def set_real_cost_async(
    session_store: SessionStore,
    session_id: str,
    real_cost_eur: float,
) -> bool:
    """Imposta il costo reale calcolato dai token effettivi."""
    return session_store.set_real_cost(session_id, real_cost_eur)


async def get_all_sessions_async(session_store: SessionStore, user_id: Optional[str] = None,
                                 fields: Optional[list] = None, status: Optional[str] = None,
                                 llm_model: Optional[str] = None, genre: Optional[str] = None) -> Dict[str, SessionData]:
    """Restituisce tutte le sessioni, con filtri opzionali."""
    if hasattr(session_store, 'get_all_sessions'):
        return session_store.get_all_sessions(user_id=user_id, fields=fields,
                                              status=status, llm_model=llm_model, genre=genre)
    # Fallback per store in-memory nei test: filtra il dict interno
    result = dict(session_store._sessions)
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

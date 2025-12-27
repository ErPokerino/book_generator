from typing import Optional, Dict, Any
from app.models import SubmissionRequest, QuestionAnswer


class SessionData:
    """Dati di una sessione."""
    def __init__(
        self,
        session_id: str,
        form_data: SubmissionRequest,
        question_answers: list[QuestionAnswer],
    ):
        self.session_id = session_id
        self.form_data = form_data
        self.question_answers = question_answers
        self.draft_history: list[Dict[str, Any]] = []  # Lista di bozze con version e text
        self.current_draft: Optional[str] = None
        self.current_version: int = 0
        self.validated: bool = False


class SessionStore:
    """Store in-memory per le sessioni."""
    
    def __init__(self):
        self._sessions: Dict[str, SessionData] = {}
    
    def create_session(
        self,
        session_id: str,
        form_data: SubmissionRequest,
        question_answers: list[QuestionAnswer],
    ) -> SessionData:
        """Crea una nuova sessione."""
        session = SessionData(session_id, form_data, question_answers)
        self._sessions[session_id] = session
        return session
    
    def get_session(self, session_id: str) -> Optional[SessionData]:
        """Recupera una sessione esistente."""
        return self._sessions.get(session_id)
    
    def update_draft(
        self,
        session_id: str,
        draft_text: str,
        version: Optional[int] = None,
    ) -> SessionData:
        """Aggiorna la bozza corrente di una sessione."""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Sessione {session_id} non trovata")
        
        if version is None:
            session.current_version += 1
            version = session.current_version
        else:
            session.current_version = version
        
        session.current_draft = draft_text
        session.draft_history.append({
            "version": version,
            "text": draft_text,
            "timestamp": None,  # Potrebbe essere aggiunto datetime se necessario
        })
        
        return session
    
    def validate_session(self, session_id: str) -> SessionData:
        """Marca una sessione come validata."""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Sessione {session_id} non trovata")
        
        session.validated = True
        return session
    
    def delete_session(self, session_id: str) -> bool:
        """Elimina una sessione."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False


# Istanza globale del session store
_session_store = SessionStore()


def get_session_store() -> SessionStore:
    """Restituisce l'istanza globale del session store."""
    return _session_store


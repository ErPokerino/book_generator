import json
import os
import sys
from pathlib import Path
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
        self.current_title: Optional[str] = None
        self.current_version: int = 0
        self.validated: bool = False
        self.current_outline: Optional[str] = None
        self.outline_version: int = 0
        self.book_chapters: list[Dict[str, Any]] = []  # Lista di capitoli completati
        self.writing_progress: Optional[Dict[str, Any]] = None  # Stato di avanzamento scrittura
        self.cover_image_path: Optional[str] = None  # Path dell'immagine copertina
        self.literary_critique: Optional[Dict[str, Any]] = None  # Valutazione critica del libro
        self.critique_status: Optional[str] = None  # pending|running|completed|failed
        self.critique_error: Optional[str] = None  # Dettaglio errore se failed
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte SessionData in un dizionario per la serializzazione JSON."""
        return {
            "session_id": self.session_id,
            "form_data": self.form_data.model_dump(),
            "question_answers": [qa.model_dump() for qa in self.question_answers],
            "draft_history": self.draft_history,
            "current_draft": self.current_draft,
            "current_title": self.current_title,
            "current_version": self.current_version,
            "validated": self.validated,
            "current_outline": self.current_outline,
            "outline_version": self.outline_version,
            "book_chapters": self.book_chapters,
            "writing_progress": self.writing_progress,
            "cover_image_path": self.cover_image_path,
            "literary_critique": self.literary_critique,
            "critique_status": self.critique_status,
            "critique_error": self.critique_error,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionData":
        """Crea SessionData da un dizionario (deserializzazione JSON)."""
        session = cls(
            session_id=data["session_id"],
            form_data=SubmissionRequest(**data["form_data"]),
            question_answers=[QuestionAnswer(**qa) for qa in data["question_answers"]],
        )
        session.draft_history = data.get("draft_history", [])
        session.current_draft = data.get("current_draft")
        session.current_title = data.get("current_title")
        session.current_version = data.get("current_version", 0)
        session.validated = data.get("validated", False)
        session.current_outline = data.get("current_outline")
        session.outline_version = data.get("outline_version", 0)
        session.book_chapters = data.get("book_chapters", [])
        session.writing_progress = data.get("writing_progress")
        session.cover_image_path = data.get("cover_image_path")
        session.literary_critique = data.get("literary_critique")
        session.critique_status = data.get("critique_status")
        session.critique_error = data.get("critique_error")
        return session


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
        title: Optional[str] = None,
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
        if title is not None:
            session.current_title = title
        session.draft_history.append({
            "version": version,
            "text": draft_text,
            "title": title,
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
    
    def update_outline(
        self,
        session_id: str,
        outline_text: str,
    ) -> SessionData:
        """Aggiorna l'outline corrente di una sessione."""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Sessione {session_id} non trovata")
        
        session.current_outline = outline_text
        session.outline_version += 1
        
        return session
    
    def delete_session(self, session_id: str) -> bool:
        """Elimina una sessione."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False
    
    def update_writing_progress(
        self,
        session_id: str,
        current_step: int,
        total_steps: int,
        current_section_name: Optional[str] = None,
        is_complete: bool = False,
        error: Optional[str] = None,
    ) -> SessionData:
        """Aggiorna lo stato di avanzamento della scrittura del romanzo."""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Sessione {session_id} non trovata")
        
        session.writing_progress = {
            "session_id": session_id,
            "current_step": current_step,
            "total_steps": total_steps,
            "current_section_name": current_section_name,
            "is_complete": is_complete,
            "error": error,
        }
        
        return session
    
    def update_book_chapter(
        self,
        session_id: str,
        chapter_title: str,
        chapter_content: str,
        section_index: int,
    ) -> SessionData:
        """Aggiunge o aggiorna un capitolo completato."""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Sessione {session_id} non trovata")
        
        # Cerca se esiste già un capitolo con questo section_index
        chapter_dict = {
            "title": chapter_title,
            "content": chapter_content,
            "section_index": section_index,
        }
        
        # Rimuovi eventuale capitolo esistente con lo stesso section_index
        session.book_chapters = [
            ch for ch in session.book_chapters 
            if ch.get("section_index") != section_index
        ]
        
        # Aggiungi il nuovo capitolo
        session.book_chapters.append(chapter_dict)
        
        # Ordina per section_index
        session.book_chapters.sort(key=lambda x: x.get("section_index", 0))
        
        return session
    
    def update_cover_image_path(
        self,
        session_id: str,
        cover_image_path: str,
    ) -> SessionData:
        """Aggiorna il path dell'immagine copertina."""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Sessione {session_id} non trovata")
        
        session.cover_image_path = cover_image_path
        return session
    
    def update_critique(
        self,
        session_id: str,
        critique: Dict[str, Any],
    ) -> SessionData:
        """Aggiorna la valutazione critica del libro."""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Sessione {session_id} non trovata")
        
        session.literary_critique = critique
        session.critique_status = "completed"
        session.critique_error = None
        return session

    def update_critique_status(
        self,
        session_id: str,
        status: str,
        error: Optional[str] = None,
    ) -> SessionData:
        """Aggiorna lo stato della critica (pending|running|completed|failed) e opzionale errore."""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Sessione {session_id} non trovata")

        session.critique_status = status
        session.critique_error = error
        # Se fallita, non cancelliamo automaticamente una critica già presente (utile per storico/debug)
        return session


class FileSessionStore(SessionStore):
    """Store con persistenza su file JSON per le sessioni."""
    
    def __init__(self, file_path: Optional[Path] = None):
        """Inizializza il file store e carica le sessioni esistenti."""
        super().__init__()
        if file_path is None:
            # Default: .sessions.json nella directory backend (file nascosto per evitare reload di uvicorn)
            # Usa Path.cwd() se stiamo eseguendo dal backend, altrimenti cerca di risolvere relativamente al file
            current_file = Path(__file__).resolve()
            backend_dir = current_file.parent.parent.parent
            file_path = backend_dir / ".sessions.json"
        
        self.file_path = file_path
        print(f"[FileSessionStore] Inizializzato. File path: {self.file_path}", file=sys.stderr)
        self._load_sessions()
    
    def _load_sessions(self):
        """Carica le sessioni dal file JSON."""
        if not self.file_path.exists():
            print(f"[FileSessionStore] File {self.file_path} non esiste, inizializzo store vuoto")
            return
        
        try:
            with open(self.file_path, "r", encoding="utf-8", errors="replace") as f:
                data = json.load(f)
            
            for session_id, session_dict in data.items():
                try:
                    session = SessionData.from_dict(session_dict)
                    self._sessions[session_id] = session
                except Exception as e:
                    print(f"[FileSessionStore] Errore nel caricamento sessione {session_id}: {e}")
                    continue
            
            print(f"[FileSessionStore] Caricate {len(self._sessions)} sessioni da {self.file_path}")
        except json.JSONDecodeError as e:
            print(f"[FileSessionStore] Errore nel parsing JSON: {e}")
        except Exception as e:
            print(f"[FileSessionStore] Errore nel caricamento file: {e}")
    
    def _save_sessions(self):
        """Salva tutte le sessioni su file JSON (atomic write)."""
        try:
            print(f"[FileSessionStore] Salvataggio di {len(self._sessions)} sessioni su {self.file_path}...", file=sys.stderr)
            # Prepara i dati per la serializzazione
            data = {}
            for session_id, session in self._sessions.items():
                data[session_id] = session.to_dict()
            
            # Atomic write: scrivi su file temporaneo, poi rinomina
            temp_path = self.file_path.with_suffix(".json.tmp")
            # Usa encoding UTF-8 esplicitamente e gestisci errori di encoding
            with open(temp_path, "w", encoding="utf-8", errors="replace") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # Rinomina atomico (su Windows potrebbe fallire se il file è aperto, ma è raro)
            if temp_path.exists():
                if self.file_path.exists():
                    self.file_path.unlink() # Rimuovi vecchio file per sicurezza su Windows
                temp_path.rename(self.file_path)
            
            print(f"[FileSessionStore] Salvataggio completato con successo.", file=sys.stderr)
        except UnicodeEncodeError as e:
            print(f"[FileSessionStore] ERRORE di encoding nel salvataggio: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            # Non solleviamo l'eccezione per non interrompere il flusso
            pass
        except Exception as e:
            print(f"[FileSessionStore] ERRORE CRITICO nel salvataggio: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            # Non solleviamo l'eccezione per non interrompere il flusso
            pass
    
    def create_session(
        self,
        session_id: str,
        form_data: SubmissionRequest,
        question_answers: list[QuestionAnswer],
    ) -> SessionData:
        """Crea una nuova sessione e salva su file."""
        session = super().create_session(session_id, form_data, question_answers)
        self._save_sessions()
        return session
    
    def update_draft(
        self,
        session_id: str,
        draft_text: str,
        version: Optional[int] = None,
        title: Optional[str] = None,
    ) -> SessionData:
        """Aggiorna la bozza e salva su file."""
        session = super().update_draft(session_id, draft_text, version, title)
        self._save_sessions()
        return session
    
    def validate_session(self, session_id: str) -> SessionData:
        """Marca una sessione come validata e salva su file."""
        session = super().validate_session(session_id)
        self._save_sessions()
        return session
    
    def update_outline(
        self,
        session_id: str,
        outline_text: str,
        version: Optional[int] = None,
    ) -> SessionData:
        """Aggiorna l'outline e salva su file."""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Sessione {session_id} non trovata")
        
        session.current_outline = outline_text
        if version is None:
            session.outline_version += 1
            version = session.outline_version
        else:
            session.outline_version = version
        
        self._save_sessions()
        return session
    
    def delete_session(self, session_id: str) -> bool:
        """Elimina una sessione e salva su file."""
        result = super().delete_session(session_id)
        if result:
            self._save_sessions()
        return result
    
    def update_writing_progress(
        self,
        session_id: str,
        current_step: int,
        total_steps: int,
        current_section_name: Optional[str] = None,
        is_complete: bool = False,
        error: Optional[str] = None,
    ) -> SessionData:
        """Aggiorna lo stato di avanzamento della scrittura e salva su file."""
        session = super().update_writing_progress(
            session_id, current_step, total_steps, current_section_name, is_complete, error
        )
        self._save_sessions()
        return session
    
    def update_book_chapter(
        self,
        session_id: str,
        chapter_title: str,
        chapter_content: str,
        section_index: int,
    ) -> SessionData:
        """Aggiunge o aggiorna un capitolo completato e salva su file."""
        session = super().update_book_chapter(
            session_id, chapter_title, chapter_content, section_index
        )
        self._save_sessions()
        return session
    
    def update_cover_image_path(
        self,
        session_id: str,
        cover_image_path: str,
    ) -> SessionData:
        """Aggiorna il path dell'immagine copertina e salva su file."""
        session = super().update_cover_image_path(session_id, cover_image_path)
        self._save_sessions()
        return session
    
    def update_critique(
        self,
        session_id: str,
        critique: Dict[str, Any],
    ) -> SessionData:
        """Aggiorna la valutazione critica del libro e salva su file."""
        session = super().update_critique(session_id, critique)
        self._save_sessions()
        return session


# Istanza globale del session store (usa FileSessionStore per persistenza)
_session_store: Optional[SessionStore] = None


def get_session_store() -> SessionStore:
    """Restituisce l'istanza globale del session store (con persistenza su file)."""
    global _session_store
    if _session_store is None:
        _session_store = FileSessionStore()
    return _session_store



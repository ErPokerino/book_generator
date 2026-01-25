import json
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
from app.models import SubmissionRequest, QuestionAnswer


class SessionData:
    """Dati di una sessione."""
    def __init__(
        self,
        session_id: str,
        form_data: SubmissionRequest,
        question_answers: list[QuestionAnswer],
        user_id: Optional[str] = None,  # ID utente proprietario della sessione
    ):
        self.session_id = session_id
        self.form_data = form_data
        self.question_answers = question_answers
        self.user_id = user_id  # Associazione con utente
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
        self.writing_start_time: Optional[datetime] = None  # Timestamp inizio scrittura capitoli
        self.writing_end_time: Optional[datetime] = None  # Timestamp fine scrittura capitoli
        self.chapter_timings: list[float] = []  # Tempo in secondi per ogni capitolo completato
        self.chapter_start_time: Optional[datetime] = None  # Timestamp inizio capitolo corrente
        self.generated_questions: Optional[list[Dict[str, Any]]] = None  # Domande generate per questa sessione
        self.questions_progress: Optional[Dict[str, Any]] = None  # Stato avanzamento generazione domande
        self.draft_progress: Optional[Dict[str, Any]] = None  # Stato avanzamento generazione bozza
        self.outline_progress: Optional[Dict[str, Any]] = None  # Stato avanzamento generazione outline
        self.created_at: datetime = datetime.now()  # Timestamp creazione sessione
        self.updated_at: datetime = datetime.now()  # Timestamp ultima modifica
        # Token usage tracking per calcolo costi reali
        self.token_usage: Dict[str, Any] = {
            "questions": {"input_tokens": 0, "output_tokens": 0, "model": None},
            "draft": {"input_tokens": 0, "output_tokens": 0, "model": None, "calls": 0},
            "outline": {"input_tokens": 0, "output_tokens": 0, "model": None},
            "chapters": {"input_tokens": 0, "output_tokens": 0, "model": None, "calls": 0},
            "critique": {"input_tokens": 0, "output_tokens": 0, "model": None},
            "total": {"input_tokens": 0, "output_tokens": 0},
        }
        self.real_cost_eur: Optional[float] = None  # Costo effettivo calcolato dai token reali
    
    def get_status(self) -> str:
        """
        Calcola lo stato corrente della sessione basandosi sui dati disponibili.
        Restituisce: "draft", "outline", "writing", "paused", "complete"
        """
        if self.writing_progress:
            if self.writing_progress.get("is_complete", False):
                return "complete"
            elif self.writing_progress.get("is_paused", False):
                return "paused"
            else:
                return "writing"
        elif self.current_outline:
            return "outline"
        else:
            return "draft"
    
    def update_timestamp(self):
        """Aggiorna il timestamp updated_at."""
        self.updated_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte SessionData in un dizionario per la serializzazione JSON."""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,  # Associazione utente
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
            "writing_start_time": self.writing_start_time.isoformat() if self.writing_start_time else None,
            "writing_end_time": self.writing_end_time.isoformat() if self.writing_end_time else None,
            "chapter_timings": self.chapter_timings,
            "chapter_start_time": self.chapter_start_time.isoformat() if self.chapter_start_time else None,
            "generated_questions": self.generated_questions,
            "questions_progress": self.questions_progress,
            "draft_progress": self.draft_progress,
            "outline_progress": self.outline_progress,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "token_usage": self.token_usage,
            "real_cost_eur": self.real_cost_eur,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionData":
        """Crea SessionData da un dizionario (deserializzazione JSON)."""
        session = cls(
            session_id=data["session_id"],
            form_data=SubmissionRequest(**data["form_data"]),
            question_answers=[QuestionAnswer(**qa) for qa in data.get("question_answers", [])],  # Defensivo: usa .get() con fallback
            user_id=data.get("user_id"),  # Associazione utente (retrocompatibile)
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
        # Parse datetime da ISO string se presente
        start_time_str = data.get("writing_start_time")
        end_time_str = data.get("writing_end_time")
        session.writing_start_time = datetime.fromisoformat(start_time_str) if start_time_str else None
        session.writing_end_time = datetime.fromisoformat(end_time_str) if end_time_str else None
        session.chapter_timings = data.get("chapter_timings", [])
        chapter_start_str = data.get("chapter_start_time")
        session.chapter_start_time = datetime.fromisoformat(chapter_start_str) if chapter_start_str else None
        session.generated_questions = data.get("generated_questions")
        session.questions_progress = data.get("questions_progress")
        session.draft_progress = data.get("draft_progress")
        session.outline_progress = data.get("outline_progress")
        # Parse created_at e updated_at con fallback a datetime.now() se non presente (retrocompatibilità)
        created_at_str = data.get("created_at")
        session.created_at = datetime.fromisoformat(created_at_str) if created_at_str else datetime.now()
        updated_at_str = data.get("updated_at")
        session.updated_at = datetime.fromisoformat(updated_at_str) if updated_at_str else datetime.now()
        # Token usage (retrocompatibile: se non presente, usa default)
        session.token_usage = data.get("token_usage", {
            "questions": {"input_tokens": 0, "output_tokens": 0, "model": None},
            "draft": {"input_tokens": 0, "output_tokens": 0, "model": None, "calls": 0},
            "outline": {"input_tokens": 0, "output_tokens": 0, "model": None},
            "chapters": {"input_tokens": 0, "output_tokens": 0, "model": None, "calls": 0},
            "critique": {"input_tokens": 0, "output_tokens": 0, "model": None},
            "total": {"input_tokens": 0, "output_tokens": 0},
        })
        session.real_cost_eur = data.get("real_cost_eur")
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
        session.update_timestamp()
        
        return session
    
    def validate_session(self, session_id: str) -> SessionData:
        """Marca una sessione come validata."""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Sessione {session_id} non trovata")
        
        session.validated = True
        session.update_timestamp()
        return session
    
    def save_generated_questions(
        self,
        session_id: str,
        questions: list[Dict[str, Any]],
    ) -> SessionData:
        """Salva le domande generate per una sessione."""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Sessione {session_id} non trovata")
        
        session.generated_questions = questions
        session.update_timestamp()
        return session
    
    def update_outline(
        self,
        session_id: str,
        outline_text: str,
        allow_if_writing: bool = False,
    ) -> SessionData:
        """
        Aggiorna l'outline corrente di una sessione.
        
        Args:
            session_id: ID della sessione
            outline_text: Nuovo testo dell'outline in formato markdown
            allow_if_writing: Se True, permette modifiche anche se la scrittura è già iniziata
        
        Raises:
            ValueError: Se la sessione non esiste o se la scrittura è già iniziata (e allow_if_writing=False)
        """
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Sessione {session_id} non trovata")
        
        # Valida che non si stia già scrivendo (a meno che non sia esplicitamente permesso)
        if not allow_if_writing and session.writing_progress:
            writing_status = session.writing_progress
            if not writing_status.get("is_complete", False):
                raise ValueError(
                    f"Non è possibile modificare l'outline: la scrittura del libro è già iniziata "
                    f"(capitolo {writing_status.get('current_step', 0)}/{writing_status.get('total_steps', 0)})."
                )
        
        session.current_outline = outline_text
        session.outline_version += 1
        session.update_timestamp()
        
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
        is_paused: bool = False,
        error: Optional[str] = None,
        total_pages: Optional[int] = None,
        completed_chapters_count: Optional[int] = None,
    ) -> SessionData:
        """Aggiorna lo stato di avanzamento della scrittura del romanzo (merge-safe)."""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Sessione {session_id} non trovata")
        
        # Merge-safe: preserva campi esistenti come estimated_cost, writing_time_minutes, etc.
        existing_progress = session.writing_progress or {}
        
        # Crea nuovo dict partendo da quello esistente
        new_progress = existing_progress.copy()
        
        # Aggiorna sempre i campi "core" (stato progresso)
        new_progress["session_id"] = session_id
        new_progress["current_step"] = current_step
        new_progress["total_steps"] = total_steps
        new_progress["current_section_name"] = current_section_name
        new_progress["is_complete"] = is_complete
        new_progress["is_paused"] = is_paused
        new_progress["error"] = error
        
        # Aggiorna campi opzionali solo se passati esplicitamente
        if total_pages is not None:
            new_progress["total_pages"] = total_pages
        if completed_chapters_count is not None:
            new_progress["completed_chapters_count"] = completed_chapters_count
        
        # Campi come estimated_cost, writing_time_minutes vengono preservati automaticamente
        # perché partiamo da existing_progress.copy()
        
        session.writing_progress = new_progress
        session.update_timestamp()
        
        return session
    
    def update_questions_progress(self, session_id: str, progress_dict: Dict[str, Any]) -> SessionData:
        """Aggiorna lo stato di avanzamento della generazione domande."""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Sessione {session_id} non trovata")
        
        session.questions_progress = progress_dict
        session.update_timestamp()
        return session
    
    def update_draft_progress(self, session_id: str, progress_dict: Dict[str, Any]) -> SessionData:
        """Aggiorna lo stato di avanzamento della generazione bozza."""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Sessione {session_id} non trovata")
        
        session.draft_progress = progress_dict
        session.update_timestamp()
        return session
    
    def update_outline_progress(self, session_id: str, progress_dict: Dict[str, Any]) -> SessionData:
        """Aggiorna lo stato di avanzamento della generazione outline."""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Sessione {session_id} non trovata")
        
        session.outline_progress = progress_dict
        session.update_timestamp()
        return session
    
    def set_estimated_cost(self, session_id: str, estimated_cost: float) -> bool:
        """
        Aggiorna solo estimated_cost in writing_progress senza sovrascrivere l'intero dict.
        
        Args:
            session_id: ID della sessione
            estimated_cost: Costo stimato da salvare (in EUR)
        
        Returns:
            True se l'aggiornamento è riuscito, False altrimenti
        """
        session = self.get_session(session_id)
        if not session:
            return False
        
        if session.writing_progress is None:
            session.writing_progress = {}
        
        session.writing_progress["estimated_cost"] = estimated_cost
        session.update_timestamp()
        
        return True
    
    def update_token_usage(
        self,
        session_id: str,
        phase: str,
        input_tokens: int,
        output_tokens: int,
        model: str,
    ) -> bool:
        """
        Aggiorna il conteggio token per una fase specifica della generazione.
        
        Args:
            session_id: ID della sessione
            phase: Fase di generazione ("questions", "draft", "outline", "chapters", "critique")
            input_tokens: Numero di token in input
            output_tokens: Numero di token in output
            model: Nome del modello utilizzato
        
        Returns:
            True se l'aggiornamento è riuscito, False altrimenti
        """
        session = self.get_session(session_id)
        if not session:
            return False
        
        # Inizializza token_usage se non esiste (retrocompatibilità)
        if not hasattr(session, 'token_usage') or session.token_usage is None:
            session.token_usage = {
                "questions": {"input_tokens": 0, "output_tokens": 0, "model": None},
                "draft": {"input_tokens": 0, "output_tokens": 0, "model": None, "calls": 0},
                "outline": {"input_tokens": 0, "output_tokens": 0, "model": None},
                "chapters": {"input_tokens": 0, "output_tokens": 0, "model": None, "calls": 0},
                "critique": {"input_tokens": 0, "output_tokens": 0, "model": None},
                "total": {"input_tokens": 0, "output_tokens": 0},
            }
        
        # Aggiorna i token per la fase specifica
        if phase in session.token_usage:
            session.token_usage[phase]["input_tokens"] += input_tokens
            session.token_usage[phase]["output_tokens"] += output_tokens
            session.token_usage[phase]["model"] = model
            # Incrementa il contatore chiamate per draft e chapters
            if phase in ("draft", "chapters") and "calls" in session.token_usage[phase]:
                session.token_usage[phase]["calls"] += 1
        
        # Aggiorna anche il totale
        session.token_usage["total"]["input_tokens"] += input_tokens
        session.token_usage["total"]["output_tokens"] += output_tokens
        
        session.update_timestamp()
        return True
    
    def set_real_cost(self, session_id: str, real_cost_eur: float) -> bool:
        """
        Imposta il costo reale calcolato dai token effettivi.
        
        Args:
            session_id: ID della sessione
            real_cost_eur: Costo reale in EUR
        
        Returns:
            True se l'aggiornamento è riuscito, False altrimenti
        """
        session = self.get_session(session_id)
        if not session:
            return False
        
        session.real_cost_eur = real_cost_eur
        session.update_timestamp()
        return True
    
    def pause_writing(
        self,
        session_id: str,
        current_step: int,
        total_steps: int,
        current_section_name: Optional[str],
        error_msg: str,
    ) -> SessionData:
        """Mette in pausa la generazione del libro dopo un errore."""
        return self.update_writing_progress(
            session_id=session_id,
            current_step=current_step,
            total_steps=total_steps,
            current_section_name=current_section_name,
            is_complete=False,
            is_paused=True,
            error=error_msg,
        )
    
    def resume_writing(self, session_id: str) -> SessionData:
        """Riprende la generazione del libro rimuovendo lo stato di pausa."""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Sessione {session_id} non trovata")
        
        if not session.writing_progress:
            raise ValueError(f"Sessione {session_id} non ha uno stato di scrittura")
        
        # Mantieni tutti i valori tranne is_paused e error
        progress = session.writing_progress
        return self.update_writing_progress(
            session_id=session_id,
            current_step=progress.get("current_step", 0),
            total_steps=progress.get("total_steps", 0),
            current_section_name=progress.get("current_section_name"),
            is_complete=False,
            is_paused=False,
            error=None,
        )
    
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
        session.update_timestamp()
        
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
        session.update_timestamp()
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
        session.update_timestamp()
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
        session.update_timestamp()
        # Se fallita, non cancelliamo automaticamente una critica già presente (utile per storico/debug)
        return session

    def update_writing_times(
        self,
        session_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> SessionData:
        """Aggiorna i timestamp di inizio e fine scrittura capitoli."""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Sessione {session_id} non trovata")

        if start_time is not None:
            session.writing_start_time = start_time
        if end_time is not None:
            session.writing_end_time = end_time
        self._save_sessions()
        return session

    def start_chapter_timing(self, session_id: str, start_time: Optional[datetime] = None) -> SessionData:
        """Inizia il tracciamento del tempo per un capitolo."""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Sessione {session_id} non trovata")
        
        session.chapter_start_time = start_time or datetime.now()
        self._save_sessions()
        return session

    def end_chapter_timing(self, session_id: str, end_time: Optional[datetime] = None) -> SessionData:
        """Termina il tracciamento del tempo per un capitolo e salva il risultato."""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Sessione {session_id} non trovata")
        
        if session.chapter_start_time:
            end = end_time or datetime.now()
            duration_seconds = (end - session.chapter_start_time).total_seconds()
            session.chapter_timings.append(duration_seconds)
            session.chapter_start_time = None  # Reset per il prossimo capitolo
            self._save_sessions()
        
        return session

    def _save_sessions(self):
        """Metodo vuoto per compatibilità. Sovrascritto in FileSessionStore per salvare su file."""
        pass


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
    
    def save_generated_questions(
        self,
        session_id: str,
        questions: list[Dict[str, Any]],
    ) -> SessionData:
        """Salva le domande generate per una sessione e salva su file."""
        session = super().save_generated_questions(session_id, questions)
        self._save_sessions()
        return session
    
    def update_outline(
        self,
        session_id: str,
        outline_text: str,
        allow_if_writing: bool = False,
        version: Optional[int] = None,
    ) -> SessionData:
        """Aggiorna l'outline e salva su file."""
        # Chiama il metodo della classe base che include la validazione
        session = super().update_outline(session_id, outline_text, allow_if_writing)
        
        # Se è specificata una versione, usa quella invece di incrementare
        if version is not None:
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
        is_paused: bool = False,
        error: Optional[str] = None,
    ) -> SessionData:
        """Aggiorna lo stato di avanzamento della scrittura e salva su file."""
        session = super().update_writing_progress(
            session_id, current_step, total_steps, current_section_name, is_complete, is_paused, error
        )
        self._save_sessions()
        return session
    
    def pause_writing(
        self,
        session_id: str,
        current_step: int,
        total_steps: int,
        current_section_name: Optional[str],
        error_msg: str,
    ) -> SessionData:
        """Mette in pausa la generazione del libro dopo un errore e salva su file."""
        session = super().pause_writing(session_id, current_step, total_steps, current_section_name, error_msg)
        self._save_sessions()
        return session
    
    def resume_writing(self, session_id: str) -> SessionData:
        """Riprende la generazione del libro rimuovendo lo stato di pausa e salva su file."""
        session = super().resume_writing(session_id)
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
    
    def update_token_usage(
        self,
        session_id: str,
        phase: str,
        input_tokens: int,
        output_tokens: int,
        model: str,
    ) -> bool:
        """Aggiorna il conteggio token e salva su file."""
        result = super().update_token_usage(session_id, phase, input_tokens, output_tokens, model)
        if result:
            self._save_sessions()
        return result
    
    def set_real_cost(self, session_id: str, real_cost_eur: float) -> bool:
        """Imposta il costo reale e salva su file."""
        result = super().set_real_cost(session_id, real_cost_eur)
        if result:
            self._save_sessions()
        return result


# Istanza globale del session store
_session_store: Optional[SessionStore] = None


def get_session_store() -> SessionStore:
    """
    Restituisce l'istanza globale del session store.
    Se MONGODB_URI è configurata, usa MongoSessionStore, altrimenti FileSessionStore.
    """
    global _session_store
    if _session_store is None:
        mongo_uri = os.getenv("MONGODB_URI")
        if mongo_uri:
            try:
                from app.agent.mongo_session_store import MongoSessionStore
                _session_store = MongoSessionStore(mongo_uri)
                print(f"[SessionStore] Usando MongoSessionStore (URI: {mongo_uri[:50]}...)", file=sys.stderr)
            except ImportError as e:
                print(f"[SessionStore] ERRORE: Impossibile importare MongoSessionStore: {e}", file=sys.stderr)
                print(f"[SessionStore] Fallback a FileSessionStore", file=sys.stderr)
                _session_store = FileSessionStore()
        else:
            _session_store = FileSessionStore()
            print(f"[SessionStore] Usando FileSessionStore", file=sys.stderr)
    return _session_store



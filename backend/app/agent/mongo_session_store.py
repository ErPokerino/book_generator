"""Store MongoDB per le sessioni usando Motor (driver async)."""
import os
import sys
from typing import Optional, Dict, Any
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import IndexModel, ASCENDING
from app.models import SubmissionRequest, QuestionAnswer
from app.agent.session_store import SessionStore, SessionData


class MongoSessionStore(SessionStore):
    """Store MongoDB per le sessioni con persistenza su database."""
    
    def __init__(self, connection_string: str, database: str = "narrai", collection: str = "sessions"):
        """
        Inizializza il MongoDB store.
        
        Args:
            connection_string: MongoDB connection string (es: mongodb://localhost:27017 o mongodb+srv://...)
            database: Nome del database (default: "narrai")
            collection: Nome della collection (default: "sessions")
        """
        # Non chiamare super().__init__() perché inizializza _sessions come dict
        # MongoSessionStore usa una property invece
        self.client: Optional[AsyncIOMotorClient] = None
        self.connection_string = connection_string
        self.database_name = database
        self.collection_name = collection
        self.db = None
        self.sessions_collection = None
        print(f"[MongoSessionStore] Inizializzato. DB: {database}, Collection: {collection}", file=sys.stderr)
    
    async def connect(self):
        """Connette al database MongoDB e crea gli indici."""
        if self.client is None:
            try:
                self.client = AsyncIOMotorClient(self.connection_string)
                self.db = self.client[self.database_name]
                self.sessions_collection = self.db[self.collection_name]
                
                # Crea indici per performance
                await self._create_indexes()
                
                # Test connessione
                await self.client.admin.command('ping')
                print(f"[MongoSessionStore] Connesso a MongoDB: {self.database_name}", file=sys.stderr)
            except Exception as e:
                print(f"[MongoSessionStore] ERRORE nella connessione a MongoDB: {e}", file=sys.stderr)
                raise
    
    async def disconnect(self):
        """Chiude la connessione a MongoDB."""
        if self.client:
            self.client.close()
            self.client = None
            self.db = None
            self.sessions_collection = None
            print(f"[MongoSessionStore] Disconnesso da MongoDB", file=sys.stderr)
    
    async def _create_indexes(self):
        """Crea indici per ottimizzare le query."""
        try:
            indexes = [
                IndexModel([("status", ASCENDING)]),
                IndexModel([("user_id", ASCENDING)]),  # Indice per filtro per utente
                IndexModel([("form_data.llm_model", ASCENDING)]),
                IndexModel([("form_data.genre", ASCENDING)]),
                IndexModel([("created_at", ASCENDING)]),
                IndexModel([("updated_at", ASCENDING)]),
            ]
            await self.sessions_collection.create_indexes(indexes)
            print(f"[MongoSessionStore] Indici creati con successo", file=sys.stderr)
        except Exception as e:
            print(f"[MongoSessionStore] Avviso: errore nella creazione indici: {e}", file=sys.stderr)
    
    def _session_to_doc(self, session: SessionData) -> Dict[str, Any]:
        """Converte SessionData in documento MongoDB."""
        doc = session.to_dict()
        # Usa session_id come _id
        doc["_id"] = session.session_id
        # Rimuovi session_id dal documento (già in _id)
        doc.pop("session_id", None)
        # Aggiungi campo status denormalizzato per query
        doc["status"] = session.get_status()
        # Converti datetime a datetime MongoDB (sono già ISO string, MongoDB li gestisce)
        return doc
    
    def _doc_to_session(self, doc: Dict[str, Any]) -> SessionData:
        """Converte documento MongoDB in SessionData."""
        # Converti _id in session_id
        doc["session_id"] = doc["_id"]
        doc.pop("_id", None)
        # Rimuovi campo status denormalizzato
        doc.pop("status", None)
        return SessionData.from_dict(doc)
    
    async def create_session(
        self,
        session_id: str,
        form_data: SubmissionRequest,
        question_answers: list[QuestionAnswer],
        user_id: Optional[str] = None,
    ) -> SessionData:
        """Crea una nuova sessione."""
        session = SessionData(session_id, form_data, question_answers, user_id=user_id)
        await self.save_session(session)
        return session
    
    async def save_session(self, session: SessionData) -> SessionData:
        """Salva una sessione su MongoDB."""
        if self.sessions_collection is None:
            await self.connect()
        
        session.update_timestamp()
        doc = self._session_to_doc(session)
        
        try:
            await self.sessions_collection.replace_one(
                {"_id": session.session_id},
                doc,
                upsert=True
            )
            print(f"[MongoSessionStore] Sessione {session.session_id} salvata", file=sys.stderr)
        except Exception as e:
            print(f"[MongoSessionStore] ERRORE nel salvataggio sessione {session.session_id}: {e}", file=sys.stderr)
            raise
        
        return session
    
    async def get_session(self, session_id: str, user_id: Optional[str] = None) -> Optional[SessionData]:
        """
        Recupera una sessione esistente.
        
        Args:
            session_id: ID sessione
            user_id: ID utente per verificare ownership (opzionale)
        
        Returns:
            SessionData se trovata e ownership verificata, None altrimenti.
            Le sessioni legacy (senza user_id) sono accessibili da tutti durante la migrazione.
        """
        if self.sessions_collection is None:
            await self.connect()
        
        try:
            # Recupera sessione senza filtro user_id (per permettere accesso a sessioni legacy)
            query = {"_id": session_id}
            doc = await self.sessions_collection.find_one(query)
            
            if not doc:
                return None
            
            session = self._doc_to_session(doc)
            
            # Verifica ownership se user_id fornito
            # Se la sessione non ha user_id (legacy), permettere accesso
            if user_id and session.user_id:
                # Sessione ha user_id: verifica ownership
                if session.user_id != user_id:
                    return None  # Sessione appartiene a altro utente
            
            # Sessione legacy (senza user_id) o ownership verificata: permettere accesso
            return session
            
        except Exception as e:
            print(f"[MongoSessionStore] ERRORE nel recupero sessione {session_id}: {e}", file=sys.stderr)
            return None
    
    async def update_draft(
        self,
        session_id: str,
        draft_text: str,
        version: Optional[int] = None,
        title: Optional[str] = None,
    ) -> SessionData:
        """Aggiorna la bozza corrente di una sessione."""
        session = await self.get_session(session_id)
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
            "timestamp": None,
        })
        
        return await self.save_session(session)
    
    async def validate_session(self, session_id: str) -> SessionData:
        """Marca una sessione come validata."""
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Sessione {session_id} non trovata")
        
        session.validated = True
        return await self.save_session(session)
    
    async def save_generated_questions(
        self,
        session_id: str,
        questions: list[Dict[str, Any]],
    ) -> SessionData:
        """Salva le domande generate per una sessione."""
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Sessione {session_id} non trovata")
        
        session.generated_questions = questions
        return await self.save_session(session)
    
    async def update_outline(
        self,
        session_id: str,
        outline_text: str,
        allow_if_writing: bool = False,
        version: Optional[int] = None,
    ) -> SessionData:
        """
        Aggiorna l'outline corrente di una sessione.
        
        Args:
            session_id: ID della sessione
            outline_text: Nuovo testo dell'outline in formato markdown
            allow_if_writing: Se True, permette modifiche anche se la scrittura è già iniziata
            version: Versione specifica (opzionale)
        
        Raises:
            ValueError: Se la sessione non esiste o se la scrittura è già iniziata (e allow_if_writing=False)
        """
        session = await self.get_session(session_id)
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
        if version is not None:
            session.outline_version = version
        else:
            session.outline_version += 1
        
        return await self.save_session(session)
    
    async def delete_session(self, session_id: str) -> bool:
        """Elimina una sessione."""
        if self.sessions_collection is None:
            await self.connect()
        
        try:
            result = await self.sessions_collection.delete_one({"_id": session_id})
            return result.deleted_count > 0
        except Exception as e:
            print(f"[MongoSessionStore] ERRORE nell'eliminazione sessione {session_id}: {e}", file=sys.stderr)
            return False
    
    async def update_writing_progress(
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
        session = await self.get_session(session_id)
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
        
        return await self.save_session(session)
    
    async def update_questions_progress(self, session_id: str, progress_dict: Dict[str, Any]) -> SessionData:
        """Aggiorna lo stato di avanzamento della generazione domande."""
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Sessione {session_id} non trovata")
        
        session.questions_progress = progress_dict
        return await self.save_session(session)
    
    async def update_draft_progress(self, session_id: str, progress_dict: Dict[str, Any]) -> SessionData:
        """Aggiorna lo stato di avanzamento della generazione bozza."""
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Sessione {session_id} non trovata")
        
        session.draft_progress = progress_dict
        return await self.save_session(session)
    
    async def update_outline_progress(self, session_id: str, progress_dict: Dict[str, Any]) -> SessionData:
        """Aggiorna lo stato di avanzamento della generazione outline."""
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Sessione {session_id} non trovata")
        
        session.outline_progress = progress_dict
        return await self.save_session(session)
    
    async def set_estimated_cost(self, session_id: str, estimated_cost: float) -> bool:
        """
        Aggiorna solo estimated_cost in writing_progress senza sovrascrivere l'intero dict.
        
        Args:
            session_id: ID della sessione
            estimated_cost: Costo stimato da salvare (in EUR)
        
        Returns:
            True se l'aggiornamento è riuscito, False altrimenti
        """
        if self.sessions_collection is None:
            await self.connect()
        
        try:
            from datetime import datetime
            # Usa $set per aggiornare solo writing_progress.estimated_cost
            result = await self.sessions_collection.update_one(
                {"_id": session_id},
                {"$set": {"writing_progress.estimated_cost": estimated_cost, "updated_at": datetime.now().isoformat()}}
            )
            return result.modified_count > 0
        except Exception as e:
            print(f"[MongoSessionStore] ERRORE nell'aggiornamento estimated_cost per sessione {session_id}: {e}", file=sys.stderr)
            return False
    
    async def pause_writing(
        self,
        session_id: str,
        current_step: int,
        total_steps: int,
        current_section_name: Optional[str],
        error_msg: str,
    ) -> SessionData:
        """Mette in pausa la generazione del libro dopo un errore."""
        return await self.update_writing_progress(
            session_id=session_id,
            current_step=current_step,
            total_steps=total_steps,
            current_section_name=current_section_name,
            is_complete=False,
            is_paused=True,
            error=error_msg,
        )
    
    async def resume_writing(self, session_id: str) -> SessionData:
        """Riprende la generazione del libro rimuovendo lo stato di pausa."""
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Sessione {session_id} non trovata")
        
        if not session.writing_progress:
            raise ValueError(f"Sessione {session_id} non ha uno stato di scrittura")
        
        # Mantieni tutti i valori tranne is_paused e error
        progress = session.writing_progress
        return await self.update_writing_progress(
            session_id=session_id,
            current_step=progress.get("current_step", 0),
            total_steps=progress.get("total_steps", 0),
            current_section_name=progress.get("current_section_name"),
            is_complete=False,
            is_paused=False,
            error=None,
        )
    
    async def update_book_chapter(
        self,
        session_id: str,
        chapter_title: str,
        chapter_content: str,
        section_index: int,
    ) -> SessionData:
        """Aggiunge o aggiorna un capitolo completato."""
        session = await self.get_session(session_id)
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
        
        return await self.save_session(session)
    
    async def update_cover_image_path(
        self,
        session_id: str,
        cover_image_path: str,
    ) -> SessionData:
        """Aggiorna il path dell'immagine copertina."""
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Sessione {session_id} non trovata")
        
        session.cover_image_path = cover_image_path
        return await self.save_session(session)
    
    async def update_critique(
        self,
        session_id: str,
        critique: Dict[str, Any],
    ) -> SessionData:
        """Aggiorna la valutazione critica del libro."""
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Sessione {session_id} non trovata")
        
        session.literary_critique = critique
        session.critique_status = "completed"
        session.critique_error = None
        
        return await self.save_session(session)
    
    async def update_critique_status(
        self,
        session_id: str,
        status: str,
        error: Optional[str] = None,
    ) -> SessionData:
        """Aggiorna lo stato della critica (pending|running|completed|failed) e opzionale errore."""
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Sessione {session_id} non trovata")
        
        session.critique_status = status
        session.critique_error = error
        
        return await self.save_session(session)
    
    async def update_writing_times(
        self,
        session_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> SessionData:
        """Aggiorna i timestamp di inizio e fine scrittura capitoli."""
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Sessione {session_id} non trovata")
        
        if start_time is not None:
            session.writing_start_time = start_time
        if end_time is not None:
            session.writing_end_time = end_time
        
        return await self.save_session(session)
    
    async def start_chapter_timing(self, session_id: str, start_time: Optional[datetime] = None) -> SessionData:
        """Inizia il tracciamento del tempo per un capitolo."""
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Sessione {session_id} non trovata")
        
        session.chapter_start_time = start_time or datetime.now()
        return await self.save_session(session)
    
    async def end_chapter_timing(self, session_id: str, end_time: Optional[datetime] = None) -> SessionData:
        """Termina il tracciamento del tempo per un capitolo e salva il risultato."""
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Sessione {session_id} non trovata")
        
        if session.chapter_start_time:
            end = end_time or datetime.now()
            duration_seconds = (end - session.chapter_start_time).total_seconds()
            session.chapter_timings.append(duration_seconds)
            session.chapter_start_time = None  # Reset per il prossimo capitolo
        
        return await self.save_session(session)
    
    async def update_token_usage(
        self,
        session_id: str,
        phase: str,
        input_tokens: int,
        output_tokens: int,
        model: str,
    ) -> bool:
        """Aggiorna il conteggio token per una fase specifica della generazione."""
        session = await self.get_session(session_id)
        if not session:
            return False
        
        # Inizializza token_usage se non esiste
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
            if phase in ("draft", "chapters") and "calls" in session.token_usage[phase]:
                session.token_usage[phase]["calls"] += 1
        
        # Aggiorna anche il totale
        session.token_usage["total"]["input_tokens"] += input_tokens
        session.token_usage["total"]["output_tokens"] += output_tokens
        
        await self.save_session(session)
        return True
    
    async def set_real_cost(self, session_id: str, real_cost_eur: float) -> bool:
        """Imposta il costo reale calcolato dai token effettivi."""
        session = await self.get_session(session_id)
        if not session:
            return False
        
        session.real_cost_eur = real_cost_eur
        await self.save_session(session)
        return True
    
    async def get_all_sessions(self, user_id: Optional[str] = None, fields: Optional[list] = None, 
                              status: Optional[str] = None, llm_model: Optional[str] = None,
                              genre: Optional[str] = None) -> Dict[str, SessionData]:
        """
        Recupera tutte le sessioni (per libreria/statistiche).
        
        Args:
            user_id: Se fornito, filtra solo le sessioni dell'utente
            fields: Lista di campi da includere (proiezione MongoDB). Se None, carica tutto.
                    Esempio: ["_id", "current_title", "form_data.user_name"]
            status: Filtra per stato della sessione (draft, outline, writing, paused, complete)
            llm_model: Filtra per modello LLM usato
            genre: Filtra per genere del libro
        
        Returns:
            Dict di SessionData
        """
        if self.sessions_collection is None:
            await self.connect()
        
        sessions = {}
        try:
            # Costruisci query MongoDB con tutti i filtri
            query = {}
            if user_id:
                query["user_id"] = user_id
            
            # Filtri opzionali
            if status and status != "all":
                # Lo status è un campo calcolato, quindi dobbiamo costruirlo logicamente
                # Per ora manteniamo il filtro in Python, ma possiamo ottimizzare in futuro
                pass  # Gestito dopo il caricamento
            
            if llm_model:
                query["form_data.llm_model"] = llm_model
            
            if genre:
                query["form_data.genre"] = genre
            
            # Costruisci proiezione se specificata
            projection = None
            if fields:
                projection = {field: 1 for field in fields}
                # Assicurati che _id sia sempre incluso
                projection["_id"] = 1
            
            cursor = self.sessions_collection.find(query, projection)
            async for doc in cursor:
                session = self._doc_to_session(doc)
                
                # Filtra per status se richiesto (dopo la conversione perché è calcolato)
                if status and status != "all":
                    session_status = session.get_status()
                    if session_status != status:
                        continue
                
                sessions[session.session_id] = session
            return sessions
        except Exception as e:
            print(f"[MongoSessionStore] ERRORE nel recupero di tutte le sessioni: {e}", file=sys.stderr)
            return {}
    
    @property
    def _sessions(self) -> Dict[str, SessionData]:
        """
        Proprietà per compatibilità con codice esistente.
        ATTENZIONE: Questa proprietà carica tutte le sessioni in memoria.
        Usare con cautela per dataset grandi.
        """
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Se siamo in un loop già in esecuzione, non possiamo usare run()
                # In questo caso, questa proprietà non funzionerà correttamente
                print("[MongoSessionStore] AVVISO: _sessions accesso in loop già in esecuzione", file=sys.stderr)
                return {}
            return asyncio.run(self.get_all_sessions())
        except RuntimeError:
            # Nessun loop disponibile, ne creiamo uno nuovo
            return asyncio.run(self.get_all_sessions())

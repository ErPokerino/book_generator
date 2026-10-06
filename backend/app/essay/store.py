"""Essay adapter for the existing SQLite transaction, lease and revision engine."""
from __future__ import annotations
import copy
import json
import os
import time
from uuid import uuid4
from pathlib import Path
from app.essay.models import EssaySession, now
from app.persistence.sqlite_store import SQLiteSessionStore, ConcurrentUpdateError, _merge, _json, PROGRESS_FIELDS

PROGRESS_FIELDS["review"] = "review_progress"
PROGRESS_FIELDS["cover"] = "cover_progress"


class EssayStore(SQLiteSessionStore):
    def __init__(self, db_path=None):
        root = Path(__file__).resolve().parents[2] / "data" / "saggistica"
        selected = Path(db_path or os.getenv("SAGGIA_DATA_DIR", root)) if db_path is None else Path(db_path)
        target = selected / "saggia.sqlite3" if db_path is None else selected
        self.data_dir = target.parent
        super().__init__(target, legacy_path=self.data_dir / ".no-legacy-import")

    def _migrate_json(self, path):
        # Deliberately do not import any NarrAI archive.
        with self.connection(write=True) as db:
            rows = db.execute("SELECT key,value FROM metadata").fetchall()
            metadata = {r["key"]: r["value"] for r in rows}
            if metadata.get("product_id") not in (None, "saggia"):
                raise ValueError("Archivio di un altro prodotto.")
            if "product_id" not in metadata and db.execute("SELECT 1 FROM sessions LIMIT 1").fetchone():
                raise ValueError("Archivio esistente senza identità SaggIA: non verrà convertito.")
            db.execute("INSERT OR REPLACE INTO metadata VALUES ('product_id','saggia')")
            db.execute("INSERT OR REPLACE INTO metadata VALUES ('schema_version','1')")

    def _read(self, db, session_id):
        row = db.execute("SELECT payload,version FROM sessions WHERE id=?", (session_id,)).fetchone()
        if row is None:
            return None
        data = json.loads(row["payload"])
        data["book_chapters"] = [json.loads(r[0]) for r in db.execute(
            "SELECT payload FROM chapters WHERE session_id=? ORDER BY section_index", (session_id,))]
        session = EssaySession.from_dict(data)
        session._snapshot = copy.deepcopy(session.to_dict())
        session._db_version = row["version"]
        return session

    def create_session(self, session_id, form_data, question_answers=None, user_id=None):
        session = EssaySession(session_id, form_data)
        with self.connection(write=True) as db:
            if self._read(db, session_id) is not None:
                raise ConcurrentUpdateError("Un progetto con questo identificativo esiste già.")
            self._write(db, session.to_dict(), 1)
        return self.get_session(session_id)

    def _persist_session(self, session):
        with self.connection(write=True) as db:
            self._assert_lease(db)
            current = self._read(db, session.session_id)
            if current is None:
                raise ConcurrentUpdateError("Il progetto non esiste più.")
            merged = _merge(session._snapshot, session.to_dict(), current.to_dict())
            version = current._db_version + 1
            self._write(db, merged, version)
        session.__dict__.update(EssaySession.from_dict(merged).__dict__)
        session._snapshot = copy.deepcopy(merged)
        session._db_version = version

    def active(self, session_id):
        return any(j["status"] in {"pending", "running"} for j in self.list_jobs(session_id))

    def mutate(self, session_id, function, *, allow_active=False):
        with self.connection(write=True) as db:
            session = self._read(db, session_id)
            if session is None:
                raise KeyError("Saggio inesistente.")
            active = db.execute("SELECT 1 FROM jobs WHERE session_id=? AND status IN ('pending','running')",
                                (session_id,)).fetchone()
            if active and not allow_active:
                raise ConcurrentUpdateError("Attendi la pausa o la fine del processo prima di modificare.")
            function(session)
            session.update_timestamp()
            self._write(db, session.to_dict(), session._db_version + 1)
        return self.get_session(session_id)

    def edit_chapter(self, session_id, index, content, expected_hash):
        from app.essay.citations import content_hash
        def change(session):
            chapter = next((c for c in session.book_chapters if c["section_index"] == index), None)
            if chapter is None:
                raise KeyError("Capitolo inesistente.")
            if content_hash(chapter["content"]) != expected_hash:
                raise ConcurrentUpdateError("Il capitolo è cambiato. Conserva il tuo testo e ricarica prima di salvare.")
            from app.essay.citations import validate_citations
            validate_citations(content, session.sources)
            chapter["content"] = content
            chapter["summary"] = ""
            chapter["review_stale"] = True
            session.review = None
            session.review_progress = None
        return self.mutate(session_id, change)

    def enqueue(self, session_id, kind, prepare=None, *, idempotent=True):
        # Preparation and queue insertion share one transaction: no mutation can slip between them.
        with self.connection(write=True) as db:
            session = self._read(db, session_id)
            if session is None:
                raise KeyError("Saggio inesistente.")
            active = db.execute("SELECT kind FROM jobs WHERE session_id=? AND status IN ('pending','running')",
                                (session_id,)).fetchone()
            if active:
                if idempotent and active["kind"] == kind:
                    return False, getattr(session, PROGRESS_FIELDS[kind])
                raise ConcurrentUpdateError("Un altro processo è attivo in questo progetto.")
            if prepare:
                prepare(session)
            field = PROGRESS_FIELDS[kind]
            old = getattr(session, field) or {}
            value = {"status": "pending", "error": None, "queued_at": now(), "updated_at": now(),
                "current_step": 0, "total_steps": 1, "job_id": str(uuid4()), "job_type": kind,
                "source_version": session.current_version, "source_outline_version": session.outline_version,
                "attempt": int(old.get("attempt", 0)) + 1}
            setattr(session, field, value)
            self._write(db, session.to_dict(), session._db_version + 1)
            db.execute("INSERT INTO jobs(id,session_id,kind,status,created_at,updated_at) VALUES (?,?,?,'pending',?,?)",
                       (value["job_id"],session_id,kind,time.time(),time.time()))
            return True, value

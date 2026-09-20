"""SQLite sessions, chapter revisions and leased jobs. No shared mutable cache."""
from __future__ import annotations

import copy
import json
import os
import shutil
import sqlite3
import time
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from uuid import uuid4

from app.agent.session_store import SessionData, SessionStore

job_lease: ContextVar[tuple[str, str] | None] = ContextVar("job_lease", default=None)
PROGRESS_FIELDS = {"questions": "questions_progress", "draft": "draft_progress",
                   "outline": "outline_progress", "memory": "memory_progress", "book": "writing_progress", "manga": "manga_progress"}


class ConcurrentUpdateError(ValueError):
    """The caller must reload before overwriting someone else's changes."""


def _json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _merge(original, proposed, current, path=""):
    if proposed == original:
        return current
    if current == original or proposed == current:
        return proposed
    if all(isinstance(v, dict) for v in (original, proposed, current)):
        result = copy.deepcopy(current)
        for key in original.keys() | proposed.keys():
            if key == "updated_at":
                result[key] = proposed.get(key)
            elif key not in proposed:
                if current.get(key) != original[key]:
                    raise ConcurrentUpdateError(f"Modifica concorrente: {path}{key}")
                result.pop(key, None)
            else:
                result[key] = _merge(original.get(key), proposed[key], current.get(key), f"{path}{key}.")
        return result
    raise ConcurrentUpdateError(f"Modifica concorrente: {path.rstrip('.')}. Ricarica il progetto.")


class SQLiteSessionStore(SessionStore):
    def __init__(self, db_path=None, legacy_path=None):
        super().__init__()
        root = Path(__file__).resolve().parents[2]
        self.db_path = Path(db_path or os.getenv("NARRAI_DB_PATH") or root / "narrai.sqlite3")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection(transaction=False) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY, payload TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1);
                CREATE TABLE IF NOT EXISTS chapters (
                    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    section_index INTEGER NOT NULL, payload TEXT NOT NULL, revision INTEGER NOT NULL,
                    PRIMARY KEY(session_id, section_index));
                CREATE TABLE IF NOT EXISTS revisions (
                    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    section_index INTEGER NOT NULL, revision INTEGER NOT NULL, payload TEXT NOT NULL,
                    created_at REAL NOT NULL, PRIMARY KEY(session_id, section_index, revision));
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    kind TEXT NOT NULL, status TEXT NOT NULL, attempt INTEGER NOT NULL DEFAULT 0,
                    owner TEXT, lease_until REAL, created_at REAL NOT NULL, updated_at REAL NOT NULL,
                    error TEXT);
                CREATE UNIQUE INDEX IF NOT EXISTS one_active_job_per_project
                    ON jobs(session_id) WHERE status IN ('pending','running');
                CREATE TABLE IF NOT EXISTS usage_events (
                    id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    payload TEXT NOT NULL, created_at REAL NOT NULL);
                CREATE INDEX IF NOT EXISTS usage_project ON usage_events(session_id);
            """)
        self._migrate_json(Path(legacy_path) if legacy_path else self.db_path.parent / ".sessions.json")

    @contextmanager
    def connection(self, *, write=False, transaction=True):
        db = sqlite3.connect(self.db_path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA synchronous=FULL")
        try:
            if write:
                db.execute("BEGIN IMMEDIATE")
            elif transaction:
                db.execute("BEGIN")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _migrate_json(self, path):
        with self.connection(write=True) as db:
            if db.execute("SELECT 1 FROM metadata WHERE key='json_migrated'").fetchone():
                return
            if path.exists():
                raw = json.loads(path.read_text(encoding="utf-8"))
                sessions = {sid: SessionData.from_dict(value) for sid, value in raw.items()}
                if any(sid != sess.session_id for sid, sess in sessions.items()):
                    raise ValueError("Archivio JSON incoerente. Migrazione annullata; originale preservato.")
                backup = path.with_name(path.name + ".pre-sqlite.bak")
                if not backup.exists():
                    shutil.copy2(path, backup)
                for session in sessions.values():
                    if not db.execute("SELECT 1 FROM sessions WHERE id=?", (session.session_id,)).fetchone():
                        self._write(db, session.to_dict(), 1)
            db.execute("INSERT INTO metadata VALUES ('json_migrated', ?)", (_json({"source": str(path), "at": time.time()}),))
            db.execute("INSERT OR REPLACE INTO metadata VALUES ('schema_version','1')")

    def _read(self, db, session_id):
        row = db.execute("SELECT payload,version FROM sessions WHERE id=?", (session_id,)).fetchone()
        if not row:
            return None
        data = json.loads(row["payload"])
        data["book_chapters"] = [json.loads(ch[0]) for ch in db.execute(
            "SELECT payload FROM chapters WHERE session_id=? ORDER BY section_index", (session_id,))]
        session = SessionData.from_dict(data)
        session._snapshot = copy.deepcopy(session.to_dict())
        session._db_version = row["version"]
        session._usage_events = [json.loads(r[0]) for r in db.execute("SELECT payload FROM usage_events WHERE session_id=? ORDER BY created_at", (session_id,))]
        return session

    def get_session(self, session_id):
        with self.connection() as db:
            return self._read(db, session_id)

    def _assert_lease(self, db):
        lease = job_lease.get()
        if lease and not db.execute(
            "SELECT 1 FROM jobs WHERE id=? AND owner=? AND status='running' AND lease_until>?",
            (*lease, time.time()),
        ).fetchone():
            raise ConcurrentUpdateError("Prenotazione del processo scaduta; scrittura impedita.")

    def _write(self, db, data, version):
        sid = data["session_id"]
        payload = dict(data)
        chapters = payload.pop("book_chapters", [])
        db.execute("INSERT INTO sessions VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,version=excluded.version",
                   (sid, _json(payload), version))
        existing = {row["section_index"]: row for row in db.execute("SELECT * FROM chapters WHERE session_id=?", (sid,))}
        indices = set()
        for chapter in chapters:
            index = chapter["section_index"]
            if index in indices:
                raise ValueError("Indice capitolo duplicato")
            indices.add(index)
            old = existing.get(index)
            if old and json.loads(old["payload"]) == chapter:
                continue
            revision = db.execute("SELECT COALESCE(MAX(revision),0)+1 FROM revisions WHERE session_id=? AND section_index=?", (sid,index)).fetchone()[0]
            db.execute("INSERT OR REPLACE INTO chapters VALUES (?,?,?,?)", (sid,index,_json(chapter),revision))
            db.execute("INSERT INTO revisions VALUES (?,?,?,?,?)", (sid,index,revision,_json(chapter),time.time()))
        for index in existing.keys() - indices:
            db.execute("DELETE FROM chapters WHERE session_id=? AND section_index=?", (sid,index))

    def _persist_session(self, session):
        with self.connection(write=True) as db:
            self._assert_lease(db)
            current = self._read(db, session.session_id)
            if not current:
                raise ConcurrentUpdateError("Progetto eliminato o inesistente.")
            original = getattr(session, "_snapshot", current.to_dict())
            merged = _merge(original, session.to_dict(), current.to_dict())
            version = current._db_version + 1
            self._write(db, merged, version)
        fresh = SessionData.from_dict(merged)
        session.__dict__.update(fresh.__dict__)
        session._snapshot = copy.deepcopy(merged)
        session._db_version = version

    def create_session(self, session_id, form_data, question_answers, user_id=None):
        session = SessionData(session_id, form_data, question_answers, user_id=user_id)
        with self.connection(write=True) as db:
            if self._read(db, session_id):
                raise ConcurrentUpdateError("Questo progetto esiste già.")
            self._write(db, session.to_dict(), 1)
        return self.get_session(session_id)

    def save_session(self, session):
        session.update_timestamp()
        self._persist_session(session)
        return session

    def delete_session(self, session_id):
        with self.connection(write=True) as db:
            if db.execute("SELECT 1 FROM jobs WHERE session_id=? AND status IN ('pending','running')", (session_id,)).fetchone():
                raise ConcurrentUpdateError("Attendi la fine del processo prima di eliminare il progetto.")
            return db.execute("DELETE FROM sessions WHERE id=?", (session_id,)).rowcount > 0

    def get_all_sessions(self, user_id=None, fields=None, status=None, llm_model=None, genre=None):
        with self.connection() as db:
            sessions = [self._read(db, row[0]) for row in db.execute("SELECT id FROM sessions")]
        return {s.session_id: s for s in sessions if (not user_id or s.user_id == user_id)
                and (not status or s.get_status() == status)
                and (not llm_model or s.form_data.llm_model == llm_model)
                and (not genre or s.form_data.genre == genre)}

    def chapter_revisions(self, session_id, section_index):
        with self.connection() as db:
            return [{"revision": r["revision"], "created_at": r["created_at"], **json.loads(r["payload"])}
                    for r in db.execute("SELECT * FROM revisions WHERE session_id=? AND section_index=? ORDER BY revision DESC", (session_id,section_index))]

    def edit_chapter(self, session_id, index, content, expected_hash):
        from app.agent.narrative_memory import content_hash
        with self.connection(write=True) as db:
            session = self._read(db, session_id)
            if session is None:
                raise ValueError("Progetto inesistente")
            if db.execute("SELECT 1 FROM jobs WHERE session_id=? AND status IN ('pending','running')", (session_id,)).fetchone():
                raise ConcurrentUpdateError("Attendi la pausa o la fine della scrittura prima di modificare.")
            chapter = next((c for c in session.book_chapters if c["section_index"] == index), None)
            if chapter is None:
                raise ValueError("Capitolo inesistente")
            if content_hash(chapter["content"]) != expected_hash:
                raise ConcurrentUpdateError("Il capitolo è cambiato. Il tuo testo è conservato nell'editor: ricarica prima di salvare.")
            if content == chapter["content"]:
                return session
            chapter["content"] = content
            memory = session.narrative_memory
            session.narrative_memory = {
                "facts": [f for f in memory.get("facts", []) if f["section_index"] < index],
                "checks": [c for c in memory.get("checks", []) if c["section_index"] < index],
                "chapters": {k: v for k, v in memory.get("chapters", {}).items() if int(k) < index},
            }
            session.pdf_path = session.pdf_filename = None
            session.literary_critique = session.critique_status = session.critique_error = None
            session.story_bible = None
            session.update_timestamp()
            self._write(db, session.to_dict(), session._db_version+1)
        return self.get_session(session_id)

    def enqueue_job(self, session_id, kind, updates):
        with self.connection(write=True) as db:
            session = self._read(db, session_id)
            if not session:
                raise ValueError("Progetto inesistente")
            active = db.execute("SELECT * FROM jobs WHERE session_id=? AND status IN ('pending','running')", (session_id,)).fetchone()
            field = PROGRESS_FIELDS[kind]
            if active:
                if active["kind"] != kind:
                    raise ConcurrentUpdateError("Un altro processo è attivo in questo progetto.")
                return False, getattr(session, field)
            progress = (getattr(session, field) or {}) | updates
            progress.update(job_id=str(uuid4()), job_type=kind, updated_at=updates.get("queued_at"))
            progress["source_version"] = session.current_version
            progress["source_outline_version"] = session.outline_version
            progress["attempt"] = int((getattr(session, field) or {}).get("attempt", 0)) + 1
            setattr(session, field, progress)
            self._write(db, session.to_dict(), session._db_version + 1)
            db.execute("INSERT INTO jobs(id,session_id,kind,status,created_at,updated_at) VALUES (?,?,?,'pending',?,?)",
                       (progress["job_id"],session_id,kind,time.time(),time.time()))
            return True, progress

    def claim_job(self, owner, lease_seconds=45):
        now = time.time()
        with self.connection(write=True) as db:
            row = db.execute("SELECT * FROM jobs WHERE status='pending' OR (status='running' AND lease_until<?) ORDER BY created_at LIMIT 1", (now,)).fetchone()
            if not row:
                return None
            db.execute("UPDATE jobs SET status='running',owner=?,lease_until=?,attempt=attempt+1,updated_at=? WHERE id=?", (owner,now+lease_seconds,now,row["id"]))
            return dict(row) | {"owner": owner, "attempt": row["attempt"]+1}

    def heartbeat(self, job_id, owner, lease_seconds=45):
        with self.connection(write=True) as db:
            return db.execute("UPDATE jobs SET lease_until=?,updated_at=? WHERE id=? AND owner=? AND status='running' AND lease_until>?",
                              (time.time()+lease_seconds,time.time(),job_id,owner,time.time())).rowcount == 1

    def finish_job(self, job_id, owner, status, error=None):
        with self.connection(write=True) as db:
            return db.execute("UPDATE jobs SET status=?,error=?,owner=NULL,lease_until=NULL,updated_at=? WHERE id=? AND owner=? AND status='running'",
                              (status,error,time.time(),job_id,owner)).rowcount == 1

    def list_jobs(self, session_id):
        with self.connection() as db:
            return [dict(r) for r in db.execute("SELECT * FROM jobs WHERE session_id=? ORDER BY created_at DESC", (session_id,))]

    def record_usage(self, event):
        with self.connection(write=True) as db:
            db.execute("INSERT INTO usage_events VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload",
                       (event["id"],event["session_id"],_json(event),event["created_at"]))

    def usage_events(self, session_id):
        with self.connection() as db:
            return [json.loads(row[0]) for row in db.execute("SELECT payload FROM usage_events WHERE session_id=? ORDER BY created_at", (session_id,))]

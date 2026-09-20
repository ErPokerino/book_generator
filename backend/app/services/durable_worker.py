"""Local worker with persistent queue, expiring leases and checkpoint recovery."""
import asyncio
import os
from contextlib import suppress
from uuid import uuid4

from app.persistence.sqlite_store import PROGRESS_FIELDS, SQLiteSessionStore, job_lease
from app.core.logging import get_logger

logger = get_logger("durable-worker")


def schedule_generation(background_tasks, session_store, function, **kwargs):
    """SQLite jobs are already committed by begin; ephemeral stores are test adapters."""
    if not isinstance(session_store, SQLiteSessionStore):
        background_tasks.add_task(function, **kwargs)


async def dispatch_job(job, store):
    from app.services.generation_service import background_generate_questions, background_generate_draft, background_generate_outline
    from app.services.book_generation_service import background_book_generation, background_resume_book_generation
    from app.services.manga_generation_service import background_manga_generation, background_resume_manga_generation
    from app.models import MangaCreateRequest

    session = store.get_session(job["session_id"])
    if session is None:
        raise ValueError("Progetto eliminato")
    sid = session.session_id
    key = os.getenv("GOOGLE_API_KEY") or None
    match job["kind"]:
        case "memory":
            from app.agent.narrative_memory import ensure_narrative_memory
            from app.services.process_job_service import mark_process_running_async, mark_process_completed_async
            await mark_process_running_async(store, sid, "memory")
            await ensure_narrative_memory(store, session, key)
            await mark_process_completed_async(store, sid, "memory")
        case "questions":
            if job["attempt"] > 1 and session.generated_questions is not None:
                from app.services.process_job_service import mark_process_completed_async
                await mark_process_completed_async(store, sid, "questions", current_step=1, total_steps=1, progress_percentage=100.0,
                    result={"success": True, "session_id": sid, "questions": session.generated_questions, "message": "Domande recuperate"})
            else:
                await background_generate_questions(sid, session.form_data, key)
        case "draft":
            if job["attempt"] > 1 and session.current_draft and session.current_version > (session.draft_progress or {}).get("source_version", -1):
                from app.services.process_job_service import mark_process_completed_async
                await mark_process_completed_async(store, sid, "draft", current_step=1, total_steps=1, progress_percentage=100.0,
                    result={"success": True, "session_id": sid, "draft_text": session.current_draft, "title": session.current_title, "version": session.current_version, "message": "Bozza recuperata"})
            else:
                await background_generate_draft(sid, session.form_data, session.question_answers, key)
        case "outline":
            if job["attempt"] > 1 and session.current_outline and session.outline_version > (session.outline_progress or {}).get("source_outline_version", -1):
                from app.services.process_job_service import mark_process_completed_async
                await mark_process_completed_async(store, sid, "outline", current_step=1, total_steps=1, progress_percentage=100.0,
                    result={"success": True, "session_id": sid, "outline_text": session.current_outline, "version": session.outline_version, "message": "Indice recuperato"})
            else:
                await background_generate_outline(sid, key)
        case "book":
            if session.book_chapters or job["attempt"] > 1:
                await background_resume_book_generation(sid, api_key=key)
            else:
                await background_book_generation(session_id=sid, form_data=session.form_data,
                    question_answers=session.question_answers, validated_draft=session.current_draft,
                    draft_title=session.current_title, outline_text=session.current_outline, api_key=key)
        case "manga":
            if session.manga_plan or job["attempt"] > 1:
                await background_resume_manga_generation(session_id=sid, api_key=key)
            else:
                await background_manga_generation(session_id=sid, request=MangaCreateRequest(**session.manga_form_data), api_key=key)
        case _:
            raise ValueError(f"Tipo processo sconosciuto: {job['kind']}")


class DurableWorker:
    def __init__(self, store, handler=dispatch_job, poll_seconds=1, heartbeat_seconds=10):
        self.store = store
        self.handler = handler
        self.owner = str(uuid4())
        self.poll_seconds = poll_seconds
        self.heartbeat_seconds = heartbeat_seconds

    async def _heartbeat(self, job, task):
        while True:
            await asyncio.sleep(self.heartbeat_seconds)
            if not self.store.heartbeat(job["id"], self.owner):
                task.cancel()
                return

    async def run_once(self):
        job = self.store.claim_job(self.owner)
        if not job:
            return False
        token = job_lease.set((job["id"], self.owner))
        task = asyncio.create_task(self.handler(job, self.store))
        heartbeat = asyncio.create_task(self._heartbeat(job, task))
        try:
            await task
            session = self.store.get_session(job["session_id"])
            progress = getattr(session, PROGRESS_FIELDS[job["kind"]], {}) or {}
            status = progress.get("status")
            if status not in {"completed", "failed", "paused"}:
                raise RuntimeError("Il processo è terminato senza un risultato persistito")
            self.store.finish_job(job["id"], self.owner, status, progress.get("error"))
        except asyncio.CancelledError:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            self.store.finish_job(job["id"], self.owner, "pending")
            if asyncio.current_task().cancelling():
                raise  # Server shutdown: leave the durable job queued.
            # A lost lease cancelled only the handler. Keep this worker available.
        except Exception as exc:
            logger.exception("Processo durevole fallito", context={"job_id": job["id"]})
            from app.services.process_job_service import mark_process_failed_async, mark_process_paused_async
            try:
                if job["kind"] in {"book", "manga"}:
                    await mark_process_paused_async(self.store, job["session_id"], job["kind"], str(exc), is_paused=True, is_complete=False)
                else:
                    await mark_process_failed_async(self.store, job["session_id"], job["kind"], str(exc))
            finally:
                self.store.finish_job(job["id"], self.owner, "failed", str(exc))
        finally:
            heartbeat.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat
            job_lease.reset(token)
        return True

    async def run(self):
        while True:
            try:
                if not await self.run_once():
                    await asyncio.sleep(self.poll_seconds)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Errore worker; nuovo tentativo tra pochi secondi")
                await asyncio.sleep(3)

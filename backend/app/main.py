import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routers import (
    book,
    config as config_router,
    critique,
    draft,
    files,
    health,
    library,
    manga,
    outline,
    questions,
    session,
    submission,
)
from app.agent.session_store import get_session_store
from app.core.environment import allow_detailed_diagnostics, get_environment
from app.core.logging import configure_logging, get_logger
from app.services.process_job_service import recover_interrupted_processes_async

env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)
load_dotenv()
configure_logging()
logger = get_logger("app.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Avvio locale: verifica API key e recupera i job interrotti."""
    if not os.getenv("GOOGLE_API_KEY"):
        logger.warning(
            "GOOGLE_API_KEY non configurata: le generazioni falliranno. "
            "Aggiungi GOOGLE_API_KEY=... al file .env nella root del progetto.",
        )
    session_store = get_session_store()
    recovered_jobs = await recover_interrupted_processes_async(session_store)
    if recovered_jobs:
        logger.warning(
            "Job interrotti recuperati allo startup",
            context={"count": recovered_jobs},
        )

    yield


app = FastAPI(title="NarrAI API", version="0.2.0", lifespan=lifespan)
app.state.environment = get_environment()
app.state.allow_detailed_diagnostics = allow_detailed_diagnostics()

frontend_url = os.getenv("FRONTEND_URL", "")
cors_origins = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:3000",
]
if frontend_url:
    cors_origins.append(frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

app.include_router(config_router.router)
app.include_router(submission.router)
app.include_router(questions.router)
app.include_router(draft.router)
app.include_router(outline.router)
app.include_router(book.router)
app.include_router(library.router)
app.include_router(critique.router)
app.include_router(session.router)
app.include_router(health.router)
app.include_router(files.router)
app.include_router(manga.router)




static_path = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.exists(static_path):
    static_root = Path(static_path).resolve()
    assets_path = os.path.join(static_path, "assets")
    if os.path.exists(assets_path):
        app.mount("/assets", StaticFiles(directory=assets_path), name="assets")

    @app.get("/favicon.svg")
    async def serve_favicon():
        favicon_path = os.path.join(static_path, "favicon.svg")
        if os.path.exists(favicon_path):
            return FileResponse(favicon_path, media_type="image/svg+xml")
        raise HTTPException(status_code=404, detail="Favicon not found")

    @app.get("/manifest.webmanifest")
    async def serve_manifest():
        manifest_path = os.path.join(static_path, "manifest.webmanifest")
        if os.path.exists(manifest_path):
            return FileResponse(manifest_path, media_type="application/manifest+json")
        raise HTTPException(status_code=404, detail="Manifest not found")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")

        normalized_path = full_path.lstrip("/\\")
        if normalized_path:
            requested_file = (static_root / normalized_path).resolve()
            try:
                requested_file.relative_to(static_root)
            except ValueError as exc:
                raise HTTPException(status_code=404, detail="Not found") from exc

            if requested_file.is_file():
                return FileResponse(str(requested_file))
            if Path(normalized_path).suffix:
                raise HTTPException(status_code=404, detail="Static asset not found")

        index_path = static_root / "index.html"
        if index_path.exists():
            return FileResponse(
                str(index_path),
                headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
            )
        raise HTTPException(status_code=404, detail="Frontend not found")

# NarrAI — generazione locale di romanzi

App single-user per creare romanzi (e manga in beta) con **Gemini Developer API**.
Tutto gira in locale: FastAPI + React, persistenza su file JSON, nessuna autenticazione e nessun cloud.

## Documentazione

- [Modelli e costi](docs/MODELLI_E_COSTI.md): mappa Gemini per attività e stime per un libro da 100 pagine.
- [Documentazione tecnica](docs/TECNICA.md): architettura e stack (versione locale).
- [Documentazione funzionale](docs/FUNZIONALE.md): flusso di generazione.

## Prerequisiti

- Python 3.11+ e [uv](https://github.com/astral-sh/uv)
- Node.js 18+ e npm
- Una chiave [Gemini API](https://aistudio.google.com/apikey)

## Quick start

### 1. Chiave API

Copia `.env.example` in `.env` nella root del repo e inserisci la chiave:

```env
GOOGLE_API_KEY=la_tua_chiave_gemini

# Opzionale, solo per TTS:
# GOOGLE_APPLICATION_CREDENTIALS=credentials/narrai-app-credentials.json
```

Non committare `.env`. Senza `GOOGLE_API_KEY` l'app parte ma le generazioni falliscono.

### 2. Backend (porta 8000)

```powershell
cd backend
uv sync
uv run uvicorn app.main:app --reload --reload-dir app --host 127.0.0.1 --port 8000
```

> Con `--reload` limita il watch a `app/`: PDF e copertine vengono scritti in `backend/books/` e `backend/sessions/` e possono innescare un restart.

### 3. Frontend (porta 5173)

```powershell
cd frontend
npm install
npm run dev
```

Il proxy Vite inoltra `/api` a `http://127.0.0.1:8000`. Apri `http://localhost:5173`.

## Funzionalità

- Wizard libro: domande, bozza, outline, scrittura capitoli, copertina, critica
- Libreria locale con export PDF / EPUB / DOCX
- Manga beta
- Analytics e benchmark sui libri generati in locale
- TTS opzionale (Google Cloud Text-to-Speech) se è presente un service account JSON

Rimosso rispetto alla versione cloud: login, crediti, social, GDPR, MongoDB, GCS, Vertex AI, OpenAI.

## Persistenza

Sessioni e libri stanno in file JSON sotto `backend/` (`sessions/`, `books/`, `manga/`). Niente database da avviare.

## Test

```powershell
cd backend
uv run pytest

cd ..\frontend
npm run typecheck
npm run test:run
npm run build
```

# NarrAI — generazione locale di romanzi

App single-user per creare romanzi (e manga in beta) con **Gemini Developer API**.
Interfaccia, backend e archivio girano in locale: FastAPI + React, persistenza transazionale SQLite e nessuna autenticazione. La generazione invia il contesto narrativo alle API di Google; richiede una connessione Internet.

## Documentazione

- [Modelli e costi](docs/MODELLI_E_COSTI.md): listino verificato, registro dei consumi e limiti delle stime.
- [Documentazione tecnica](docs/TECNICA.md): architettura e stack (versione locale).
- [Documentazione funzionale](docs/FUNZIONALE.md): flusso di generazione.
- [Revisione e priorità](docs/REVISIONE_2026-09-20.md): difetti corretti, verifiche e cinque aree di miglioramento.
- [Evolutive implementate](docs/EVOLUTIVE_2026-09-20.md): studio, processi durevoli, memoria, migrazione e backup.

## Prerequisiti

- Python 3.11+ e [uv](https://github.com/astral-sh/uv)
- Node.js 18+ e npm
- Una chiave [Gemini API](https://aistudio.google.com/apikey)

## Quick start

### 1. Chiave API

Copia `.env.example` in `.env` nella root del repo e inserisci la chiave:

```env
GOOGLE_API_KEY=la_tua_chiave_gemini

# Opzionale: percorso alternativo dell'archivio SQLite
# NARRAI_DB_PATH=C:/archivi/narrai.sqlite3
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
- Studio del manoscritto: editor con revisioni, prove narrative, pausa/ripresa e costi per richiesta
- Memoria dei fatti documentati, controllo della continuità e recupero dei processi al riavvio
- Libreria locale con export PDF / EPUB / DOCX
- Manga beta
- Analytics e benchmark sui libri generati in locale
- Audio opzionale tramite Gemini TTS, con la stessa chiave API

Rimosso rispetto alla versione cloud: login, crediti, social, GDPR, MongoDB, GCS, Vertex AI, OpenAI.

## Persistenza

L'archivio è `backend/narrai.sqlite3` (o `NARRAI_DB_PATH`); non serve avviare un database separato. Al primo avvio viene importato `.sessions.json` dalla stessa directory, preservando originale e copia `.pre-sqlite.bak`. PDF e audio restano in `backend/books/`, copertine in `backend/sessions/`, tavole manga in `backend/manga/`.

I job vengono accodati nel database e recuperati al riavvio del backend. La pausa volontaria e gli errori richiedono una ripresa esplicita. Per backup consistenti e rollback vedi [evolutive](docs/EVOLUTIVE_2026-09-20.md).

## Test

```powershell
cd backend
uv run pytest

cd ..\frontend
npm run typecheck
npm run test:run
npm run build
```

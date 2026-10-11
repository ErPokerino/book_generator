# NarrAI — studio locale per narrativa, saggi e fumetti

App single-user per creare narrativa, saggi documentati e fumetti (Manga e Graphic Novel, in beta) con **Gemini Developer API**. Le tre modalità condividono navigazione, biblioteca e lettore; il saggio conserva fonti, citazioni e revisione argomentativa di SaggIA. Valuta usa criteri adatti al formato e Analisi raccoglie produzione e consumi dei tre percorsi.
Interfaccia, backend e archivi girano in locale: FastAPI + React, persistenza transazionale SQLite e nessuna autenticazione. Generazione, ricerca e valutazione inviano ai servizi Google il contesto necessario dell’opera; richiedono Internet. Stato documentato: **11 ottobre 2026**.

## Documentazione

- [Indice della documentazione](docs/README.md): guide correnti e documenti storici.
- [Modelli e costi](docs/MODELLI_E_COSTI.md): catalogo applicato, registro dei consumi e limiti delle stime.
- [Studio unificato](docs/NARRAI_UNIFICATO.md): integrazione SaggIA, archivio, nuova UI e verifiche.
- [Documentazione tecnica](docs/TECNICA.md): architettura e stack (versione locale).
- [Documentazione funzionale](docs/FUNZIONALE.md): tre modalità, lettura, valutazione e analisi.
- [Operazioni](docs/OPERAZIONI.md): avvio, backup dei due archivi, ripristino e importazione SaggIA.

## Prerequisiti

- Python 3.11+ e [uv](https://github.com/astral-sh/uv)
- Node.js 22.13+ e npm, per l’intera toolchain di sviluppo e test
- Una chiave [Gemini API](https://aistudio.google.com/apikey)

## Quick start

Su Windows l’unico avvio è **avvia.cmd**, che apre NarrAI con tutte e tre le modalità. Il lancio manuale è descritto sotto.

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
npm ci
npm run dev
```

Il proxy Vite inoltra `/api` a `http://127.0.0.1:8000`. Apri `http://localhost:5173`.

## Funzionalità

- Percorso Narrativa: domande, bozza, outline, scrittura capitoli, copertina, critica
- Studio del manoscritto: editor con revisioni, prove narrative, pausa/ripresa e costi per richiesta
- Memoria dei fatti documentati, controllo della continuità e recupero dei processi al riavvio
- Libreria locale con export PDF / EPUB / DOCX
- Saggi argomentativi, divulgativi e accademici: brief, domande, piano approvato, fonti, evidenze, indice, capitoli, revisione e copertina
- Lunghezza dei saggi in pagine e previsione di costo/tempo, disponibile anche senza storico
- Biblioteca comune con ricerca, tipo di opera, stato, genere/profilo e ordinamento
- Lettura da copertina e titolo, lettore comune con indice e segnalibro, eliminazione per tutte le opere
- Fumetto: Manga e Graphic Novel con sottogeneri dedicati, storyboard e prompt visivi coerenti, pausa e ripresa
- Valuta: PDF esterni o opere della biblioteca, con criteri narrativi, argomentativi o visivi
- Analisi: opere e stati, parole, capitoli, tavole, consumi registrati e copertura dei dati
- Impostazioni: suoni di carta e scrittura facoltativi; stile bianco e nero con dettagli disegnati a mano
- Suoni discreti anche al passaggio del mouse sulle tre modalità, dopo la prima interazione e solo se abilitati
- Audio opzionale tramite Gemini TTS, con la stessa chiave API

Rimosso rispetto alla versione cloud: login, crediti, social, GDPR, MongoDB, GCS, Vertex AI, OpenAI.

## Persistenza

I saggi conservano l'archivio compatibile con SaggIA in `backend/data/saggistica/saggia.sqlite3`, insieme a fonti e copertine. `SAGGIA_DATA_DIR` permette di scegliere una directory diversa. I worker delle tre modalità condividono il backend e mantengono separati archivi e consumi. Per importare un precedente archivio SaggIA, vedi [studio unificato](docs/NARRAI_UNIFICATO.md).

L'archivio è `backend/narrai.sqlite3` (o `NARRAI_DB_PATH`); non serve avviare un database separato. Al primo avvio viene importato `.sessions.json` dalla stessa directory, preservando originale e copia `.pre-sqlite.bak`. PDF e audio restano in `backend/books/`, copertine in `backend/sessions/`, tavole manga in `backend/manga/`.

I job vengono accodati nel database e recuperati al riavvio del backend. La pausa volontaria e gli errori richiedono una ripresa esplicita. Per backup consistenti e ripristino dei due archivi vedi [operazioni](docs/OPERAZIONI.md). Nuovi archivi, documenti prodotti, credenziali e build sono esclusi da Git; i PDF dimostrativi storici già versionati non sono richiesti per avviare l’app.

## Test

```powershell
cd backend
uv run pytest

cd ..\frontend
npm run typecheck
npm run test:run -- --maxWorkers=2
npm run build
```

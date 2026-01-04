# NarrAI - Agente di Scrittura Romanzi

Sistema per la creazione di romanzi personalizzati utilizzando modelli LLM della famiglia Google Gemini.

## Documentazione

Per approfondire l'applicazione, consulta la documentazione completa:

- **[Documentazione Tecnica](docs/TECNICA.md)**: Architettura, stack tecnologico, struttura del codice, API design, sistema di persistenza, configurazione e pattern implementati.
- **[Documentazione Funzionale](docs/FUNZIONALE.md)**: Flussi utente, logiche di business, processi di generazione, calcoli e metriche, validazioni e regole.
- **[Guida Deploy](DEPLOY.md)**: Istruzioni per il deploy su Google Cloud Run.

Questa documentazione (README.md) contiene informazioni essenziali per setup e utilizzo rapido.

## Prerequisiti

- **Python 3.11+**
- **uv** (gestore pacchetti Python) - [Installazione](https://github.com/astral-sh/uv)
- **Node.js 18+** e **npm**
- **MongoDB** (opzionale, può usare MongoDB Atlas o Docker locale)
- **Docker** (opzionale, per MongoDB locale) - [Installazione](https://www.docker.com/get-started)

## Quick Start

### 1. Configurazione Variabili d'Ambiente

Crea un file `.env` nella root del progetto:

```env
# Obbligatorio
GOOGLE_API_KEY=your_gemini_api_key_here

# Opzionale (MongoDB - se non configurato usa File JSON)
MONGODB_URI=mongodb://admin:admin123@localhost:27017/narrai?authSource=admin

# Opzionale (Autenticazione - default generato)
SESSION_SECRET=change-me-in-production-secret-key
SESSION_EXPIRE_DAYS=7

# Opzionale (Email service - per verifica email e password reset)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
FRONTEND_URL=http://localhost:5173

# Opzionale (Google Cloud Storage - per produzione)
GCS_ENABLED=false
GCS_BUCKET_NAME=your-bucket-name
GOOGLE_APPLICATION_CREDENTIALS=path/to/credentials.json
```

### 2. Backend (FastAPI)

```bash
# Installa dipendenze
cd backend
uv sync

# Avvia il server
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Il backend sarà disponibile su `http://localhost:8000`

> **Note per Windows PowerShell**: Se usi PowerShell, esegui i comandi separatamente invece di usare `&&`:
> ```powershell
> cd backend
> uv sync
> uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
> ```

### 3. Frontend (React)

```bash
# Installa dipendenze
cd frontend
npm install

# Avvia il server di sviluppo
npm run dev
```

Il frontend sarà disponibile su `http://localhost:5173`

### 4. MongoDB Locale (Opzionale)

Per sviluppo locale con MongoDB usando Docker:

```bash
# Avvia MongoDB e Mongo Express
docker-compose up -d

# MongoDB: mongodb://localhost:27017
# Mongo Express (UI): http://localhost:8081
# Credenziali: vedi docker-compose.yml
```

## Configurazione Essenziale

### Variabili d'Ambiente Minime

**Per funzionamento base** (senza autenticazione email e storage cloud):
- `GOOGLE_API_KEY`: Obbligatoria per chiamate LLM

**Per autenticazione completa**:
- `GOOGLE_API_KEY`: Obbligatoria
- `MONGODB_URI`: Consigliata (altrimenti usa File JSON)
- `SESSION_SECRET`: Consigliata per produzione
- `SMTP_*`: Opzionali (per email verification e password reset)

**Per produzione/cloud**:
- `GOOGLE_API_KEY`: Obbligatoria
- `MONGODB_URI`: Obbligatoria
- `SESSION_SECRET`: Obbligatoria
- `GCS_*`: Opzionali (per storage cloud)

Per dettagli completi sulla configurazione, consulta [Documentazione Tecnica - Configurazione](docs/TECNICA.md#configurazione).

## Struttura del Progetto

```
scrittura-libro/
├── backend/          # Backend FastAPI
│   ├── app/         # Codice applicazione
│   │   ├── agent/   # Agenti AI (generazione, critica, copertina)
│   │   ├── api/     # API routers
│   │   ├── services/# Business logic services
│   │   └── ...
│   └── pyproject.toml
├── frontend/        # Frontend React + Vite
│   ├── src/
│   │   ├── components/  # Componenti React
│   │   ├── api/         # Client API
│   │   └── ...
│   └── package.json
├── config/          # File di configurazione
│   ├── inputs.yaml      # Configurazione form
│   ├── app.yaml         # Configurazione applicazione
│   └── ...
├── docs/            # Documentazione dettagliata
│   ├── FUNZIONALE.md
│   └── TECNICA.md
└── .env             # Variabili d'ambiente (da creare)
```

## Funzionalità Principali

- **Generazione Automatica**: Scrittura capitoli con processo autoregressivo per coerenza narrativa
- **Export Multiformato**: PDF, EPUB, DOCX con layout professionale
- **Critica Letteraria**: Valutazione automatica AI con score, punti di forza/debolezza
- **Calcolo Costi**: Stima automatica basata su token utilizzati e modelli LLM
- **Statistiche Avanzate**: Analytics con grafici temporali e confronto modelli (admin-only)
- **Autenticazione Utenti**: Registrazione, login, email verification, password reset
- **Ripristino Sessione**: Continuazione processi interrotti con stato persistito
- **Copertina AI**: Generazione automatica immagini copertina con Gemini

Per dettagli completi, consulta [Documentazione Funzionale](docs/FUNZIONALE.md).

## Interfaccia Utente

L'applicazione è organizzata in quattro sezioni principali:

- **📚 Libreria**: Visualizzazione libri con filtri, ricerca, ordinamento, export e azioni (leggi, elimina, riprendi)
- **📖 Nuovo Libro**: Wizard guidato con form semplificato (Base/Avanzate) e step indicator
- **📊 Analisi**: Dashboard statistiche con grafici temporali e confronto modelli (solo admin)
- **🎯 Valuta**: Valutazione e confronto modelli LLM

Per dettagli sulle funzionalità, consulta [Documentazione Funzionale](docs/FUNZIONALE.md).

## Note Tecniche

Per approfondimenti tecnici dettagliati, consulta [Documentazione Tecnica](docs/TECNICA.md) che copre:

- Architettura sistema e pattern implementati
- Stack tecnologico completo
- Struttura del codice e organizzazione
- Sistema di persistenza (MongoDB/File)
- Sistema di autenticazione (JWT, UserStore)
- Design API RESTful
- Configurazione e gestione dati
- Pattern e convenzioni di sviluppo

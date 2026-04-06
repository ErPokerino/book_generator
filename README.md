# NarrAI - Agente di Scrittura Romanzi

Sistema per la creazione di romanzi personalizzati utilizzando modelli LLM della famiglia Google Gemini.
In produzione il backend usa Vertex AI; in sviluppo locale e' disponibile un fallback compatibile via Gemini Developer API.

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
# Opzione A (consigliata): sviluppo locale con Vertex AI
GOOGLE_LLM_PROVIDER=vertex
GOOGLE_CLOUD_PROJECT=your-gcp-project
GOOGLE_CLOUD_LOCATION=global
GOOGLE_GENAI_USE_VERTEXAI=true
# Autenticazione locale via ADC:
# gcloud auth application-default login

# Opzione B (fallback compatibilita'): Gemini Developer API
# GOOGLE_API_KEY=your_gemini_api_key_here

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

# Opzionale (Google Cloud Text-to-Speech - per audiobook critica)
# Riusa GOOGLE_APPLICATION_CREDENTIALS se stai usando un service account locale
```

Per lo sviluppo locale puoi quindi scegliere tra due modalita':
- `Vertex AI`: usa `GOOGLE_LLM_PROVIDER=vertex`, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION=global` e ADC (`gcloud auth application-default login` o un service account JSON).
- `Gemini Developer API`: lascia assenti le variabili Vertex e imposta solo `GOOGLE_API_KEY`.

In Cloud Run non e' necessaria `GOOGLE_API_KEY`: il servizio usa ADC tramite il service account associato e Vertex AI con endpoint `global`.

### 2. Backend (FastAPI)

```bash
# Installa dipendenze
cd backend
uv sync

# Avvia il server
uv run uvicorn app.main:app --reload --reload-dir app --host 0.0.0.0 --port 8000
```

Il backend sarà disponibile su `http://localhost:8000`

> Nota: durante la generazione di PDF/cover il backend può scrivere file in `backend/books/` e `backend/sessions/`.
> Se usi `--reload` e watchi tutta `backend/`, queste scritture possono triggerare reload e interrompere richieste in corso (nel browser appare “Failed to fetch”).
> Per test “lunghi” puoi anche avviare senza `--reload`.

> **Note per Windows PowerShell**: Se usi PowerShell, usa `;` invece di `&&` per concatenare comandi, oppure eseguili separatamente:
> ```powershell
> # Opzione 1: Usa ; come separatore
> cd backend; uv run uvicorn app.main:app --reload --reload-dir app --host 0.0.0.0 --port 8000
> 
> # Opzione 2: Esegui i comandi separatamente
> cd backend
> uv run uvicorn app.main:app --reload --reload-dir app --host 0.0.0.0 --port 8000
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

> **Note per Windows PowerShell**: Usa `;` invece di `&&` per concatenare comandi:
> ```powershell
> cd frontend; npm run dev
> ```

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

**Per funzionamento base in locale** (senza autenticazione email e storage cloud):
- `GOOGLE_API_KEY`, oppure
- `GOOGLE_LLM_PROVIDER=vertex` + `GOOGLE_CLOUD_PROJECT` + `GOOGLE_CLOUD_LOCATION=global` + credenziali ADC

**Per autenticazione completa**:
- Una configurazione LLM valida tra quelle sopra
- `MONGODB_URI`: Consigliata (altrimenti usa File JSON)
- `SESSION_SECRET`: Consigliata per produzione
- `SMTP_*`: Opzionali (per email verification e password reset)

**Per produzione/cloud**:
- `GOOGLE_LLM_PROVIDER=vertex`
- `GOOGLE_GENAI_USE_VERTEXAI=true`
- `GOOGLE_CLOUD_PROJECT`: Obbligatoria
- `GOOGLE_CLOUD_LOCATION=global`: Obbligatoria
- `MONGODB_URI`: Obbligatoria
- `SESSION_SECRET`: Obbligatoria
- `GCS_*`: Opzionali (per storage cloud)
- `GOOGLE_API_KEY`: Non richiesta sul path Cloud Run/Vertex standard

Per dettagli completi sulla configurazione, consulta [Documentazione Tecnica - Configurazione](docs/TECNICA.md#configurazione).

## Struttura del Progetto

```
scrittura-libro/
├── backend/              # Backend FastAPI
│   ├── app/             # Codice applicazione
│   │   ├── agent/       # Agenti AI e Store MongoDB
│   │   ├── api/routers/ # 18 Router REST organizzati
│   │   ├── services/    # 10 Business logic services
│   │   ├── analytics/   # Tools analisi dati
│   │   ├── middleware/  # Autenticazione e autorizzazione
│   │   └── utils/       # Utility functions
│   └── pyproject.toml
├── frontend/            # Frontend React + Vite
│   ├── src/
│   │   ├── components/  # 50+ Componenti React
│   │   ├── contexts/    # AuthContext, NotificationContext
│   │   ├── hooks/       # Custom hooks (polling, toast)
│   │   ├── api/         # Client API TypeScript
│   │   └── routing/     # Route guards (RequireAuth, RequireAdmin)
│   └── package.json
├── config/              # File di configurazione
│   ├── inputs.yaml      # Configurazione form dinamico
│   ├── app.yaml         # Configurazione applicazione
│   └── ...
├── docs/                # Documentazione dettagliata
│   ├── FUNZIONALE.md    # Flussi utente e logiche
│   └── TECNICA.md       # Architettura e stack
└── .env                 # Variabili d'ambiente (da creare)
```

## Funzionalità Principali

- **Generazione Automatica**: Scrittura capitoli con processo autoregressivo per coerenza narrativa
- **Export Multiformato**: PDF, EPUB, DOCX con layout professionale
- **Critica Letteraria**: Valutazione automatica AI con score, punti di forza/debolezza
- **Audiobook Critica**: Lettura vocale della critica letteraria con Google Cloud Text-to-Speech
- **Calcolo Costi**: Stima automatica basata su token utilizzati e modelli LLM
- **Statistiche Avanzate**: Analytics con grafici temporali e confronto modelli (admin-only)
- **Autenticazione Utenti**: Registrazione, login, email verification, password reset
- **Condivisione Libri**: Condivisione libri tra utenti connessi con notifiche in-app
- **Sistema di Connessioni**: Sezione "La tua rete" per connessioni tra utenti
- **Notifiche In-App**: Sistema notifiche in-app con polling automatico per condivisioni e connessioni
- **Sistema Referral**: Inviti esterni con tracking e statistiche (conteggio unico per email)
- **Onboarding Interattivo**: Carousel guidato per nuovi utenti con 5 step informativi
- **Ripristino Sessione**: Continuazione processi interrotti con stato persistito
- **Copertina AI**: Generazione automatica immagini copertina con Gemini
- **Ottimizzazione Mobile**: Bottom navigation, filtri collassabili, tab icone, empty state CTA

Per dettagli completi, consulta [Documentazione Funzionale](docs/FUNZIONALE.md).

## Progressive Web App (PWA)

NarrAI è installabile come applicazione nativa su dispositivi mobile e desktop:

- **Installazione**: Clicca "Aggiungi alla schermata Home" dal browser mobile o "Installa app" su desktop
- **Offline**: Service worker per caching risorse statiche e funzionalità offline
- **Icone**: Ottimizzate per tutti i contesti (circolari Android con safe zone, quadrate iOS)
- **Splash Screen**: Animazione di caricamento con icona e branding
- **Manifest**: Configurazione PWA completa con theme color e background color coerenti

Le icone vengono generate automaticamente da `app-icon-original.png` usando lo script `frontend/scripts/generate-icons.js` che crea versioni standard e maskable per supporto completo su tutti i dispositivi.

## Interfaccia Utente

L'applicazione è organizzata in cinque sezioni principali:

- **📚 Libreria**: Visualizzazione libri con filtri collassabili, ricerca, ordinamento, export e azioni
- **📖 Nuovo Libro**: Wizard guidato con form semplificato (Base/Avanzate) e step indicator
- **👥 La tua rete**: Connessioni tra utenti, richieste pendenti, inviti referral
- **📊 Analisi**: Dashboard statistiche con grafici temporali e confronto modelli (solo admin)
- **🎯 Valuta**: Valutazione e confronto modelli LLM

**Mobile**: Bottom navigation con 4 tab (Libreria, Nuovo, Rete, Profilo) e badge notifiche.

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

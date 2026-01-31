# Documentazione Tecnica - NarrAI

## Indice

1. [Architettura del Sistema](#architettura-del-sistema)
2. [Stack Tecnologico](#stack-tecnologico)
3. [Struttura del Codice](#struttura-del-codice)
4. [Sistema di Persistenza](#sistema-di-persistenza)
5. [API Design](#api-design)
6. [Configurazione](#configurazione)
7. [Gestione Dati](#gestione-dati)
8. [Pattern e Convenzioni](#pattern-e-convenzioni)
9. [GDPR Compliance - Implementazione Tecnica](#gdpr-compliance---implementazione-tecnica)

## Architettura del Sistema

### Panoramica

NarrAI è un'applicazione full-stack per la generazione automatica di libri utilizzando modelli LLM (Large Language Models) della famiglia Google Gemini.

```mermaid
graph TB
    subgraph Client["Frontend (React + TypeScript)"]
        UI[Interfaccia Utente]
        API_Client[API Client]
    end
    
    subgraph Server["Backend (FastAPI + Python)"]
        Router[API Routers]
        Services[Business Services]
        Agents[AI Agents]
        SessionStore[Session Store]
        UserStore[User Store]
        BookShareStore[BookShare Store]
        ConnectionStore[Connection Store]
        NotificationStore[Notification Store]
        ReferralStore[Referral Store]
    end
    
    subgraph Storage["Persistenza"]
        MongoDB[(MongoDB)]
        FileStore[File JSON<br/>Fallback]
    end
    
    subgraph External["Servizi Esterni"]
        Gemini[Google Gemini API]
        EmailService[Email Service SMTP]
    end
    
    UI --> API_Client
    API_Client --> Router
    Router --> Services
    Services --> Agents
    Agents --> Gemini
    Services --> SessionStore
    Services --> UserStore
    Services --> BookShareStore
    Services --> ConnectionStore
    Services --> NotificationStore
    Services --> ReferralStore
    Services --> EmailService
    SessionStore --> MongoDB
    SessionStore --> FileStore
    UserStore --> MongoDB
    BookShareStore --> MongoDB
    ConnectionStore --> MongoDB
    NotificationStore --> MongoDB
    ReferralStore --> MongoDB
    
    style Client fill:#e1f5ff
    style Server fill:#fff4e1
    style Storage fill:#e8f5e9
    style External fill:#fce4ec
```

### Pattern Architetturali

L'applicazione adotta una **Clean Architecture** semplificata con separazione delle responsabilità:

- **Presentation Layer** (Frontend): Componenti React per l'interfaccia utente
- **API Layer** (Backend Routers): Endpoint REST organizzati per dominio
- **Business Logic Layer** (Services): Logica di business e orchestrazione
- **Domain Layer** (Agents): Agenti AI specializzati per ogni fase
- **Infrastructure Layer** (SessionStore, Config): Persistenza e configurazione

### Separazione delle Responsabilità

- **Agenti AI** (`backend/app/agent/`): Contengono la logica di interazione con i modelli LLM
- **Servizi** (`backend/app/services/`): Implementano logica di business (calcolo costi, export, statistiche)
- **Router** (`backend/app/api/routers/`): Gestiscono le richieste HTTP e la validazione
- **Modelli** (`backend/app/models.py`): Definiscono gli schema Pydantic per validazione dati

## Stack Tecnologico

### Backend

- **Framework**: FastAPI 0.104.0+
- **Python**: 3.11+
- **Package Manager**: uv (Astral)
- **Database**: 
  - MongoDB (con driver async `motor`)
  - Fallback: File JSON (FileSessionStore)
- **LLM Integration**: 
  - `langchain-google-genai` 2.0.0+
  - `google-generativeai` 0.8.0+
- **Text-to-Speech**: 
  - `google-cloud-texttospeech` 2.16.0+ (audiobook critica)
- **PDF Generation**: 
  - `xhtml2pdf` 0.2.11+
  - `reportlab` 4.0.0+
- **Export**: 
  - `ebooklib` 0.18+ (EPUB)
  - `python-docx` 1.1.0+ (DOCX)
- **Configurazione**: PyYAML 6.0.1+
- **Validazione**: Pydantic 2.5.0+

### Frontend

- **Framework**: React 18+
- **Language**: TypeScript 5+
- **Build Tool**: Vite 5+
- **PWA**: vite-plugin-pwa 0.20+ (service worker, manifest)
- **Styling**: CSS Modules + CSS Variables
- **Charts**: Recharts 3+
- **Notifications**: react-hot-toast 2+
- **Icons**: lucide-react 0.400+ (icon library)
- **Drag & Drop**: @dnd-kit/core, @dnd-kit/sortable 6+
- **Markdown**: react-markdown 10+, remark-gfm 4+
- **HTTP Client**: Fetch API nativo
- **Image Processing**: sharp (Node.js, per generazione icone)

### Infrastruttura

- **Database**: MongoDB 7.0+ (Docker o Atlas)
- **Admin UI**: Mongo Express (opzionale, sviluppo locale)
- **Orchestrazione**: Docker Compose (sviluppo locale)
- **Email Service**: SMTP (Gmail o altro provider)
- **Cloud Storage**: Google Cloud Storage (opzionale, produzione)
- **Deploy**: Google Cloud Run (con Cloud Build)

## Struttura del Codice

### Backend (`backend/app/`)

```
backend/app/
├── main.py                 # Entry point FastAPI, lifecycle hooks
├── models.py               # Schema Pydantic per validazione
├── agent/                  # Agenti AI e Store MongoDB
│   ├── question_generator.py      # Genera domande preliminari
│   ├── draft_generator.py         # Genera bozza estesa
│   ├── outline_generator.py       # Genera struttura libro
│   ├── writer_generator.py        # Genera capitoli (autoregressivo)
│   ├── literary_critic.py         # Valuta libro completato
│   ├── cover_generator.py         # Genera copertina AI
│   ├── session_store.py           # Interface + FileSessionStore
│   ├── mongo_session_store.py     # MongoDB implementation sessioni
│   ├── session_store_helpers.py   # Helper async/sync compatibility
│   ├── user_store.py              # Gestione utenti MongoDB
│   ├── book_share_store.py        # Condivisione libri tra utenti
│   ├── connection_store.py        # Connessioni tra utenti
│   ├── notification_store.py      # Notifiche in-app
│   ├── referral_store.py          # Sistema referral/inviti
│   └── state.py                   # Gestione stato applicazione
├── api/                   # Layer API
│   ├── deps.py            # Dependency injection FastAPI
│   └── routers/           # 18 Router REST organizzati per dominio
│       ├── admin.py       # Statistiche utenti (admin-only)
│       ├── auth.py        # Autenticazione (login, register, verify)
│       ├── book.py        # Generazione e gestione libri
│       ├── book_shares.py # Condivisione libri
│       ├── config.py      # GET /api/config
│       ├── connections.py # Connessioni tra utenti
│       ├── critique.py    # Critica letteraria e audio
│       ├── draft.py       # Generazione/modifica bozza
│       ├── files.py       # Download file (PDF, cover)
│       ├── health.py      # Health check endpoint
│       ├── library.py     # Libreria utente e statistiche
│       ├── notifications.py # Notifiche in-app
│       ├── outline.py     # Generazione/modifica struttura
│       ├── questions.py   # Domande preliminari
│       ├── referrals.py   # Sistema inviti referral
│       ├── session.py     # Gestione sessioni libro
│       └── submission.py  # Creazione nuova sessione
├── analytics/             # Tools analisi dati
│   ├── estimate_linear_params.py  # Stima parametri lineari
│   └── export_chapter_timings.py  # Export tempi capitoli CSV
├── core/                  # Configurazione centralizzata
│   └── config.py          # Caricamento YAML, cache
├── middleware/            # Middleware FastAPI
│   └── auth.py            # Autenticazione e autorizzazione
├── services/              # 10 Business logic services
│   ├── book_generation_service.py # Orchestrazione generazione libro
│   ├── cost_service.py            # Calcolo costi generazione
│   ├── critique_service.py        # Generazione critica letteraria
│   ├── email_service.py           # Invio email (SMTP)
│   ├── export_service.py          # Export EPUB/DOCX
│   ├── generation_service.py      # Servizio generazione generico
│   ├── library_service.py         # Gestione libreria
│   ├── pdf_service.py             # Generazione PDF
│   ├── stats_service.py           # Calcolo statistiche
│   └── storage_service.py         # Storage GCS/locale
├── utils/                 # Utility functions
│   └── stats_utils.py     # Utility statistiche
├── static/                # File statici (CSS PDF)
│   └── book_styles.css
└── templates/             # Template HTML
    └── book_template.html
```

### Frontend (`frontend/src/`)

```
frontend/src/
├── App.tsx                # Componente root, routing, Toaster
├── main.tsx               # Entry point React
├── router.tsx             # Configurazione routing
├── api/
│   └── client.ts          # Client API TypeScript, tipi, funzioni API
├── components/            # Componenti React modulari
│   ├── DynamicForm.tsx    # Wizard creazione libro (Base/Avanzate, step indicator)
│   ├── PlotTextarea.tsx   # Textarea avanzata (autosave, modale, contatori)
│   ├── LibraryView.tsx    # Visualizzazione libreria (filtri, ricerca, ordinamento)
│   ├── FilterBar.tsx      # Filtri libreria (collassabili su mobile)
│   ├── AnalyticsView.tsx  # Dashboard statistiche (admin-only)
│   ├── BenchmarkView.tsx  # Valutazione modelli LLM
│   ├── BookReader.tsx     # Visualizzatore libro completo
│   ├── BookViewer.tsx     # Visualizzatore libro compatto
│   ├── BookCard.tsx       # Card libro nella libreria
│   ├── OutlineEditor.tsx  # Editor drag-and-drop struttura
│   ├── WritingStep.tsx    # Monitoraggio generazione
│   ├── DraftStep.tsx      # Generazione/modifica bozza (manuale + LLM)
│   ├── DraftChat.tsx      # Chat modifica bozza interattiva (approccio chirurgico)
│   ├── DraftViewer.tsx    # Visualizzatore/Editor bozza (toggle view/edit)
│   ├── ConnectionsView.tsx    # Gestione connessioni e referral
│   ├── ShareBookModal.tsx     # Modal condivisione libro
│   ├── NotificationBell.tsx   # Icona notifiche con badge
│   ├── Navigation.tsx         # Header navigazione desktop
│   ├── BottomNavigation.tsx   # Navigazione bottom bar mobile
│   ├── Dashboard.tsx          # Dashboard view
│   ├── CritiqueModal.tsx      # Modal critica letteraria
│   ├── CritiqueAudioPlayer.tsx # Player audio critica
│   ├── ExportDropdown.tsx     # Dropdown export formati
│   ├── ModelComparisonTable.tsx # Tabella confronto modelli
│   ├── Skeleton.tsx       # Skeleton loaders (SkeletonText, SkeletonCard, etc.)
│   ├── AlertModal.tsx     # Modal alert
│   ├── ConfirmModal.tsx   # Modal conferma
│   ├── LoginPage.tsx      # Pagina login
│   ├── RegisterPage.tsx   # Pagina registrazione
│   ├── ForgotPasswordPage.tsx  # Richiesta reset password
│   ├── ResetPasswordPage.tsx   # Reset password
│   ├── VerifyEmailPage.tsx     # Verifica email
│   ├── Onboarding/        # Componenti onboarding
│   │   ├── OnboardingCarousel.tsx  # Carousel 5 step
│   │   └── OnboardingTooltip.tsx   # Tooltip guidati
│   ├── routing/           # Route Guards
│   │   ├── RequireAuth.tsx     # Guard autenticazione
│   │   └── RequireAdmin.tsx    # Guard ruolo admin
│   └── ui/                # Componenti UI riutilizzabili
│       ├── FadeIn.tsx         # Animazione fade-in
│       ├── ProgressBar.tsx    # Barra progresso
│       ├── ProcessProgressIndicator.tsx  # Indicatore progresso processo
│       └── icons/             # Icone SVG
│           ├── ModeIcons.tsx  # Icone modalità (Flash, Pro, Ultra)
│           └── StepIcons.tsx  # Icone step wizard
├── contexts/              # React Context
│   ├── AuthContext.tsx    # Autenticazione (AuthProvider, useAuth)
│   └── NotificationContext.tsx  # Notifiche (polling, badge)
├── hooks/                 # Custom hooks
│   ├── useOnboarding.ts   # Gestione stato onboarding
│   ├── useProcessPolling.ts   # Polling stato processi
│   └── useToast.ts        # Gestione toast notifications
└── utils/
    └── parseOutline.ts    # Parser outline Markdown
```

### Configurazione (`config/`)

```
config/
├── inputs.yaml            # Configurazione form dinamico
├── app.yaml               # Configurazione applicazione (timeout, retry, costi)
├── literary_critic.yaml   # Configurazione critico letterario
├── agent_context.md       # Context per question generator
├── draft_agent_context.md # Context per draft generator
├── outline_agent_context.md # Context per outline generator
└── writer_agent_context.md  # Context per writer generator
```

## Sistema di Persistenza

### Pattern SessionStore

Il sistema utilizza un pattern **Strategy + Factory** per supportare diversi backend di persistenza:

```mermaid
classDiagram
    class SessionStore {
        <<abstract>>
        +get_session(id)
        +create_session(id, form, answers)
        +update_draft(...)
        +update_outline(...)
        +save_session(session)
    }
    
    class FileSessionStore {
        -_sessions: Dict
        -file_path: Path
        +_load_sessions()
        +_save_sessions()
    }
    
    class MongoSessionStore {
        -client: AsyncIOMotorClient
        -db: Database
        -sessions_collection: Collection
        +connect()
        +disconnect()
        +get_all_sessions()
    }
    
    SessionStore <|-- FileSessionStore
    SessionStore <|-- MongoSessionStore
    
    note for SessionStore "Interface base per persistenza"
    note for FileSessionStore "JSON file-based storage\n(sincrono)"
    note for MongoSessionStore "MongoDB storage\n(asincrono con motor)"
```

### Factory Pattern

La selezione del SessionStore viene effettuata dinamicamente basandosi sulla variabile d'ambiente `MONGODB_URI`:

```python
def get_session_store() -> SessionStore:
    """Factory che restituisce l'istanza appropriata."""
    global _session_store
    if _session_store is None:
        mongo_uri = os.getenv("MONGODB_URI")
        if mongo_uri:
            _session_store = MongoSessionStore(mongo_uri)
        else:
            _session_store = FileSessionStore()
    return _session_store
```

### FileSessionStore

- **Percorso**: `backend/.sessions.json` (file nascosto per evitare reload di uvicorn)
- **Formato**: JSON con chiavi = session_id, valori = SessionData serializzato
- **Operazioni**: Sincrone (read/write file)
- **Backup**: Automatico durante migrazione MongoDB

### MongoSessionStore

- **Driver**: `motor` (async MongoDB driver)
- **Database**: `narrai` (configurabile)
- **Collection**: `sessions` (configurabile)
- **Indici**: Creati automaticamente su `status`, `form_data.llm_model`, `genre`, `created_at`, `updated_at`
- **Operazioni**: Asincrone (async/await)
- **Lifecycle**: Connessione/disconnessione tramite FastAPI lifecycle hooks

### Struttura SessionData

La classe `SessionData` rappresenta lo stato completo di una sessione di creazione libro:

```python
class SessionData:
    session_id: str
    form_data: SubmissionRequest
    question_answers: List[QuestionAnswer]
    current_draft: Optional[str]
    current_title: Optional[str]
    current_version: int
    validated: bool
    current_outline: Optional[str]
    outline_version: int
    book_chapters: List[Dict[str, Any]]
    writing_progress: Optional[Dict[str, Any]]
    cover_image_path: Optional[str]
    literary_critique: Optional[Dict[str, Any]]
    critique_status: Optional[str]  # pending|running|completed|failed
    writing_start_time: Optional[datetime]
    writing_end_time: Optional[datetime]
    chapter_timings: List[float]
    created_at: datetime
    updated_at: datetime
```

### Compatibilità Async/Sync

Per supportare entrambi i tipi di SessionStore (sync e async), sono stati implementati helper functions in `session_store_helpers.py`:

```python
async def get_session_async(session_store, session_id):
    if hasattr(session_store, 'connect'):  # MongoSessionStore
        return await session_store.get_session(session_id)
    else:  # FileSessionStore
        return session_store.get_session(session_id)
```

## API Design

### Organizzazione RESTful

Gli endpoint sono organizzati per dominio in router separati:

- **`/api/config`**: Configurazione form dinamico
- **`/api/submissions`**: Inizializzazione nuova sessione
- **`/api/questions/*`**: Generazione e salvataggio risposte domande
- **`/api/draft/*`**: Generazione, modifica (manuale e LLM chirurgica), validazione bozza
- **`/api/outline/*`**: Generazione e modifica struttura
- **`/api/book/*`**: Scrittura, progresso, export, critica
- **`/api/library/*`**: Lista libri, statistiche, gestione
- **`/api/session/*`**: Ripristino sessione, gestione stato

### Schema Pydantic

Tutti gli endpoint utilizzano modelli Pydantic per:
- Validazione automatica input/output
- Documentazione automatica OpenAPI
- Type safety nel codice Python

Esempio:

```python
class DraftGenerationRequest(BaseModel):
    form_data: SubmissionRequest
    question_answers: list[QuestionAnswer]
    session_id: str

class DraftResponse(BaseModel):
    success: bool
    session_id: str
    draft_text: str
    title: Optional[str] = None
    version: int
    message: Optional[str] = None

class DraftManualUpdateRequest(BaseModel):
    session_id: str
    draft_text: str
    title: Optional[str] = None
    current_version: int
```

### Editing Bozza

Il sistema supporta due modalità di modifica della bozza:

#### Editing Manuale (`POST /api/draft/update`)

Salvataggio diretto delle modifiche senza passare dall'LLM:

```python
@router.post("/update", response_model=DraftResponse)
async def update_draft_manually_endpoint(request: DraftManualUpdateRequest):
    # Incrementa versione
    new_version = session.current_version + 1
    # Salva direttamente senza chiamata LLM
    await update_draft_async(session_store, session_id, draft_text, new_version, title)
```

**Caratteristiche**:
- Nessuna chiamata API LLM
- Salvataggio immediato
- Incremento versione automatico
- Ideale per correzioni puntuali

#### Modifica Chirurgica (`POST /api/draft/modify`)

Modifica tramite LLM con approccio chirurgico:

```python
user_prompt = f"""MODIFICA CHIRURGICA RICHIESTA.

**REGOLA FONDAMENTALE**: Modifica SOLO le parti specifiche indicate nel feedback.
Tutto ciò che NON è menzionato deve rimanere IDENTICO, parola per parola.

**Feedback dell'utente:**
{user_feedback}

**Bozza attuale (mantieni IDENTICO tutto ciò che non è nel feedback):**
{previous_draft}
"""
```

**Caratteristiche**:
- Modifica solo parti specifiche richieste
- Mantiene invariato il resto della bozza
- Istruzioni dettagliate nel prompt per approccio chirurgico
- Ideale per modifiche narrative e strutturali

### Gestione Errori

- **400 Bad Request**: Validazione fallita, stato sessione errato
- **404 Not Found**: Sessione non trovata
- **500 Internal Server Error**: Errori server con dettaglio in response
- **HTTPException**: FastAPI standard per errori strutturati

### Background Tasks

Operazioni lunghe (generazione libro, critica) vengono eseguite in background usando `FastAPI BackgroundTasks`:

```python
@app.post("/api/book/generate")
async def generate_book_endpoint(
    request: BookGenerationRequest,
    background_tasks: BackgroundTasks,
):
    background_tasks.add_task(
        background_book_generation,
        session_id=request.session_id,
        ...
    )
    return BookGenerationResponse(success=True, ...)
```

## Configurazione

### Sistema di Configurazione YAML

L'applicazione utilizza file YAML in `config/` per configurazioni modificabili senza cambiare codice:

- **`inputs.yaml`**: Definisce i campi del form dinamico (modelli LLM, opzioni, validazioni)
- **`app.yaml`**: Configurazione applicazione (timeout, retry, costi, database)
- **`literary_critic.yaml`**: Configurazione critico letterario (modelli, temperatura, prompt)

### Caricamento e Cache

La configurazione viene caricata all'avvio e mantenuta in cache:

```python
# backend/app/core/config.py
_config: ConfigResponse | None = None

def get_config() -> ConfigResponse:
    global _config
    if _config is None:
        _config = load_config()
    return _config

def reload_config() -> ConfigResponse:
    """Hot-reload per sviluppo."""
    global _config
    _config = load_config()
    return _config
```

### Variabili d'Ambiente

File `.env` nella root del progetto:

**Variabili Obbligatorie**:
```env
GOOGLE_API_KEY=your_gemini_api_key_here
```

**Variabili Consigliate**:
```env
# MongoDB (consigliata per produzione)
MONGODB_URI=mongodb://admin:admin123@localhost:27017/narrai?authSource=admin
# oppure MongoDB Atlas:
# MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/narrai?retryWrites=true&w=majority

# Autenticazione (consigliata per produzione)
SESSION_SECRET=change-me-in-production-secret-key-minimum-32-characters
SESSION_EXPIRE_DAYS=7
```

**Variabili Opzionali (Email Service)**:
```env
# Email service (per verifica email e password reset)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
FRONTEND_URL=http://localhost:5173
```

**Variabili Opzionali (Google Cloud Storage)**:
```env
# GCS (per produzione/cloud storage)
GCS_ENABLED=false
GCS_BUCKET_NAME=your-bucket-name
GOOGLE_APPLICATION_CREDENTIALS=path/to/credentials.json
```

**Variabili Opzionali (Google Cloud Text-to-Speech)**:
```env
# TTS (per audiobook critica)
# Se non configurato, usa fallback a credentials/narrai-app-credentials.json
GOOGLE_APPLICATION_CREDENTIALS=path/to/credentials.json
```

**Note**:
- `GOOGLE_API_KEY`: Obbligatoria per chiamate LLM
- `MONGODB_URI`: Opzionale, se non configurata usa FileSessionStore (JSON file)
- `SESSION_SECRET`: Opzionale, default generato (cambiare in produzione)
- `SMTP_*`: Opzionali, se non configurate email non vengono inviate (processo continua)
- `GCS_*`: Opzionali, fallback a storage locale se non configurato
- `GOOGLE_APPLICATION_CREDENTIALS`: Condiviso tra GCS e TTS, fallback a `credentials/narrai-app-credentials.json`

### Configurazione Modelli LLM

I modelli supportati sono configurati in `config/inputs.yaml`:

```yaml
llm_models:
  - "gemini-2.5-flash"
  - "gemini-2.5-pro"
  - "gemini-3-flash-preview"
  - "gemini-3-pro-preview"
```

## Gestione Dati

### Serializzazione/Deserializzazione

`SessionData` implementa metodi `to_dict()` e `from_dict()` per serializzazione JSON:

```python
def to_dict(self) -> Dict[str, Any]:
    """Converte SessionData in dict per JSON."""
    return {
        "session_id": self.session_id,
        "form_data": self.form_data.model_dump(),
        "question_answers": [qa.model_dump() for qa in self.question_answers],
        # ... altri campi
        "created_at": self.created_at.isoformat(),
        "updated_at": self.updated_at.isoformat(),
    }

@classmethod
def from_dict(cls, data: Dict[str, Any]) -> "SessionData":
    """Crea SessionData da dict (deserializzazione)."""
    # Parse datetime da ISO string
    # Ricostruisce oggetti Pydantic
```

### Migrazione Dati

Script `backend/scripts/migrate_to_mongodb.py` per migrare dati da JSON a MongoDB:

```bash
cd backend
uv run python scripts/migrate_to_mongodb.py --verify
```

**Caratteristiche**:
- Backup automatico file JSON originale
- Verifica integrità post-migrazione
- Modalità dry-run per test
- Supporto per migrazione incrementale

### Indici MongoDB

Indici creati automaticamente per performance query:

```python
indexes = [
    IndexModel([("status", ASCENDING)]),
    IndexModel([("form_data.llm_model", ASCENDING)]),
    IndexModel([("form_data.genre", ASCENDING)]),
    IndexModel([("created_at", ASCENDING)]),
    IndexModel([("updated_at", ASCENDING)]),
]
```

### Backup Automatico

Durante la migrazione, viene creato un backup timestamped:

```
.sessions.json.backup_YYYYMMDD_HHMMSS
```

## Sistema di Autenticazione

### Architettura Autenticazione

Il sistema utilizza **session-based authentication** con cookie httpOnly invece di JWT:

**Session Management**:
- Session ID: UUID v4 generato al login
- Storage: MongoDB collection `sessions_auth` (separata da `sessions` per libri)
- Cookie: `session_id` (httpOnly, secure in produzione, samesite=lax)
- Scadenza: 7 giorni (configurabile via `SESSION_EXPIRE_DAYS`)

**Flusso Autenticazione**:

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant Backend
    participant MongoDB
    participant EmailService

    User->>Frontend: Registrazione
    Frontend->>Backend: POST /api/auth/register
    Backend->>MongoDB: Crea utente (is_verified=False)
    Backend->>EmailService: Invia email verifica
    EmailService-->>User: Email con token
    User->>Frontend: Clicca link verifica
    Frontend->>Backend: GET /api/auth/verify?token=...
    Backend->>MongoDB: Aggiorna is_verified=True
    User->>Frontend: Login
    Frontend->>Backend: POST /api/auth/login
    Backend->>MongoDB: Verifica credenziali
    Backend->>MongoDB: Crea sessione (sessions_auth)
    Backend-->>Frontend: Cookie session_id
    Frontend->>Backend: Richiesta autenticata
    Backend->>MongoDB: Valida sessione
    Backend-->>Frontend: Dati utente
```

**File**: `backend/app/middleware/auth.py`, `backend/app/api/routers/auth.py`

### UserStore

Persistenza utenti in MongoDB (collection `users`):

**Struttura**:
- Pattern simile a SessionStore (factory + interface)
- Implementazione: MongoUserStore (async)
- Operazioni: create_user, get_user_by_id, get_user_by_email, update_user

**Indici MongoDB**:
- Index unico su `email`
- Index su `created_at`, `updated_at`

**Password Hashing**:
- Libreria: `passlib[bcrypt]`
- Algoritmo: bcrypt
- Rounds: default (10)

**File**: `backend/app/agent/user_store.py`

### Middleware Authentication

FastAPI Dependencies per autenticazione e autorizzazione:

**Dependencies**:
- `get_current_user`: Dependency che richiede autenticazione (401 se non autenticato)
- `get_current_user_optional`: Dependency opzionale (restituisce None se non autenticato)
- `require_admin`: Dependency che richiede ruolo admin (403 se non admin)

**Implementazione**:
```python
async def get_current_user(
    auth_session_id: Optional[str] = Cookie(None, alias="session_id")
) -> User:
    user = await get_user_from_session(auth_session_id)
    if not user:
        raise HTTPException(401, "Non autenticato")
    if not user.is_active:
        raise HTTPException(403, "Utente disattivato")
    return user

async def require_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    if current_user.role != "admin":
        raise HTTPException(403, "Accesso negato: richiesto ruolo admin")
    return current_user
```

**Uso negli Endpoint**:
```python
@app.get("/api/library/stats")
async def get_stats(current_user = Depends(require_admin)):
    # Solo admin può accedere
    ...
```

**File**: `backend/app/middleware/auth.py`

### Email Service Integration

Il sistema utilizza SMTP per invio email:

**Configurazione**:
- Provider: Qualsiasi SMTP (default: Gmail)
- Protocollo: STARTTLS (porta 587)
- Credenziali: `SMTP_USER`, `SMTP_PASSWORD` (env vars)

**Email Inviate**:
- **Email verifica**: Link con token verifica, HTML + testo (`send_verification_email`)
  - Link: `{FRONTEND_URL}/verify?token={token}`
  - Scadenza token: 24 ore (configurabile)
- **Email password reset**: Link con token reset, HTML + testo (`send_password_reset_email`)
  - Link: `{FRONTEND_URL}/reset-password?token={token}`
  - Scadenza token: 1 ora (configurabile)
  - Invio asincrono: usa `asyncio.to_thread` per non bloccare richiesta (best-effort)
- **Email connection request**: Notifica richiesta connessione (`send_connection_request_email`)
  - Link: `{FRONTEND_URL}/connections`
  - Inviata al destinatario quando riceve richiesta connessione
- **Email referral**: Invito a registrarsi (`send_referral_email`)
  - Link: `{FRONTEND_URL}/register?ref={token}`
  - Descrizione app: "Scrivi i tuoi libri con l'AI" (aggiornata)
  - Token univoco per tracking registrazione

**URL Frontend**:
- Configurabile via variabile d'ambiente `FRONTEND_URL`
- Default: `http://localhost:5173` (sviluppo)
- Produzione: `https://narrai.it`

**Fallback**:
- Se credenziali SMTP non configurate, email non vengono inviate
- Processo continua comunque (utile per sviluppo)
- Log warning quando credenziali mancanti
- Email password reset: invio asincrono non blocca richiesta anche se fallisce (best-effort)

**File**: `backend/app/services/email_service.py`, `backend/app/api/routers/auth.py` (password reset asincrono)

### Sistema di Condivisione Libri

Il sistema permette agli utenti di condividere libri con altri utenti connessi.

**Architettura BookShareStore**:
- Pattern similar a SessionStore (factory + interface)
- Persistenza in MongoDB (collection `book_shares`)
- Implementazione: MongoBookShareStore (async)

**Struttura BookShare**:
```python
class BookShare:
    id: str  # UUID
    book_session_id: str  # ID sessione libro condiviso
    owner_id: str  # Proprietario originale
    recipient_id: str  # Destinatario
    status: Literal["pending", "accepted", "declined"]
    created_at: datetime
    updated_at: datetime
    owner_name: Optional[str]  # Nome proprietario (per frontend)
    recipient_name: Optional[str]  # Nome destinatario (per frontend)
    book_title: Optional[str]  # Titolo libro (per frontend)
```

**Indici MongoDB**:
- Index su `book_session_id`, `owner_id`, `recipient_id`, `status`, `created_at`
- Compound unique index: `(book_session_id, recipient_id)` per evitare condivisioni duplicate
- Compound index per query frequenti: `(owner_id, recipient_id, status)`

**Endpoint API**:
- `POST /api/books/{session_id}/share`: Condividi libro con utente (richiede connessione accettata)
- `GET /api/books/shared`: Recupera libri condivisi (ricevuti/inviati)
- `POST /api/books/{share_id}/action`: Accetta/rifiuta condivisione (accept/decline)

**Validazioni**:
- Richiede connessione accettata tra owner e recipient
- Verifica ownership libro (owner_id deve corrispondere a current_user)
- Previene condivisioni duplicate (compound unique index)

**Integrazione con NotificationStore**:
- Creazione notifica automatica al recipient quando libro condiviso
- Tipo notifica: `book_shared`
- Dati notifica: `from_user_id`, `from_user_name`, `book_session_id`, `book_title`, `share_id`

**Frontend**:
- Componente `ShareBookModal` per ricerca utente e condivisione
- Autocompletamento email basato su connessioni esistenti
- Filtro titolo libro: rimozione asterischi markdown (`stripMarkdownBold`)
- Pulsante "Condividi" in LibraryView/BookCard

**File**: `backend/app/agent/book_share_store.py`, `backend/app/api/routers/book_shares.py`, `frontend/src/components/ShareBookModal.tsx`

### Sistema di Connessioni tra Utenti

Il sistema permette agli utenti di connettersi tra loro per condividere libri e interagire.

**Architettura ConnectionStore**:
- Pattern similar a SessionStore (factory + interface)
- Persistenza in MongoDB (collection `connections`)
- Implementazione: MongoConnectionStore (async)

**Struttura Connection**:
```python
class Connection:
    id: str  # UUID
    from_user_id: str  # Chi invia la richiesta
    to_user_id: str  # Chi riceve la richiesta
    status: Literal["pending", "accepted"]
    created_at: datetime
    updated_at: datetime
    from_user_name: Optional[str]  # Nome utente mittente (per frontend)
    to_user_name: Optional[str]  # Nome utente destinatario (per frontend)
    from_user_email: Optional[str]  # Email utente mittente (per frontend)
    to_user_email: Optional[str]  # Email utente destinatario (per frontend)
```

**Indici MongoDB**:
- Index su `from_user_id`, `to_user_id`, `status`, `created_at`
- Compound unique index: `(from_user_id, to_user_id)` per evitare connessioni duplicate

**Endpoint API**:
- `POST /api/connections/request`: Invia richiesta connessione (cerca utente per email e crea richiesta)
- `GET /api/connections`: Recupera connessioni (accepted/pending, in arrivo/in uscita)
- `GET /api/connections/pending`: Recupera richieste pendenti (in arrivo)
- `GET /api/connections/pending-count`: Conteggio richieste pendenti (per badge)
- `POST /api/connections/{connection_id}/action`: Accetta/rifiuta richiesta (accept/decline)

**Email di Richiesta Connessione**:
- EmailService.send_connection_request_email invia notifica email al destinatario
- Link alla pagina `/connections` per accettare/rifiutare
- HTML + testo plain

**Frontend**:
- Componente `ConnectionsView` con 4 tab:
  - **Cerca**: Ricerca utente per email e invio richiesta connessione
  - **Pendenti**: Lista richieste in arrivo (accetta/rifiuta)
  - **Connessioni**: Lista connessioni accettate
  - **Invita**: Invio inviti referral a email esterne
- Filtro duplicati: evita mostrare se stesso nelle connessioni (verifica email e ID)
- Autocompletamento email nelle connessioni esistenti (ShareBookModal)

**File**: `backend/app/agent/connection_store.py`, `backend/app/api/routers/connections.py`, `frontend/src/components/ConnectionsView.tsx`

### Sistema di Notifiche

Il sistema gestisce notifiche in-app per eventi sociali (condivisioni libri, connessioni, ecc.).

**Architettura NotificationStore**:
- Pattern similar a SessionStore (factory + interface)
- Persistenza in MongoDB (collection `notifications`)
- Implementazione: MongoNotificationStore (async)

**Struttura Notification**:
```python
class Notification:
    id: str  # UUID
    user_id: str  # destinatario
    type: Literal["connection_request", "connection_accepted", "book_shared", "book_share_accepted", "system"]
    title: str
    message: str
    data: Optional[Dict[str, Any]] = None  # dati extra (es: from_user_id, book_session_id, share_id)
    is_read: bool = False
    created_at: datetime
```

**Tipi Notifiche**:
- `connection_request`: Richiesta connessione ricevuta
- `connection_accepted`: Richiesta connessione accettata
- `book_shared`: Libro condiviso da altro utente
- `book_share_accepted`: Condivisione libro accettata
- `system`: Notifiche di sistema

**Indici MongoDB**:
- Index su `user_id`, `type`, `is_read`, `created_at`
- Compound index per query frequenti: `(user_id, is_read, created_at)`

**Endpoint API**:
- `GET /api/notifications`: Recupera notifiche (limit, skip, unread_only)
- `GET /api/notifications/unread-count`: Conteggio notifiche non lette (per badge, polling ottimizzato)
- `PATCH /api/notifications/{id}/read`: Marca notifica come letta
- `PATCH /api/notifications/read-all`: Marca tutte le notifiche come lette

**Polling Automatico Frontend**:
- NotificationContext gestisce stato globale notifiche
- Polling automatico ogni 30 secondi per conteggio non lette (`/api/notifications/unread-count`)
- Cleanup automatico quando utente disconnesso
- Polling solo quando utente autenticato

**Frontend**:
- Componente `NotificationBell` con badge conteggio non lette
- Dropdown con lista notifiche (più recenti prima)
- Mark as read individuale o "tutte come lette"
- Integrazione in Navigation component

**Creazione Automatica Notifiche**:
- BookShareStore crea notifica quando libro condiviso (tipo: `book_shared`)
- ConnectionStore crea notifica quando richiesta connessione inviata (tipo: `connection_request`)
- ConnectionStore crea notifica quando connessione accettata (tipo: `connection_accepted`)

**File**: `backend/app/agent/notification_store.py`, `backend/app/api/routers/notifications.py`, `frontend/src/contexts/NotificationContext.tsx`, `frontend/src/components/NotificationBell.tsx`

### Sistema Referral

Il sistema gestisce inviti esterni a nuovi utenti con tracking e statistiche.

**Architettura ReferralStore**:
- Pattern similar a SessionStore (factory + interface)
- Persistenza in MongoDB (collection `referrals`)
- Implementazione: MongoReferralStore (async)

**Struttura Referral**:
```python
class Referral:
    id: str  # UUID
    referrer_id: str  # Chi ha invitato (ID utente)
    invited_email: str  # Email invitato (lowercase, salvato già normalizzato)
    status: Literal["pending", "registered", "expired"]  # Stato invito
    token: str  # Token univoco per tracking
    created_at: datetime
    registered_at: Optional[datetime]  # Quando si è registrato
    invited_user_id: Optional[str]  # ID utente dopo registrazione
    referrer_name: Optional[str]  # Nome di chi ha invitato (per frontend)
```

**Indici MongoDB**:
- Index su `referrer_id`, `invited_email`, `status`, `token`, `created_at`
- Compound unique index: `(referrer_id, invited_email)` per evitare inviti duplicate
- Index unico su `token` per lookup rapido

**Endpoint API**:
- `POST /api/referrals`: Crea invito referral (verifica limite giornaliero, normalizza email)
- `GET /api/referrals`: Recupera inviti inviati (limit, skip, paginazione)
- `GET /api/referrals/stats`: Statistiche referral (total_sent, total_registered, pending)

**Statistiche Uniche per Email**:
- Pipeline MongoDB che raggruppa per `invited_email` e prende solo l'ultimo invito (più recente)
- Conta solo inviti unici: se stessa persona invitata più volte, conta come 1
- Processo:
  1. Match per `referrer_id`
  2. Sort per `created_at` decrescente (più recente prima)
  3. Group per `invited_email` e prendi `$first` (più recente)
  4. ReplaceRoot con ultimo referral
  5. Group per `status` e conta
- Statistiche finali: `total_sent` (tutti gli inviti unici), `total_registered` (inviti unici registrati), `pending` (inviti unici in attesa)

**Email Referral**:
- EmailService.send_referral_email invia email con link registrazione
- Link: `{FRONTEND_URL}/register?ref={token}`
- Descrizione app: "Scrivi i tuoi libri con l'AI" (aggiornata)
- HTML + testo plain

**Limite Giornaliero**:
- Max 10 inviti/giorno per utente (configurabile)
- Verifica tramite `check_daily_limit()` prima di creare invito
- Conta inviti creati nelle ultime 24 ore

**Tracking Registrazione**:
- Al momento registrazione con token referral (`/api/auth/register?ref={token}`)
- Verifica token e email corrispondente
- Aggiornamento referral: `status = "registered"`, `registered_at`, `invited_user_id`
- Tracking non blocca registrazione se fallisce (best-effort)

**Frontend**:
- Componente `ConnectionsView` tab "Invita": form invio inviti
- Lista "Inviti Inviati": mostra solo ultimo invito per email (filtro duplicati lato frontend)
- Statistiche: card con total_sent, total_registered, pending (conteggio unico per email)
- Filtro duplicati: Map con email lowercase come chiave, mantiene solo ultimo per data creazione

**File**: `backend/app/agent/referral_store.py`, `backend/app/api/routers/referrals.py`, `frontend/src/components/ConnectionsView.tsx`

### Storage Service (GCS)

Persistenza file su Google Cloud Storage con fallback locale:

**Configurazione**:
- Variabile: `GCS_ENABLED=true/false`
- Bucket: `GCS_BUCKET_NAME`
- Credenziali: `GOOGLE_APPLICATION_CREDENTIALS` (path JSON key)

**Struttura Bucket**:
- Con user_id: `users/{user_id}/books/...`, `users/{user_id}/covers/...`
- Senza user_id: `books/...`, `covers/...`

**Signed URLs**:
- Generazione signed URLs per download temporanei
- Fallback a download diretto se private key non disponibile (Cloud Run default service account)

**File**: `backend/app/services/storage_service.py`

## PWA e Service Worker

L'applicazione è configurata come Progressive Web App (PWA) installabile su dispositivi mobile e desktop.

### Configurazione vite-plugin-pwa

Il plugin `vite-plugin-pwa` gestisce automaticamente:
- Generazione service worker
- Caching risorse statiche
- Manifest PWA
- Auto-update del service worker

**Configurazione** (`frontend/vite.config.ts`):
```typescript
VitePWA({
  registerType: 'autoUpdate',
  includeAssets: ['favicon.svg', 'icon-192.png', 'icon-512.png', ...],
  manifest: {
    name: 'NarrAI - Crea libri con AI',
    short_name: 'NarrAI',
    theme_color: '#0f3460',
    background_color: '#0f3460',
    icons: [
      { src: '/icon-192.png', sizes: '192x192', type: 'image/png' },
      { src: '/icon-512.png', sizes: '512x512', type: 'image/png' },
      { src: '/icon-192-maskable.png', sizes: '192x192', type: 'image/png', purpose: 'maskable' },
      { src: '/icon-512-maskable.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
    ],
  },
})
```

### Generazione Icone

Lo script `frontend/scripts/generate-icons.js` genera tutte le icone necessarie:

**Icone Generate**:
- `icon-192.png`, `icon-512.png`: Icone standard PWA
- `icon-192-maskable.png`, `icon-512-maskable.png`: Icone maskable con safe zone 20% per Android adaptive icons
- `apple-touch-icon.png`: Icona iOS (180x180)
- `favicon.png`, `favicon-16.png`: Favicon browser

**Processo**:
1. Carica `app-icon-original.png` da `frontend/public/`
2. Trim automatico spazio bianco (threshold: 20)
3. Genera versioni standard con background blu (`#0f3460`)
4. Genera versioni maskable con safe zone 20% (contenuto ridotto all'80% e centrato)
5. Salva tutte le icone in `frontend/public/`

**Libreria**: `sharp` (Node.js) per processing immagini

**File**: `frontend/scripts/generate-icons.js`

### Manifest e Meta Tags

**Manifest** (`manifest.webmanifest`):
- Generato automaticamente da vite-plugin-pwa
- Include tutte le icone (standard + maskable)
- Theme color e background color coerenti con header

**Meta Tags** (`frontend/index.html`):
- `viewport-fit=cover`: Supporto safe area (notch)
- `theme-color`: Colore barra stato (`#0f3460`)
- `apple-mobile-web-app-*`: Meta tags iOS

**File**: `frontend/index.html`, `frontend/vite.config.ts`

### Service Worker

Il service worker viene generato automaticamente e gestisce:
- **Precaching**: Risorse statiche (HTML, CSS, JS, immagini)
- **Runtime Caching**: 
  - Google Fonts (CacheFirst, 1 anno)
  - API calls (NetworkFirst, 10s timeout)
- **Auto-update**: Aggiornamento automatico quando nuova versione disponibile

**File**: Generato in `frontend/dist/sw.js` durante build

## Safe Area Support

Supporto per dispositivi con notch e system bars (iPhone X+, Android moderni).

### Viewport Meta Tag

```html
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
```

Il `viewport-fit=cover` permette all'app di estendersi fino ai bordi del dispositivo.

### CSS Environment Variables

Utilizzo di variabili CSS `env()` per safe area insets:

```css
:root {
  --safe-area-inset-top: env(safe-area-inset-top, 0px);
  --safe-area-inset-right: env(safe-area-inset-right, 0px);
  --safe-area-inset-bottom: env(safe-area-inset-bottom, 0px);
  --safe-area-inset-left: env(safe-area-inset-left, 0px);
}
```

**Uso**:
- Header navigation: `padding-top: calc(1rem + var(--safe-area-inset-top))`
- App container: `padding-bottom: var(--safe-area-inset-bottom)`

**File**: `frontend/src/index.css`, `frontend/src/components/Navigation.css`, `frontend/src/App.css`

## Google Cloud Text-to-Speech

Integrazione con Google Cloud Text-to-Speech per generazione audiobook della critica letteraria.

### Configurazione

**Credenziali**:
- Variabile d'ambiente: `GOOGLE_APPLICATION_CREDENTIALS` (path a JSON key)
- Fallback: `credentials/narrai-app-credentials.json` (se variabile non configurata)

**Endpoint**:
- `POST /api/critique/audio/{session_id}`: Genera audio da testo critica

### Processo Generazione

1. Backend legge testo critica da `SessionData.literary_critique`
2. Chiamata a Google Cloud TTS API con:
   - **Voce**: Italiana (`it-IT-Wavenet-A` o equivalente)
   - **Formato**: MP3
   - **Velocità**: 1.0x (standard)
   - **Pitch**: 0.0 (standard)
3. Risposta: Blob audio binario
4. Frontend riproduce audio con HTML5 Audio API

### Gestione Errori

**Errori Comuni**:
- `SERVICE_DISABLED`: Servizio TTS non abilitato nel progetto GCP
- `PERMISSION_DENIED`: Credenziali insufficienti
- `credentials not found`: File credenziali non trovato

**Fallback**: Se TTS non disponibile, pulsante "Ascolta" non viene mostrato

**File**: 
- Backend: `backend/app/main.py` (`generate_critique_audio_endpoint`)
- Frontend: `frontend/src/components/CritiqueAudioPlayer.tsx`

## Splash Screen

Animazione di caricamento mostrata durante l'inizializzazione dell'applicazione.

### Implementazione

**HTML Inline** (`frontend/index.html`):
- Splash screen definito direttamente in HTML con CSS inline
- Mostra icona app e testo "NarrAI"
- Background blu con gradiente coerente con header

**Animazioni**:
- **Pulse**: Icona scala delicatamente (1.0 → 1.05 → 1.0)
- **FadeIn**: Testo appare con fade-in e slide-up

**Rimozione**:
- React rimuove splash screen dopo render iniziale
- Transizione fade-out smooth (500ms)
- Rimozione completa dal DOM dopo transizione

**File**: `frontend/index.html`, `frontend/src/main.tsx`

## Pattern e Convenzioni

### Naming Conventions

- **File Python**: `snake_case.py`
- **Classi**: `PascalCase`
- **Funzioni/Metodi**: `snake_case`
- **Costanti**: `UPPER_SNAKE_CASE`
- **Router FastAPI**: `endpoint_name_endpoint()`

### Gestione Async

- Tutti gli endpoint FastAPI sono `async`
- SessionStore helpers gestiscono compatibilità sync/async
- Operazioni I/O (MongoDB, API calls) sono sempre async

### Logging

Stampa strutturata su `stderr` con prefissi:

```python
print(f"[MODULE] Messaggio", file=sys.stderr)
```

Prefissi comuni:
- `[WRITER]`: Writer generator
- `[DRAFT]`: Draft generator
- `[OUTLINE]`: Outline generator
- `[CRITIQUE]`: Literary critic
- `[COST CALCULATION]`: Cost service (solo modelli pro o molti capitoli)
- `[MongoSessionStore]`: MongoDB operations
- `[AUTH]`: Authentication operations
- `[EmailService]`: Email operations
- `[STORAGE]`: Storage operations

### Error Handling

- **Try/Except** con logging dettagliato
- **HTTPException** per errori client/server
- **Retry logic** configurata in `app.yaml`
- **Fallback** a valori conservativi quando possibile

### Lifecycle Hooks

FastAPI lifecycle hooks per MongoDB:

```python
@app.on_event("startup")
async def startup_db():
    session_store = get_session_store()
    if hasattr(session_store, 'connect'):
        await session_store.connect()
    
    user_store = get_user_store()
    if hasattr(user_store, 'connect'):
        await user_store.connect()

@app.on_event("shutdown")
async def shutdown_db():
    session_store = get_session_store()
    if hasattr(session_store, 'disconnect'):
        await session_store.disconnect()
    
    user_store = get_user_store()
    if hasattr(user_store, 'disconnect'):
        await user_store.disconnect()
```

### Type Hints

Uso estensivo di type hints per type safety:

```python
from typing import Optional, List, Dict, Any, Literal

def function_name(param: str) -> Optional[Dict[str, Any]]:
    ...
```

### Route Guards

Il sistema utilizza componenti wrapper per proteggere le route che richiedono autenticazione o ruoli specifici.

**RequireAuth** (`routing/RequireAuth.tsx`):
- Wrapper per route che richiedono autenticazione
- Redirect a `/login` se utente non autenticato
- Mostra loading durante verifica stato auth

```typescript
<Route path="/library" element={
  <RequireAuth>
    <LibraryView />
  </RequireAuth>
} />
```

**RequireAdmin** (`routing/RequireAdmin.tsx`):
- Wrapper per route che richiedono ruolo admin
- Verifica `user.role === 'admin'`
- Redirect a `/` se non admin

```typescript
<Route path="/analytics" element={
  <RequireAdmin>
    <AnalyticsView />
  </RequireAdmin>
} />
```

**File**: `frontend/src/components/routing/RequireAuth.tsx`, `frontend/src/components/routing/RequireAdmin.tsx`

### Navigazione Mobile (Bottom Navigation)

L'applicazione utilizza una bottom navigation bar su dispositivi mobile per migliorare l'accessibilità.

**Componente BottomNavigation**:
- Visibile solo su schermi < 768px
- 4 tab principali: Libreria, Nuovo, Rete, Profilo
- Badge dinamici per notifiche e connessioni pendenti
- Icone lucide-react con label

**Caratteristiche**:
- Fixed bottom con safe area support
- Background blur (glassmorphism)
- Active state con indicatore visivo
- Badge rosso per conteggio notifiche/richieste

**Polling Badge**:
- Connessioni pendenti: polling ogni 30s (`/api/connections/pending-count`)
- Notifiche non lette: gestite da NotificationContext

**File**: `frontend/src/components/BottomNavigation.tsx`, `frontend/src/components/BottomNavigation.css`

### Custom Hooks

**useProcessPolling** (`hooks/useProcessPolling.ts`):
- Hook per polling stato processi (generazione libro, critica)
- Intervallo configurabile
- Cleanup automatico al unmount
- Gestione errori con retry

```typescript
const { data, isPolling, error } = useProcessPolling({
  sessionId,
  endpoint: '/api/book/progress',
  interval: 2000,
  enabled: isGenerating,
});
```

**useToast** (`hooks/useToast.ts`):
- Wrapper per react-hot-toast
- Metodi: `success()`, `error()`, `loading()`, `dismiss()`
- Configurazione centralizzata durate e stili

**useOnboarding** (`hooks/useOnboarding.ts`):
- Gestione stato onboarding carousel
- Persistenza in localStorage
- Reset e skip funzionalità

**File**: `frontend/src/hooks/`

### Pattern UI/UX

**Progressive Disclosure** (Form Base/Avanzate):
- Mostra solo campi essenziali di default
- Campi avanzati in accordion collassabile
- Stato accordion salvato in localStorage
- Compatibilità backend: tutti i campi rimangono nella configurazione

**Filtri Collassabili** (FilterBar mobile):
- Su mobile, filtri avanzati nascosti di default
- Toggle "Filtri" con badge conteggio filtri attivi
- Icona chevron per stato espanso/collassato
- Animazione slide-down per espansione
- Ricerca sempre visibile in primo piano

**Toast Notifications**:
- Notifiche non bloccanti per feedback operazioni
- Sostituisce `alert()` e modali
- Tipi: success, error, info
- Posizione: top-right, animazioni slide

**Skeleton Loading**:
- Placeholder durante caricamento dati
- Migliora percezione di velocità
- Animazione shimmer
- Componenti riutilizzabili per diversi layout

**Responsive Design**:
- Media queries per breakpoint mobile/desktop (768px)
- Step indicator: verticale (desktop) → orizzontale compatto (mobile)
- Navigation: menu completo (desktop) → hamburger menu + bottom nav (mobile)
- Touch targets: minimo 44px per tutti gli elementi interattivi su mobile
- Tab Connessioni: testo + icone (desktop) → solo icone (mobile)

**Mobile Optimization**:
- Safe area support per dispositivi con notch
- Hamburger menu con overlay e animazioni
- Book card espandibile con menu dropdown su mobile
- Step indicator compatto orizzontale su schermi piccoli
- Bottom navigation sticky con badge notifiche
- Empty state con CTA per guidare utenti

## GDPR Compliance - Implementazione Tecnica

### Architettura GDPR

```mermaid
graph TB
    subgraph Frontend["Frontend Components"]
        CookieBanner[CookieBanner.tsx]
        PrivacySettings[PrivacySettings.tsx]
        LegalPages[Legal Pages]
        RegisterConsent[Register Consent]
    end
    
    subgraph Backend["Backend Services"]
        GDPRRouter[gdpr.py Router]
        AuditService[audit_service.py]
        RetentionService[retention_service.py]
    end
    
    subgraph Storage["MongoDB Collections"]
        Users[(users)]
        AuditLogs[(audit_logs)]
    end
    
    CookieBanner --> localStorage
    PrivacySettings --> GDPRRouter
    RegisterConsent --> Users
    GDPRRouter --> AuditService
    GDPRRouter --> Users
    AuditService --> AuditLogs
    RetentionService --> AuditLogs
    RetentionService --> Users
```

### Nuovi File Creati

**Frontend** (`frontend/src/components/`):
```
legal/
├── LegalPage.css          # Stili condivisi pagine legali
├── PrivacyPolicy.tsx      # Privacy Policy completa
├── CookiePolicy.tsx       # Cookie Policy
└── TermsOfService.tsx     # Terms of Service

CookieBanner.tsx           # Banner cookie con gestione consensi
CookieBanner.css
PrivacySettings.tsx        # Pagina impostazioni privacy utente
PrivacySettings.css
Footer.tsx                 # Footer con link legali
Footer.css
```

**Backend** (`backend/app/`):
```
api/routers/
└── gdpr.py                # Endpoint GDPR (export, delete, summary)

services/
├── audit_service.py       # Logging strutturato eventi
└── retention_service.py   # Policy retention e cleanup job
```

### Modelli Dati Aggiornati

**User Model** (`backend/app/models.py`):
```python
class User(BaseModel):
    # ... campi esistenti ...
    
    # GDPR: Consensi privacy
    privacy_accepted_at: Optional[datetime] = None
    terms_accepted_at: Optional[datetime] = None
```

**RegisterRequest** (`backend/app/models.py`):
```python
class RegisterRequest(BaseModel):
    # ... campi esistenti ...
    
    # GDPR: Consensi obbligatori
    privacy_accepted: bool = Field(False)
    data_processing_accepted: bool = Field(False)
```

### API Endpoints GDPR

| Metodo | Endpoint | Autenticazione | Descrizione |
|--------|----------|----------------|-------------|
| GET | `/api/gdpr/export` | Richiesta | Export dati in ZIP |
| DELETE | `/api/gdpr/account` | Richiesta | Cancellazione account |
| GET | `/api/gdpr/data-summary` | Richiesta | Riepilogo dati utente |
| POST | `/api/admin/retention/cleanup` | Admin | Job pulizia dati |

### Export Dati - Implementazione

```python
# Struttura ZIP generato
narrai_export_{user_id}_{timestamp}.zip
├── profile.json      # Dati profilo (no password hash)
├── books.json        # Libri con metadati
├── connections.json  # Connessioni utente
├── notifications.json
├── referrals.json
├── shares.json       # sent + received
└── README.txt        # Guida contenuto
```

### Retention Service - Policy

```python
RETENTION_POLICIES = {
    "auth_sessions": 7,           # giorni
    "password_reset_tokens": 1,   # giorni
    "verification_tokens": 1,     # giorni
    "referrals_pending": 30,      # giorni
    "notifications_read": 90,     # giorni
    "book_sessions_incomplete": 365,
    "audit_logs": 730,            # 2 anni
}
```

### Audit Service - Eventi

```python
AuditEventType = Literal[
    "login", "logout", "login_failed",
    "password_reset_request", "password_reset_complete",
    "email_verification",
    "account_created", "account_deleted",
    "profile_updated", "consent_updated",
    "data_export", "data_access",
    "book_created", "book_deleted", "book_shared",
    "admin_action", "retention_cleanup",
]
```

### Cookie Consent - localStorage

```typescript
interface CookieConsent {
  necessary: boolean;    // sempre true
  functional: boolean;   // preferenze utente
  version: string;       // per invalidazione
  timestamp: string;     // ISO datetime
}

// Chiave localStorage
const COOKIE_CONSENT_KEY = 'cookie_consent';
```

### Metodi Store Aggiunti

**NotificationStore**:
- `get_user_notifications(user_id, limit)` - Per export
- `delete_user_notifications(user_id)` - Per cancellazione
- `count_user_notifications(user_id)` - Per summary

**ConnectionStore**:
- `anonymize_user_connections(user_id)` - Anonimizza invece di eliminare

**BookShareStore**:
- `get_sent_shares(owner_id)` - Per export
- `get_received_shares(recipient_id)` - Per export
- `delete_shares_for_book(session_id)` - Per cancellazione libro
- `anonymize_user_shares(user_id)` - Per cancellazione account

**ReferralStore**:
- `delete_user_referrals(user_id)` - Per cancellazione

**UserStore**:
- `delete_user(user_id)` - Cancellazione per ID

**MongoSessionStore**:
- `get_sessions_by_user(user_id)` - Per export

### Routing Frontend

```typescript
// Route pubbliche (no auth)
{ path: '/privacy', element: <PrivacyPolicy /> }
{ path: '/cookies', element: <CookiePolicy /> }
{ path: '/terms', element: <TermsOfService /> }

// Route protette
{ path: '/settings/privacy', element: <PrivacySettings /> }
```

### Sicurezza Implementata

- **Password verification** per cancellazione account
- **Confirm flag** esplicito richiesto
- **Audit trail** per tutte le operazioni sensibili
- **IP anonymization** dopo 90 giorni nei log
- **Consent versioning** per re-richiesta consenso
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
        SessionStore[Session Store Interface]
    end
    
    subgraph Storage["Persistenza"]
        MongoDB[(MongoDB)]
        FileStore[File JSON<br/>Fallback]
    end
    
    subgraph External["Servizi Esterni"]
        Gemini[Google Gemini API]
    end
    
    UI --> API_Client
    API_Client --> Router
    Router --> Services
    Services --> Agents
    Agents --> Gemini
    Services --> SessionStore
    SessionStore --> MongoDB
    SessionStore --> FileStore
    
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
- **Styling**: CSS Modules + CSS Variables
- **Charts**: Recharts 3+
- **Notifications**: react-hot-toast 2+
- **Drag & Drop**: @dnd-kit/core, @dnd-kit/sortable 6+
- **Markdown**: react-markdown 10+, remark-gfm 4+
- **HTTP Client**: Fetch API nativo

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
├── agent/                  # Agenti AI specializzati
│   ├── question_generator.py      # Genera domande preliminari
│   ├── draft_generator.py         # Genera bozza estesa
│   ├── outline_generator.py       # Genera struttura libro
│   ├── writer_generator.py        # Genera capitoli (autoregressivo)
│   ├── literary_critic.py         # Valuta libro completato
│   ├── cover_generator.py         # Genera copertina AI
│   ├── session_store.py           # Interface + FileSessionStore
│   ├── mongo_session_store.py     # MongoDB implementation
│   └── session_store_helpers.py   # Helper async/sync compatibility
├── api/routers/           # Endpoint REST organizzati
│   ├── config.py          # GET /api/config
│   ├── submission.py      # POST /api/submissions
│   ├── questions.py       # POST /api/questions/*
│   ├── draft.py           # POST /api/draft/*
│   └── outline.py         # POST /api/outline/*
├── core/                  # Configurazione centralizzata
│   └── config.py          # Caricamento YAML, cache
├── services/              # Business logic services
│   ├── cost_service.py    # Calcolo costi generazione
│   ├── export_service.py  # Export EPUB/DOCX
│   ├── library_service.py # Gestione libreria, statistiche
│   └── pdf_service.py     # Generazione PDF
├── static/                # File statici (CSS PDF)
│   └── book_styles.css
└── templates/             # Template HTML
    └── book_template.html
```

### Frontend (`frontend/src/`)

```
frontend/src/
├── App.tsx                # Componente root, routing, Toaster
├── api/
│   └── client.ts          # Client API TypeScript, tipi
├── components/            # Componenti React modulari
│   ├── DynamicForm.tsx    # Wizard creazione libro (Base/Avanzate, step indicator)
│   ├── PlotTextarea.tsx   # Textarea avanzata (autosave, modale, contatori)
│   ├── LibraryView.tsx    # Visualizzazione libreria (filtri, ricerca, ordinamento)
│   ├── AnalyticsView.tsx  # Dashboard statistiche (admin-only)
│   ├── BenchmarkView.tsx  # Valutazione modelli LLM
│   ├── BookReader.tsx     # Visualizzatore libro
│   ├── OutlineEditor.tsx  # Editor drag-and-drop struttura
│   ├── WritingStep.tsx    # Monitoraggio generazione
│   ├── DraftStep.tsx      # Generazione/modifica bozza
│   ├── Skeleton.tsx       # Skeleton loaders (SkeletonText, SkeletonCard, etc.)
│   ├── LoginPage.tsx      # Pagina login
│   ├── RegisterPage.tsx   # Pagina registrazione
│   ├── ForgotPasswordPage.tsx  # Richiesta reset password
│   ├── ResetPasswordPage.tsx   # Reset password
│   ├── VerifyEmailPage.tsx     # Verifica email
│   └── ...                # Altri componenti UI
├── contexts/
│   └── AuthContext.tsx    # Context autenticazione (AuthProvider, useAuth)
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
- **`/api/draft/*`**: Generazione, modifica, validazione bozza
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
```

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

**Note**:
- `GOOGLE_API_KEY`: Obbligatoria per chiamate LLM
- `MONGODB_URI`: Opzionale, se non configurata usa FileSessionStore (JSON file)
- `SESSION_SECRET`: Opzionale, default generato (cambiare in produzione)
- `SMTP_*`: Opzionali, se non configurate email non vengono inviate (processo continua)
- `GCS_*`: Opzionali, fallback a storage locale se non configurato

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
- Email verifica: Link con token, HTML + testo
- Email password reset: Link con token, HTML + testo

**Fallback**:
- Se credenziali non configurate, email non vengono inviate
- Processo continua comunque (utile per sviluppo)
- Log warning quando credenziali mancanti

**File**: `backend/app/services/email_service.py`

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

### Pattern UI/UX

**Progressive Disclosure** (Form Base/Avanzate):
- Mostra solo campi essenziali di default
- Campi avanzati in accordion collassabile
- Stato accordion salvato in localStorage
- Compatibilità backend: tutti i campi rimangono nella configurazione

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

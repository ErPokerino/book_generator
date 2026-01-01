# NarrAI - Agente di Scrittura Romanzi

Sistema per la creazione di romanzi personalizzati utilizzando modelli LLM della famiglia Gemini.

## Documentazione

Per approfondire l'applicazione, consulta la documentazione completa:

- **[Documentazione Tecnica](docs/TECNICA.md)**: Architettura, stack tecnologico, struttura del codice, API design, sistema di persistenza, configurazione e pattern implementati.
- **[Documentazione Funzionale](docs/FUNZIONALE.md)**: Flussi utente, logiche di business, processi di generazione, calcoli e metriche, validazioni e regole.

Questa documentazione (README.md) contiene informazioni essenziali per setup e utilizzo rapido.

## Struttura del Progetto

```
scrittura-libro/
├── backend/          # Backend FastAPI
│   ├── app/         # Codice applicazione
│   │   ├── agent/   # Agenti AI (generazione, critica, copertina)
│   │   ├── static/  # File CSS per PDF
│   │   └── templates/ # Template HTML
│   └── books/       # PDF generati (creata automaticamente)
├── frontend/        # Frontend React + Vite
├── config/          # File di configurazione
│   └── inputs.yaml  # Configurazione campi form
└── README.md
```

## Prerequisiti

- **Python 3.11+**
- **uv** (gestore pacchetti Python) - [Installazione](https://github.com/astral-sh/uv)
- **Node.js 18+** e **npm** (o pnpm/yarn)
- **Docker** (opzionale, per MongoDB locale) - [Installazione](https://www.docker.com/get-started)
- **MongoDB** (opzionale, può usare MongoDB Atlas o Docker locale)

## Installazione e Avvio

### Backend (FastAPI)

1. Naviga nella directory backend:
   ```bash
   cd backend
   ```

2. Installa le dipendenze con uv:
   ```bash
   uv sync
   ```

3. Avvia il server:
   ```bash
   uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

   Oppure usa lo script definito in `pyproject.toml`:
   ```bash
   uv run start
   ```

Il backend sarà disponibile su `http://localhost:8000`

### Frontend (React)

1. Naviga nella directory frontend:
   ```bash
   cd frontend
   ```

2. Installa le dipendenze:
   ```bash
   npm install
   ```

3. Avvia il server di sviluppo:
   ```bash
   npm run dev
   ```

Il frontend sarà disponibile su `http://localhost:5173` (o un'altra porta se 5173 è occupata)

## Configurazione

### Configurazione degli Input

Il file `config/inputs.yaml` definisce tutti i campi del form che l'utente può compilare.

### Configurazione Costi

Il file `config/app.yaml` contiene la sezione `cost_estimation` per configurare la stima dei costi:

```yaml
cost_estimation:
  tokens_per_page: 350  # Token stimati per pagina
  currency: "EUR"       # Valuta di visualizzazione
  exchange_rate_usd_to_eur: 0.92  # Tasso di cambio
  
  model_costs:
    gemini-2.5-flash:
      input_cost_per_million: 0.30
      output_cost_per_million: 2.50
    # ... altri modelli
```

Aggiorna questi valori con i costi reali da Google Gemini API pricing per avere stime accurate.

### Configurazione Database (MongoDB)

Il sistema supporta due modalità di persistenza:

1. **File JSON** (default): Se `MONGODB_URI` non è configurata, il sistema usa `FileSessionStore` che salva i dati in `.sessions.json`
2. **MongoDB**: Se `MONGODB_URI` è configurata nel file `.env`, il sistema usa `MongoSessionStore`

#### Setup MongoDB Locale (Docker) - Sviluppo

1. Avvia MongoDB usando Docker Compose:
   ```bash
   docker-compose up -d
   ```

2. MongoDB sarà disponibile su `mongodb://localhost:27017`
   - Mongo Express (UI admin) sarà disponibile su `http://localhost:8081`
   - Credenziali default: vedi file `docker-compose.yml` (credenziali di esempio per sviluppo locale)

3. Configura il file `.env` nella root del progetto:
   ```env
   MONGODB_URI=mongodb://username:password@localhost:27017/narrai?authSource=admin
   ```
   
   **Nota**: Sostituisci `username` e `password` con le credenziali configurate in Docker Compose.

#### Setup MongoDB Atlas - Produzione

1. Crea un cluster su [MongoDB Atlas](https://www.mongodb.com/cloud/atlas)

2. Ottieni la connection string e aggiungila al `.env`:
   ```env
   MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/narrai?retryWrites=true&w=majority
   ```

#### Migrazione Dati da JSON a MongoDB

Per migrare le sessioni esistenti da file JSON a MongoDB:

```bash
cd backend
python scripts/migrate_to_mongodb.py
```

Opzioni disponibili:
- `--mongodb-uri`: MongoDB connection string (default: da variabile d'ambiente)
- `--database`: Nome database (default: "narrai")
- `--collection`: Nome collection (default: "sessions")
- `--dry-run`: Simula la migrazione senza scrivere dati
- `--verify`: Verifica la migrazione dopo il completamento
- `--no-backup`: Non crea backup del file JSON originale

Lo script crea automaticamente un backup del file `.sessions.json` prima della migrazione.

## Configurazione Critico Letterario

La configurazione dell’agente **critico letterario** è in `config/literary_critic.yaml` e permette di modificare senza cambiare codice:
- modello **default** e **fallback**
- temperatura e retry
- prompt di sistema e prompt utente

### Comportamento
- La critica viene generata usando **il PDF finale** del libro come input **multimodale** (PDF inviato direttamente al modello).
- Se la critica fallisce, viene salvato `critique_status=failed` e `critique_error` (nessun placeholder). In UI compare il pulsante **Riprova critica**.

### Endpoint utile
- `POST /api/book/critique/{session_id}`: rigenera la critica dal PDF finale e aggiorna lo stato.

### Struttura del File YAML

```yaml
llm_models:
  - "gemini-2.5-flash"
  - "gemini-2.5-pro"
  # ... altri modelli

fields:
  - id: nome_campo
    label: "Etichetta Visualizzata"
    type: select  # oppure "text"
    required: true  # oppure false
    options:      # solo per type: select
      - value: "opzione1"
        label: "Opzione 1"  # opzionale, usa value se assente
      - value: "opzione2"
    placeholder: "Testo placeholder"  # opzionale, solo per type: text
```

### Aggiungere un Nuovo Campo

Per aggiungere un nuovo campo al form:

1. Apri `config/inputs.yaml`

2. Aggiungi una nuova entry nella sezione `fields`:

   **Per un campo select (menu a tendina):**
   ```yaml
   - id: nuovo_campo
     label: "Nuovo Campo"
     type: select
     required: false
     options:
       - value: "opzione1"
       - value: "opzione2"
   ```

   **Per un campo testo libero:**
   ```yaml
   - id: descrizione
     label: "Descrizione"
     type: text
     required: true
     placeholder: "Inserisci una descrizione..."
   ```

3. Riavvia il backend (se necessario, ricarica la configurazione)

4. Il nuovo campo apparirà automaticamente nel form frontend!

### Campi Attualmente Configurati

- **Modello LLM** (required, select): Selezione del modello Gemini da utilizzare
- **Trama** (required, text): Descrizione della trama del romanzo
- **Genere** (opzionale, select): letterario, storico, fantascienza, fantasy, giallo, thriller, horror, romantico, formazione
- **Sottogenere** (opzionale, select): hard sci-fi, soft sci-fi, noir, cozy, epico, urbano, distopico
- **Tema** (opzionale, select): identità, potere, memoria, colpa, crescita, alienazione, amore, morte
- **Protagonista** (opzionale, select): singolo, corale, anti-eroe, ordinario, eroico
- **Arco del personaggio** (opzionale, select): crescita, caduta, disillusione, statico, circolare
- **Punto di vista** (opzionale, select): prima persona, terza limitata, terza onnisciente, multiplo, inaffidabile
- **Voce narrante** (opzionale, select): neutra, soggettiva, ironica, distaccata, lirica
- **Stile** (opzionale, select): asciutto, lirico, complesso, minimale, dialogico
- **Struttura temporale** (opzionale, select): lineare, flashback, frammentata, circolare
- **Ritmo** (opzionale, select): rapido, medio, lento, variabile
- **Realismo** (opzionale, select): realistico, simbolico, allegorico, fantastico
- **Ambiguità** (opzionale, select): chiuso, aperto, ellittico
- **Intenzionalità** (opzionale, select): intrattenimento, letterario, sperimentale, ibrido

## API Endpoints

### `GET /api/config`
Restituisce la configurazione degli input (modelli LLM disponibili e definizione dei campi).

**Risposta:**
```json
{
  "llm_models": ["gemini-2.5-flash", ...],
  "fields": [
    {
      "id": "llm_model",
      "label": "Modello LLM",
      "type": "select",
      "required": true,
      "options": [...]
    },
    ...
  ]
}
```

### `POST /api/submissions`
Riceve e valida i dati del form.

**Body:**
```json
{
  "llm_model": "gemini-2.5-pro",
  "plot": "Trama del romanzo...",
  "genre": "fantascienza",
  ...
}
```

**Risposta:**
```json
{
  "success": true,
  "message": "Submission ricevuta con successo",
  "data": { ... }
}
```

### `GET /api/book/generate`
Avvia la generazione del libro completo in background.

**Body:**
```json
{
  "session_id": "uuid-sessione"
}
```

### `GET /api/book/progress/{session_id}`
Recupera lo stato di avanzamento della scrittura del libro.

**Risposta:**
```json
{
  "session_id": "uuid",
  "current_step": 5,
  "total_steps": 10,
  "current_section_name": "Capitolo 6",
  "completed_chapters": [...],
  "is_complete": false,
  "total_pages": null,
  "critique": null,
  "critique_status": "running",
  "critique_error": null
}
```

### `GET /api/book/{session_id}`
Restituisce il libro completo con tutti i capitoli.

**Risposta:**
```json
{
  "title": "Titolo del Libro",
  "author": "Nome Autore",
  "chapters": [...],
  "total_pages": 150,
  "critique": {
    "score": 7.5,
    "pros": "Punti di forza...",
    "cons": "Punti di debolezza...",
    "summary": "Sintesi valutazione..."
  }
}
```

### `GET /api/book/pdf/{session_id}`
Genera e scarica il PDF completo del libro.

**Formato nome file:** `YYYY-MM-DD_TitoloLibro.pdf`

Il PDF viene anche salvato automaticamente in `backend/books/`.

### `POST /api/book/critique/{session_id}`
Rigenera la critica letteraria per un libro completato usando il PDF finale.

### `POST /api/book/cover/regenerate/{session_id}`
Rigenera la copertina per un libro specifico.

### `GET /api/library`
Restituisce la lista dei libri nella libreria con filtri e ordinamento.

**Query parameters:**
- `status`: filtro per stato (draft, outline, writing, paused, complete, all)
- `llm_model`: filtro per modello LLM
- `genre`: filtro per genere
- `search`: ricerca in titolo/autore
- `sort_by`: ordinamento (created_at, title, score, cost, updated_at)
- `sort_order`: ordine (asc, desc)

**Risposta:**
```json
{
  "books": [...],
  "total": 10,
  "stats": {
    "total_books": 15,
    "completed_books": 10,
    "average_score": 7.5,
    "average_pages": 180,
    "average_writing_time_minutes": 45,
    "average_cost_by_model": {...},
    "average_cost_per_page_by_model": {...}
  }
}
```

### `GET /api/library/stats`
Restituisce statistiche aggregate della libreria (libri totali, completati, voto medio, pagine medie, tempi medi, costi).

### `GET /api/library/stats/advanced`
Restituisce statistiche avanzate con analisi temporali e confronto modelli.

**Risposta:**
```json
{
  "books_over_time": {"2024-01-15": 3, "2024-01-16": 5, ...},
  "score_trend_over_time": {"2024-01-15": 7.2, "2024-01-16": 7.8, ...},
  "model_comparison": [
    {
      "model": "gemini-3-flash",
      "completed_books": 5,
      "average_score": 8.0,
      "average_pages": 200,
      "average_writing_time_minutes": 40,
      "average_cost": 2.50
    },
    ...
  ]
}
```

### `DELETE /api/library/{session_id}`
Elimina un progetto dalla libreria.

### `GET /health`
Health check endpoint.

## Processo di Generazione del Libro

Il processo di generazione del libro segue 6 fasi principali:

1. **Setup** - Configurazione iniziale (form dinamico)
2. **Domande** - Domande preliminari generate automaticamente
3. **Bozza** - Generazione e modifica bozza estesa
4. **Struttura** - Generazione outline con editor drag-and-drop
5. **Scrittura** - Generazione capitoli autoregressiva con monitoraggio progresso
6. **Critica** - Valutazione automatica del libro completato

Per dettagli completi sul flusso e le logiche di business, consulta la [Documentazione Funzionale - Flusso Generazione Libro](docs/FUNZIONALE.md#flusso-generazione-libro).

## Interfaccia Utente

L'applicazione è organizzata in quattro sezioni principali:

- **📚 Libreria**: Visualizzazione libri con filtri, ricerca, ordinamento, export e azioni (leggi, elimina, riprendi)
- **📖 Nuovo Libro**: Wizard guidato con step indicator per creazione nuovo libro
- **📊 Analisi**: Dashboard statistiche con grafici temporali, confronto modelli, analisi costi
- **🎯 Valuta**: Valutazione e confronto modelli LLM

Per dettagli sulle funzionalità e logiche di business, consulta la [Documentazione Funzionale](docs/FUNZIONALE.md).

## Funzionalità Principali

- **Generazione Automatica**: Scrittura capitoli con processo autoregressivo per coerenza narrativa
- **Export Multiformato**: PDF, EPUB, DOCX con layout professionale
- **Critica Letteraria**: Valutazione automatica AI con score, punti di forza/debolezza
- **Calcolo Costi**: Stima automatica basata su token utilizzati e modelli LLM
- **Statistiche Avanzate**: Analytics con grafici temporali e confronto modelli
- **Ripristino Sessione**: Continuazione processi interrotti con stato persistito
- **Copertina AI**: Generazione automatica immagini copertina con Gemini

Per dettagli completi su logiche di business, calcoli e processi, consulta la [Documentazione Funzionale](docs/FUNZIONALE.md).

## Sviluppo

### Backend

- Il backend carica la configurazione YAML all'avvio e la mette in cache
- Per ricaricare la configurazione senza riavviare, usa `reload_config()` (utile per sviluppo)

### Frontend

- Il frontend costruisce dinamicamente il form basandosi sulla configurazione ricevuta dall'API
- Non è necessario modificare il codice React per aggiungere nuovi campi: basta aggiornare il YAML
- Lo step indicator fornisce feedback visivo continuo sullo stato del processo di generazione
- Interfaccia modulare con componenti separati per ogni fase (Setup, Domande, Bozza, Struttura, Scrittura)

## Note Tecniche

Per approfondimenti tecnici dettagliati, consulta la [Documentazione Tecnica](docs/TECNICA.md) che copre:

- Architettura sistema e pattern implementati
- Stack tecnologico completo
- Struttura del codice e organizzazione
- Sistema di persistenza (MongoDB/File)
- Design API RESTful
- Configurazione e gestione dati
- Pattern e convenzioni di sviluppo




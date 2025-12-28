# Scrittura Libro - Agente di Scrittura Romanzi

Sistema per la creazione di romanzi personalizzati utilizzando modelli LLM della famiglia Gemini.

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

## Configurazione degli Input

Il file `config/inputs.yaml` definisce tutti i campi del form che l'utente può compilare.

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

### `GET /health`
Health check endpoint.

## Funzionalità Principali

### Generazione Automatica del Libro
- **Generazione capitoli**: Scrittura automatica sezione per sezione con contesto autoregressivo
- **Validazione capitoli**: Controllo automatico per evitare capitoli vuoti con retry (max 2 tentativi)
- **Progress tracking**: Monitoraggio in tempo reale dello stato di avanzamento

### Copertina AI
- **Generazione automatica**: Copertina generata con AI usando `gemini-3-pro-image-preview` (fallback: `gemini-2.5-flash-image`)
- **Contenuto copertina**: Include titolo, autore e immagine generata dalla trama
- **Integrazione PDF**: La copertina viene automaticamente inclusa come prima pagina del PDF

### Calcolo Pagine
- **Pagine per capitolo**: Calcolo automatico basato su parole/250 (arrotondato per eccesso)
- **Totale pagine**: Include capitoli + copertina (1 pagina) + indice (calcolato dinamicamente)
- **Visualizzazione**: Numero pagine mostrato per ogni capitolo e totale nel libro

### Valutazione Critica Automatica
- **Agente critico letterario**: Valutazione automatica del libro completato
- **Modelli**: Usa `gemini-3-pro` (default) con fallback `gemini-3-flash`
- **Valutazione**: Score 0-10 con punti di forza, debolezze e sintesi
- **Timing**: La critica viene generata automaticamente dopo il completamento del libro

### Gestione PDF
- **Salvataggio automatico**: I PDF vengono salvati in `backend/books/` con nome formato `YYYY-MM-DD_TitoloLibro.pdf`
- **Download**: Download diretto tramite browser con nome file corretto
- **Layout professionale**: PDF generato con xhtml2pdf, layout tipografico ottimizzato

## Sviluppo

### Backend

- Il backend carica la configurazione YAML all'avvio e la mette in cache
- Per ricaricare la configurazione senza riavviare, usa `reload_config()` (utile per sviluppo)

### Frontend

- Il frontend costruisce dinamicamente il form basandosi sulla configurazione ricevuta dall'API
- Non è necessario modificare il codice React per aggiungere nuovi campi: basta aggiornare il YAML

## Note Tecniche

### Validazione Capitoli
Il sistema include validazione automatica per evitare capitoli vuoti:
- Controllo lunghezza minima (50 caratteri)
- Retry automatico fino a 2 tentativi
- Messaggio di errore se la generazione fallisce completamente

### Polling e Aggiornamenti
- Il frontend effettua polling ogni 2 secondi durante la generazione
- Il polling continua anche dopo il completamento del libro finché la critica non è disponibile
- Progress bar aggiornata in tempo reale con indicatore per generazione critica

### Formato File PDF
I file PDF vengono salvati con il seguente formato:
- **Pattern**: `YYYY-MM-DD_TitoloLibro.pdf`
- **Esempio**: `2024-01-15_Il_Romanzo_di_Esempio.pdf`
- **Posizione**: `backend/books/` (creata automaticamente)




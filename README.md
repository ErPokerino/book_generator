# Scrittura Libro - Agente di Scrittura Romanzi

Sistema per la creazione di romanzi personalizzati utilizzando modelli LLM della famiglia Gemini.

## Struttura del Progetto

```
scrittura-libro/
├── backend/          # Backend FastAPI
│   └── app/         # Codice applicazione
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

### `GET /health`
Health check endpoint.

## Sviluppo

### Backend

- Il backend carica la configurazione YAML all'avvio e la mette in cache
- Per ricaricare la configurazione senza riavviare, usa `reload_config()` (utile per sviluppo)

### Frontend

- Il frontend costruisce dinamicamente il form basandosi sulla configurazione ricevuta dall'API
- Non è necessario modificare il codice React per aggiungere nuovi campi: basta aggiornare il YAML

## Prossimi Passi

Questa è l'impalcatura iniziale. In futuro verrà implementata:
- Integrazione con l'API Gemini per la generazione del romanzo
- Gestione dello stato di avanzamento della scrittura
- Salvataggio e gestione dei progetti



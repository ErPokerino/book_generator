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

Il processo di generazione del libro segue questi step visualizzati nell'interfaccia utente:

1. **Setup** 📝 - L'utente compila il form iniziale con i dettagli del romanzo (trama, genere, stile, ecc.) e seleziona il modello LLM (predefinito: Gemini 3 Flash)

2. **Domande** ❓ - Il sistema genera automaticamente domande preliminari basate sulla configurazione per approfondire alcuni aspetti narrativi

3. **Bozza** 📄 - Viene generata una bozza estesa della trama che l'utente può rivedere e modificare tramite un'interfaccia chat

4. **Struttura** 📋 - Dopo la validazione della bozza, viene generata automaticamente la struttura dettagliata del libro (capitoli e sezioni). L'utente può modificare la struttura usando un editor drag-and-drop prima di procedere

5. **Scrittura** ✍️ - Avvio della scrittura completa del libro. Il sistema genera tutti i capitoli automaticamente con monitoraggio del progresso in tempo reale

Durante tutto il processo, uno step indicator verticale mostra sempre lo step corrente e lo stato di avanzamento.

## Interfaccia Utente

L'applicazione è organizzata in quattro sezioni principali accessibili tramite la navigazione:

### 📚 Libreria
- **Visualizzazione libri**: Lista completa di tutti i libri generati con informazioni dettagliate (titolo, autore, genere, modello, stato, voto, pagine, tempo di scrittura/lettura, costo stimato)
- **Filtri avanzati**: Filtra per stato (bozza, struttura, in scrittura, pausa, completati), modello LLM, genere
- **Ricerca**: Cerca libri per titolo o autore
- **Ordinamento**: Ordina per data creazione, ultima modifica, titolo, voto, costo
- **Azioni**: Per ogni libro è possibile:
  - Leggere il libro completo in un visualizzatore dedicato
  - Visualizzare la critica letteraria completa in un modal
  - Scaricare il PDF
  - Continuare la generazione se in pausa
  - Eliminare il progetto

### 📖 Nuovo Libro
Interfaccia guidata per la creazione di un nuovo libro con step indicator visuale:
- **Setup**: Form dinamico configurato tramite YAML (modello predefinito: Gemini 3 Flash)
- **Domande**: Domande preliminari generate automaticamente
- **Bozza**: Generazione e modifica bozza tramite chat interattiva
- **Struttura**: Generazione struttura dettagliata con editor drag-and-drop per modifiche
- **Scrittura**: Generazione completa con monitoraggio progresso in tempo reale

### 📊 Analisi
Sezione dedicata a statistiche e analisi avanzate:
- **Dashboard**: Statistiche generali (libri totali, completati, voto medio, pagine medie, tempo medio scrittura)
- **Grafici temporali**:
  - Libri creati nel tempo (line chart)
  - Trend voto nel tempo (line chart)
- **Grafici per modello**:
  - Tempo medio di generazione (libro/pagina)
  - Pagine medie per libro
  - Costo medio (libro/pagina)
- **Confronto modelli**: Tabella comparativa con:
  - Libri completati
  - Voto medio
  - Pagine medie
  - Tempo medio scrittura
  - Tempo medio per pagina
  - Costo medio per libro

### 🎯 Benchmark
Sezione per valutare e confrontare i modelli LLM (funzionalità dedicata).

## Funzionalità Principali

### Generazione Automatica del Libro
- **Generazione capitoli**: Scrittura automatica sezione per sezione con contesto autoregressivo
- **Validazione capitoli**: Controllo automatico per evitare capitoli vuoti con retry (max 2 tentativi)
- **Progress tracking**: Monitoraggio in tempo reale dello stato di avanzamento con step indicator visivo
- **Editing struttura interattivo**: Editor drag-and-drop per modificare la struttura prima della scrittura

### Copertina AI
- **Generazione automatica**: Copertina generata con AI usando `gemini-3-pro-image-preview` (fallback: `gemini-2.5-flash-image`)
- **Contenuto copertina**: Include titolo, autore e immagine generata dalla trama
- **Integrazione PDF**: La copertina viene automaticamente inclusa come prima pagina del PDF
- **Rigenerazione**: Possibilità di rigenerare la copertina per libri esistenti

### Calcolo Pagine
- **Pagine per capitolo**: Calcolo automatico basato su parole/250 (arrotondato per eccesso)
- **Totale pagine**: Include capitoli + copertina (1 pagina) + indice (calcolato dinamicamente)
- **Visualizzazione**: Numero pagine mostrato per ogni capitolo e totale nel libro
- **Tempo di lettura**: Calcolo automatico del tempo stimato di lettura in ore

### Stima Costi
- **Calcolo automatico**: Stima del costo di generazione basato su:
  - Modello LLM utilizzato
  - Numero di pagine generate
  - Costi per token input/output configurati in `app.yaml`
- **Configurazione**: Parametri configurabili in `config/app.yaml`:
  - Token per pagina (default: 350)
  - Costi per modello (input/output per milione di token)
  - Tasso di cambio USD/EUR
- **Visualizzazione**: Costo mostrato per ogni libro nella libreria e nelle statistiche

### Valutazione Critica Automatica
- **Agente critico letterario**: Valutazione automatica del libro completato
- **Modelli**: Usa `gemini-3-pro` (default) con fallback `gemini-3-flash`
- **Valutazione**: Score 0-10 con punti di forza, debolezze e sintesi
- **Timing**: La critica viene generata automaticamente dopo il completamento del libro
- **Visualizzazione**: Modal dedicato per visualizzare la critica completa con formattazione Markdown
- **Rigenerazione**: Possibilità di rigenerare la critica per libri completati

### Gestione PDF
- **Salvataggio automatico**: I PDF vengono salvati in `backend/books/` con nome formato `YYYY-MM-DD_TitoloLibro.pdf`
- **Download**: Download diretto tramite browser con nome file corretto
- **Layout professionale**: PDF generato con xhtml2pdf, layout tipografico ottimizzato
- **Visualizzazione inline**: BookReader dedicato per leggere i libri direttamente nell'interfaccia web

### Statistiche e Analytics
- **Statistiche aggregate**: Calcolo automatico di metriche globali e per modello
- **Analisi temporali**: Tracking di libri creati e trend voti nel tempo
- **Confronto modelli**: Analisi comparativa delle performance dei diversi modelli LLM
- **Visualizzazione grafici**: Grafici interattivi con recharts per visualizzare i dati

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

### Design System
L'interfaccia utilizza un design system moderno con:
- **Gradienti e glassmorphism**: Effetti visivi moderni per un'esperienza utente elegante
- **CSS Variables**: Sistema di variabili per colori, ombre, transizioni e radius
- **Tipografia**: Font "Outfit" per il testo e "Playfair Display" per i titoli
- **Responsive**: Layout adattivo per diversi dispositivi
- **Animazioni**: Transizioni fluide e feedback visivi per le interazioni utente

### Componenti Principali
- **DynamicForm**: Form dinamico con step indicator per la creazione libri
- **LibraryView**: Visualizzazione libreria con filtri e ordinamento
- **AnalyticsView**: Dashboard analitica con grafici e statistiche
- **BookReader**: Visualizzatore libri con navigazione capitoli
- **OutlineEditor**: Editor drag-and-drop per modificare la struttura
- **CritiqueModal**: Modal per visualizzare la critica letteraria
- **ModelComparisonTable**: Tabella comparativa per i modelli




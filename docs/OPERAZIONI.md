# Avvio e gestione degli archivi

Aggiornamento: 11 ottobre 2026. Eseguire i comandi dalla root del repository, salvo indicazione diversa.

## Avvio locale

Requisiti: Python 3.11+, uv, Node.js 22.13+ e npm. Copiare `.env.example` in `.env` e impostare `GOOGLE_API_KEY`. La chiave serve anche per Gemini TTS; non serve un service account GCP per il percorso attuale.

Su Windows `avvia.cmd` controlla uv/npm, installa le dipendenze se le directory mancano e apre backend e frontend. `avvia-saggia.cmd` è un alias. Se la porta 8000 ospita NarrAI viene riutilizzata; se ospita un altro servizio si cerca una porta tra 8001 e 8020. Il proxy frontend riceve `NARRAI_API_TARGET`. Il launcher non sincronizza automaticamente dipendenze già installate dopo un aggiornamento: eseguire i comandi sotto.

```powershell
cd backend
uv sync
uv run uvicorn app.main:app --reload --reload-dir app --host 127.0.0.1 --port 8000
```

In un secondo terminale:

```powershell
cd frontend
npm ci
npm run dev
```

Frontend normalmente su `http://localhost:5173`; backend su `http://127.0.0.1:8000`. Per una porta backend diversa impostare `NARRAI_API_TARGET` nel terminale Vite. Limitare il reload a `app/` evita riavvii causati dai file prodotti. Non esporre il servizio single-user senza autenticazione direttamente su Internet.

## Build servita dal backend

```powershell
cd frontend
npm run typecheck
npm run build
```

Vite copia la build in `backend/static/`. Un backend avviato **dopo** la prima build serve anche l’interfaccia su porta 8000. La build conserva i chunk delle ultime tre versioni per le schede già aperte. Non cancellare `backend/static/` durante l’uso. La PWA conserva gli asset, mentre le API richiedono il backend; generazione e ricerca richiedono Internet.

## Dati da conservare

| Archivio / directory predefinita | Contenuto |
| --- | --- |
| `backend/narrai.sqlite3` | Narrativa e fumetti: progetti, capitoli, revisioni, job e consumi |
| `backend/books/` | PDF e audio narrativi |
| `backend/sessions/` | Copertine narrative |
| `backend/manga/` | Tavole e copertine dei fumetti |
| `backend/data/saggistica/saggia.sqlite3` | Saggi: progetti, capitoli, fonti, revisioni, job e consumi |
| `backend/data/saggistica/sources/` e `covers/` | Materiali e copertine dei saggi |

`NARRAI_DB_PATH` sostituisce il percorso del database principale; `SAGGIA_DATA_DIR` sostituisce la directory saggistica. Non puntare i due motori allo stesso file: gli schemi di dominio e l’identità degli archivi sono distinti. Segnalibri, preferenze, onboarding e alcune bozze sono nel browser, non nel backup SQLite.

## Backup consistente

Da `backend`, scegliere nomi nuovi: il comando rifiuta una destinazione esistente.

```powershell
uv run python -m app.persistence.archive backup --output narrai-backup.sqlite3
uv run python -m app.persistence.archive backup --database data/saggistica/saggia.sqlite3 --output saggi-backup.sqlite3
```

Il backup SQLite comprende WAL, revisioni, job e registro. Copiare anche le directory dei materiali e degli artefatti. Usare i percorsi effettivi se configurati diversamente. Per una fotografia senza elaborazioni, richiedere la pausa e attendere che tutti i job siano fermi. Non copiare soltanto il file principale di un database aperto.

## Ripristino e importazione

Fermare tutti i backend prima di sostituire archivi. Conservare una copia dell’archivio corrente, dei file WAL/SHM e degli artefatti. Per narrativa si può impostare `NARRAI_DB_PATH` su una copia del backup. Per i saggi collocare il backup come `saggia.sqlite3` in una directory completa di fonti/copertine e impostare `SAGGIA_DATA_DIR`. Se cambia la directory saggistica, i percorsi assoluti degli artefatti vanno riallineati; usare l’importatore per copiare un archivio con i suoi materiali.

Per importare SaggIA in una destinazione **vuota**, da `backend`:

```powershell
uv run python ../scripts/import-saggia.py --source C:/archivi/SaggIA --target C:/archivi/NarrAI-saggi
```

Impostare poi `SAGGIA_DATA_DIR=C:/archivi/NarrAI-saggi`. L’importatore verifica l’identità, esegue backup SQLite, copia materiali/copertine e riscrive i percorsi nella copia. La sorgente rimane intatta. I job importati attivi vengono fermati e richiedono una ripresa esplicita; un normale backup può invece contenere job recuperabili automaticamente al riavvio.

Il JSON narrativo storico `.sessions.json` viene importato una sola volta nella directory del database principale, dopo validazione, preservando originale e copia `.pre-sqlite.bak`. L’export JSON seguente è utile per ispezione, ma **non** conserva l’intero registro di revisioni, job e consumi:

```powershell
uv run python -m app.persistence.archive export-json --output sessions-export.json
```

## Verifica e diagnosi

Da `backend`: `uv run pytest -q`. Da `frontend`: `npm run typecheck`, `npm run test:run -- --maxWorkers=2`, `npm run build`. I test AI usano risposte simulate e archivi temporanei, senza generazioni a pagamento.

Contratti API: `/docs` per NarrAI e `/api/saggistica/docs` per il dominio saggi. Le API saggi sono montate come sottoapp: non compaiono tutte nell’OpenAPI principale. Errori 409 indicano attività incompatibile o conflitto di versione/hash; preservare la bozza prima di ricaricare. Per diagnosi locale consultare i log e `backend/.llm_traces/`, secondo la configurazione, senza pubblicare contenuti o credenziali.

I prezzi applicati sono una fotografia del catalogo del repository; controllare disponibilità e listino del proprio account prima di attività estese. I consumi sconosciuti e i costi della ricerca non quantificabili restano espliciti. Un limite di spesa viene verificato tra richieste: una chiamata già avviata può superarlo.

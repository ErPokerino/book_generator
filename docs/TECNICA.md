# Architettura attuale di NarrAI

Questa documentazione descrive la versione locale del repository. Per l'avvio vedi [README](../README.md); per il catalogo configurato vedi [modelli e costi](MODELLI_E_COSTI.md).

## Componenti e responsabilità

| Area | Codice | Responsabilità |
| --- | --- | --- |
| Interfaccia | `frontend/src/components/`, `router.tsx` | Creazione, libreria, lettore, manga, valutazione e analytics |
| Accesso HTTP | `frontend/src/api/client.ts` | Chiamate e tipi client; parsing dei nomi di download in `utils/downloadFilename.ts` |
| Routing API | `backend/app/api/routers/` | Validazione delle richieste, risposte HTTP, avvio dei processi |
| Processi applicativi | `backend/app/services/` | Generazione libri/manga, esportazioni, critica, costi e statistiche |
| Generazione narrativa | `backend/app/agent/` | Domande, piano narrativo, outline, capitoli, copertina e story bible |
| Runtime dei modelli | `backend/app/llm/` | Selezione modelli, retry, output strutturati e tracing |
| Persistenza | `backend/app/persistence/sqlite_store.py` | Transazioni, capitoli, revisioni, job e consumi |
| Configurazione | `config/` | Campi form, prompt, modelli, timeout, soglie e stime |

Il frontend usa React e TypeScript, con Vite per la build e Vitest per i test. Il backend usa FastAPI e Pydantic. L'inferenza passa dalle Gemini Developer API; il TTS opzionale ha un servizio dedicato.

Non sono presenti login, crediti, social, MongoDB, GCS o un servizio email. Il parametro storico `user_id` resta in alcuni contratti per leggere i dati esistenti: non rappresenta autenticazione.

## Percorso di una generazione

1. Submission e risposte inizializzano una sessione.
2. I generatori preparano bozza, profili e struttura; il piano può includere già l'outline.
3. Dopo la validazione, il router libro registra il job prima di accodare il task.
4. `writer/book_orchestrator.py` genera le sezioni in ordine, salva i capitoli e aggiorna la memoria narrativa.
5. I capitoli completati vengono seguiti da copertina, PDF e critica. Lo stato di scrittura e quello della critica sono distinti.
6. La libreria e il frontend leggono i progressi attraverso le API.

`durable_worker.py`, avviato dal lifespan, acquisisce i job da SQLite con una prenotazione di 45 secondi rinnovata ogni 10. Un vincolo univoco impedisce due job attivi sullo stesso progetto; un controllo della prenotazione impedisce le scritture di un worker scaduto. L'arresto ordinato riaccoda il job; dopo un crash un nuovo worker recupera la prenotazione scaduta. Pause volontarie ed errori applicativi restano espliciti. `BackgroundTasks` è mantenuto solo per l'adapter in memoria dei test.

La ripresa dei libri percorre i capitoli contigui effettivamente salvati e riparte dal primo assente. Questo evita di rigenerare l'ultimo capitolo se il processo si è fermato fra il suo salvataggio e l'aggiornamento del contatore. Il normale avvio non sovrascrive libri che contengono già capitoli e non sono in esecuzione.

## Archivio e file

| Percorso | Contenuto |
| --- | --- |
| `backend/narrai.sqlite3` | Sessioni, capitoli, revisioni, job, registro dei consumi |
| `backend/.sessions.json` | Archivio precedente, importato una volta e preservato |
| `backend/books/` | PDF e audio |
| `backend/sessions/` | Copertine dei libri |
| `backend/manga/` | Immagini manga |
| `backend/.llm_traces/` | Tracce locali delle invocazioni, secondo configurazione |
| `backend/static/` | Build del frontend, rigenerabile |
| `backend/app/static/book_styles.css` | Stili dei PDF: separati dalla build del frontend |

`SessionStore` implementa le mutazioni e invoca un solo hook di persistenza. `SQLiteSessionStore` usa WAL, sincronizzazione FULL, chiavi esterne e transazioni di lettura consistenti. Le scritture iniziano con `BEGIN IMMEDIATE`; letture scollegate e confronto fra originale, modifica e stato corrente uniscono campi indipendenti e rifiutano sovrascritture concorrenti (HTTP 409). Capitolo, revisione e checkpoint sono salvati nella stessa transazione. `FileSessionStore` resta per compatibilità, import/export e test.

Un archivio non leggibile o contenente record non validi interrompe il caricamento: non viene interpretato come archivio vuoto né riscritto eliminando implicitamente i record problematici. Prima di operazioni manuali sull'archivio, farne una copia e fermare il backend.

SQLite coordina più processi sullo stesso dispositivo; ogni worker esegue un job per volta. Questa architettura è locale: non è una coda distribuita fra host. Un'interruzione dopo la risposta del fornitore ma prima del salvataggio può richiedere una nuova chiamata; non è garantita l'esecuzione esattamente una volta presso Google. Il registro segnala le chiamate di esito ignoto. [Backup e ripristino](EVOLUTIVE_2026-09-20.md) usano l'API backup SQLite, comprensiva del WAL.

Gli export PDF del libro passano tutti da `pdf_service.generate_complete_book_pdf`; i nomi includono l'ID sessione per distinguere titoli uguali. I percorsi sono registrati nella sessione. La cancellazione usa solo associazioni esplicite, preserva file condivisi con altri progetti e non indovina il proprietario dal titolo. Eventuali vecchi file privi di associazione restano sul disco.

Le conversioni PDF/EPUB/DOCX e le chiamate SDK native vengono eseguite fuori dall'event loop. La cache esplicita a pagamento del writer è stata rimossa; i prefissi stabili possono beneficiare della cache implicita, contabilizzata dai consumi restituiti. Non tutto il backend è stato convertito a I/O asincrono.

`agent/narrative_memory.py` estrae fatti con citazioni esatte, capitolo, hash e posizione della prova. Le deduzioni restano distinte dai fatti espliciti; il recupero cerca per entità e fili aperti nell'intera storia. Il writer riceve fino a 36 fatti pertinenti; il controllo ne considera fino a 80, quindi non è una verifica esaustiva. Una contraddizione documentata attiva una sola revisione mirata; se persiste, la scrittura si ferma. Modificare un capitolo invalida memoria dipendente, PDF e critica, conservando le revisioni.

## Frontend e rete

Il polling generico mantiene callback aggiornate senza ricreare il ciclo a ogni render, ignora risposte di cicli invalidati, applica backoff e consente un nuovo tentativo. I polling specifici di libro e manga conservano responsabilità ulteriori, fra cui la critica e i progressi per pagina.

La ricerca in libreria annulla la richiesta precedente e controlla l'identità della risposta. Un errore mostra una possibilità di riprovare, preservando i risultati già caricati. Il lettore rende Markdown senza eseguire HTML grezzo; l'audio viene invalidato al cambio del capitolo.

Il service worker conserva gli asset dell'interfaccia ma usa `NetworkOnly` per le API. Le navigazioni `/api` non ricevono l'HTML della SPA come fallback offline. Il backend locale e una connessione Internet sono necessari per generare.

## API e configurazione

Le route attuali sono in `backend/app/api/routers/`; `/docs` espone il contratto OpenAPI dell'istanza avviata. I principali prefissi sono `/api/config`, `/api/questions`, `/api/draft`, `/api/outline`, `/api/book`, `/api/library`, `/api/manga`, `/api/critique`, `/api/session`, `/api/studio` e `/api/files`. Lo studio espone testo, revisioni, fatti, pausa e dettaglio dei consumi; il salvataggio verifica l'hash del testo di partenza.

La chiave di generazione viene letta da `GOOGLE_API_KEY`. Non è necessario esporre il backend in rete per usare l'app sullo stesso dispositivo. I contenuti inclusi nei prompt vengono trasmessi ai servizi AI di Google; l'archivio locale non implica inferenza offline.

`usage_service.py` è la fonte unica delle tariffe e conserva per ogni chiamata modello, consumi, listino e cambio applicato. Include tentativi falliti, risposte scartate, ragionamento, cache, immagini e audio. Le differenze rispetto alla fattura e i prezzi verificati sono descritti in [MODELLI_E_COSTI.md](MODELLI_E_COSTI.md). Le stime di pagine sono basate sulle parole e non equivalgono alla paginazione fisica del PDF.

## Verifiche e limiti

Eseguire `uv run pytest` da `backend`, poi `npm run typecheck`, `npm run test:run` e `npm run build` da `frontend`. I test usano risposte simulate per le invocazioni AI e directory temporanee per la persistenza.

Gli eval in `evals/` verificano contratti, contesto e campioni statici: non misurano automaticamente la qualità letteraria di romanzi nuovi. Per debito residuo, evidenze e priorità vedi la [revisione tecnica](REVISIONE_2026-09-20.md).

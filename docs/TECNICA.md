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
| Persistenza | `backend/app/agent/session_store.py` | Stato delle sessioni e salvataggio JSON |
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

`BackgroundTasks` esegue i processi nello stesso processo FastAPI. Non è una coda durevole e non sopravvive alla chiusura del server. All'avvio, il lifespan marca i job interrotti come falliti o sospesi e recuperabili; la ripresa resta esplicita.

La ripresa dei libri percorre i capitoli contigui effettivamente salvati e riparte dal primo assente. Questo evita di rigenerare l'ultimo capitolo se il processo si è fermato fra il suo salvataggio e l'aggiornamento del contatore. Il normale avvio non sovrascrive libri che contengono già capitoli e non sono in esecuzione.

## Archivio e file

| Percorso | Contenuto |
| --- | --- |
| `backend/.sessions.json` | Tutte le sessioni, capitoli, progressi e metadati |
| `backend/books/` | PDF e audio |
| `backend/sessions/` | Copertine dei libri |
| `backend/manga/` | Immagini manga |
| `backend/.llm_traces/` | Tracce locali delle invocazioni, secondo configurazione |
| `backend/static/` | Build del frontend, rigenerabile |
| `backend/app/static/book_styles.css` | Stili dei PDF: separati dalla build del frontend |

`SessionStore` implementa le mutazioni e invoca un solo hook di persistenza. `FileSessionStore` implementa il caricamento e il commit: file temporaneo nella stessa directory, flush, fsync e `os.replace`, senza rimuovere prima il file precedente. Un errore di scrittura viene propagato e lo stato in memoria viene ricaricato dall'ultimo archivio valido.

Un archivio non leggibile o contenente record non validi interrompe il caricamento: non viene interpretato come archivio vuoto né riscritto eliminando implicitamente i record problematici. Prima di operazioni manuali sull'archivio, farne una copia e fermare il backend.

**Vincolo operativo:** avviare un solo processo backend. Il file store mantiene oggetti condivisi in memoria, riscrive l'intero archivio e non offre transazioni fra worker o processi. Il commit atomico protegge il file, non introduce un database né backup automatici.

Gli export PDF del libro passano tutti da `pdf_service.generate_complete_book_pdf`; i nomi includono l'ID sessione per distinguere titoli uguali. I percorsi sono registrati nella sessione. La cancellazione usa solo associazioni esplicite, preserva file condivisi con altri progetti e non indovina il proprietario dal titolo. Eventuali vecchi file privi di associazione restano sul disco.

Le conversioni PDF/EPUB/DOCX richieste dalle route libro e la creazione della cache Gemini del writer sono eseguite fuori dall'event loop. Non tutto il backend è stato convertito a I/O asincrono.

## Frontend e rete

Il polling generico mantiene callback aggiornate senza ricreare il ciclo a ogni render, ignora risposte di cicli invalidati, applica backoff e consente un nuovo tentativo. I polling specifici di libro e manga conservano responsabilità ulteriori, fra cui la critica e i progressi per pagina.

La ricerca in libreria annulla la richiesta precedente e controlla l'identità della risposta. Un errore mostra una possibilità di riprovare, preservando i risultati già caricati. Il lettore rende Markdown senza eseguire HTML grezzo; l'audio viene invalidato al cambio del capitolo.

Il service worker conserva gli asset dell'interfaccia ma usa `NetworkOnly` per le API. Le navigazioni `/api` non ricevono l'HTML della SPA come fallback offline. Il backend locale e una connessione Internet sono necessari per generare.

## API e configurazione

Le route attuali sono in `backend/app/api/routers/`; `/docs` espone il contratto OpenAPI dell'istanza avviata. I principali prefissi sono `/api/config`, `/api/questions`, `/api/draft`, `/api/outline`, `/api/book`, `/api/library`, `/api/manga`, `/api/critique`, `/api/session` e `/api/files`. Verificare il path completo nel router/OpenAPI, anziché ricavarlo dai nomi delle funzioni.

La chiave di generazione viene letta da `GOOGLE_API_KEY`. Non è necessario esporre il backend in rete per usare l'app sullo stesso dispositivo. I contenuti inclusi nei prompt vengono trasmessi ai servizi AI di Google; l'archivio locale non implica inferenza offline.

Modelli e tariffe configurate non sono una verifica della disponibilità o del listino del fornitore. Le stime di pagine sono basate sulle parole e non equivalgono alla paginazione fisica del PDF; i costi sono stime, non fatture.

## Verifiche e limiti

Eseguire `uv run pytest` da `backend`, poi `npm run typecheck`, `npm run test:run` e `npm run build` da `frontend`. I test usano risposte simulate per le invocazioni AI e directory temporanee per la persistenza.

Gli eval in `evals/` verificano contratti, contesto e campioni statici: non misurano automaticamente la qualità letteraria di romanzi nuovi. Per debito residuo, evidenze e priorità vedi la [revisione tecnica](REVISIONE_2026-09-20.md).

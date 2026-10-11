# Architettura attuale di NarrAI

Aggiornamento: **11 ottobre 2026**. Questa documentazione descrive l’app locale unificata per Narrativa, Saggio e Fumetto. Per l’avvio vedi [README](../README.md); per backup e importazioni vedi [operazioni](OPERAZIONI.md); per il catalogo applicato vedi [modelli e costi](MODELLI_E_COSTI.md).

## Componenti e responsabilità

| Area | Codice | Responsabilità |
| --- | --- | --- |
| Interfaccia comune | `frontend/src/components/`, `router.tsx`, `Notebook.css` | Creazione, biblioteca, lettore, fumetti, valutazione, analisi e impostazioni |
| Saggistica | `backend/app/essay/`, `frontend/src/essay/` | Brief, fonti, evidenze, piano, scrittura, revisione, export e stime |
| Vista trasversale | `api/routers/works.py`, `services/studio_analytics.py` | Biblioteca paginata e metriche sui due archivi |
| Fumetti | `core/comics.py`, `agent/manga/`, `utils/comics.ts` | Formato, sottogenere e direzione di storyboard e immagini |
| Accesso HTTP | `frontend/src/api/client.ts`, `frontend/src/essay/api.ts` | Contratti comuni e saggi; parsing dei download in `utils/downloadFilename.ts` |
| Routing API | `backend/app/api/routers/` | Validazione delle richieste, risposte HTTP, avvio dei processi |
| Processi applicativi | `backend/app/services/` | Generazione libri/manga, esportazioni, critica, costi e statistiche |
| Generazione narrativa | `backend/app/agent/` | Domande, piano narrativo, outline, capitoli, copertina e story bible |
| Runtime dei modelli | `backend/app/llm/` | Selezione modelli, retry, output strutturati e tracing |
| Persistenza | `backend/app/persistence/sqlite_store.py` | Transazioni, capitoli, revisioni, job e consumi |
| Configurazione | `config/` | Campi form, prompt, modelli, timeout, soglie e stime |

Il frontend usa React 18 e TypeScript, React Router, Vite 5 e Vitest 4. Il backend usa Python 3.11+, FastAPI e Pydantic 2; uv e npm mantengono i lockfile. Per la toolchain frontend completa usare Node.js 22.13+. L’inferenza passa dalle Gemini Developer API; il TTS opzionale usa la stessa chiave. `google-cloud-texttospeech` resta una dipendenza storica, non il requisito del percorso TTS corrente.

Non sono presenti login, crediti, social, MongoDB, GCS o un servizio email. Il parametro storico `user_id` resta in alcuni contratti per leggere i dati esistenti: non rappresenta autenticazione.

## Percorso di una generazione narrativa

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
| `backend/data/saggistica/saggia.sqlite3` | Progetti saggistici, capitoli, revisioni, fonti, job e consumi |
| `backend/data/saggistica/sources/`, `covers/` | Materiali e copertine dei saggi |
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

La build conserva i chunk delle ultime tre versioni distinte in `backend/static/assets`, con cronologia locale `.asset-history.json`. Il precache include solo gli asset della versione corrente. Non svuotare la directory mentre l'app è in uso: le schede aperte possono ancora richiedere un vecchio modulo lazy. Per versioni più vecchie o errori di rete, il fallback propone un ricaricamento esplicito e non aggiorna automaticamente una pagina con testo in modifica.

Lo schema Gemini della memoria mantiene tipi e valori ammessi ma omette limiti di lunghezza e default che rendevano troppo complessa la grammatica. Questi vincoli sono verificati da Pydantic sulla risposta. Le citazioni che differiscono soltanto per Markdown, virgolette tipografiche o spazi vengono ricondotte alla sottostringa originale e alle sue posizioni; parole, negazioni, numeri e punteggiatura di frase devono coincidere. Il repair riceve il contesto completo, senza troncare il capitolo a 6.000 caratteri.

## Domini integrati e API trasversali

Il lifespan avvia worker narrativo e saggistico sullo stesso backend. `EssayStore` riusa transazioni, revisioni e coda, ma verifica `product_id=saggia` e carica `EssaySession`. Non importa il JSON narrativo né converte un archivio di un altro dominio. `SAGGIA_DATA_DIR` sceglie directory e database saggistici; `NARRAI_DB_PATH` riguarda narrativa e fumetti.

Ogni job lega lo store a un `ContextVar`: lookup di sessioni e metering seguono quel contesto anche con ID uguali e richieste concorrenti nei due archivi. L’unicità dei job attivi è per progetto nel rispettivo database. L’unificazione non impone uno schema comune dei payload.

| Contratto | Responsabilità |
| --- | --- |
| `GET /api/works` | Unisce archivi prima di filtri e paginazione; campi storici `books` e `session_id` conservati |
| `GET /api/works/analytics` | Produzione e consumi; filtro `content_type` |
| `POST /api/critique/analyze-pdf` | PDF esterno e rubrica selezionata; risultato non persistito |
| `POST /api/critique/analyze-work/{work_type}/{session_id}` | Opera interna e rubrica del dominio; consumi nel suo store |
| `/api/saggistica` | Sottoapp FastAPI con archivio e worker saggi |

Le API saggi hanno OpenAPI distinto su `/api/saggistica/docs`, non incluso automaticamente nel documento principale. I contratti principali, relativi a `/api/saggistica`, sono `GET /essay-config`, `POST /essay-estimates`, CRUD `/essays`, brief/pubblicazione/piano con `expected_version`, approvazione, job, pausa, ricerca, fonti/evidenze, capitoli con `expected_hash`, revisioni, copertina ed export. `app.essay.main:app` conserva l’adapter autonomo con prefisso `/api` per test e strumenti.

`content_type` conserva `book`, `essay`, `manga`, presentati come Narrativa, Saggio, Fumetto. Il fumetto aggiunge `comic_format` (`manga` o `graphic_novel`) e `comic_genre`. I vecchi progetti restano Manga. Moduli e route `manga` sono nomi compatibili; storyboard, tavole e copertine ricevono istruzioni del formato effettivo, inclusa lettura da sinistra a destra per l’edizione italiana.

Route frontend: `/library`, `/new`, `/new/essay`, `/essay/:id`, `/comics`, `/studio/:sessionId`, `/read/:kind/:id`, `/benchmark`, `/analytics`, `/settings`. `/manga` e `/beta/manga` reindirizzano conservando la query; `/book/:sessionId` mantiene il lettore narrativo precedente. La creazione narrativa riprende soltanto con una sessione esplicitamente richiesta tramite `?session=…`.

### Scrittura e fonti dei saggi

Il piano approvato assegna ID stabili a sezioni, argomenti ed evidenze. Il writer genera parti con obiettivo di circa 1.300 parole e salva checkpoint prima di comporre il capitolo. Controllo dei capitoli e revisione complessiva sono distinti. Le correzioni delegate hanno massimo due passaggi, hash/versioni verificati e salvataggio atomico del capitolo, revisione e ricevuta di avanzamento.

`sources.py` limita importazioni a 12 MB e 250.000 caratteri per fonte e controlla URL pubblici; non offre OCR o accessi riservati. `citations.py` valida marcatori `[@E…]` e compone riferimenti/bibliografia dagli estratti. La revisione vincola i riferimenti ai capitoli effettivamente forniti nel gruppo, con un solo tentativo di riparazione semantica. La corrispondenza testuale non dimostra la verità delle affermazioni.

Gli export saggi passano da `exports.py` e `pdf_layout.py`, distinti dal PDF narrativo. La biblioteca può calcolare le pagine PDF da dati salvati, senza AI, con cache limitata e invalidazione per versione. Durante un job attivo non calcola quel conteggio.

### Previsioni, analisi e interazioni

La UI saggi mostra pagine, conservando `target_words` per compatibilità: 250 parole/pagina, preset 15.000/35.000/60.000, intervallo 1.000–120.000. La visualizzazione arrotonda in eccesso; modificare altri campi non arrotonda il budget storico.

`essay/estimates.py` calcola `POST /api/saggistica/essay-estimates` senza generare, creare progetti o registrare consumi. Applica budget di token e listino comune ai modelli di domande, piano, scrittura e controllo. Le ipotesi sono in `config/essay.yaml:estimation`; il tempo usa fallback in `config/app.yaml` oppure, con almeno tre scritture comparabili e ininterrotte, la mediana per parola. Ricerca, fonti, correzioni, revisione separata e copertina AI sono aggiuntive. Il client usa debounce, AbortController e identificazione della richiesta per ignorare risposte obsolete.

`studio_analytics.py` raccoglie stati, parole/capitoli, tavole completate, mesi di creazione e consumi per fase/modello. Somma solo costi quantificabili, con il cambio conservato negli eventi; copertura parziale e chiamate non quantificate sono esplicite. I PDF esterni non hanno sessione e restano esclusi.

`NotebookSoundProvider` sintetizza rumore filtrato tramite Web Audio. L’opzione è spenta per default e salvata localmente. Click/digitazione possono sbloccare il contesto audio; hover non lo sblocca. Il fruscio hover riguarda solo `.notebook-mode-card`, con mouse/puntatore fine, volume inferiore e intervallo minimo di 450 ms; passare fra figli non lo ripete. Disabilitare i suoni rimuove i listener e sospende l’audio. SVG/CSS rispettano il movimento ridotto del sistema.

## API e configurazione

Le route attuali sono in `backend/app/api/routers/`; `/docs` espone il contratto OpenAPI dell'istanza avviata. I principali prefissi sono `/api/config`, `/api/questions`, `/api/draft`, `/api/outline`, `/api/book`, `/api/library`, `/api/manga`, `/api/critique`, `/api/session`, `/api/studio` e `/api/files`. Lo studio espone testo, revisioni, fatti, pausa e dettaglio dei consumi; il salvataggio verifica l'hash del testo di partenza.

La chiave di generazione viene letta da `GOOGLE_API_KEY`. Non è necessario esporre il backend in rete per usare l'app sullo stesso dispositivo. I contenuti inclusi nei prompt vengono trasmessi ai servizi AI di Google; l'archivio locale non implica inferenza offline.

`usage_service.py` è la fonte unica delle tariffe e conserva per ogni chiamata modello, consumi, listino e cambio applicato. Include tentativi falliti, risposte scartate, ragionamento, cache, immagini e audio. Le differenze rispetto alla fattura e i prezzi verificati sono descritti in [MODELLI_E_COSTI.md](MODELLI_E_COSTI.md). Le stime di pagine sono basate sulle parole e non equivalgono alla paginazione fisica del PDF.

## Verifiche e limiti

Eseguire `uv run pytest` da `backend`, poi `npm run typecheck`, `npm run test:run` e `npm run build` da `frontend`. I test usano risposte simulate per le invocazioni AI e directory temporanee per la persistenza.

Gli eval in `evals/` verificano contratti, contesto e campioni statici: non misurano automaticamente la qualità letteraria di romanzi nuovi. La [revisione del 20 settembre](REVISIONE_2026-09-20.md) è storica: SQLite, worker, memoria e studio sono stati poi implementati. Restano contratti in parte duplicati, componenti grandi e più percorsi di invocazione AI. Non è presente un benchmark umano comparabile delle tre modalità.

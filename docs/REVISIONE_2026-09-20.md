# Revisione del progetto — 20 settembre 2026

L'analisi ha individuato difetti concreti nei percorsi di recupero, nella persistenza, negli export e nella sincronizzazione del frontend. Le correzioni descritte sotto sono applicate al codice. Le cinque aree finali sono proposte di evoluzione, non funzionalità già implementate.

## Metodo e perimetro

Revisione del codice di sessioni, job, writer, memoria narrativa, API, file, libreria e componenti principali del frontend; esecuzione delle suite esistenti e aggiunta di regressioni sui problemi riscontrati. Controllo nel browser del percorso iniziale, della libreria e del modulo di creazione con una build reale e un backend isolato in memoria.

I test iniziali erano verdi: **76 backend e 6 frontend**. Questo non copriva i guasti poi riprodotti: mancavano soprattutto sequenze fra API e worker, errori del filesystem e risposte asincrone fuori ordine.

Non sono state avviate generazioni a pagamento né modificati i libri dell'archivio personale. Le chiamate AI nei test sono simulate. L'audit non certifica qualità letteraria, disponibilità dei modelli, prezzi attuali o impaginazione editoriale di ogni formato e lingua.

## Esito delle verifiche

- Backend: **92 test superati** (`uv run pytest -q`).
- Frontend: **20 test superati**, controllo TypeScript e build di produzione riusciti.
- Differenze Git: nessun errore di whitespace rilevato.
- Browser: libreria e modulo di creazione verificati con archivio isolato in memoria.
- Rimane un avviso della build sulla banca dati Browserslist datata; non è un errore di compilazione. L'audit non ha effettuato un aggiornamento generale delle dipendenze frontend.

## Difetti corretti

| Gravità | Difetto e conseguenza | Intervento |
| --- | --- | --- |
| Alta | Il salvataggio eliminava il JSON precedente prima del rename e nascondeva gli errori: un guasto poteva perdere l'archivio o simulare un salvataggio riuscito. | Commit con temporaneo, flush/fsync e sostituzione atomica; propagazione dell'errore e ripristino in memoria dell'ultimo stato persistito. |
| Alta | Un archivio corrotto o una sessione invalida venivano ignorati, predisponendo una successiva riscrittura incompleta. | Caricamento completo oppure errore esplicito, preservando il file originale. |
| Alta | La route di ripresa rimuoveva `is_paused` e il worker richiedeva ancora quel flag: il comando di ripresa falliva. | Contratto coerente fra accodamento, worker e orchestratore; test che esegue la sequenza completa. |
| Alta | Un crash dopo il salvataggio di un capitolo poteva causarne la rigenerazione; gli errori inattesi azzeravano il checkpoint. | Ripresa dal primo capitolo contiguo assente; checkpoint conservato e stato recuperabile anche per errori inattesi. Avvio ordinario bloccato sui libri già scritti. |
| Alta | Il lettore inseriva il testo del modello con `dangerouslySetInnerHTML`. | Rendering Markdown con HTML grezzo disabilitato; regressione con tag eseguibili. |
| Alta | Il download generico non controllava i separatori Windows e il percorso finale. | Validazione dei nomi e contenimento nella directory autorizzata, anche dopo risoluzione del percorso. |
| Alta | Il cleanup considerava obsoleti tutti i libri senza critica; la cancellazione cercava PDF anche per somiglianza del titolo. | Rimossi gli endpoint di cleanup inutilizzati; cancellazione basata su associazioni esplicite, con tutela dei file condivisi e rifiuto durante processi attivi rilevati. |
| Media | La libreria cercava alcuni PDF nella directory sbagliata; due titoli uguali potevano produrre lo stesso nome file. | Directory ricavata dal servizio storage, ID sessione nel nome, percorso PDF registrato nella sessione e scanner unico. |
| Media | I nomi Unicode potevano rendere invalido l'header del download o essere interpretati male dal client. | Header `filename*` e parser condiviso nel frontend. |
| Media | Polling con callback inline, risultati tardivi e retry sullo stesso processo potevano aggiornare lo stato sbagliato o non ripartire. | Ciclo stabile, invalidazione delle risposte precedenti, ripartenza e stop terminale. Protezione delle risposte tardive anche nel monitor libro. |
| Media | Cambiando ricerca, una risposta vecchia poteva sostituire quella nuova; il caricamento incrementale eseguiva effetti dentro un aggiornamento di stato. | AbortController, identificatore della richiesta e caricamento senza effetti nei setter. Errori distinti da archivio vuoto, risultati conservati e pulsante Riprova. |
| Media | La cache PWA poteva restituire progressi vecchi senza backend. | API solo dalla rete, escluse dal fallback di navigazione della SPA. |
| Media | Cambiando capitolo, il player poteva mantenere o ricevere l'audio del capitolo precedente. | Reset, invalidazione delle richieste e rilascio di audio e URL al cambio di contenuto. |
| Media | Alcuni outline escludevano prologo ed epilogo; un heading vuoto poteva duplicare la sezione precedente. | Correzione concorde dei parser Python e TypeScript e test sui casi misti. |
| Media | Cache writer senza scadenza locale e creazione sincrona durante una funzione async. | Scadenza delle entry e creazione fuori dall'event loop. |
| Media | Dopo un riavvio, la critica poteva restare indefinitamente pending/running anche a libro completo. | Recupero come valutazione fallita e ritentabile, senza cambiare il completamento del libro. |
| Minore | Timestamp con fuso orario causavano sottrazioni incompatibili; un nuovo job manteneva il flag di completamento precedente. | Normalizzazione UTC nel calcolo delle metriche e reset del completamento all'avvio. |
| Minore | Una parentesi CSS in eccesso produceva un warning di sintassi; i plugin della build interferivano con il runtime dei test. | CSS corretto e configurazioni Vite/Vitest separate. |

Le verifiche sono in `backend/tests/test_session_persistence.py`, `test_book_resume.py`, `test_file_exports.py`, `test_writer_cache.py`, nei test di job e writer aggiornati, e nei test frontend di polling, libreria, lettore, audio, outline e download.

## Debito tecnico già ridotto

- **Persistenza:** eliminati gli override che ripetevano il salvataggio nel file store, anche due volte per pausa/ripresa. Memory store e file store usano gli stessi metodi e gli stessi filtri.
- **PDF e statistiche:** rimossa l'implementazione PDF duplicata nella route e unificati scanner, abbreviazioni e conteggio delle pagine. Le conversioni delle route libro sono eseguite fuori dall'event loop. Il servizio della critica non importa più il router per il proprio fallback PDF.
- **Gestione degli errori:** sostituiti i quattro blocchi ripetuti di fallimento della generazione/ripresa con un percorso condiviso che preserva il lavoro.
- **Codice storico:** rimossi lo script che reinseriva credenziali per la vecchia autenticazione, l'utility che importava uno user store eliminato, lo stato LangGraph inutilizzato e la relativa dipendenza. Lockfile allineato.
- **Avvio:** sostituito il vecchio evento startup con il lifespan FastAPI.
- **Documentazione:** riscritte le guide tecnica e funzionale, che descrivevano ancora cloud, crediti, social e componenti assenti. Corretto anche il messaggio ambiguo sul funzionamento locale: l'archivio è locale, l'inferenza usa servizi online.

## Le cinque aree di miglioramento più importanti

### 1. Persistenza transazionale e processi durevoli — architettura

**Perché è prioritaria.** Il commit del JSON è ora più sicuro, ma ogni aggiornamento riscrive tutte le opere. Lo stato resta condiviso in memoria, la concorrenza fra più processi non è gestita e i task dipendono dalla vita del server. Le correzioni riducono i guasti; questi limiti strutturali restano.

**Proposta.** SQLite locale con repository separati per progetti, revisioni, capitoli, job e artefatti. Transazioni per salvare insieme capitolo e checkpoint; vincolo che impedisca due job attivi equivalenti; worker con stato persistito, heartbeat e acquisizione esclusiva del lavoro. Migrazione esplicita e reversibile dal JSON, preceduta da backup. Contratti API generati dall'OpenAPI per ridurre il disallineamento con TypeScript.

**Risultato verificabile.** Spegnimenti in punti diversi non duplicano capitoli o richieste pagate; il riavvio trova uno stato coerente; il tempo di aggiornamento non cresce con il testo di tutti i libri. Impegno relativo: alto. Non è necessario introdurre servizi cloud per ottenere questi benefici.

### 2. Memoria narrativa basata su fatti — qualità dei libri

**Perché è prioritaria.** La story bible attuale conserva estratti euristici, un contesto recente e pochi capitoli integrali. Non rappresenta esplicitamente chi conosce un segreto, la posizione dei personaggi, gli oggetti, le promesse narrative e la cronologia. Una sintesi ottenuta scegliendo apertura e chiusura può perdere un fatto decisivo nel mezzo.

**Proposta.** Estrarre dopo ogni capitolo fatti strutturati con riferimento al testo: personaggi e loro conoscenze, luoghi, tempo, cambiamenti, relazioni e fili aperti. Conservare i fatti lontani ancora rilevanti. Prima del capitolo successivo recuperare i vincoli pertinenti; dopo la scrittura controllare le contraddizioni e chiedere una revisione mirata. Il modello deve distinguere fatti espliciti da inferenze.

**Risultato verificabile.** Un benchmark con segreti, oggetti e promesse introdotti molti capitoli prima misura contraddizioni, dimenticanze e risoluzioni mancate. Le correzioni riportano evidenza testuale. Impegno relativo: alto; impatto atteso sulla coerenza: molto alto, da misurare.

### 3. Uno studio di scrittura centrato sul manoscritto — UX/UI

**Perché è prioritaria.** Il wizard è chiaro per iniziare, ma resta un insieme di schermate di configurazione e avanzamento. Nel modulo attuale la copertina compare prima di diverse scelte narrative; costo e modelli sono raggruppati nello stesso pannello. Il lettore non diventa un ambiente di lavoro editoriale.

**Proposta.** Conservare il linguaggio visivo carta/inchiostro, riorganizzando il prodotto attorno a un progetto: indice e stato delle sezioni a sinistra, manoscritto al centro, note e controlli a destra. Su mobile usare tre viste a schede. Avvio breve con idea, pubblico, obiettivo di lunghezza e tono; dettagli avanzati progressivi. Mostrare sempre stato di salvataggio, attività in corso, stima di costo e azione successiva. Spostare copertina ed export nella preparazione finale dell'opera.

**Risultato verificabile.** Un autore riesce a iniziare, ritrovare il punto di lavoro e correggere un capitolo senza conoscere i nomi dei modelli. Test con tastiera, mobile e utenti reali misurano completamento, errori e tempo per i compiti principali. Impegno relativo: medio-alto.

### 4. Revisioni e rigenerazione selettiva — funzionalità

**Perché è prioritaria.** La pipeline privilegia la prima generazione. Una critica utile dovrebbe poter diventare un intervento concreto senza rifare l'intero libro o perdere un passaggio riuscito. La cronologia della bozza non equivale al versionamento del manoscritto.

**Proposta.** Versioni immutabili per capitolo, confronto delle modifiche, ripristino e parti bloccate dall'autore. Comandi mirati: riscrivere una scena, cambiare punto di vista, accorciare un dialogo, sviluppare il finale. Prima dell'applicazione mostrare anteprima, costo previsto e sezioni successive potenzialmente da aggiornare. Ogni export deve riferirsi a una revisione precisa.

**Risultato verificabile.** Rigenerare una scena lascia identiche le parti bloccate, è annullabile e segnala le conseguenze sulla continuità. Impegno relativo: alto; dipende dalla base di versionamento dell'area 1 e beneficia della memoria dell'area 2.

### 5. Valutazione editoriale ripetibile e controllo dei costi — qualità e affidabilità

**Perché è prioritaria.** Gli eval attuali verificano soprattutto parsing, frammenti del contesto e campioni statici. La critica finale e le medie in analytics non bastano per decidere se una modifica a prompt o modelli migliori davvero i libri. L'aggregazione dei token per fase non è un registro completo di ogni tentativo, parte o modello usato.

**Proposta.** Un corpus stabile di brief per generi e lunghezze, con confronti alla cieca e valutazione umana su un campione. Rubriche distinte per struttura, causalità, personaggi, dialoghi, ripetizioni, stile e finale. Separare generatore e revisore, con un numero limitato di revisioni. Registrare ogni chiamata, compresi tentativi falliti con output ricevuto, parti Ultra e cache, e consentire un tetto di spesa. Aggiungere verifiche degli export: contenuto, ordine, metadati, font, immagini e apertura nei lettori.

**Risultato verificabile.** Ogni cambiamento confronta qualità, costo e tempo sullo stesso set; una regressione blocca il rilascio. Un voto più alto non basta se peggiorano coerenza o costo oltre i limiti fissati. Impegno relativo: medio-alto, incrementale.

## Ordine operativo suggerito

Consolidare prima la base transazionale; avviare un piccolo corpus di valutazione mentre si introduce la memoria narrativa. Sviluppare poi studio editoriale e revisioni selettive sullo stesso modello di progetto. Eviterei di giudicare il progresso dalla sola lunghezza generata o dall'adozione di un modello più costoso.

## Limiti residui da mantenere visibili

- Un solo processo backend per l'archivio JSON attuale; nessuna garanzia fra worker multipli e nessun backup automatico.
- Alcuni componenti, soprattutto il form e il servizio manga, restano grandi; i contratti di stato sono ancora in parte dizionari e tipi duplicati.
- Il runtime usa più percorsi di invocazione e politiche di retry; serve consolidamento prima di promettere contabilità completa o controllo uniforme della spesa.
- Gli export sono verificati funzionalmente sui campioni di regressione, non certificati per pubblicazione o copertura tipografica universale.
- Il test nel browser è una verifica desktop del percorso iniziale, non una campagna completa su tutti i dispositivi né una generazione reale end-to-end.

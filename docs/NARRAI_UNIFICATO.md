# NarrAI: narrativa, saggi e fumetti nello stesso studio

Integrazione dell'11 ottobre 2026, dal codice SaggIA sul branch `codex/saggistica`, commit `63a4c0d`, nel checkout NarrAI. Il precedente piano di prodotto autonomo resta come documento storico; questa integrazione porta la saggistica dentro NarrAI.

## Esperienza

Ordine delle modalità: **Narrativa → Saggio → Fumetto**. Le tre scelte sono disponibili sulla biblioteca e nel selettore di creazione. Biblioteca, navigazione, notifiche e tema sono comuni; ogni opera conserva il percorso editoriale appropriato. Crea e Narrativa aprono un nuovo progetto; la ripresa di una bozza è esplicita dalla biblioteca, tramite `?session=…`.

Il saggio mantiene i tre profili (argomentativo, divulgativo, accademico) e i tre ruoli AI indipendenti. Sono inclusi brief, domande, argomenti e fonti, piano approvato, indice, scrittura con pausa/ripresa, editor e storico, revisione delegabile, copertina, PDF/EPUB/DOCX e apparato delle citazioni. La navigazione protegge le modifiche non salvate nello studio e l'uscita dalla pagina.

L’ampiezza del saggio si sceglie in pagine: 60/140/240 oppure 4–480 personalizzate, equivalenti a 250 parole/pagina. I budget salvati restano compatibili. La previsione di pagine, costo e tempo è disponibile anche senza storico tramite ipotesi dichiarate; si aggiorna con lunghezza, modelli e percorso. Con almeno tre scritture comparabili e ininterrotte il tempo usa lo storico. Ricerca, fonti, correzioni, revisione separata e copertina AI sono aggiuntive. Metodo: [modelli e costi](MODELLI_E_COSTI.md).

La biblioteca combina le opere **prima** di filtrare, ordinare e paginare. La ricerca include titolo, autore, genere/profilo e tema del saggio. Una scheda comune offre Leggi, Apri studio, export e rimozione per ogni formato. Copertina e titolo aprono il lettore. Anche opere incomplete sono leggibili; la pagina indica che la lavorazione è in corso. L'eliminazione richiede conferma ed è disponibile dopo aver fermato i processi attivi. Standard/Ultra restano filtri della generazione.

Il lettore ha indice, dimensione del testo, navigazione da tastiera e segnalibro locale per ogni opera. Narrativa e saggi mostrano il testo salvato, i saggi includono la bibliografia, i fumetti mostrano le tavole pronte nell'ordine corretto. La lettura non avvia generazioni di copertine o tavole.

### Fumetto

Il percorso `/comics` permette di scegliere **Manga** (azione/avventura, fantasy, romance, slice of life, mistero/thriller, fantascienza, horror, sport) o **Graphic Novel** (letterario, autobiografico, storico, noir/thriller, sociale/reportage, fantasy, fantascienza, avventura). Il pubblico editoriale giapponese è una scelta separata, mostrata solo per Manga. Formato e sottogenere guidano storyboard, tavole, copertina e retro: Graphic Novel non eredita obblighi di stile manga. Entrambi adottano una lettura da sinistra a destra per l'edizione italiana. I vecchi progetti restano Manga; le vecchie route conservano i link alle sessioni.

La pausa termina e salva la chiamata in corso, poi si ferma prima della successiva. La ripresa conserva tavole, piano e formato.

### Valuta e Analisi

Valuta accetta un PDF esterno oppure un'opera della biblioteca. I criteri cambiano con il formato: costruzione narrativa; tesi, ragioni, evidenze e limiti per il saggio; sequenza, leggibilità, disegno e continuità per il fumetto. Il critico legge anche le immagini del PDF. I risultati restano nella pagina; i consumi di un'opera interna sono registrati nel suo archivio. Un'opera attiva va prima messa in pausa.

Analisi usa `/api/works/analytics` e filtri per formato. Mostra opere completate, attive, in pausa e in preparazione; parole e capitoli dei testi; tavole dei fumetti, escludendo le copertine; idee per mese; consumi per fase e modello e opere recenti. I costi includono solo chiamate quantificabili del registro, con il cambio salvato per ciascuna. La copertura incompleta è esplicita; un costo sconosciuto non diventa zero. Le valutazioni di PDF esterni restano escluse dalle metriche delle opere.

## Carta e inchiostro

Palette quasi bianca e nera, tipografia leggibile, piccoli appunti manoscritti nei margini, illustrazioni SVG originali a tratto, cornici irregolari e sottolineature da matita. La stessa direzione si applica a creazione, biblioteca, moduli e studio dei saggi. Logo, splash e icone PWA sono coerenti.

Le illustrazioni si disegnano al passaggio del mouse e il caricamento richiama una matita. La preferenza del sistema per movimento ridotto disattiva questi effetti. **Impostazioni → Suoni di scrittura** attiva piccoli fruscii sintetizzati localmente con Web Audio. I suoni sono disattivati per impostazione predefinita; la scelta viene ricordata sul dispositivo. Nessun file audio remoto è richiesto. Favicon, icone di installazione e logo usano la stessa penna a inchiostro.

## Backend e compatibilità

L’integrazione conserva il motore saggistico e le relative regressioni del branch `codex/saggistica`: generazione, evidenze, revisioni ed export. L’adapter API è stato reso montabile e i lookup sono isolati per contesto. Biblioteca, UI, branding e launcher autonomi sono stati adattati allo studio comune; i vecchi script di avvio/QA dedicati e il marchio SaggIA non sono necessari nel prodotto unificato. La cronologia del branch è integrata in `main`, che diventa la linea di sviluppo consolidata.

- Avvio unico: `app.main:app`, con API narrative esistenti, biblioteca comune `/api/works` e API saggi `/api/saggistica`.
- Database narrativo: `backend/narrai.sqlite3`, oppure `NARRAI_DB_PATH`.
- Archivio saggi: `backend/data/saggistica/saggia.sqlite3`, oppure la directory `SAGGIA_DATA_DIR`.
- Ogni job lega il proprio store al contesto asincrono. Scrittura e registro dei consumi rimangono corretti anche con richieste concorrenti e identificativi uguali nei due archivi.
- L'entry point autonomo `app.essay.main:app` resta compatibile per strumenti e test del motore SaggIA.

Gli archivi non sono forzati in uno schema comune: mantengono versioni, fonti, revisioni e riferimenti esistenti. L'unificazione avviene nell'esperienza e nel backend.

## Importazione SaggIA

Da `backend`, usando la stessa installazione Python dell'app:

```powershell
.venv/Scripts/python.exe ../scripts/import-saggia.py --source C:/percorso/SaggIA/backend/data/saggistica
```

La destinazione predefinita è `backend/data/saggistica`. È possibile specificare `--target` e configurare la stessa directory in `SAGGIA_DATA_DIR`. La destinazione deve essere vuota: il comando rifiuta di sostituire un archivio esistente.

L'importazione usa il backup SQLite consistente, copia fonti e copertine e aggiorna i percorsi assoluti nella copia. I processi in corso richiedono una ripresa esplicita, evitando generazioni duplicate. L'originale resta intatto.

L’importazione è verificata senza sovrascrivere archivi: capitoli, cronologia, fonti e copertine vengono conservati. Gli archivi personali e le copie di QA restano locali ed esclusi da Git.

## Avvio e verifica

I suoni hover sono limitati alle tre scelte di creazione, solo con mouse/puntatore fine e audio già sbloccato da una prima interazione. Il volume è inferiore al click; un intervallo di 450 ms limita le ripetizioni e il passaggio fra elementi della stessa scheda è ignorato. L’impostazione generale dei suoni li disabilita insieme agli altri effetti audio.

Su Windows, `avvia.cmd` è l’unico launcher e avvia NarrAI con tutte le modalità. Il precedente alias e il collegamento SaggIA sono stati rimossi. L’avvio manuale continua a usare FastAPI sulla porta 8000 e Vite sulla 5173. La build frontend viene servita anche dal backend.

Verifiche: **270 test backend e 104 test frontend**, TypeScript e build PWA completati. I test coprono biblioteca combinata, paginazione, API coesistenti, consumi concorrenti, importazione senza sovrascrittura, creazione senza ripresa implicita, azioni condivise, formati e prompt dei fumetti, pausa tra chiamate, lettura senza generazione, valutazione per formato e metriche con costi mancanti. Le nuove regressioni verificano pagine e compatibilità dei budget, previsioni senza creazione di job/consumi, aggiornamento con modelli/percorso, risposte fuori ordine, errori di rete e suoni hover solo dopo interazione. La verifica nel browser usa opere esistenti e form non inviati, senza avviare chiamate AI a pagamento. La CI esegue gli stessi controlli con Python 3.11 e Node 22; i test frontend limitano i worker a due. La build conserva il warning non bloccante sulla banca dati Browserslist datata.

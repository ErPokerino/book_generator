# Funzionalità di NarrAI

NarrAI è uno studio locale per creare libri e manga. Le opere vengono salvate sul dispositivo; la generazione e la valutazione usano servizi AI online. Non sono richiesti login o crediti interni all'app.

## Creare un libro

Il percorso visibile è **Idea → Domande → Bozza → Struttura → Scrittura**.

- **Idea:** trama obbligatoria, genere, stile, pubblico e ampiezza facoltativi. La pagina mostra sempre modalità di scrittura e previsione. Personaggi e conflitto, voce e struttura, firma e copertina sono pannelli espandibili coerenti con Modelli AI. I modelli si scelgono con menu compatti e la personalizzazione per fase è facoltativa. **Continua con le domande** rende esplicito il passaggio successivo.
- **Domande:** chiarimenti generati a partire dal brief, con possibilità di proseguire secondo i comandi disponibili nel wizard.
- **Bozza:** lettura e modifica del piano narrativo, anche con feedback in chat. La validazione approva il piano prima della scrittura.
- **Struttura:** controllo e modifica dell'outline. I capitoli sono ricavati dai titoli Markdown; prologo ed epilogo autonomi vengono conservati. Le modifiche dell'indice sono soggette ai vincoli dello stato di scrittura.
- **Scrittura:** apre lo studio con indice, manoscritto e taccuino. Il testo è leggibile appena salvato; il taccuino raccoglie fatti con prove, revisioni e consumi. Dopo i capitoli seguono copertina e valutazione critica.

Le modalità Standard e Ultra controllano il modo di generare i capitoli; Ultra usa due parti sequenziali. Questo non costituisce di per sé una revisione editoriale o una garanzia di qualità superiore. I valori precisi e i modelli per fase sono descritti dalla configurazione e da [MODELLI_E_COSTI.md](MODELLI_E_COSTI.md).

La previsione di pagine e costo parte dai libri completati della modalità scelta, con numero di campioni e fascia di variabilità. Non usa più 100 pagine per entrambe le modalità. Senza storico compare uno stato esplicito; il primo libro può essere creato normalmente. L'ampiezza scelta aggiorna la previsione; l'importo resta distinto dai consumi effettivi riportati nello studio.

## Interruzioni e ripresa

La chiusura della pagina non cancella la sessione. Il lavoro dipende dal backend: quando viene riavviato, recupera automaticamente i job interrotti. **Pausa dopo il capitolo** salva il testo e il controllo di continuità prima di fermarsi; **Riprendi scrittura** prosegue dal checkpoint.

I libri sospesi possono essere ripresi. La ripresa usa i capitoli già salvati e ricomincia dal primo assente, evitando di spendere nuovamente per l'ultimo capitolo persistito prima di un crash. Gli errori inattesi mantengono il checkpoint e una possibilità di recupero. Un avvio ordinario non sostituisce i capitoli di un progetto già scritto.

Un problema di rete è distinto da un archivio vuoto. Nella libreria, **Riprova** ricarica i dati; il polling tollera errori transitori con attese crescenti. Nessuna risposta API viene recuperata da una vecchia cache offline per simulare un avanzamento.

## Libreria e lettura

**Apri studio** consente di leggere, modificare e confrontare versioni del manoscritto. Ogni salvataggio conserva una revisione; una versione precedente può essere portata nell'editor e salvata dopo la lettura. L'interfaccia protegge le modifiche non salvate durante la navigazione e conserva il testo se il server segnala un conflitto. Durante la generazione l'editor è in sola lettura. Su mobile indice, manoscritto e taccuino sono pannelli selezionabili.

I fatti mostrano la citazione che li sostiene. **Aggiorna memoria** analizza i capitoli non ancora controllati dopo una modifica; una contraddizione residua viene mostrata con la prova e richiede revisione. L'analisi usa il modello e concorre ai consumi. Le revisioni manuali invalidano PDF e critica precedenti.

La sezione **Opere** raccoglie libri e manga. Sono disponibili ricerca, filtri per stato/modalità/genere, ordinamento e caricamento progressivo. Le azioni dipendono dallo stato: continuare la preparazione, monitorare o riprendere la scrittura, leggere, valutare ed esportare.

Il lettore presenta copertina, indice, capitoli, regolazione della dimensione del testo e navigazione. Il contenuto narrativo è reso come Markdown, senza interpretare HTML eseguibile. Il lettore audio opzionale viene reimpostato al cambio del capitolo.

L'eliminazione rimuove il progetto e i file esplicitamente associati, se accessibili e non condivisi. Non è disponibile mentre è rilevata una generazione attiva. I file legacy senza un'associazione verificabile non vengono eliminati per somiglianza del titolo. È stato rimosso il vecchio cleanup automatico che considerava obsoleta qualsiasi opera priva di voto: poteva includere progetti validi e bozze.

## Export

I libri completi possono essere scaricati in **PDF, EPUB e DOCX**. Tutte le route PDF del libro usano lo stesso generatore. I PDF nuovi hanno nomi distinti per sessione e vengono associati al progetto; i download supportano titoli Unicode.

Il conteggio di pagine mostrato durante la scrittura è una stima basata sulle parole. Non coincide necessariamente con il numero di pagine dell'export. Il controllo editoriale e tipografico finale resta necessario per una pubblicazione.

## Valutazione e analisi

La critica AI riporta un voto, punti di forza, limiti e una sintesi. Il fallimento della critica è distinto dal completamento dei capitoli e può essere ritentato. La sezione **Valuta** permette anche l'analisi di un PDF esterno.

La sezione **Analisi** raccoglie statistiche locali su opere, tempi, pagine, costi stimati e voti. Un confronto fra medie di libri diversi non è un esperimento controllato sui modelli. Il voto del critico non misura da solo coerenza, originalità o soddisfazione del lettore.

## Manga e audio

Il manga beta usa un brief dedicato, pianificazione, tavole e copertine, con progressi e ripresa propri. La gestione dei file e degli export è separata da quella dei capitoli testuali. La disponibilità dell'audio dipende dalla configurazione del servizio TTS.

## Dati e requisiti

L'archivio principale è `backend/narrai.sqlite3`, con immagini e documenti nelle directory indicate dalla [documentazione tecnica](TECNICA.md). Il JSON precedente viene importato una volta e conservato. Se l'archivio da importare non è leggibile, il sistema interrompe la migrazione senza perdere l'originale.

I dati trasmessi alla generazione comprendono il brief e il contesto necessario al modello. Per eseguire il progetto e configurare le credenziali vedi il [README](../README.md). Le prime tre [priorità di evoluzione](REVISIONE_2026-09-20.md) sono ora implementate: dettagli e limiti nelle [note delle evolutive](EVOLUTIVE_2026-09-20.md).

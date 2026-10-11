# Funzionalità di NarrAI

Aggiornamento: 11 ottobre 2026. NarrAI è uno studio locale per **Narrativa, Saggio e Fumetto**. Le opere restano sul dispositivo; generazione, ricerca e valutazione usano servizi AI online. Non sono richiesti login o crediti interni.

## Un solo spazio di lavoro

La biblioteca si apre su `/library`. Le tre modalità compaiono nell’ordine Narrativa → Saggio → Fumetto, anche nel selettore di creazione. **Crea adesso** e **Narrativa** iniziano un progetto nuovo. Si riprende un progetto dalla sua scheda: una vecchia sessione non viene aperta implicitamente.

L’interfaccia usa carta chiara, inchiostro nero, illustrazioni a tratto e piccoli dettagli manoscritti. Navigazione, moduli, biblioteca e strumenti di analisi condividono lo stile. Logo, favicon e icone di installazione usano la stessa penna.

## Narrativa

Il percorso è **Idea → Domande → Bozza → Struttura → Scrittura**.

- **Idea:** trama obbligatoria; genere, pubblico, voce, ampiezza, personaggi e firma personalizzabili. Le opzioni avanzate si espandono quando servono.
- **Domande:** chiarimenti generati dal brief e risposte dell’autore.
- **Bozza:** piano narrativo leggibile e modificabile, anche tramite feedback. La validazione approva la direzione.
- **Struttura:** indice e capitoli; prologo ed epilogo autonomi sono conservati. Gli interventi rispettano i vincoli dei capitoli già scritti.
- **Scrittura:** studio con indice, manoscritto e taccuino; i capitoli sono leggibili appena salvati. Seguono copertina ed eventuale critica.

Standard scrive ogni capitolo in una parte; Ultra usa due parti consecutive. Entrambi usano memoria narrativa e controlli di continuità. La modalità non garantisce, da sola, qualità superiore.

La previsione di pagine usa i libri completati della stessa modalità, con numero di campioni e fascia di variabilità. Modello e ampiezza restringono lo storico quando sufficiente. Senza storico pagine, costo e tempo restano indisponibili, ma si può iniziare il primo libro.

Lo studio consente di modificare il testo e consultarne le revisioni. Una versione precedente può essere riportata nell’editor e salvata. I fatti della memoria riportano prove testuali; **Aggiorna memoria** usa l’AI e contribuisce ai consumi. Una contraddizione persistente ferma la scrittura. Le modifiche invalidano gli export e la critica dipendenti.

## Saggio

Il percorso comprende **Brief → Domande → Argomenti e fonti → Piano e indice → Manoscritto → Revisione**. Tipo di saggio e ruolo dell’AI sono indipendenti:

| Tipo | Obiettivo |
| --- | --- |
| Argomentativo | Sostenere una posizione, affrontando ragioni, obiezioni e limiti |
| Divulgativo | Spiegare concetti e confrontare interpretazioni |
| Accademico | Domanda di ricerca, metodo, corpus e apparato documentale |

L’AI può **sviluppare e mettere alla prova**, **sostenere la posizione** oppure **esplorare con l’autore**. Dopo l’approvazione del piano rispetta la direzione scelta. Il pubblico è adulto. Il profilo accademico non autorizza a inventare studi, interviste o risultati.

La lunghezza si sceglie in **pagine**: breve 60, medio 140, ampio 240; personalizzata da 4 a 480. Sono pagine di testo equivalenti, a circa 250 parole per pagina. L’impaginazione PDF e il testo effettivo possono variare. I budget dei progetti esistenti rimangono compatibili.

Il riquadro di previsione mostra pagine, costo e tempo indicativi e si aggiorna con ampiezza, modelli e percorso. È disponibile anche per il primo saggio, usando ipotesi esplicite sui token e sulle chiamate. Con almeno tre scritture comparabili e ininterrotte il tempo usa la durata mediana per parola dello storico. Include domande, progetto e scrittura, con controllo dei capitoli se scelto; ricerca, fonti, correzioni, revisione separata e copertina AI sono aggiuntive. La copertina tipografica è locale. La fascia di costo è indicativa e non è un tetto di spesa.

Le fonti possono provenire dalla ricerca web, da URL pubblici, documenti PDF/DOCX/TXT/Markdown o appunti dell’autore. La ricerca individua materiali: un riassunto del motore di ricerca non diventa una prova. Gli estratti citabili devono corrispondere al testo acquisito. Dati bibliografici ed evidenze sono modificabili; un materiale può essere escluso o acquisito nuovamente.

Il piano alloca il budget, definisce argomenti, obiezioni, evidenze, sezioni e limiti. Serve l’approvazione della versione corrente prima di scrivere. Una modifica di direzione invalida l’approvazione; i soli cambi di risorse non alterano la direzione. Dopo la scrittura si conservano ordine e identificativi dei capitoli.

La scrittura può includere il controllo dei capitoli oppure lasciare la revisione a una fase separata. La revisione del saggio produce rilievi localizzati; le correzioni possono essere delegate all’AI, con cronologia e checkpoint. Non è una certificazione di verità. Editor e dati bibliografici proteggono dalle sovrascritture concorrenti e conservano le bozze locali quando il salvataggio fallisce.

Autore, titolo, sottotitolo e retro sono modificabili senza cambiare l’argomentazione. Il titolo automatico è breve; i dettagli appartengono al sottotitolo. Citazioni numeriche o autore/data e bibliografia sono condivise da lettura ed export, senza promettere conformità a uno specifico manuale bibliografico.

## Fumetto: Manga e Graphic Novel

`/comics` offre due formati, entrambi in beta, con sottogeneri distinti:

| Manga | Graphic Novel |
| --- | --- |
| Azione/avventura, fantasy, romance, slice of life, mistero/thriller, fantascienza, horror, sport | Letterario, autobiografico, storico, noir/thriller, sociale/reportage, fantasy, fantascienza, avventura |

Il pubblico editoriale giapponese è una scelta aggiuntiva solo per Manga. Formato e sottogenere guidano storyboard, tavole, copertina e retro; una Graphic Novel non riceve istruzioni obbligatorie da manga. Le tavole sono da sinistra a destra per l’edizione italiana. I vecchi progetti conservano il formato Manga.

Si scelgono da 10 a 100 tavole. La previsione considera pianificazione, immagini e copertine con ipotesi dichiarate. Il processo salva il piano e ogni tavola; la pausa conclude la chiamata in corso e si ferma prima della successiva. Si riprende conservando il materiale pronto. L’export principale è il PDF.

## Biblioteca e lettore

**Sul tuo tavolo** combina le tre modalità prima di ricerca, filtri, ordinamento e paginazione. Si cerca per titolo, autore, genere/profilo e tema; i filtri distinguono formato e stato. Standard/Ultra sono modalità narrative, non profili di saggio.

Ogni scheda offre azioni coerenti: **Leggi**, **Apri studio**, export disponibili ed eliminazione. Clic su copertina o titolo apre la lettura. Le opere incomplete sono leggibili e segnalano la lavorazione in corso. Una bozza priva di testo permette di tornare alla preparazione.

Il lettore comune ha indice, dimensione del testo, navigazione da tastiera e segnalibro locale per opera. I saggi includono la bibliografia; i fumetti mostrano le tavole pronte in ordine. Il testo Markdown non esegue HTML grezzo. Aprire il lettore non genera immagini né avvia chiamate AI.

L’eliminazione richiede conferma per tutti i formati. Con un processo attivo occorre prima fermarlo. Si rimuovono i file associati in modo verificabile, preservando quelli condivisi; i file storici senza associazione non vengono riconosciuti per somiglianza del titolo. L’eliminazione dell’opera non è un cestino recuperabile.

## Pausa, recupero e salvataggio

Chiudere una pagina non elimina il progetto e non equivale a interrompere il backend. Narrativa si ferma dopo il capitolo e i suoi controlli; saggi e fumetti rispettano i rispettivi checkpoint e chiamate in corso. Le pause volontarie e gli errori richiedono ripresa esplicita. I job interrotti da un arresto del server vengono recuperati al riavvio.

L’editor avvisa prima di lasciare modifiche non salvate. Durante i processi attivi le modifiche incompatibili sono bloccate. Errori di rete si distinguono dall’archivio vuoto e offrono **Riprova**; una risposta vecchia non sostituisce le nuove scelte.

## Export e audio

Narrativa e saggi supportano **PDF, EPUB e DOCX**; per i saggi sono disponibili anche versioni di lavoro. Il PDF del saggio comprende frontespizio, indice, riferimenti, bibliografia e retro. I fumetti hanno PDF con tavole e copertine. Le pagine di testo previste e le pagine fisiche del PDF sono misure diverse.

L’audio narrativo opzionale usa Gemini TTS con la stessa chiave API; è un servizio distinto dai suoni dell’interfaccia e contribuisce ai consumi. Non è un audiolibro universale per tutte le modalità.

## Valuta e Analisi

**Valuta** accetta un PDF esterno, per cui si sceglie il tipo, oppure un’opera della biblioteca. La rubrica cambia: costruzione narrativa; tesi, evidenze e limiti; sequenza, leggibilità e continuità visiva del fumetto. Il critico legge anche le immagini del PDF. Un’opera attiva va prima fermata.

I risultati della valutazione trasversale restano nella pagina. Le chiamate su opere interne entrano nel loro registro dei consumi; i PDF esterni non entrano nell’archivio o nelle metriche delle opere. Il voto non misura automaticamente verità, originalità o soddisfazione del lettore.

**Analisi** offre filtri per formato e mostra opere completate/attive/in pausa/in preparazione, parole e capitoli testuali, tavole completate dei fumetti, creazioni per mese, consumi per fase e modello e opere recenti. Le copertine non contano come tavole. Non presenta medie di voti o tempi come confronti scientifici fra modelli.

I costi sono il subtotale quantificabile del registro, al cambio conservato per richiesta. La copertura incompleta è dichiarata: un dato sconosciuto non è zero. Le cifre non sono la fattura dell’account Google.

## Impostazioni e dati

**Impostazioni → Suoni di scrittura** abilita carta e matita sintetizzate localmente. Sono spenti per default; la preferenza resta sul dispositivo. Dopo una prima interazione, il mouse può produrre un fruscio lieve sulle tre scelte di creazione, con limitazione delle ripetizioni. Il touch e il passaggio tra elementi della stessa scheda non lo attivano. Gli effetti visivi rispettano il movimento ridotto del sistema.

Narrativa e fumetti usano l’archivio principale SQLite; i saggi mantengono un archivio compatibile con SaggIA. Nessuno dei due database è incluso in Git. Per avvio, importazione, backup e limiti consultare [README](../README.md), [tecnica](TECNICA.md) e [operazioni](OPERAZIONI.md).

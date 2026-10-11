# SaggIA — implementazione e verifiche

> Cronologia della versione autonoma, conservata per le verifiche del motore. Dall’11 ottobre 2026 il motore è integrato in NarrAI: avvio unico `app.main:app`, UI condivisa, API `/api/saggistica`, biblioteca/lettore/Valuta/Analisi trasversali. L’ampiezza si imposta in pagine e il modulo mostra la previsione di pagine, costo e tempo. I riferimenti alle porte 5174/8001, ai launcher autonomi e ai test sotto descrivono la versione storica. Guide correnti: [studio unificato](NARRAI_UNIFICATO.md) e [operazioni](OPERAZIONI.md).

Branch: codex/saggistica. Base: main, f95b493. Data: 6 ottobre 2026.

La linea di prodotto è implementata in un worktree autonomo. Le modifiche preesistenti nel checkout NarrAI sono preservate. L'applicazione usa le porte 5174/8001 e un archivio proprio; NarrAI continua a rispondere sulla porta 5173.

## Risultato funzionale

Sono selezionabili tutti e tre i profili editoriali e tutti e tre i ruoli dell'AI, in combinazioni indipendenti. Sono sostituiti i campi narrativi con tema, domanda, tesi, premesse, ragioni, lettore adulto, metodo, corpus, perimetro, voce e registro. Il cambio di profilo aggiorna i default non personalizzati; ogni nuova direzione richiede approvazione.

Il percorso attivo comprende progetto, domande, argomenti/fonti, indice, manoscritto e revisione. Copertina ed esportazioni sono nello studio finale. Il piano è modificabile, comprese obiezioni, evidenze e struttura. Dopo la scrittura, l'ordine e gli identificativi dei capitoli restano vincolati per conservarne lo storico.

La ricerca usa Google Search attraverso il servizio Gemini. Sono registrate soltanto le fonti presenti nei metadati di grounding del provider. I documenti vengono acquisiti tramite richieste HTTP separate; non si trasformano riassunti di ricerca in evidenze. Gli estratti devono corrispondere al testo realmente acquisito.

Sono implementati importazione PDF/DOCX/TXT/Markdown, appunti dell'autore, localizzatori, dati bibliografici modificabili, esclusione e nuovo tentativo di acquisizione. I marcatori delle citazioni hanno identificativi stabili; anteprima e tre export condividono lo stesso ordinamento e bibliografia.

L'editor conserva bozze locali, impedisce sovrascritture concorrenti e registra revisioni nel database. Le modifiche invalidano i controlli dipendenti. Una parte incompleta incompatibile con un nuovo piano viene archiviata internamente e rimossa dal checkpoint attivo, evitando di mescolare due direzioni.

I job sono persistenti, con lease e inserimento atomico. La ripresa conserva capitoli e parti già salvati; la ricerca conserva la fase di scoperta già pagata. I tentativi di correzione sono limitati e le risposte non valide vengono rifiutate.

## Organizzazione effettiva

| Area | File attivi |
| --- | --- |
| Contratti, profili e ruoli | backend/app/essay/models.py, config/essay.yaml |
| API e archivio isolato | backend/app/essay/main.py, store.py |
| Fonti e riferimenti | sources.py, citations.py |
| Domande, piano, writer e revisione | prompts.py, generation.py |
| Copertina e tre export | cover.py, exports.py |
| Interfaccia e impostazioni | frontend/src/essay/ |
| Avvio locale | avvia-saggia.cmd, scripts/avvia-saggia.ps1 |
| Test e prova reale | backend/tests/test_essay_product.py, frontend/src/essay/essay.test.tsx, GenerationProgress.test.tsx, scripts/verifica-saggia.py |

Sono riutilizzati il motore SQLite per transazioni/revisioni, il worker durevole, il registro dei consumi e il controllo di corrispondenza degli estratti. Il codice di dominio narrativo precedente non viene chiamato dal flusso SaggIA. Restano nel repository componenti storici e test per verificare la compatibilità dell'infrastruttura.

## Verifiche completate

- 218 test backend: 131 dell'infrastruttura precedente e 87 SaggIA.
- 78 test frontend: 31 precedenti e 47 SaggIA. Verificate le nove combinazioni di profilo/ruolo, i default, le bozze, i conflitti, i riferimenti e i dati bibliografici.
- TypeScript senza errori; build Vite/PWA completata.
- Prova reale con Gemini 3.8 Flash: creazione nel browser, domande, ricerca web, analisi, piano, approvazione, tre capitoli, revisione, copertina e tre export.
- Prove reali con profilo divulgativo/ruolo esplorativo (Gemini 3.5 Flash Lite) e profilo accademico/ruolo di sostegno (Gemini 3.8 Flash): domande, upload di materiali dell'autore, evidenze e piano coerente.
- Prova nel browser dell'editor, dello storico, dei dati bibliografici, della nuova approvazione e della revisione dopo una modifica.
- Verifica responsive a 390 px e alla larghezza ordinaria del pannello.
- Rendering e ispezione visiva del PDF; verifica testuale dei riferimenti e apertura strutturale di EPUB/DOCX. Verificati anche titoli lunghi e copertine nei tre formati.
- Avvio/riuso dei servizi con il launcher, health check dedicato e navigazione diretta alla build.

La prova iniziale ha usato un libro dimostrativo chiamato “Esempio verificato · Biblioteche e confronto”: tre capitoli, circa mille parole, sei fonti individuate, venti estratti disponibili e ventidue citazioni. I progetti temporanei degli altri due profili sono stati rimossi dopo averne salvato gli esiti tecnici nella directory QA esclusa da Git.

## Difetti trovati e corretti

Gemini rifiutava additionalProperties nello schema nativo: il contratto inviato al provider viene compattato, mantenendo i vincoli Pydantic locali. Un riferimento malformato nella prova reale ha mostrato la necessità di una correzione limitata prima del salvataggio. Sono stati inoltre corretti perdita dei campi dopo un'importazione fallita, sovrascrittura concorrente dei metadati, preparazione/accodamento dei job non atomica, ricompra di una ricerca durante il recupero, contesto che escludeva evidenze assegnate tardive, layout sui tablet, copertina PDF troppo grande e limite di 255 caratteri nei metadati DOCX.

## Limiti della prima versione

La ricerca non aggira accessi riservati e non legge scansioni prive di testo. I file sono limitati a 12 MB e il testo a 250.000 caratteri per fonte. Le citazioni sono numeriche oppure autore/data, senza dichiarare conformità a un particolare manuale bibliografico.

Il rapporto valuta uso delle evidenze e struttura argomentativa; non certifica la verità del libro. Gli export sono disponibili anche come versioni di lavoro. Il limite di spesa controlla i consumi misurati tra richieste; non costituisce una garanzia di fattura e non include eventuali tariffe di ricerca non determinabili dal provider.

La lunghezza è un obiettivo editoriale: nel piano viene allocata esattamente, mentre il testo effettivo può variare. Il writer conserva i checkpoint e rifiuta risposte troppo brevi.

La libreria offre ricerca per titolo/tema e filtro per profilo. Dashboard statistiche per disciplina, stime predittive senza storico, OCR, connettori bibliografici avanzati, collaborazione e pubblicazione esterna restano evoluzioni successive. La copertina tipografica è stata verificata con il servizio reale; le varianti con sfondo AI usano l'integrazione immagini ereditata, senza una prova live di generazione in questo intervento.

## Rifinitura dei titoli e dell'avanzamento

I titoli dello studio hanno una dimensione più contenuta su desktop e mobile; prima che esista un titolo editoriale, il tema usa un carattere ancora più compatto, mantenendo il testo completo.

Il pannello distingue il capitolo in lavorazione, i capitoli completati e il passaggio di scrittura interno al capitolo. I passaggi producono porzioni di testo mediante richieste AI, poi riunite. In modalità con revisione automatica, il capitolo diventa completo dopo i controlli; la revisione ha uno stato dedicato e può richiedere altre chiamate. Il contatore descrive i passaggi editoriali, non il numero totale di chiamate fatturate.

Undici test di regressione coprono numerazione, revisione, ripresa in coda, recupero, transizioni tra capitoli, fine della scrittura, modalità senza revisione, pausa e altri processi. TypeScript, 59 test frontend e build sono passati. Verificati nel browser il titolo del progetto reale e una simulazione locale di scrittura/revisione/ripresa, anche a 390 px, senza generare nuovi testi o modificare il manoscritto dell'autore.


## Gestione delle opere e nuova edizione PDF (7 ottobre 2026)

Le schede di Opere mostrano pagine del PDF, costo di generazione in euro, parole e data di aggiornamento. Per un processo attivo resta la stima delle pagine; senza richieste AI non viene inventato un prezzo. La copertura dei consumi è condivisa con il registro dello studio e i totali incompleti sono esplicitamente parziali.

L'eliminazione è disponibile direttamente sulla scheda, con dialogo di conferma, annullamento ed errore recuperabile. Durante i processi è disabilitata; l'API continua a proteggere la concorrenza. La conferma riuscita rimuove solo il libro selezionato e le sue bozze locali.

Il PDF usa un'impaginazione A5 con font serif incorporati quando disponibili, frontespizio adattivo, aperture dei capitoli, testatine alternate, foliazione del testo e indice con numeri di pagina e collegamenti interni. Mantiene grassetti, corsivi, citazioni, elenchi annidati e tabelle anche su più pagine. I sottotitoli restano con le prime righe del paragrafo, evitando grandi vuoti. Fonti e riferimenti conservano il registro canonico degli altri export.

Una cache limitata a otto edizioni evita di impaginare nuovamente ogni richiesta della biblioteca: testo, riferimenti, metadati e aggiornamento della copertina invalidano il risultato. Il numero delle pagine in Opere è quello dello stesso PDF scaricabile.

Sono passati 188 test backend, 68 frontend, TypeScript e build. Verificati annullamento, errore concorrente, doppia richiesta, rimozione selettiva e gestione dei costi assenti/parziali; layout della biblioteca a 390 px e 1280 px. Il saggio esistente è stato esportato in 67 pagine, renderizzate e ispezionate; verificati separatamente titoli/sottotitoli/autori lunghi, elenchi, tabelle, simboli, citazioni e navigazione. Il download dall'API conferma 67 pagine e sette voci di indice.


## Autore, quarta di copertina e titoli sintetici (7 ottobre 2026)

Il nome autore è visibile nel brief iniziale. In Progetto e Revisione, il pannello “Autore, titolo e retro” modifica firma, titolo, sottotitolo e presentazione anche dopo la scrittura. Un endpoint dedicato con controllo di versione conserva approvazione, revisione, manoscritto e checkpoint. Il polling non sovrascrive le modifiche in corso; i salvataggi concorrenti lasciano recuperabile la bozza.

La copertina tipografica viene composta nuovamente al salvataggio senza costi AI. Gli sfondi illustrati delle nuove copertine sono conservati separatamente, così cambiare il nome non acquista un'altra immagine. Le vecchie copertine illustrate prive dello sfondo originale richiedono una rigenerazione esplicita. La pulizia del progetto comprende lo sfondo conservato.

Le nuove proposte AI preferiscono titoli di 2-6 parole, con massimo 8 parole/64 caratteri per il libro e 10 parole/85 caratteri per i capitoli. I dettagli vanno nel sottotitolo e nelle descrizioni dell'indice. La validazione locale rifiuta le proposte troppo lunghe e ammette un solo nuovo tentativo, senza troncare i titoli. I titoli scelti esplicitamente dall'autore e le modifiche manuali restano liberi.

Il progetto editoriale propone anche una presentazione di 80-140 parole per il retro, modificabile fino a 1500 caratteri. Il PDF termina con una quarta di copertina A5 coordinata nei colori e nei font, senza testatina o numero di pagina. EPUB e DOCX includono lo stesso testo alla fine. I libri precedenti usano la direzione editoriale come testo iniziale, senza chiamate AI aggiuntive. Il retro partecipa alla cache del PDF e al conteggio delle pagine in Opere.

Verificati 198 test backend e 71 frontend, TypeScript e build; prove dedicate a conflitti, blocco durante i job, conservazione della revisione, riuso degli sfondi, export finali, cache e correzione dei titoli. Ispezionate visivamente copertina con firma, retro e una prova con testi ai limiti di lunghezza. Pannello controllato a 390 px e 1280 px; nessuna modifica al nome o al titolo del manoscritto esistente.


## Delega completa degli interventi di revisione (7 ottobre 2026)

In Revisione, “Applica tutte le correzioni con l’AI” avvia un job durevole dedicato. Applica tutti i livelli di intervento ai capitoli interessati; quelli generali raggiungono tutti i capitoli. Conserva la direzione approvata e i riferimenti registrati. Il controllo locale rifiuta citazioni inesistenti e riduzioni sotto il 70% del testo, prima di sovrascrivere un capitolo.

Dopo le correzioni viene generata una nuova revisione del manoscritto. Se sono rimasti interventi e il testo è stato modificato, segue un secondo passaggio automatico. Il ciclo si ferma dopo due passaggi, oppure quando non ci sono cambiamenti; il risultato distingue i capitoli aggiornati dagli interventi ancora aperti. Le lacune che richiedono altre fonti non diventano prove inventate.

Rapporto letto, versione e hash dei capitoli vengono verificati nell'accodamento atomico. Un doppio clic non crea un secondo job, e durante il lavoro le modifiche manuali sono bloccate. Ogni capitolo corretto e la ricevuta di avanzamento vengono salvati nella stessa transazione, preservando le versioni originali nell'editor. La nuova revisione salva anche i gruppi già verificati: “Riprendi le correzioni AI” evita di ricomprare capitoli e verifiche salvati dopo un guasto o un riavvio.

Il limite di spesa vale anche per correzioni e controlli. Modificare soltanto budget o modelli conserva l'approvazione e il checkpoint; lo stesso vale per i dati di pubblicazione. Modifiche editoriali, fonti e revisioni manuali invalidano il piano di correzioni precedente.

Verificati 218 test backend e 78 frontend, TypeScript e build. Venti regressioni backend coprono concorrenza, idempotenza, interventi generali, riferimenti, versioni, limite di due passaggi, testi invariati, ripresa dopo rete/annullamento, verifica a gruppi e budget. Sette test frontend coprono delega, stato, blocchi, ripresa ed esito. Verifica nel browser su un archivio QA isolato e risposte di modello simulate: accodamento, correzione reale del testo salvato, nuovo rapporto senza interventi e storico recuperabile. Nessuna correzione è stata avviata sul manoscritto dell'autore durante il collaudo.


## Riferimenti ai capitoli nella revisione (7 ottobre 2026)

Il controllo finale del manoscritto viene suddiviso in gruppi di massimo 90.000 caratteri. Il modello riceveva l'indice completo ma poteva indicare qualsiasi section_id: il controllo locale rifiutava anche un riferimento a un capitolo reale esterno al gruppo, con il messaggio fuorviante “capitolo inesistente”. La validazione semantica era inoltre esterna ai tentativi di riparazione.

Ogni richiesta di revisione ora espone gli identificativi effettivamente esaminabili e li vincola nello schema inviato a Gemini. L'indice resta contesto editoriale; il prompt chiarisce che i capitoli non forniti non sono mancanti. I problemi generali usano un identificativo dedicato, non vuoto e senza collisioni con i capitoli, convertito nel section_id vuoto del contratto salvato. Gemini rifiuta valori vuoti negli enum, come verificato nella prova reale.

Un riferimento non valido o una citazione non presente produce un solo tentativo di riparazione, con errore e rapporto precedente. Le osservazioni valide devono essere conservate; non vengono scartati automaticamente interventi, né spostati su altri capitoli. Se la riparazione resta invalida, il checkpoint conserva i risultati già salvati e l'errore identifica il gruppo ammesso.

La ripresa del controllo ricostruisce anche il numero del passaggio e i capitoli aggiornati dal checkpoint, evitando contatori azzerati. Dieci test aggiuntivi coprono schema SDK, identificativi fuori gruppo/inventati/titoli, citazioni nel capitolo sbagliato, tentativo limitato, problemi generali, collisioni e ripresa del secondo passaggio senza riscritture. Suite backend: 228 test superati; frontend non modificato.

Prova reale sul progetto “Le nuove destre radicali”: ripreso esclusivamente il controllo finale del secondo passaggio; entrambi i gruppi verificati e ciclo completato. Tutti i cinque hash dei capitoli coincidono con quelli precedenti alla ripresa. Il nuovo rapporto conserva sei interventi editoriali (tutti riferiti a capitoli esistenti o al manoscritto nel suo insieme); nessun testo è stato riscritto durante il recupero.

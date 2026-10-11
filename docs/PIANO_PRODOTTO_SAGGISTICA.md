# Piano del prodotto per la scrittura di saggi

> Piano storico del 6 ottobre 2026. Implementato successivamente in SaggIA e integrato in NarrAI l’11 ottobre: la saggistica è ora una delle tre modalità dello stesso prodotto. La scelta originaria di un’app autonoma è superata; profili, ruoli e requisiti documentali restano alla base del motore. Stato attuale: [funzionale](FUNZIONALE.md), [tecnica](TECNICA.md), [studio unificato](NARRAI_UNIFICATO.md).

Data: 6 ottobre 2026. Branch proposto: `codex/saggistica`.

Stato alla stesura originaria: pianificazione, senza implementazione. Analisi basata su `main` al commit `f95b493`, prima della creazione del branch di prodotto. Le modifiche preesistenti a `frontend/vite.config.ts`, `avvia.cmd` e `scripts/` erano fuori dal perimetro di quel piano.

## 1. Obiettivo e decisioni

Creare un prodotto autonomo, derivato da NarrAI, per accompagnare un autore adulto dall'idea a un libro di saggistica. Il nucleo del progetto è una tesi sostenuta da ragioni, esempi, evidenze e confronto con obiezioni. Il risultato deve poter avere una voce personale e una posizione riconoscibile.

Il motore deve distinguere quattro elementi: ciò che l'autore sostiene, ciò che assume, ciò che deduce e ciò che documenta con fonti. Una posizione persuasiva non deve diventare automaticamente un fatto verificato.

| Decisione | Stato |
| --- | --- |
| Prodotto distinto, ispirato all'esperienza di NarrAI | Richiesta dell'utente |
| Saggio basato su tesi, opinioni e argomentazioni | Richiesta dell'utente |
| Pubblico esclusivamente adulto | Richiesta dell'utente |
| Tre profili selezionabili: argomentativo, divulgativo e accademico | Confermato dall'utente; tutti nella prima versione |
| Fonti: ricerca web e materiali dell'autore, tracciabili | Confermato dall'utente |
| Ruolo dell'AI selezionabile dall'autore | Confermato dall'utente; tre modalità descritte sotto |
| Nome di lavoro: SaggIA | Segnaposto editoriale, da scegliere successivamente |
| Lingua iniziale: italiano; applicazione locale e single-user | Proposta coerente con NarrAI |

Il prodotto deve poter trattare discipline diverse. I tre profili usano lo stesso motore, con contratti, istruzioni, impostazioni predefinite e criteri di revisione coerenti con il profilo scelto. La selezione non può limitarsi a cambiare il testo di un prompt.

### Profili editoriali selezionabili

| Profilo | Obiettivo | Impostazioni e revisione specifiche |
| --- | --- | --- |
| Argomentativo | Sostenere una posizione riconoscibile con ragioni, esempi ed evidenze | Tesi esplicita, premesse, progressione delle ragioni, obiezioni forti, limiti e implicazioni; voce anche personale |
| Divulgativo | Rendere comprensibile un tema e confrontare le interpretazioni rilevanti | Domanda guida, concetti e termini spiegati, esempi, sintesi delle evidenze, confronto delle letture; non imporre una posizione polemica |
| Accademico | Esaminare una domanda di ricerca con metodo e apparato documentale espliciti | Stato della questione, domanda/ipotesi, metodo dichiarato, corpus o materiali, criteri di selezione delle fonti, analisi, discussione e limiti; citazioni formali |

Il profilo accademico non deve inventare una ricerca svolta, un campione, interviste o risultati sperimentali. Il metodo può essere, per esempio, analisi concettuale, ricostruzione storica o analisi della letteratura; eventuali risultati empirici devono provenire dai materiali acquisiti. Un'ipotesi può risultare non sostenuta e le conclusioni devono poterlo dichiarare.

Default proposto: argomentativo. La disciplina, l'approccio critico/comparativo e il registro restano impostazioni distinte dal profilo. Un saggio accademico può essere storico e comparativo; un saggio divulgativo può riguardare un tema tecnico.

### Ruolo dell'AI selezionabile

| Modalità | Comportamento dell'AI | Controllo dell'autore |
| --- | --- | --- |
| Sviluppa e metti alla prova | Rafforza l'argomentazione, esamina obiezioni e propone precisazioni o alternative quando utili | Cambi sostanziali alla tesi restano proposte da approvare; default suggerito |
| Sostieni la mia posizione | Lavora sulla tesi scelta, segnala debolezze e lacune senza proporre una posizione alternativa | La tesi resta il vincolo editoriale; prove mancanti o contrarie restano visibili |
| Esplora con me | Confronta posizioni o ipotesi concorrenti e aiuta a scegliere l'impostazione | Prima della scrittura estesa l'autore approva una direzione, anche comparativa o aperta |

Profilo editoriale e ruolo dell'AI sono due selezioni indipendenti, salvate nel progetto e modificabili. L'esplorazione non autorizza l'AI a cambiare autonomamente la tesi di un capitolo già approvato. Nessuna modalità autorizza l'invenzione di prove o l'occultamento delle lacune.

## 2. Strategia del branch e separazione del prodotto

Partire dal commit di `main` effettivamente verificato all'inizio dell'implementazione, registrandolo nel piano. Usare `codex/saggistica` come branch di sviluppo del nuovo prodotto, in un checkout separato quando si passa all'implementazione. Il piano non richiede un push o una pubblicazione.

Il branch è la linea di sviluppo di un prodotto autonomo. Riutilizzare le infrastrutture esistenti e sostituire il dominio narrativo senza introdurre adesso un framework generico per molti prodotti. Un eventuale nucleo condiviso tra repository sarà una decisione successiva, motivata dalla manutenzione reale.

La separazione deve riguardare:

- Nome, navigazione, onboarding, manifest PWA, icone e metadati dei documenti.
- Database e directory di fonti, copertine, export e tracce. Prevedere una root dati dedicata, per esempio `backend/data/saggistica/`, con `product_id` e versione dello schema registrati nell'archivio.
- Variabili di avvio dedicate al prodotto, evitando che un `NARRAI_DB_PATH` ereditato indirizzi accidentalmente al database dei romanzi. Nessuna importazione automatica del vecchio `.sessions.json` di NarrAI.
- Chiavi di localStorage, sessioni e cache del service worker. In sviluppo, proporre frontend `5174` e backend `8001`, controllando le porte realmente disponibili.
- Directory di build e destinazione dei file, in modo che l'avvio parallelo non sostituisca gli asset serviti da NarrAI.

L'avvio del nuovo prodotto deve aprire una libreria di saggi e usare esclusivamente i propri job. L'eventuale importazione di materiali da NarrAI sarà esplicita e successiva.

## 3. Percorso dell'autore

Percorso visibile proposto: **Progetto → Domande → Argomenti e fonti → Indice → Scrittura → Revisione**. La copertina e gli export sono azioni dello studio finale.

| Fase | Risultato da ottenere | Possibilità dell'autore |
| --- | --- | --- |
| Progetto | Profilo, ruolo dell'AI, tema, domanda centrale, tesi iniziale se disponibile, lettore e obiettivo | Partire anche da un tema senza una posizione già definita |
| Domande | Chiarire significato dei termini, perimetro, posizione, destinatario e materiali | Rispondere solo ai chiarimenti utili; niente domande sui personaggi |
| Argomenti e fonti | Progetto editoriale con tesi, premesse, ragioni, obiezioni, fonti e lacune | Modificare la tesi, valutare fonti, aggiungere appunti e approvare il piano |
| Indice | Introduzione, progressione dei capitoli, conclusione, apparato delle fonti | Riordinare e modificare la struttura; vedere la funzione di ogni capitolo |
| Scrittura | Capitoli salvati e modificabili, con riferimenti collegati alle evidenze | Monitorare, mettere in pausa, riprendere e intervenire sul manoscritto |
| Revisione | Problemi concreti di argomentazione, documentazione e leggibilità | Applicare correzioni mirate e confrontare le revisioni |

Ricerca e piano sono iterativi: una fonte contraria può richiedere una riformulazione della tesi o un limite al suo ambito, secondo il ruolo dell'AI selezionato. La direzione può mancare all'inizio, ma deve essere esplicita e approvata prima della scrittura estesa: tesi per l'argomentativo, domanda e impostazione interpretativa per il divulgativo, domanda/ipotesi e metodo per l'accademico. Non cambiare silenziosamente la posizione dell'autore durante la generazione.

La struttura non impone a ogni capitolo la stessa sequenza meccanica. Definizioni, analisi, casi, confronti e confutazioni possono avere funzioni diverse, purché il contributo alla tesi sia leggibile.

## 4. Revisione di tutte le impostazioni attuali

La matrice copre tutti i 21 campi di `config/inputs.yaml`. Le sostituzioni sono semantiche: i nuovi concetti devono avere nomi propri anche nei contratti API e nella persistenza. Modalità di generazione, override dei modelli e parametri applicativi sono trattati nelle sezioni successive.

| Campo attuale | Impostazione nel prodotto per saggi | Valori e comportamento proposti |
| --- | --- | --- |
| `plot` — Trama | Tema, domanda centrale e tesi iniziale, separati | Tema obbligatorio; domanda e tesi affinabili nelle fasi successive |
| `genre` — Genere | Profilo editoriale | Argomentativo, divulgativo, accademico; predefinito argomentativo |
| `subgenre` — Sottogenere | Disciplina e ambito | Testo libero, anche interdisciplinare; niente lista di sottogeneri narrativi |
| `target_audience` — Fascia d'età | Competenza e profilo del lettore adulto | Generalista, informato, specialista; generalista predefinito; descrizione libera dei bisogni |
| `theme` — Tema narrativo | Concetti chiave e questioni correlate | Termini scelti dall'autore; evitare di imporre amore, morte o crescita come categorie |
| `protagonist` — Protagonista | Rimosso; introdurre la posizione dell'autore | Convinta, esplorativa, comparativa; non usare un campo personaggio per la tesi |
| `protagonist_archetype` — Archetipo | Rimosso; introdurre premesse e assunzioni | Elenco modificabile di punti da cui parte l'argomentazione |
| `character_arc` — Arco | Rimosso; introdurre il risultato per il lettore | Comprendere, riconsiderare, sostenere una posizione, orientare una scelta |
| `point_of_view` — Punto di vista | Persona dell'esposizione | Impersonale, prima persona singolare, prima persona plurale; impersonale predefinita |
| `narrative_voice` — Voce | Tono argomentativo | Analitico, riflessivo, dialogico, assertivo, polemico; analitico predefinito |
| `style` — Stile | Registro e densità | Chiaro/divulgativo, saggistico, tecnico, accademico; predefinito coerente con il profilo, modificabile |
| `temporal_structure` — Struttura temporale | Progressione dell'esposizione | Problema → analisi → proposta; tesi → argomenti → obiezioni; comparativa; tematica; cronologica se pertinente |
| `pace` — Ritmo | Densità dell'argomentazione e degli esempi | Equilibrata come default; più sintetica o più approfondita senza alterare la lunghezza obiettivo |
| `realism` — Realismo | Politica degli esempi | Casi documentati; esempi ipotetici etichettati; esperienze dell'autore; nessun caso inventato presentato come reale |
| `ambiguity` — Ambiguità | Gestione delle incertezze e dei limiti | Esplicitare limiti e domande aperte, distinguendo posizioni ferme e questioni irrisolte |
| `intentionality` — Intenzionalità | Finalità del saggio | Argomentare, divulgare, criticare, proporre, confrontare; predefinito coerente con il profilo |
| `length` — Ampiezza | Lunghezza obiettivo in parole | Preset proposti 15.000, 35.000, 60.000 parole e valore personalizzato; 35.000 come default da validare |
| `author` — Autore di riferimento | Riferimenti editoriali e caratteristiche desiderate | Facoltativo; distinguere modelli di esposizione da fonti da citare |
| `user_name` — Nome autore | Nome autore | Facoltativo nella preparazione; mostrato nei metadati e negli export quando fornito |
| `cover_style` — Copertina | Copertina di saggistica | Tipografica/minimale predefinita; concettuale, fotografica o illustrata opzionali; copertina facoltativa |
| `llm_model` — Modello testo | Modello predefinito con scelte per fase | Un catalogo backend unico; nessun modello scelto in base a una promessa di veridicità |

Il pubblico adulto è un vincolo del prodotto, non un menu con bambini e adolescenti. La competenza del lettore governa definizioni, lessico e profondità dell'esposizione.

Il campo `author` oggi indica un riferimento stilistico e `user_name` l'autore del libro: chiarire questa distinzione anche nella persistenza, eliminando i default che possono trasformare la parola “Autore” in un riferimento stilistico.

### Nuove impostazioni specifiche

| Impostazione | Proposta iniziale |
| --- | --- |
| Ruolo dell'AI | Sviluppa e metti alla prova; sostieni la mia posizione; esplora con me |
| Approccio | Analitico, critico, comparativo, propositivo; distinto dalla disciplina e dal profilo |
| Perimetro | Paese/area, periodo, temi inclusi ed esclusi, termini da definire |
| Trattamento delle obiezioni | Presentare le obiezioni più forti e rispondere senza caricaturarle; obbligo di considerarle nel piano |
| Metodo e corpus | Per il profilo accademico: metodo dichiarato, materiali analizzati, criteri di selezione e limiti |
| Materiali dell'autore | Appunti ed esperienze distinguibili dalle fonti esterne; PDF testuali, DOCX, TXT/Markdown e link |
| Ricerca | Materiali dell'autore e web; tracciamento delle acquisizioni e possibilità di escludere una fonte |
| Citazioni | Riferimenti numerici o autore-data, entrambi nell'MVP, con bibliografia; default autore-data per l'accademico; note native come estensione |
| Aggiornamento delle fonti | Data di consultazione e periodo dei dati; intervallo richiesto dall'autore se pertinente |
| Revisione | Controllo logico, controllo dei riferimenti, confronto con le obiezioni, revisione stilistica |
| Titolo e sottotitolo | Entrambi modificabili, distinti dalla tesi |
| Budget | Stima e consumi per ricerca, pianificazione, scrittura, revisione, copertina; eventuale tetto deciso dall'autore |

Il primo schermo deve restare leggero: tema, tesi/domanda iniziale facoltativa, profilo, ruolo dell'AI, lettore e ampiezza. Perimetro, voce, metodo, fonti, firma e modelli possono essere pannelli espandibili. Premesse e obiezioni si affinano nello spazio di lavoro, senza richiedere subito un modulo enciclopedico.

Il cambio di profilo propone nuovi default e mostra gli impatti, preservando le personalizzazioni già scelte. Dopo la pianificazione, cambiare profilo o ruolo dell'AI aggiorna la versione del progetto e richiede una revisione dei piani dipendenti; non riscrive automaticamente i capitoli.

## 5. Motore di argomentazione e memoria

Sostituire la story bible con un dossier argomentativo persistente:

- Profilo e ruolo dell'AI, tesi o domanda guida versionata e approvata, definizioni, perimetro e posizione dell'autore.
- Premesse, sotto-tesi e relazioni tra ragioni e conclusioni.
- Evidenze favorevoli, contrarie o miste, con collegamento ai passaggi delle fonti.
- Obiezioni, risposte, punti irrisolti e limiti dichiarati.
- Distribuzione degli argomenti nell'indice; distinguere ciò che è già sviluppato da ciò che resta da dimostrare.
- Per il profilo accademico: metodo, corpus, criteri di selezione, stato della questione e risultati realmente documentati.

Modelli proposti: `EssayBrief`, `EssayPlan`, `ArgumentClaim`, `ArgumentRelation`, `SourceRecord`, `EvidenceExcerpt`, `EssaySectionPlan`, `EssayReview`. Identificatori stabili permettono di collegare capitoli, affermazioni e fonti anche quando un titolo cambia.

Ogni affermazione rilevante porta un tipo: fattuale, interpretativa, normativa, ipotesi o esperienza dichiarata dell'autore. Una citazione nel manoscritto prova che un'affermazione è stata scritta; il sostegno esterno richiede un passaggio pertinente in una fonte acquisita. La pertinenza semantica va valutata separatamente dalla corrispondenza testuale.

Per ogni capitolo il writer riceve funzione argomentativa, ragioni assegnate, evidenze pertinenti, obiezioni, definizioni e sintesi degli argomenti già trattati. Il recupero deve seguire anche dipendenze logiche e fonti, oltre alla vicinanza fra capitoli. Rendere visibili le lacune quando il contesto non contiene il materiale necessario.

Le revisioni di tesi, fonte o capitolo invalidano gli elementi dipendenti: controlli, riferimenti, parti del piano, critica ed export. Conservare gli originali e proporre aggiornamenti mirati; evitare rigenerazioni integrali implicite.

## 6. Fonti e citazioni

La ricerca deve diventare una capacità applicativa esplicita. Non affidarsi alla richiesta “cita fonti reali” contenuta in un prompt.

Pipeline proposta: ricerca o importazione → acquisizione del contenuto → estrazione → scheda della fonte → collegamento alle affermazioni → revisione dei riferimenti.

Una scheda della fonte conserva autore/ente, titolo, URL o identificativo disponibile, data di pubblicazione se reperita, data di acquisizione, tipo di documento, versione/hash e localizzatore del passaggio. I metadati mancanti restano mancanti. Registrare gli estratti necessari per ricostruire le citazioni; la conservazione del testo completo dipende dal materiale importato e dalla modalità di acquisizione.

Stati separati: fonte proposta, contenuto acquisito, estratto localizzato, sostegno valutato, revisione dell'autore. L'esistenza di un URL o una risposta del modello non equivalgono a una verifica del fatto. Risultati di ricerca e snippet servono a individuare documenti, non a simulare di averli letti.

Preferire fonti dirette pertinenti alla disciplina e confrontare letture discordanti. Fonti primarie, sintesi e commenti hanno ruoli distinti; il solo tipo della fonte non ne garantisce l'attendibilità. Per numeri e studi, conservare contesto, periodo, popolazione e condizioni quando disponibili.

Il writer può usare soltanto identificativi di fonti presenti nel registro. Controlli deterministici rifiutano riferimenti sconosciuti, estratti inesistenti e numerazioni incoerenti. Se una prova manca, mantenere la lacuna visibile o qualificare il passaggio come ipotesi/opinione, senza inventare autori, date, DOI, dati o citazioni.

L'integrazione web va scelta durante l'implementazione, dopo verifica delle capacità, dei costi e dei contratti del fornitore: interfacce di ricerca e acquisizione separate dai prompt, con timeout, errori, limite di ricerche e consumo registrato. I tool disponibili in questa chat non costituiscono automaticamente un servizio disponibile dentro il prodotto.

Nell'MVP, gestire PDF testuali e file supportati con estrazione verificabile. Scansioni che richiedono OCR, accessi autenticati e contenuti non acquisibili devono avere uno stato esplicito; aggiungere OCR e connettori avanzati in seguito. I documenti acquisiti sono materiale da analizzare, non istruzioni per il motore.

Il prodotto supporta ricerca web e materiali dell'autore fin dalla prima versione, come confermato. La ricerca deve poter partire dai punti da documentare e dalle obiezioni, includendo prove che possono mettere in difficoltà la tesi. Nel profilo accademico, conservare query, criteri di selezione e motivi di inclusione/esclusione delle fonti per rendere il metodo ricostruibile.

## 7. Prompt, scrittura e revisione

| Area attuale | Intervento previsto |
| --- | --- |
| `config/agent_context.md` | Domande su tesi, ambito, termini, lettore, ragioni e fonti |
| `config/draft_agent_context.md` | Progetto editoriale: tesi, premesse, argomenti, obiezioni, metodo e indice preliminare |
| `config/draft_edit_context.md` | Modifiche mirate del progetto con impatti sulle ragioni e sulle evidenze |
| `config/outline_agent_context.md` | Capitoli organizzati per contributo alla tesi e prerequisiti concettuali |
| `config/writer_agent_context.md` | Prosa saggistica, transizioni logiche, distinzione fatti/opinioni, uso dei riferimenti |
| `config/narrative_craft.md` | Sostituzione con `essay_craft.md`: precisione dei termini, chiarezza, esempi pertinenti, niente ripetizioni di riempimento |
| `config/literary_critic.yaml` | Criteri saggistici e problemi localizzati nel testo; nessun criterio di caratterizzazione |

Sostituire anche le istruzioni narrative inserite direttamente nel codice, in particolare nei contratti strutturati, nel contesto del writer, nella riparazione della memoria e nel prompt della copertina. Cambiare i soli file Markdown lascerebbe istruzioni sui personaggi e sulla trama nel percorso di generazione.

Comporre le istruzioni con un nucleo comune, un blocco del profilo e un blocco del ruolo dell'AI. Il nucleo mantiene tracciabilità e distinzione dei tipi di affermazione; il profilo governa metodo e organizzazione; il ruolo governa se proporre alternative o lavorare sulla posizione scelta. I contratti strutturati devono rappresentare queste differenze e non richiedere una tesi polemica a un saggio divulgativo.

La gerarchia deve distinguere autorità editoriale e riscontro empirico: le scelte approvate dell'autore governano tesi e stile; le fonti governano le affermazioni documentate. Una contraddizione con una fonte richiede analisi e una proposta, non un'alterazione della fonte per proteggere la tesi.

### Modalità e parametri

Le attuali modalità Standard/Ultra determinano una o due parti narrative. Nel nuovo prodotto separare lunghezza del manoscritto, granularità delle sezioni e intensità della revisione. Proposta: “Scrittura” e “Scrittura con revisione”, con quest'ultima predefinita; una revisione mirata per sezione, poi segnalazione e pausa se restano problemi bloccanti. Entrambe eseguono i controlli deterministici sui riferimenti.

Prevedere modelli per domande, piano, analisi fonti, indice, capitoli, verifica degli argomenti, revisione e copertina opzionale. Il catalogo deve avere una sola fonte di verità: oggi parte dei valori è duplicata fra YAML, routing e frontend. Verificare disponibilità e prezzi dei modelli quando si implementa il branch.

Nel codice attuale `get_temperature_for_agent` restituisce la temperatura del modello e non applica un'impostazione specifica dell'agente. Se servono parametri per fase, renderli effettivi e testarli. Valutare impostazioni coerenti con i modelli scelti senza considerare una temperatura bassa una garanzia di accuratezza.

Validazione dei capitoli: contributo al piano, copertura delle ragioni assegnate, riferimenti validi, assenza di materiale fittizio presentato come reale e gestione degli irrisolti. Lunghezza minima in caratteri e doppia generazione non misurano la qualità del saggio.

### Rapporto di revisione

Valutare chiarezza della tesi, solidità dei passaggi logici, adeguatezza delle evidenze, trattamento delle obiezioni, precisione concettuale, organizzazione e leggibilità. Evitare un voto che sembri certificare la verità del contenuto o premi il solo orientamento della tesi.

Adattare il rapporto al profilo: nell'argomentativo pesano ragioni e obiezioni; nel divulgativo comprensibilità, definizioni e rappresentazione delle interpretazioni; nell'accademico metodo, relazione tra corpus e conclusioni, documentazione e limiti. Non penalizzare un saggio divulgativo perché non prende una posizione netta o un saggio accademico perché dichiara un esito inconclusivo.

Per ogni problema: passaggio interessato, ragione della segnalazione, impatto e intervento proposto. Distinguere riferimenti mancanti o scorretti, debolezze argomentative e suggerimenti stilistici. Misure utili: affermazioni da documentare, riferimenti controllati, obiezioni trattate e controlli ancora da aggiornare, con denominatori e stato delle analisi.

## 8. Studio, copertina, export e stime

Riutilizzare lo studio con indice, editor e pannello laterale. Sostituire il taccuino narrativo con viste di argomenti, fonti, obiezioni e revisioni. Dal testo si deve poter aprire il passaggio citato e risalire alla fonte; da un problema si deve poter raggiungere il capitolo interessato.

Mantenere revisioni, conflitti di salvataggio, protezione del testo non salvato, pausa/ripresa e consumi. “Manoscritto scritto” e “revisione conclusa” sono stati distinti. Consentire export di lavoro con irrisolti dichiarati; gli export indicati come revisionati devono avere riferimenti risolti e controlli aggiornati. Le opinioni esplicitamente dichiarate non richiedono una finta dimostrazione fattuale.

Export MVP in PDF, EPUB e DOCX: frontespizio con sottotitolo facoltativo, indice, capitoli, riferimenti numerici o autore-data e bibliografia generata dal registro delle fonti effettivamente citate. Il profilo accademico include sezioni di metodo e apparato coerenti con il piano. Usare un modello canonico comune per mantenere gli stessi identificativi nei tre formati, gestendo autori omonimi, più opere nello stesso anno e date mancanti. Note a piè di pagina native e conformità a template di singole riviste possono seguire la prima versione.

La copertina tipografica deve poter essere composta in modo deterministico con titolo, sottotitolo e autore leggibili. Un'immagine concettuale generata è opzionale. Aggiornare i prompt che oggi parlano di storia, logline e atmosfera del romanzo.

Le stime devono derivare dalle parole richieste, dai materiali da elaborare e dalle fasi selezionate. Separare ricerca, analisi delle fonti, pianificazione, scrittura, revisione e copertina. Usare intervalli e dichiarare l'assenza di storico; non trasferire automaticamente i coefficienti e i campioni dei romanzi. Le pagine restano una stima finché non viene prodotto il PDF. Il registro dei consumi effettivi conserva il comportamento attuale e include i nuovi stadi.

Manga, valutazione letteraria e filtri per generi narrativi non appartengono alla navigazione del nuovo prodotto. L'audio può restare opzionale; riproduzione delle citazioni e loro resa orale saranno decise prima di esporlo.

## 9. Mappa tecnica degli interventi

| Area del repository | Intervento |
| --- | --- |
| `backend/app/models.py`, `frontend/src/api/client.ts` | Contratti del brief saggistico, enum e nuovi risultati; eliminare la dipendenza da `plot` |
| `backend/app/llm/contracts.py` | Piano strutturato con argomenti, fonti e sezioni; sostituire `character_profiles` |
| `backend/app/agent/session_store.py`, `persistence/sqlite_store.py` | Sessioni di saggio, dossier, versioni e relazioni con evidenze; archiviazione e migrazioni proprie del prodotto |
| `backend/app/agent/question_generator.py`, `draft_generator.py`, `outline_generator.py` | Fasi editoriali saggistiche e output coerenti con i nuovi contratti |
| `backend/app/agent/story_bible.py`, `narrative_memory.py`, `writer/context_builder.py` | Dossier argomentativo, recupero delle evidenze e controlli di coerenza concettuale |
| `backend/app/agent/writer/chapter_generator.py`, `writer/book_orchestrator.py` | Scrittura per sezioni logiche, revisione limitata e checkpoint |
| Nuovi servizi e router delle fonti | Importazione, ricerca, acquisizione, registro, estratti e collegamenti |
| `backend/app/services/process_job_service.py`, `durable_worker.py` | Nuovi job di ricerca/analisi/revisione, prenotazioni e ripresa |
| `backend/app/services/critique_service.py`, `agent/literary_critic.py` | Revisione argomentativa e report localizzati |
| `frontend/src/components/DynamicForm.tsx`, `DraftStep.tsx`, `OutlineEditor.tsx` | Brief, piano argomentativo e indice; aggiornare anche mapping dei campi e restore |
| `frontend/src/components/ManuscriptStudio.tsx` e relative API | Pannelli di argomenti/fonti/obiezioni e navigazione dal riferimento alla prova |
| `frontend/src/components/ModelSettingsPanel.tsx`, `utils/estimateGeneration.ts`, `services/book_estimate_service.py` | Nuove fasi, separazione fra ampiezza e revisione, stime specifiche |
| `services/library_service.py`, `stats_service.py`, viste libreria/analisi | Filtri per disciplina e stato editoriale, statistiche proprie dei saggi |
| `services/export_service.py`, `pdf_service.py`, template, `agent/cover_generator.py` | Bibliografia e riferimenti coerenti, metadati e copertina del saggio |
| `backend/app/main.py`, configurazione, launcher e Vite | Identità del prodotto, root dati, isolamento, porte e asset |
| `frontend/src/router.tsx`, navigazione, onboarding e manifest | Percorso e identità di saggistica |

Estendere `FieldConfig` e il renderer del form solo per i controlli effettivamente necessari: oggi supportano `select` e `text`. I materiali e le relazioni tra argomenti richiedono componenti dedicati, non stringhe inserite in un select. Gli schemi strutturati restano compatti; vincoli complessi si verificano lato Pydantic, tenendo conto dei problemi Gemini già documentati nel repository.

## 10. Sequenza di realizzazione del branch

| Passo / commit indicativo | Consegna | Criterio di completamento |
| --- | --- | --- |
| 1. `feat: isolate essay product` | Identità, avvio e archivio del prodotto | Avvio parallelo con NarrAI; nessun job o file condiviso accidentalmente |
| 2. `feat: add essay brief and planning` | Campi, tre profili, tre ruoli dell'AI, contratti e progetto editoriale | Un tema con o senza tesi iniziale arriva a un piano coerente con il profilo; ripristino della sessione |
| 3. `feat: add evidence and sources` | Materiali, ricerca web, registro, estratti e collegamenti | Fonti favorevoli/contrarie distinguibili; riferimenti falsi rifiutati; acquisizioni fallite visibili |
| 4. `feat: generate argumentative manuscripts` | Indice, writer, dossier e checkpoint | Capitoli collegati al piano, obiezioni trattate, ripresa senza riscrivere i capitoli salvati |
| 5. `feat: add essay review and studio` | Revisione logica e pannelli dello studio | Segnalazioni localizzate; cambi alla tesi proposti; revisioni e invalidazioni verificabili |
| 6. `feat: export essays with bibliography` | Tre export, citazioni numeriche/autore-data, copertina, libreria e stime | Citazioni e bibliografia coerenti per i tre profili, contenuto leggibile nei tre formati |
| 7. `test: validate essay workflow` | Verifiche integrate, valutazione editoriale e documentazione | Percorso completo da tema a libro revisionabile; isolamento e recupero testati |

Ordine delle dipendenze: i contratti precedono le fonti; il registro delle fonti precede la scrittura documentata; la revisione usa le relazioni già persistite; gli export usano riferimenti canonici. Ogni passo deve lasciare un risultato verificabile senza fingere che una capacità ancora assente sia completata.

L'MVP comprende tutti e tre i profili e tutti e tre i ruoli dell'AI selezionabili, pubblico adulto, ricerca web e materiali tracciabili, trattamento delle obiezioni o delle interpretazioni concorrenti, editor con revisioni, ripresa, controllo dei riferimenti e tre export con due modalità di citazione. Rimandare OCR, connettori bibliografici avanzati, grafici da dataset, collaborazione, multilingua e pubblicazione esterna.

## 11. Verifica e criteri di accettazione

Test mirati con risposte simulate e database temporanei:

- Brief senza tesi iniziale, direzione approvata, pubblico adulto e persistenza di profilo, ruolo dell'AI e nuovi campi.
- Combinazioni dei tre profili con i tre ruoli dell'AI: modifiche proposte solo quando ammesse; nessuna perdita dei controlli sulle fonti. Cambio di profilo con preservazione delle personalizzazioni.
- Divulgativo senza tesi polemica e accademico con ipotesi non sostenuta: piani e conclusioni leciti senza forzare un'opinione o inventare risultati.
- Piano con sotto-tesi, premesse, obiezioni e sezioni; nessun personaggio obbligatorio o arco narrativo.
- Fonte inesistente, URL non acquisibile, citazione inventata, estratto che non sostiene l'affermazione e metadati mancanti: esiti distinti.
- Saggio personale senza dati empirici; saggio con numeri; fonte contraria; caso ipotetico; esperienza dell'autore: trattamento coerente per tipo di affermazione.
- Modifica della tesi o di una fonte con invalidazione dei controlli e delle sezioni dipendenti.
- Crash, pausa/ripresa e conflitto di salvataggio: conservazione dei capitoli, delle fonti e delle revisioni.
- Citazioni riordinate o rimosse, numeriche o autore-data: nessun riferimento orfano e bibliografia coerente nei tre export.
- Coesistenza di NarrAI e nuovo prodotto: database, file, worker, localStorage e asset isolati.
- Consumi e stime delle nuove fasi: totale parziale esplicito quando manca una misura.

Eseguire i controlli del repository pertinenti: `uv run pytest`, `npm run typecheck`, `npm run test:run`, `npm run build`. Verificare visivamente desktop e mobile, collegamenti alle fonti e documenti esportati. La copertura dei contratti non dimostra da sola la qualità dei nuovi saggi.

Valutazione editoriale su almeno un brief per profilo e casi di una tesi di opinione, evidenze empiriche e ipotesi messa in difficoltà dalle fonti. Giudicare comprensibilità, forza delle ragioni, correttezza dei riferimenti, adeguatezza del metodo e fedeltà alla direzione approvata. Eventuali chiamate reali ai modelli vanno registrate nei consumi del progetto di prova.

Il branch è pronto per una prima release quando l'autore può completare il percorso, leggere un manoscritto con argomentazione riconoscibile, risalire dalle citazioni alle fonti, identificare le lacune, modificare senza perdere versioni, riprendere dopo un'interruzione ed esportare un libro con apparato coerente.

## 12. Decisioni da consolidare durante la realizzazione

Le risposte dell'utente sono incorporate: tre profili selezionabili, tre ruoli dell'AI selezionabili e fonti provenienti sia dal web sia dai materiali dell'autore. Non restano chiarimenti bloccanti per la pianificazione.

Il nome definitivo, i preset di ampiezza, i default del ruolo dell'AI e il fornitore della ricerca possono essere consolidati durante la realizzazione. La scelta del fornitore richiede verifica tecnica e del listino; questo piano non certifica prezzi o capacità correnti di un servizio esterno.

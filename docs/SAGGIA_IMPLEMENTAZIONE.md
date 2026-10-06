# SaggIA — implementazione e verifiche

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
| Test e prova reale | backend/tests/test_essay_product.py, frontend/src/essay/essay.test.tsx, scripts/verifica-saggia.py |

Sono riutilizzati il motore SQLite per transazioni/revisioni, il worker durevole, il registro dei consumi e il controllo di corrispondenza degli estratti. Il codice di dominio narrativo precedente non viene chiamato dal flusso SaggIA. Restano nel repository componenti storici e test per verificare la compatibilità dell'infrastruttura.

## Verifiche completate

- 182 test backend: 131 dell'infrastruttura precedente e 51 SaggIA.
- 48 test frontend: 31 precedenti e 17 SaggIA. Verificate le nove combinazioni di profilo/ruolo, i default, le bozze, i conflitti, i riferimenti e i dati bibliografici.
- TypeScript senza errori; build Vite/PWA completata.
- Prova reale con Gemini 3.8 Flash: creazione nel browser, domande, ricerca web, analisi, piano, approvazione, tre capitoli, revisione, copertina e tre export.
- Prove reali con profilo divulgativo/ruolo esplorativo (Gemini 3.5 Flash Lite) e profilo accademico/ruolo di sostegno (Gemini 3.8 Flash): domande, upload di materiali dell'autore, evidenze e piano coerente.
- Prova nel browser dell'editor, dello storico, dei dati bibliografici, della nuova approvazione e della revisione dopo una modifica.
- Verifica responsive a 390 px e alla larghezza ordinaria del pannello.
- Rendering e ispezione visiva del PDF; verifica testuale dei riferimenti e apertura strutturale di EPUB/DOCX. Verificati anche titoli lunghi e copertine nei tre formati.
- Avvio/riuso dei servizi con il launcher, health check dedicato e navigazione diretta alla build.

Il libro dimostrativo rimane nella biblioteca come “Esempio verificato · Biblioteche e confronto”: tre capitoli, circa mille parole, sei fonti individuate, venti estratti disponibili e ventidue citazioni. I progetti temporanei degli altri due profili sono stati rimossi dopo averne salvato gli esiti tecnici nella directory QA esclusa da Git.

## Difetti trovati e corretti

Gemini rifiutava additionalProperties nello schema nativo: il contratto inviato al provider viene compattato, mantenendo i vincoli Pydantic locali. Un riferimento malformato nella prova reale ha mostrato la necessità di una correzione limitata prima del salvataggio. Sono stati inoltre corretti perdita dei campi dopo un'importazione fallita, sovrascrittura concorrente dei metadati, preparazione/accodamento dei job non atomica, ricompra di una ricerca durante il recupero, contesto che escludeva evidenze assegnate tardive, layout sui tablet, copertina PDF troppo grande e limite di 255 caratteri nei metadati DOCX.

## Limiti della prima versione

La ricerca non aggira accessi riservati e non legge scansioni prive di testo. I file sono limitati a 12 MB e il testo a 250.000 caratteri per fonte. Le citazioni sono numeriche oppure autore/data, senza dichiarare conformità a un particolare manuale bibliografico.

Il rapporto valuta uso delle evidenze e struttura argomentativa; non certifica la verità del libro. Gli export sono disponibili anche come versioni di lavoro. Il limite di spesa controlla i consumi misurati tra richieste; non costituisce una garanzia di fattura e non include eventuali tariffe di ricerca non determinabili dal provider.

La lunghezza è un obiettivo editoriale: nel piano viene allocata esattamente, mentre il testo effettivo può variare. Il writer conserva i checkpoint e rifiuta risposte troppo brevi.

La libreria offre ricerca per titolo/tema e filtro per profilo. Dashboard statistiche per disciplina, stime predittive senza storico, OCR, connettori bibliografici avanzati, collaborazione e pubblicazione esterna restano evoluzioni successive. La copertina tipografica è stata verificata con il servizio reale; le varianti con sfondo AI usano l'integrazione immagini ereditata, senza una prova live di generazione in questo intervento.

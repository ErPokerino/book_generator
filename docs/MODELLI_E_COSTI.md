# Modelli e costi di generazione

Stato del codice: **11 ottobre 2026**. NarrAI usa Gemini Developer API (`GOOGLE_API_KEY`). Modelli e override narrativi/visivi sono in `config/app.yaml`; modelli, profili e fasi dei saggi sono in `config/essay.yaml`. La fonte unica delle tariffe applicate è `backend/app/services/usage_service.py`. I nomi legacy sono risolti al modello API effettivamente invocato prima della registrazione.

## Listino applicato

La fotografia del catalogo nel repository riporta `verified_at=2026-09-20` e il [listino ufficiale Google](https://ai.google.dev/gemini-api/docs/pricing) come fonte. Questo aggiornamento documentale non costituisce una nuova verifica del listino o della disponibilità sull’account. Valori configurati Standard a pagamento, USD per milione di token:

| Modello API | Input | Output testo/ragionamento | Input in cache | Output immagini/audio |
| --- | ---: | ---: | ---: | ---: |
| gemini-3.8-flash | 0,75 | 3,75 | 0,075 | — |
| gemini-3.5-flash-lite | 0,30 | 2,50 | 0,03 | — |
| gemini-3.1-flash-lite | 0,25 | 1,50 | 0,025 | — |
| gemini-3.1-pro-preview | 2,00 | 12,00 | 0,20 | — |
| gemini-3-flash-preview | 0,50 | 3,00 | 0,05 | — |
| gemini-3.1-flash-image | 0,50 | 3,00 | — | 60,00 immagini |
| gemini-3.1-flash-lite-image | 0,25 | 1,50 | — | 30,00 immagini |
| gemini-3.1-flash-tts-preview | 1,00 | — | — | 20,00 audio |

Il catalogo applica un raddoppio delle tariffe Flash 3.8 dal 1° gennaio 2027 in base alla data della richiesta. Per Pro 3.1 applica, oltre 200.000 token di input, input/output/cache pari a 4,00 / 18,00 / 0,40. Sono regole dell’attuale implementazione; la soglia è per richiesta, non sulla somma dell’opera.

## Registro dei consumi

Ogni tentativo associato a un progetto viene registrato **prima** dell'invio, quindi completato con i consumi della risposta, modello, fase, tariffa, cambio e identificativo risposta quando disponibile. Il registro include scrittura, memoria, correzioni, copertine, manga, critica e audio. Una risposta scartata dal validatore può aver consumato token: resta nel totale.

Per richiesta si calcola:

`((input − cache) × prezzo_input + cache × prezzo_cache + output_testuale × prezzo_output + output_immagine × prezzo_immagine) / 1.000.000`

Il ragionamento nativo Gemini viene aggiunto all'output; nei metadati LangChain è già incluso e non viene contato due volte. Per le immagini si usa la suddivisione delle modalità riportata dal provider. Se manca, il costo resta non quantificato: nessuna tariffa forfettaria viene presentata come consumo misurato.

La cache esplicita del writer è stata rimossa, eliminando nuovi costi di conservazione associati a quella funzionalità. L'eventuale cache implicita viene conteggiata con la tariffa ridotta restituita dal listino. Il registro non ricostruisce eventuali cache create da versioni precedenti.

Timeout, interruzioni senza risposta e modelli privi di tariffa restano da verificare. Il taccuino mostra il subtotale noto e segnala la copertura incompleta. Libreria, ripristino e progressi usano lo stesso registro; i vecchi totali per fase non vengono rivalutati con l'ultimo modello scelto.

## Consumo misurato, stima e fattura

- **Consumi API:** token effettivamente restituiti, valorizzati al listino Standard a pagamento. Il cambio USD→EUR configurato viene conservato per richiesta; EUR è indicativo.
- **Stima prima di generare:** estensione prevista dallo storico della modalità scelta, con ipotesi sulle chiamate. Include l'analisi della memoria; non predice audio, retry, correzioni e ragionamento variabile. Le ipotesi sulle immagini sono 1K Lite / 2K Flash, non prezzi reali per qualsiasi risoluzione.
- **Fattura:** può differire per quota gratuita, crediti, sconti, imposte e cambio effettivo. L'app non accede alla fatturazione Google e non afferma di averla verificata.

I progetti storici non hanno un registro per richiesta: vengono marcati come non ricostruibili. Anche dopo nuove generazioni il loro totale rimane parziale. Consultare il dettaglio in `/api/studio/{session_id}/costs` o nel taccuino del libro; la fattura Google resta il riferimento per l'addebito.

Anche il percorso sincrono delle domande crea ora la sessione prima di chiamare il modello, registrando il primo consumo e i tentativi falliti. Nelle versioni precedenti quei token potevano comparire solo nei contatori aggregati: se mancano gli eventi delle domande, il progetto viene segnalato come storicamente incompleto e il subtotale non viene presentato come completo.

## Saggi e fumetti

La previsione dei saggi usa `/api/saggistica/essay-estimates`, senza chiamate AI. Le pagine sono l’obiettivo scelto (60/140/240 o 4–480 personalizzate), a 250 parole/pagina. Il budget interno `target_words` conserva la compatibilità con SaggIA.

Il costo usa il listino comune e ipotesi configurate: capitoli da circa 3.000 parole, parti da circa 1.300, 1,4 token/parola, contesto base da 6.000 token e reinvio delle parti precedenti della stessa sezione. Include domande, piano e scrittura; nel percorso con revisione include un controllo per capitolo. La fascia 65–160% del valore centrale è una variabilità indicativa, non un intervallo statistico misurato né un limite di spesa. Modelli generali e override delle fasi aggiornano la previsione.

Il tempo iniziale usa fallback per modello dalla configurazione; con almeno tre scritture completate e ininterrotte, dello stesso percorso e modelli di scrittura/controllo, usa la mediana dei secondi per parola. Esclude pause e tempi di lavoro dell’autore. Una tariffa mancante resta non disponibile, senza diventare zero.

Ricerca web, analisi dei materiali, correzioni, revisione complessiva separata e copertina AI sono aggiuntive. La copertina tipografica è locale e non richiede generazione. Nel registro saggi le fasi hanno prefisso `essay-`; eventuali costi del servizio di ricerca non quantificabili rendono incompleta la copertura. Il limite `budget_eur` si verifica tra richieste: una già avviata può superarlo.

Manga e Graphic Novel condividono la formula della previsione fumetti: storyboard, numero di tavole e due copertine. Le ipotesi di token/risoluzione sono configurate; la fattura e i consumi reali non vengono ricavati dal numero di immagini. La scelta del formato cambia i prompt editoriali e visivi, non la tariffa per token del modello selezionato.

Valuta registra le chiamate su opere interne nel loro archivio; le valutazioni PDF esterne restano fuori dai totali delle opere. Analisi somma i costi noti e dichiara la copertura incompleta. Audio AI e suoni Web Audio dell’interfaccia sono distinti: i secondi non chiamano il provider e non hanno consumi API.

## Pipeline e scelta dei modelli narrativi

### Previsione dell'estensione

La base fissa di 100 pagine è stata rimossa. `/api/config/book-estimates` considera soltanto libri completati con capitoli presenti, non vuoti e contigui. Standard e Ultra sono stimati separatamente: i campioni di una modalità non sostituiscono quelli dell'altra.

Ogni libro contribuisce con le sue parole medie per capitolo. Si usa la mediana fra libri, evitando che un romanzo molto lungo pesi più degli altri. Con almeno tre campioni del modello scelto si preferisce quel gruppo; altrimenti si usa lo storico della modalità, dichiarando che il modello non è filtrato. Lo stesso criterio restringe ulteriormente il gruppo per ampiezza, quando disponibile.

La scelta breve/media/lunga moltiplica la densità osservata per 6/12/20 capitoli; senza scelta si usa la mediana dei capitoli nello storico. Le pagine sono equivalenti testuali, con il rapporto parole/pagina della configurazione, non la paginazione esatta del PDF. Sono mostrati conteggio dei campioni e variabilità dell'estensione (minimo/massimo sotto cinque libri; percentili 20–80 da cinque in poi). Il costo viene ricalcolato anche agli estremi della fascia, che non rappresenta un limite di spesa.

Con zero libri della modalità non viene inventata una previsione: pagine, costo e tempo del libro restano indisponibili e si può comunque iniziare. Uno o due libri producono una previsione esplicitamente indicativa. Errori di rete hanno un messaggio e un comando Riprova distinti dall'assenza di storico. La modifica di modalità, ampiezza e modello aggiorna la previsione. Il tempo usa ancora il modello indicativo per modalità, applicato al numero di capitoli previsto, e non una nuova regressione sulle durate.

Nel costo Ultra viene incluso anche il contesto della prima parte reinviato per generare la seconda. I consumi successivi alla generazione continuano a usare il registro per richiesta descritto sopra.

Il catalogo UI propone Flash 3.8 e Flash Lite 3.5 per il testo, Flash Image e Lite Image per le immagini. La scelta per fase prevale su quella generale; memoria e correzioni seguono rispettivamente il modello testo e quello capitoli, salvo override.

Standard genera un capitolo in una chiamata writer; Ultra usa due parti sequenziali. Entrambi aggiungono estrazione dei fatti e controllo di continuità, con al massimo una revisione mirata per analisi. Il contesto combina piano, story bible, ultimo capitolo integrale e fatti pertinenti recuperati da tutta la storia.

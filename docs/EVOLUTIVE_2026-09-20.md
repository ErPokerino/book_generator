# Evolutive implementate — 20 settembre 2026

## Stato consegnato

- Persistenza SQLite con transazioni, migrazione dal JSON, revisioni dei capitoli e letture consistenti.
- Coda persistente per domande, bozza, indice, libro, manga e analisi della memoria. Recupero dei job interrotti tramite prenotazioni a scadenza e checkpoint; protezione da avvii duplicati.
- Memoria narrativa con prove testuali, ricerca di fatti anche lontani, stati sostituiti, fili aperti e distinzione fra fatti e inferenze. Una revisione mirata in caso di contraddizione, poi pausa se il conflitto rimane.
- Studio `/studio/:sessionId`: indice, editor Markdown, versioni, prove, costi, pausa/ripresa e pannelli adattati a mobile. Salvataggi protetti da hash, errori senza perdita del testo e avviso sulle modifiche non salvate.
- Registro dei consumi per singola richiesta, con tariffa storicizzata e totale parziale esplicito quando mancano dati. Eliminati i vecchi calcoli post-generazione ricavati dalle pagine o da aggregati per modello.

## Migrazione e backup

Al primo avvio si importa `.sessions.json` dalla directory del database. Tutti i record vengono validati prima del commit; l'originale resta intatto e viene coperto da `.sessions.json.pre-sqlite.bak`. I successivi avvii non reimportano versioni vecchie. Con `NARRAI_DB_PATH` in una directory diversa, collocare lì il JSON da importare prima del primo avvio.

Da `backend`, creare un backup consistente anche a server acceso:

```powershell
uv run python -m app.persistence.archive backup --output narrai-backup.sqlite3
```

Il comando rifiuta un file di destinazione già esistente. Il backup conserva anche revisioni, job e consumi. Immagini, PDF e audio vanno copiati separatamente dalle directory elencate nel README. Non copiare solo il file principale di un database aperto: potrebbe avere modifiche ancora nel WAL.

Per ripristinare: fermare tutti i backend, conservare l'archivio corrente con i suoi file WAL/SHM e avviare usando `NARRAI_DB_PATH` sul percorso di una copia del backup. I job attivi al momento del backup possono riprendere all'avvio; per una fotografia senza lavoro in corso richiedere prima la pausa e attendere che non ci siano job attivi.

Per leggere i contenuti con la precedente versione a file:

```powershell
uv run python -m app.persistence.archive export-json --output sessions-export.json
```

Questo export conserva sessioni e capitoli correnti; non è un backup completo di revisioni, coda e registro dei consumi. Per tornare temporaneamente a `main`, fermare il backend e usare la copia JSON esportata come `.sessions.json`, preservando entrambi gli archivi. La precedente versione non conosce le evolutive SQLite.

## Branch

`main` contiene la versione locale consolidata, inclusi i fix dell'audit (`b3a7c03`). `codex/evolutive-studio` contiene queste evolutive e parte da quel commit. I branch precedenti `local-only` e `feature/improve-narrative-quality` sono stati eliminati solo dopo aver verificato che tutti i loro commit fossero conservati in `main`. Entrambi i branch mantenuti sono pubblicati su origin; non sono stati usati force push.

## Verifica

Esito finale: **118 test backend e 23 test frontend superati**, TypeScript e build di produzione completati; nessun errore nel controllo whitespace del diff.

Test backend su database temporanei: migrazione idempotente, rollback atomico, conflitti, prenotazioni scadute, arresto/ripresa, salvataggio di prove, revisione e invalidazione degli export, backup ed export JSON. Un test integra worker reale, SQLite, orchestratore e memoria con risposte AI simulate, verificando che il capitolo già salvato non venga rigenerato.

Test costi: cache, ragionamento nativo e LangChain, modalità immagine/testo, contesto oltre 200.000 token, modelli diversi, tentativi di esito ignoto e risposte rifiutate dal validatore ma comunque consumate. Frontend: protezione del testo, hash di salvataggio e costi incompleti; typecheck, test e build di produzione.

Verifica visiva e funzionale nel browser su progetto temporaneo: tre colonne desktop, pannelli mobile a 390 px, prova nel testo, modifica, salvataggio e storico revisioni. Nessuna generazione a pagamento è stata eseguita per questi test.

## Limiti espliciti

Il worker richiede che il backend sia acceso e usa SQLite locale, senza distribuzione fra dispositivi. Le operazioni richieste direttamente, come TTS o rigenerazione della critica, restano legate alla richiesta HTTP. Un crash fra risposta AI e salvataggio non può garantire assenza di doppio consumo presso il fornitore; il registro conserva le chiamate di esito ignoto.

Le citazioni sono controllate testualmente, ma la loro interpretazione e l'individuazione di contraddizioni sono affidate al modello. I test non sostituiscono una valutazione editoriale su romanzi nuovi. La fattura non è stata riconciliata con l'account Google: consumi misurati, cambio, prezzi e dati storici non ricostruibili sono descritti in [modelli e costi](MODELLI_E_COSTI.md).

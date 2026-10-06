# SaggIA — studio locale per scrivere saggi

Prodotto derivato da NarrAI, dedicato a libri di saggistica per lettori adulti. Il nome SaggIA è provvisorio.

Tre profili selezionabili (argomentativo, divulgativo, accademico) e tre ruoli AI indipendenti (sviluppare e mettere alla prova, sostenere la posizione, esplorare alternative). Il percorso comprende brief, domande, argomenti e fonti, indice, manoscritto e revisione.

## Avvio locale

Prerequisiti: Python 3.11+, uv, Node.js 18+ e npm. Copia .env.example in .env nella root e configura GOOGLE_API_KEY per le funzioni AI. L'editor e la biblioteca funzionano anche senza chiave.

Su Windows esegui **avvia-saggia.cmd**. Il launcher installa le dipendenze mancanti, verifica i servizi, evita duplicati e apre http://127.0.0.1:5174. Per avviare senza aprire un browser:

    powershell -NoProfile -ExecutionPolicy Bypass -File scripts/avvia-saggia.ps1 -NoBrowser

Avvio manuale, in due terminali:

    cd backend
    uv sync --locked
    uv run uvicorn app.essay.main:app --reload --reload-dir app/essay --host 127.0.0.1 --port 8001

    cd frontend
    npm ci
    npm run dev

Il proxy frontend usa la porta 8001. Le porte distinte permettono di usare SaggIA e NarrAI contemporaneamente. Per la build locale:

    cd frontend
    npm run build

Il backend SaggIA può anche servire la build su http://127.0.0.1:8001.

## Scrittura e documentazione

- Brief: domanda, tesi facoltativa, lettore adulto, ampiezza in parole, voce, registro, struttura, metodo, corpus e criteri delle fonti.
- Piano: premesse, tipi di affermazione, ragioni, obiezioni, risposte, lacune, definizioni e indice. La direzione deve essere approvata prima della scrittura.
- Fonti: ricerca Google attraverso Gemini, link pubblici, PDF testuali, DOCX, TXT, Markdown e appunti dell'autore. Le ricerche registrano query e riferimenti restituiti dal servizio. I materiali vengono acquisiti prima di diventare evidenze.
- Evidenze: estratti letterali con localizzatore, relazione con la tesi e limiti. Sono disponibili inserimento manuale, dati bibliografici modificabili, esclusione e nuovo tentativo per un link non acquisito.
- Manoscritto: capitoli leggibili mentre procede la generazione, pausa al termine del capitolo, ripresa dopo errori e riavvii, editor con conflitti protetti, bozze locali e storico delle revisioni.
- Revisione: logica, uso delle evidenze, obiezioni, metodo e stile. La modalità con revisione può correggere una volta un problema bloccante e poi fermarsi per l'intervento dell'autore.
- Citazioni: riferimenti numerici oppure autore/data, composti dallo stesso registro per anteprima, PDF, EPUB e DOCX. Nell'editor si usa il marcatore stabile [@E…].
- Copertina: tipografica senza chiamata AI, oppure sfondo generato su richiesta e titolo/firmatario composti localmente.

La revisione valuta il materiale acquisito: non certifica la verità delle affermazioni. Una scansione senza testo richiede OCR esterno; una pagina non accessibile resta segnalata e può essere importata come documento. Il testo acquisito è limitato a 250.000 caratteri e i file a 12 MB.

## Archivio, privacy e consumi

SQLite, originali, copertine e log sono in **backend/data/saggistica/**. La variabile SAGGIA_DATA_DIR permette di scegliere un'altra directory. Non vengono importati o convertiti gli archivi NarrAI.

I job usano transazioni, lease e checkpoint persistenti. Ogni parte di capitolo viene salvata prima della successiva. I risultati di una ricerca già registrati vengono riutilizzati dopo un'interruzione. Un errore recuperabile richiede una ripresa esplicita; un processo interrotto dal riavvio riparte quando scade il lease.

Il backend ascolta solo su localhost. Google riceve il contesto e gli estratti necessari alle operazioni AI; la ricerca richiede rete. La chiave resta nel file .env escluso da Git.

I consumi sono stimati dai token restituiti dall'API e dal listino configurato, con cambio EUR configurabile. Il limite di spesa viene controllato tra richieste. Le richieste già avviate possono superarlo. I costi specifici della ricerca Google dipendono dal piano e sono indicati come non inclusi nel totale misurato quando non determinabili. La fattura del provider resta il riferimento.

## Verifica

    cd backend
    uv run pytest -q

    cd ../frontend
    npm run typecheck
    npm run test:run
    npm run build

I test SaggIA coprono le nove combinazioni editoriali, isolamento dei dati, approvazione del piano, evidenze letterali, citazioni/export, concorrenza, revisioni e ripresa dei checkpoint. Sono mantenuti anche i test dell'infrastruttura ereditata da NarrAI.

Piano del prodotto e scelte approvate: [docs/PIANO_PRODOTTO_SAGGISTICA.md](docs/PIANO_PRODOTTO_SAGGISTICA.md).
Dettagli implementativi e risultati: [docs/SAGGIA_IMPLEMENTAZIONE.md](docs/SAGGIA_IMPLEMENTAZIONE.md).

Il codice narrativo precedente resta nel repository per riutilizzo e compatibilità dei test. L'entry point di SaggIA è app.essay.main:app; il frontend di questo branch usa esclusivamente il dominio saggistico.

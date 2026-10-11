# Documentazione di NarrAI

Stato del prodotto e del repository: **11 ottobre 2026**. Le guide correnti descrivono un’unica applicazione locale per Narrativa, Saggio e Fumetto.

| Documento corrente | Contenuto |
| --- | --- |
| [README](../README.md) | Requisiti, installazione, avvio e verifiche |
| [Funzionale](FUNZIONALE.md) | Percorsi, biblioteca, lettore, valutazione e impostazioni |
| [Tecnica](TECNICA.md) | Architettura, API, persistenza, worker e compatibilità |
| [Modelli e costi](MODELLI_E_COSTI.md) | Catalogo applicato, previsioni, consumi e limiti |
| [Operazioni](OPERAZIONI.md) | Avvio, archivi, backup, ripristino e importazione |
| [Studio unificato](NARRAI_UNIFICATO.md) | Integrazione SaggIA, restyling e verifiche della consegna |
| [Eval](../evals/README.md) | Corpus statico, regressioni e perimetro della valutazione |

## Documenti storici

Le date, i conteggi dei test e i nomi dei branch seguenti descrivono il momento della loro stesura. Non sono istruzioni per avviare la versione corrente.

- [Revisione del 20 settembre](REVISIONE_2026-09-20.md): difetti e priorità dell’audit originario.
- [Evolutive del 20 settembre](EVOLUTIVE_2026-09-20.md): introduzione di SQLite, worker, memoria e studio.
- [Piano SaggIA del 6 ottobre](PIANO_PRODOTTO_SAGGISTICA.md): progetto inizialmente autonomo, poi integrato.
- [Implementazione SaggIA](SAGGIA_IMPLEMENTAZIONE.md): verifiche e sviluppi della versione autonoma.
- [Proposte di nome](../frontend/PROPOSTE_NOMI.md): alternative considerate prima del nome NarrAI.

I Markdown in `config/` sono istruzioni operative dei generatori narrativi; i prompt saggistici e le istruzioni visive dei fumetti sono nel codice del rispettivo dominio. Non sono guide generiche dell’app.

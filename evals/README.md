# LLM Generation Evals

Aggiornamento: 11 ottobre 2026. `representative_books.json` raccoglie casi narrativi statici per regressioni dei contratti, caricati da `backend/tests/test_writer_quality.py`. Non è un corpus completo dei tre formati e non genera nuove opere con chiamate AI.

Le verifiche automatiche attuali coprono:

- correttezza dell'outline: il markdown atteso deve produrre le sezioni scrivibili previste
- continuity/context: il contesto del writer deve includere vincoli, tone of voice e riferimenti narrativi rilevanti
- placeholder leakage: output con marker tecnici vietati devono fallire la validazione
- style adherence: i capitoli campione devono mantenere parole chiave o segnali stilistici attesi

Uso consigliato:

- aggiornare `representative_books.json` quando si introducono nuovi generi, strutture o contratti prompt
- usare i casi per confrontare trace e output reali dopo modifiche ai prompt o al runtime
- aggiungere nuovi casi solo se rappresentano un rischio regressivo reale

Esecuzione da `backend`:

```powershell
uv run pytest tests/test_writer_quality.py tests/test_prompts.py -q
```

Le regressioni dei saggi sono in `test_essay_product.py`, `test_essay_revision.py`, `test_essay_review_scope.py`, `test_essay_estimates.py`. Verificano fonti, marcatori, confini dei gruppi, approvazione, checkpoint, correzioni e previsione senza consumi. `test_product_consistency.py` verifica formati/sottogeneri, prompt e pausa dei fumetti, rubriche trasversali e metriche. `test_unified_studio.py` verifica biblioteca comune e isolamento degli archivi; `test_saggia_import.py` l’importazione senza sovrascrittura.

Il confronto editoriale ripetibile tra narrativa, saggi e fumetti richiede ancora brief stabili, risultati prodotti nelle stesse condizioni, rubriche dedicate e valutazioni umane. Il critico in Valuta e i conteggi di Analisi non sostituiscono tale esperimento. Per la suite completa e i comandi frontend vedere [operazioni](../docs/OPERAZIONI.md).

`data/chapter_timings_export.csv` conserva l’esportazione storica dei tempi narrativi, distinta dalle metriche correnti dell’app. L’utility `python -m app.analytics.export_chapter_timings`, eseguita da `backend`, scrive in quel percorso; il CSV non viene caricato dal frontend.

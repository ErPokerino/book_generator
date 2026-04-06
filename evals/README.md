# LLM Generation Evals

Questo dataset raccoglie casi rappresentativi per controllare regressioni nella pipeline di generazione.

Le verifiche automatiche attuali coprono:
- correttezza dell'outline: il markdown atteso deve produrre le sezioni scrivibili previste
- continuity/context: il contesto del writer deve includere vincoli, tone of voice e riferimenti narrativi rilevanti
- placeholder leakage: output con marker tecnici vietati devono fallire la validazione
- style adherence: i capitoli campione devono mantenere parole chiave o segnali stilistici attesi

Uso consigliato:
- aggiornare `representative_books.json` quando si introducono nuovi generi, strutture o contratti prompt
- usare i casi per confrontare trace e output reali dopo modifiche ai prompt o al runtime
- aggiungere nuovi casi solo se rappresentano un rischio regressivo reale

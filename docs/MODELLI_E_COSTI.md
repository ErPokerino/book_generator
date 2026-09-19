# Modelli Gemini e stime di costo

NarrAI usa solo **Gemini Developer API** (`GOOGLE_API_KEY`). I modelli si scelgono in UI: un modello testo, un modello immagini e, in Avanzate, override per fase. Gli id API e i default stanno in `config/app.yaml` → `llm_models`.

## Catalogo

| Scopo | Modelli disponibili | Default |
|---|---|---|
| Testo (riassunti, domande, capitoli, storyboard) | `gemini-3.8-flash`, `gemini-3.5-flash-lite` | Flash 3.8, Lite sulle domande |
| Immagini | `gemini-3.1-flash-lite-image`, `gemini-3.1-flash-image` | Lite Image sulle pagine manga, Flash Image sulle copertine |
| TTS | `gemini-3.1-flash-tts-preview` | Fisso, senza picker |

## Modalità libro

- **Standard**: 1 chiamata writer per capitolo
- **Ultra**: 2 chiamate sequenziali per capitolo. Nessuna review/revisione extra.

Il contesto writer usa la story bible (personaggi, riassunti, continuity) più **solo l'ultimo capitolo integrale**.

## Mappa per attività (default, sovrascrivibili)

| Attività | Default |
|---|---|
| Domande | `gemini-3.5-flash-lite` |
| Bozza, outline, capitoli, critica | `gemini-3.8-flash` |
| Copertina libro | `gemini-3.1-flash-image` |
| Manga planning | `gemini-3.8-flash` |
| Manga pagine interne | `gemini-3.1-flash-lite-image` |
| Manga copertina / retro | `gemini-3.1-flash-image` |
| TTS | `gemini-3.1-flash-tts-preview` |

Temperatura: `1.0` per qualsiasi modello `gemini-3*`.

## Prezzi usati (USD / milione di token)

Da `config/app.yaml` `cost_estimation.model_costs`, cambio USD→EUR `0.92`. I listini dei modelli 3.8 / 3.5 Lite sono stime di configurazione, da riallineare se Google pubblica prezzi ufficiali.

| Modello | Input | Output |
|---|---:|---:|
| `gemini-3.8-flash` | $0.50 | $3.00 |
| `gemini-3.5-flash-lite` | $0.10 | $0.40 |

Copertina/manga immagine in config: $0.02 / immagine.

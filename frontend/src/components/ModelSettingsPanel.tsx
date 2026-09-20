import { useEffect, useMemo, useState } from 'react';
import { Clock3, Coins } from 'lucide-react';
import { getAppConfig, type AppConfig } from '../api/client';
import { getBookEstimates, type BookSizeEstimates } from '../api/bookEstimates';
import Disclosure from './ui/Disclosure';
import {
  estimateGeneration,
  formatEstimateCost,
  formatEstimateTime,
} from '../utils/estimateGeneration';
import './ModelSettingsPanel.css';

export type GenerationMode = 'standard' | 'ultra';

export const TEXT_MODELS = [
  {
    id: 'gemini-3.8-flash',
    label: '3.8 Flash',
    hint: 'Qualità',
    description: 'Più curato, un po’ più lento',
  },
  {
    id: 'gemini-3.5-flash-lite',
    label: '3.5 Lite',
    hint: 'Veloce',
    description: 'Più rapido ed economico',
  },
] as const;

export const IMAGE_MODELS = [
  {
    id: 'gemini-3.1-flash-lite-image',
    label: 'Lite Image',
    hint: 'Rapido',
    description: 'Più veloce, adatto alle tavole interne',
  },
  {
    id: 'gemini-3.1-flash-image',
    label: 'Flash Image',
    hint: 'Dettaglio',
    description: 'Più dettagliato, adatto alle copertine',
  },
] as const;

export const DEFAULT_TEXT_MODEL = TEXT_MODELS[0].id;
export const DEFAULT_IMAGE_MODEL = IMAGE_MODELS[0].id;
export const DEFAULT_COVER_IMAGE_MODEL = IMAGE_MODELS[1].id;
export const TTS_MODEL_LABEL = 'Gemini 3.1 Flash TTS';

export interface StageOption {
  id: string;
  label: string;
  purpose: 'text' | 'image';
  defaultModel: string;
}

export const BOOK_STAGES: StageOption[] = [
  { id: 'questions', label: 'Domande', purpose: 'text', defaultModel: 'gemini-3.5-flash-lite' },
  { id: 'draft', label: 'Bozza', purpose: 'text', defaultModel: DEFAULT_TEXT_MODEL },
  { id: 'outline', label: 'Struttura', purpose: 'text', defaultModel: DEFAULT_TEXT_MODEL },
  { id: 'chapters', label: 'Capitoli', purpose: 'text', defaultModel: DEFAULT_TEXT_MODEL },
  { id: 'critique', label: 'Critica', purpose: 'text', defaultModel: DEFAULT_TEXT_MODEL },
  { id: 'cover', label: 'Copertina', purpose: 'image', defaultModel: DEFAULT_COVER_IMAGE_MODEL },
];

export const MANGA_STAGES: StageOption[] = [
  { id: 'manga_planning', label: 'Storyboard', purpose: 'text', defaultModel: DEFAULT_TEXT_MODEL },
  { id: 'manga_pages', label: 'Pagine interne', purpose: 'image', defaultModel: DEFAULT_IMAGE_MODEL },
  { id: 'manga_cover', label: 'Copertina', purpose: 'image', defaultModel: DEFAULT_COVER_IMAGE_MODEL },
  { id: 'manga_back_cover', label: 'Retrocopertina', purpose: 'image', defaultModel: DEFAULT_COVER_IMAGE_MODEL },
];

export interface ModelSettingsValue {
  generationMode?: GenerationMode;
  stageModels: Record<string, string>;
}

interface ModelSettingsPanelProps {
  value: ModelSettingsValue;
  onChange: (next: ModelSettingsValue) => void;
  stages: StageOption[];
  showGenerationMode?: boolean;
  kind: 'book' | 'manga';
  mangaPageCount?: number;
  bookLength?: string;
}

const WRITING_MODES: Array<{
  id: GenerationMode;
  label: string;
  hint: string;
  description: string;
}> = [
  {
    id: 'standard',
    label: 'Standard',
    hint: 'Più essenziale',
    description: 'Ogni capitolo nasce in un’unica parte.',
  },
  {
    id: 'ultra',
    label: 'Ultra',
    hint: 'Più esteso',
    description: 'Due parti consecutive danno più spazio a scene e dettagli.',
  },
];

export function buildModelOverrides(value: ModelSettingsValue, stages: StageOption[]): Record<string, string> {
  const overrides: Record<string, string> = {};
  for (const stage of stages) {
    overrides[stage.id] = value.stageModels[stage.id] || stage.defaultModel;
  }
  return overrides;
}

function sharedModel(stages: StageOption[], stageModels: Record<string, string>): string | null {
  if (stages.length === 0) return null;
  const first = stageModels[stages[0].id] || stages[0].defaultModel;
  return stages.every((stage) => (stageModels[stage.id] || stage.defaultModel) === first) ? first : null;
}

export default function ModelSettingsPanel({
  value, onChange, stages, showGenerationMode = false, kind, mangaPageCount, bookLength,
}: ModelSettingsPanelProps) {
  const [appConfig, setAppConfig] = useState<AppConfig | null>(null);
  const [history, setHistory] = useState<{ key: string; data: BookSizeEstimates } | null>(null);
  const [historyError, setHistoryError] = useState('');
  const [retry, setRetry] = useState(0);
  const mode = value.generationMode || 'standard';
  const chapterModel = value.stageModels.chapters || DEFAULT_TEXT_MODEL;
  const requestKey = `${chapterModel}:${bookLength || ''}`;
  const sizes = history?.key === requestKey ? history.data : null;
  const size = sizes?.[mode];

  useEffect(() => {
    let disposed = false;
    getAppConfig().then(data => { if (!disposed) setAppConfig(data); }).catch(() => { if (!disposed) setAppConfig(null); });
    return () => { disposed = true; };
  }, []);

  useEffect(() => {
    if (kind !== 'book') return;
    let disposed = false;
    const controller = new AbortController();
    setHistory(null); setHistoryError('');
    getBookEstimates(chapterModel, bookLength, controller.signal)
      .then(data => { if (!disposed) setHistory({ key: requestKey, data }); })
      .catch(error => { if (!disposed) setHistoryError(error.message); });
    return () => { disposed = true; controller.abort(); };
  }, [kind, chapterModel, bookLength, requestKey, retry]);

  const estimate = useMemo(() => estimateGeneration({
    kind, generationMode: mode, stageModels: value.stageModels, stages,
    mangaPageCount, config: appConfig, bookSize: size,
  }), [kind, mode, value.stageModels, stages, mangaPageCount, appConfig, size]);

  function applyToGroup(purpose: 'text' | 'image', model: string) {
    if (!model) return;
    const next = { ...value.stageModels };
    for (const stage of stages.filter(s => s.purpose === purpose)) next[stage.id] = model;
    onChange({ ...value, stageModels: next });
  }

  const models = (purpose: 'text' | 'image') => purpose === 'text' ? TEXT_MODELS : IMAGE_MODELS;
  const modelSummary = `${TEXT_MODELS.find(m => m.id === chapterModel)?.label || 'Testo personalizzato'} · ${kind === 'book' ? 'copertina inclusa' : 'immagini configurabili'}`;

  return <div className="model-settings">
    {showGenerationMode && <fieldset className="writing-mode-picker">
      <legend>Come vuoi sviluppare il testo?</legend>
      <p>La modalità cambia l’ampiezza dei capitoli. Potrai rivedere il piano prima della scrittura.</p>
      <div className="writing-mode-options">
        {WRITING_MODES.map(option => <label key={option.id} className={`writing-mode-option ${mode === option.id ? 'selected' : ''}`}>
          <input type="radio" name="writing-mode" value={option.id} checked={mode === option.id}
            onChange={() => onChange({ ...value, generationMode: option.id })} />
          <span><strong>{option.label}</strong><small>{option.hint}</small></span>
          <p>{option.description}</p>
          <em>{sizes?.[option.id].available ? `~${sizes[option.id].pages} pagine dallo storico` : 'Storico da costruire'}</em>
        </label>)}
      </div>
    </fieldset>}

    <aside className="generation-forecast" aria-label="Previsione del progetto" aria-live="polite">
      <span className="forecast-eyebrow">IL TUO PROGETTO</span>
      <h3>{kind === 'book' ? 'Quanto potrebbe diventare lungo' : 'La previsione del manga'}</h3>
      {kind === 'book' && !size?.available ? <div className="forecast-empty">
        <p>{historyError || (!sizes ? 'Lettura dello storico…' : `Nessun libro ${mode === 'ultra' ? 'Ultra' : 'Standard'} completato, per ora.`)}</p>
        {historyError ? <button type="button" onClick={() => setRetry(n => n + 1)}>Riprova</button>
          : <small>La stima di pagine e costo si baserà sui libri completati in questa modalità. Puoi iniziare anche senza uno storico.</small>}
      </div> : <>
        {kind === 'book' && size && <>
          <div className="forecast-pages"><strong>~{size.pages}</strong><span>pagine di testo</span></div>
          <p>{size.chapters} capitoli {size.chapter_basis === 'requested_length' ? 'per l’ampiezza scelta' : 'stimati dallo storico'} · circa {size.words?.toLocaleString('it-IT')} parole</p>
          {size.pages_low !== size.pages_high && <p>Variabilità osservata: {size.pages_low}–{size.pages_high} pagine.</p>}
          <p className="forecast-source">{size.sample_count} {size.sample_count === 1 ? 'libro completato' : 'libri completati'} · {mode === 'ultra' ? 'Ultra' : 'Standard'}{size.scope.includes('model') ? ' · stesso modello' : ' · tutti i modelli'}{size.scope.includes('length') ? ' · stessa ampiezza' : ''}.{size.limited_history ? ' Pochi dati: previsione indicativa.' : ''}</p>
        </>}
        <div className="forecast-metrics">
          <div><Coins size={15} /><strong>{estimate.costEur == null ? '—' : `~${formatEstimateCost(estimate.costEur)}`}</strong><span>costo previsto</span></div>
          <div><Clock3 size={15} /><strong>{estimate.minutes == null ? '—' : formatEstimateTime(estimate.minutes)}</strong><span>tempo indicativo</span></div>
        </div>
        {estimate.costLowEur != null && estimate.costHighEur != null && estimate.costLowEur !== estimate.costHighEur && <p>Al variare dell’estensione: {formatEstimateCost(estimate.costLowEur)}–{formatEstimateCost(estimate.costHighEur)}.</p>}
        <details className="forecast-method"><summary>Come viene calcolata</summary>
          <p>{estimate.assumptions}</p>
          {size && <p>Mediana delle parole per capitolo nello storico della modalità; {size.words_per_page} parole per pagina. La fascia mostra la variabilità delle estensioni, non un tetto di spesa. La paginazione PDF può variare. Il tempo usa un modello indicativo per modalità.</p>}
          <p>Il consumo effettivo sarà disponibile nel taccuino. L’ascolto è facoltativo ed escluso dalla previsione.</p>
        </details>
      </>}
    </aside>

    <Disclosure title="Modelli AI" summary={modelSummary}>
      <p className="model-settings-intro">Le scelte iniziali sono già pronte. Cambiale per privilegiare velocità o dettaglio.</p>
      {(['text', 'image'] as const).map(purpose => {
        const group = stages.filter(s => s.purpose === purpose);
        if (!group.length) return null;
        const selected = sharedModel(group, value.stageModels) || '';
        return <label className="model-select-row" key={purpose}>
          <span>{purpose === 'text' ? 'Testo' : 'Immagini'}</span>
          <select aria-label={purpose === 'text' ? 'Modello per tutto il testo' : 'Modello per tutte le immagini'} value={selected} onChange={event => applyToGroup(purpose, event.target.value)}>
            <option value="">Personalizzati per fase</option>
            {models(purpose).map(model => <option key={model.id} value={model.id}>{model.label} · {model.hint}</option>)}
          </select>
        </label>;
      })}
      <Disclosure title="Personalizza per fase" summary="Usa modelli diversi nei singoli passaggi.">
        <div className="model-stage-list">{stages.map(stage => <label className="model-select-row" key={stage.id}>
          <span>{stage.label}</span><select aria-label={`Modello per ${stage.label}`} value={value.stageModels[stage.id] || stage.defaultModel}
            onChange={event => onChange({ ...value, stageModels: { ...value.stageModels, [stage.id]: event.target.value } })}>
            {models(stage.purpose).map(model => <option key={model.id} value={model.id}>{model.label}</option>)}
          </select>
        </label>)}</div>
      </Disclosure>
      <p className="model-tts-note">Audio facoltativo: {TTS_MODEL_LABEL}.</p>
    </Disclosure>
  </div>;
}

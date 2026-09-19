import { useEffect, useMemo, useState } from 'react';
import { Clock3, Coins } from 'lucide-react';
import { getAppConfig, type AppConfig } from '../api/client';
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
    hint: '1 passata',
    description: 'Un passaggio per capitolo, più rapido',
  },
  {
    id: 'ultra',
    label: 'Ultra',
    hint: '2 passate',
    description: 'Due passaggi per capitolo, testi più estesi',
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

function OptionChip({
  selected,
  label,
  hint,
  description,
  onClick,
}: {
  selected: boolean;
  label: string;
  hint: string;
  description?: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className={`option-chip ${selected ? 'selected' : ''}`}
      onClick={onClick}
      aria-pressed={selected}
      title={description}
    >
      <strong>{label}</strong>
      <em>{hint}</em>
    </button>
  );
}

export default function ModelSettingsPanel({
  value,
  onChange,
  stages,
  showGenerationMode = false,
  kind,
  mangaPageCount,
}: ModelSettingsPanelProps) {
  const [appConfig, setAppConfig] = useState<AppConfig | null>(null);
  const textStages = stages.filter((stage) => stage.purpose === 'text');
  const imageStages = stages.filter((stage) => stage.purpose === 'image');
  const selectedText = sharedModel(textStages, value.stageModels);
  const selectedImage = sharedModel(imageStages, value.stageModels);

  useEffect(() => {
    getAppConfig()
      .then(setAppConfig)
      .catch(() => setAppConfig(null));
  }, []);

  const estimate = useMemo(
    () =>
      estimateGeneration({
        kind,
        generationMode: value.generationMode || 'standard',
        stageModels: value.stageModels,
        stages,
        mangaPageCount,
        config: appConfig,
      }),
    [appConfig, kind, mangaPageCount, stages, value.generationMode, value.stageModels],
  );

  const applyToGroup = (group: StageOption[], modelId: string) => {
    const nextStages = { ...value.stageModels };
    for (const stage of group) {
      nextStages[stage.id] = modelId;
    }
    onChange({ ...value, stageModels: nextStages });
  };

  const setStageModel = (stageId: string, modelId: string) => {
    onChange({
      ...value,
      stageModels: {
        ...value.stageModels,
        [stageId]: modelId,
      },
    });
  };

  return (
    <div className="model-settings">
      {showGenerationMode ? (
        <section className="model-settings-card">
          <div className="model-settings-heading">
            <span>Modalità di scrittura</span>
            <p>Quante passate per ogni capitolo. Non cambia il modello: Standard una passata, Ultra due.</p>
          </div>
          <div className="option-chip-row" role="radiogroup" aria-label="Modalità di scrittura">
            {WRITING_MODES.map((mode) => (
              <OptionChip
                key={mode.id}
                selected={value.generationMode === mode.id}
                label={mode.label}
                hint={mode.hint}
                description={mode.description}
                onClick={() => onChange({ ...value, generationMode: mode.id })}
              />
            ))}
          </div>
        </section>
      ) : null}

      {textStages.length > 0 ? (
        <section className="model-settings-card">
          <div className="model-settings-heading">
            <span>Modelli di testo</span>
            <p>La riga per fase è quella effettiva. Le card in alto applicano lo stesso modello a tutte le fasi di testo.</p>
          </div>
          <span className="group-caption">Applica a tutte</span>
          <div className="option-chip-row" role="radiogroup" aria-label="Applica modello testo a tutte le fasi">
            {TEXT_MODELS.map((model) => (
              <OptionChip
                key={model.id}
                selected={selectedText === model.id}
                label={model.label}
                hint={model.hint}
                description={`Usa ${model.label} per tutte le fasi di testo`}
                onClick={() => applyToGroup(textStages, model.id)}
              />
            ))}
          </div>
          {selectedText === null ? (
            <p className="mixed-hint">Le fasi di testo usano modelli diversi. Scegli una card sopra per allinearle, oppure modifica fase per fase.</p>
          ) : null}
          <div className="stage-list">
            <span className="stage-list-caption">Per fase</span>
            {textStages.map((stage) => {
              const selected = value.stageModels[stage.id] || stage.defaultModel;
              return (
                <div key={stage.id} className="stage-row">
                  <span>{stage.label}</span>
                  <div className="option-chip-row compact" role="radiogroup" aria-label={`Modello per ${stage.label}`}>
                    {TEXT_MODELS.map((model) => (
                      <OptionChip
                        key={model.id}
                        selected={selected === model.id}
                        label={model.label}
                        hint={model.hint}
                        onClick={() => setStageModel(stage.id, model.id)}
                      />
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      ) : null}

      {imageStages.length > 0 ? (
        <section className="model-settings-card">
          <div className="model-settings-heading">
            <span>Modelli di immagini</span>
            <p>Stessa logica: le card in alto allineano tutte le fasi visive, sotto scegli fase per fase.</p>
          </div>
          <span className="group-caption">Applica a tutte</span>
          <div className="option-chip-row" role="radiogroup" aria-label="Applica modello immagini a tutte le fasi">
            {IMAGE_MODELS.map((model) => (
              <OptionChip
                key={model.id}
                selected={selectedImage === model.id}
                label={model.label}
                hint={model.hint}
                description={`Usa ${model.label} per tutte le immagini`}
                onClick={() => applyToGroup(imageStages, model.id)}
              />
            ))}
          </div>
          {selectedImage === null ? (
            <p className="mixed-hint">Le fasi visive usano modelli diversi. Scegli una card sopra per allinearle, oppure modifica fase per fase.</p>
          ) : null}
          <div className="stage-list">
            <span className="stage-list-caption">Per fase</span>
            {imageStages.map((stage) => {
              const selected = value.stageModels[stage.id] || stage.defaultModel;
              return (
                <div key={stage.id} className="stage-row">
                  <span>{stage.label}</span>
                  <div className="option-chip-row compact" role="radiogroup" aria-label={`Modello per ${stage.label}`}>
                    {IMAGE_MODELS.map((model) => (
                      <OptionChip
                        key={model.id}
                        selected={selected === model.id}
                        label={model.label}
                        hint={model.hint}
                        onClick={() => setStageModel(stage.id, model.id)}
                      />
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      ) : null}

      <p className="model-tts-note">
        Audio: {TTS_MODEL_LABEL}, fisso. Non entra in questa stima: si genera solo se ascolti un capitolo o la critica, uno alla volta.
      </p>

      <aside className="estimate-bar" aria-live="polite">
        <div className="estimate-heading">Stima di generazione</div>
        <div className="estimate-metric">
          <Clock3 size={16} />
          <strong>{formatEstimateTime(estimate.minutes)}</strong>
          <span>tempo stimato</span>
        </div>
        <div className="estimate-metric">
          <Coins size={16} />
          <strong>~{formatEstimateCost(estimate.costEur)}</strong>
          <span>costo stimato</span>
        </div>
        <p>
          {estimate.assumptions} Include testo e copertina, non l’ascolto. Si aggiorna quando cambi le opzioni.
        </p>
      </aside>
    </div>
  );
}

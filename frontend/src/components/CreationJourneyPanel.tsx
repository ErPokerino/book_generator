import { Gauge, RefreshCw, Save, type LucideIcon } from 'lucide-react';
import './CreationJourneyPanel.css';

export type GenerationMode = 'standard' | 'ultra';

interface CreationJourneyPanelProps {
  currentStep: 'form' | 'questions' | 'draft' | 'summary' | 'writing';
  selectedMode?: GenerationMode;
  sessionId?: string | null;
  restoreStatus?: 'restored' | 'failed' | 'idle';
}

interface SummaryItem {
  key: string;
  icon: LucideIcon;
  label: string;
  value: string;
  hint?: string;
}

const MODE_COPY: Record<GenerationMode, { label: string }> = {
  standard: { label: 'Standard' },
  ultra: { label: 'Ultra' },
};

const STEP_LABELS: Record<CreationJourneyPanelProps['currentStep'], string> = {
  form: 'Idea',
  questions: 'Domande',
  draft: 'Bozza',
  summary: 'Struttura',
  writing: 'Scrittura',
};

const STEP_DESCRIPTIONS: Record<CreationJourneyPanelProps['currentStep'], string> = {
  form: 'Compila i campi essenziali per impostare il libro.',
  questions: 'Aggiungi i dettagli che guideranno il progetto narrativo.',
  draft: 'Rifinisci la bozza prima di passare alla struttura.',
  summary: 'Controlla la struttura finale prima di avviare la scrittura.',
  writing: 'Segui l avanzamento della generazione.',
};

export default function CreationJourneyPanel({
  currentStep,
  selectedMode = 'standard',
  sessionId,
  restoreStatus = 'idle',
}: CreationJourneyPanelProps) {
  const modeInfo = MODE_COPY[selectedMode];
  const sessionSummary: SummaryItem | null =
    restoreStatus === 'restored' && sessionId
      ? {
          key: 'session',
          icon: RefreshCw,
          label: 'Sessione',
          value: `Ripresa ${sessionId.slice(0, 8)}`,
          hint: 'Continui dal punto salvato.',
        }
      : restoreStatus === 'failed'
        ? {
            key: 'session',
            icon: RefreshCw,
            label: 'Sessione',
            value: 'Nuova sessione',
            hint: 'Ripristino non disponibile.',
          }
        : null;

  const summaryItems: SummaryItem[] = [
    {
      key: 'mode',
      icon: Gauge,
      label: 'Modalità',
      value: modeInfo.label,
    },
    ...(sessionSummary ? [sessionSummary] : []),
  ];

  return (
    <section className="creation-journey-panel" aria-label="Stato creazione libro">
      <div className="creation-journey-card creation-journey-card-highlight">
        <div className="creation-journey-copy">
          <div className="creation-journey-heading">
            <span className="creation-journey-eyebrow">Percorso attivo</span>
            <strong>{STEP_LABELS[currentStep]}</strong>
          </div>
          <p>{STEP_DESCRIPTIONS[currentStep]}</p>
        </div>
        <span className="creation-journey-chip">
          <Save size={16} />
          Autosave attivo
        </span>
      </div>

      <div className="creation-journey-summary" aria-label="Riepilogo rapido">
        {summaryItems.map((item) => {
          const Icon = item.icon;

          return (
            <article className="creation-journey-summary-item" key={item.key}>
              <div className="creation-journey-summary-icon">
                <Icon size={16} />
              </div>
              <div className="creation-journey-summary-copy">
                <span className="creation-journey-summary-label">{item.label}</span>
                <strong className="creation-journey-summary-value">{item.value}</strong>
                {item.hint ? <span className="creation-journey-summary-hint">{item.hint}</span> : null}
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}

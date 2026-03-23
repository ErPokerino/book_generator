import { Clock3, Coins, RefreshCw, Save, type LucideIcon } from 'lucide-react';
import { MODE_COSTS, ModeType } from '../api/client';
import './CreationJourneyPanel.css';

interface CreationJourneyPanelProps {
  currentStep: 'form' | 'questions' | 'draft' | 'summary' | 'writing';
  selectedMode?: ModeType;
  sessionId?: string | null;
  restoreStatus?: 'restored' | 'failed' | 'idle';
  userPoints?: number | null;
  nextPointsReset?: string | null;
}

interface SummaryItem {
  key: string;
  icon: LucideIcon;
  label: string;
  value: string;
  hint?: string;
}

const MODE_COPY: Record<ModeType, { label: string; duration: string }> = {
  flash: { label: 'Flash', duration: '5-10 min' },
  pro: { label: 'Pro', duration: '8-15 min' },
  ultra: { label: 'Ultra', duration: '10-20 min' },
};

const STEP_LABELS: Record<CreationJourneyPanelProps['currentStep'], string> = {
  form: 'Setup',
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
  writing: 'Segui l avanzamento della generazione e delle revisioni.',
};

function formatResetDate(value?: string | null) {
  if (!value) return 'non disponibile';
  try {
    return new Date(value).toLocaleString('it-IT', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return value;
  }
}

export default function CreationJourneyPanel({
  currentStep,
  selectedMode = 'flash',
  sessionId,
  restoreStatus = 'idle',
  userPoints = null,
  nextPointsReset = null,
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
      icon: Coins,
      label: 'Modalita',
      value: modeInfo.label,
      hint: `${MODE_COSTS[selectedMode]} ${MODE_COSTS[selectedMode] === 1 ? 'punto' : 'punti'}`,
    },
    {
      key: 'duration',
      icon: Clock3,
      label: 'Tempo',
      value: modeInfo.duration,
      hint: 'Stima media',
    },
    ...(sessionSummary ? [sessionSummary] : []),
    {
      key: 'balance',
      icon: Coins,
      label: 'Saldo',
      value: userPoints == null ? '...' : String(userPoints),
      hint: nextPointsReset ? `Reset ${formatResetDate(nextPointsReset)}` : 'Punti disponibili',
    },
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

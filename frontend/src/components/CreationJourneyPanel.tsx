import { Clock3, Coins, RefreshCw, Save } from 'lucide-react';
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

  return (
    <section className="creation-journey-panel" aria-label="Stato creazione libro">
      <div className="creation-journey-card creation-journey-card-highlight">
        <div className="creation-journey-copy">
          <span className="creation-journey-eyebrow">Percorso attivo</span>
          <strong>{STEP_LABELS[currentStep]}</strong>
          <p>
            La sessione viene salvata automaticamente nel browser e pu{'\u00f2'} essere ripresa se torni in seguito.
          </p>
        </div>
        <span className="creation-journey-chip">
          <Save size={16} />
          Autosave attivo
        </span>
      </div>

      <div className="creation-journey-grid">
        <article className="creation-journey-card">
          <div className="creation-journey-icon">
            <Coins size={18} />
          </div>
          <div>
            <span className="creation-journey-label">Modalit{'\u00e0'} selezionata</span>
            <strong>{modeInfo.label}</strong>
            <p>{MODE_COSTS[selectedMode]} punti per avviare la scrittura.</p>
          </div>
        </article>

        <article className="creation-journey-card">
          <div className="creation-journey-icon">
            <Clock3 size={18} />
          </div>
          <div>
            <span className="creation-journey-label">Tempo atteso</span>
            <strong>{modeInfo.duration}</strong>
            <p>Stima media per outline, scrittura e critica finale.</p>
          </div>
        </article>

        <article className="creation-journey-card">
          <div className="creation-journey-icon">
            <RefreshCw size={18} />
          </div>
          <div>
            <span className="creation-journey-label">Ripristino sessione</span>
            <strong>
              {restoreStatus === 'restored' && sessionId ? `Ripresa ${sessionId.slice(0, 8)}` : restoreStatus === 'failed' ? 'Ripristino fallito' : 'Nuova sessione'}
            </strong>
            <p>
              {restoreStatus === 'restored'
                ? 'Hai ripreso il flusso dal punto salvato.'
                : restoreStatus === 'failed'
                ? 'La sessione precedente non era piu disponibile.'
                : 'Verra creata una nuova sessione quando inizi il flusso.'}
            </p>
          </div>
        </article>

        <article className="creation-journey-card">
          <div className="creation-journey-icon">
            <Coins size={18} />
          </div>
          <div>
            <span className="creation-journey-label">Saldo disponibile</span>
            <strong>{userPoints ?? '...'}</strong>
            <p>Reset previsto: {formatResetDate(nextPointsReset)}</p>
          </div>
        </article>
      </div>
    </section>
  );
}

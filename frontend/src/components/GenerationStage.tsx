import { ReactNode } from 'react';
import Meter from './ui/Meter';
import './GenerationStage.css';

interface GenerationStageProps {
  title: string;
  phase: string;
  elapsed?: string | null;
  cost?: string | null;
  estimate?: string | null;
  progress?: number | null;
  children?: ReactNode;
  actions?: ReactNode;
}

export default function GenerationStage({
  title,
  phase,
  elapsed,
  cost,
  estimate,
  progress,
  children,
  actions,
}: GenerationStageProps) {
  return (
    <section className="generation-stage">
      <header className="generation-stage-header">
        <h2 className="work-title">{title}</h2>
        <p>{phase}</p>
      </header>
      {progress != null ? <Meter value={progress} label="Avanzamento generazione" /> : null}
      <dl className="generation-stage-metrics">
        {elapsed != null ? (
          <div>
            <dt>Tempo</dt>
            <dd>{elapsed}</dd>
          </div>
        ) : null}
        {cost != null ? (
          <div>
            <dt>Costo</dt>
            <dd>{cost}</dd>
          </div>
        ) : null}
        {estimate != null ? (
          <div>
            <dt>Stima finale</dt>
            <dd>{estimate}</dd>
          </div>
        ) : null}
      </dl>
      {children}
      {actions ? <div className="generation-stage-actions">{actions}</div> : null}
    </section>
  );
}

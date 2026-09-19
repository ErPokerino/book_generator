import { LiteraryCritique } from '../api/client';
import AudioPlayer from './AudioPlayer';
import './CritiqueBlock.css';

function getScoreColor(score: number): string {
  const normalizedScore = Math.max(0, Math.min(10, score));

  if (normalizedScore <= 5) {
    const ratio = normalizedScore / 5;
    const r = Math.round(180 + (161 - 180) * ratio);
    const g = Math.round(35 + (98 - 35) * ratio);
    const b = Math.round(24 + (7 - 24) * ratio);
    return `rgb(${r}, ${g}, ${b})`;
  }

  const ratio = (normalizedScore - 5) / 5;
  const r = Math.round(161 - (161 - 63) * ratio);
  const g = Math.round(98 + (98 - 98) * ratio);
  const b = Math.round(7 + (18 - 7) * ratio);
  return `rgb(${r}, ${g}, ${b})`;
}

interface CritiqueBlockProps {
  critique: LiteraryCritique;
  sessionId?: string;
  showAudio?: boolean;
}

export default function CritiqueBlock({ critique, sessionId, showAudio = false }: CritiqueBlockProps) {
  return (
    <section className="critique-block">
      <header className="critique-block-header">
        <span>Valutazione</span>
        <strong style={{ color: getScoreColor(critique.score) }}>{critique.score.toFixed(1)}</strong>
      </header>

      {showAudio && sessionId ? <AudioPlayer sessionId={sessionId} type="critique" /> : null}

      {critique.summary ? (
        <div className="critique-block-section">
          <h3>Sintesi</h3>
          <p>{critique.summary}</p>
        </div>
      ) : null}

      {critique.pros?.length ? (
        <div className="critique-block-section">
          <h3>Punti di forza</h3>
          <ul>
            {critique.pros.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {critique.cons?.length ? (
        <div className="critique-block-section">
          <h3>Punti di debolezza</h3>
          <ul>
            {critique.cons.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

import { useState, useEffect } from 'react';
import { getBookCritique, LiteraryCritique } from '../api/client';
import './CritiqueModal.css';

interface CritiqueModalProps {
  sessionId: string;
  bookTitle: string;
  isOpen: boolean;
  onClose: () => void;
}

// Funzione per calcolare il colore del voto (riutilizzata da WritingStep)
const getScoreColor = (score: number): string => {
  const normalizedScore = Math.max(0, Math.min(10, score));
  
  if (normalizedScore <= 5) {
    const ratio = normalizedScore / 5;
    const r = 220;
    const g = Math.round(53 + (180 - 53) * ratio);
    const b = Math.round(38 + (35 - 38) * ratio);
    return `rgb(${r}, ${g}, ${b})`;
  } else {
    const ratio = (normalizedScore - 5) / 5;
    const r = Math.round(220 - (220 - 16) * ratio);
    const g = Math.round(180 - (180 - 185) * ratio);
    const b = Math.round(35 + (129 - 35) * ratio);
    return `rgb(${r}, ${g}, ${b})`;
  }
};

export default function CritiqueModal({ sessionId, bookTitle, isOpen, onClose }: CritiqueModalProps) {
  const [critique, setCritique] = useState<LiteraryCritique | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Gestione ESC per chiudere
  useEffect(() => {
    if (!isOpen) return;

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen, onClose]);

  // Carica critica quando il modal si apre
  useEffect(() => {
    if (!isOpen || !sessionId) {
      setCritique(null);
      setError(null);
      return;
    }

    const loadCritique = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await getBookCritique(sessionId);
        setCritique(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Errore nel caricamento della critica');
      } finally {
        setLoading(false);
      }
    };

    loadCritique();
  }, [isOpen, sessionId]);

  if (!isOpen) return null;

  return (
    <div className="critique-modal-overlay" onClick={onClose}>
      <div className="critique-modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="critique-modal-header">
          <h2>📚 Valutazione Critica</h2>
          <button className="critique-modal-close" onClick={onClose} aria-label="Chiudi">
            ✕
          </button>
        </div>
        
        <div className="critique-modal-body">
          <p className="critique-modal-subtitle">{bookTitle}</p>
          
          {loading && (
            <div className="critique-modal-loading">
              <p>Caricamento critica...</p>
            </div>
          )}

          {error && (
            <div className="critique-modal-error">
              <p>Errore: {error}</p>
            </div>
          )}

          {!loading && !error && critique && (
            <div className="critique-section">
              <div className="critique-score">
                <span className="score-label">Valutazione:</span>
                <span 
                  className="score-value"
                  style={{ color: getScoreColor(critique.score) }}
                >
                  {critique.score.toFixed(1)}/10
                </span>
              </div>
              
              {critique.summary && (
                <div className="critique-summary">
                  <strong>Sintesi:</strong>
                  <p>{critique.summary}</p>
                </div>
              )}
              
              {critique.pros && critique.pros.length > 0 && (
                <div className="critique-pros">
                  <strong>Punti di forza:</strong>
                  <ul>
                    {critique.pros.map((p, idx) => (
                      <li key={idx}>{p}</li>
                    ))}
                  </ul>
                </div>
              )}
              
              {critique.cons && critique.cons.length > 0 && (
                <div className="critique-cons">
                  <strong>Punti di debolezza:</strong>
                  <ul>
                    {critique.cons.map((c, idx) => (
                      <li key={idx}>{c}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {!loading && !error && !critique && (
            <div className="critique-modal-empty">
              <p>Critica non disponibile per questo libro.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

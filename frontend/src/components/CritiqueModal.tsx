import { useState, useEffect } from 'react';
import { getBookCritique, LiteraryCritique } from '../api/client';
import CritiqueBlock from './CritiqueBlock';
import './CritiqueModal.css';

interface CritiqueModalProps {
  sessionId: string;
  bookTitle: string;
  isOpen: boolean;
  onClose: () => void;
}

// Funzione per rimuovere formattazione markdown dal testo
const stripMarkdownFormatting = (text: string): string => {
  if (!text) return text;
  return text
    .replace(/\*\*\*(.+?)\*\*\*/g, '$1')
    .replace(/\*\*(.+?)\*\*/g, '$1')
    .replace(/\*(.+?)\*/g, '$1')
    .replace(/___(.+?)___/g, '$1')
    .replace(/__(.+?)__/g, '$1')
    .replace(/_(.+?)_/g, '$1')
    .replace(/`(.+?)`/g, '$1');
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
          <h2>Valutazione</h2>
          <button className="critique-modal-close" onClick={onClose} aria-label="Chiudi">
            Chiudi
          </button>
        </div>
        
        <div className="critique-modal-body">
          <p className="critique-modal-subtitle">{stripMarkdownFormatting(bookTitle)}</p>
          
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

          {!loading && !error && critique ? (
            <CritiqueBlock critique={critique} sessionId={sessionId} showAudio />
          ) : null}

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

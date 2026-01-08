import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../contexts/AuthContext';
import './PlotTextarea.css';

interface PlotTextareaProps {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  label?: React.ReactNode;
  placeholder?: string;
  minWordsHint?: number;
  error?: string;
  id?: string;
}

const STORAGE_KEY_PREFIX = 'newBook.plot';

export default function PlotTextarea({
  value,
  onChange,
  disabled = false,
  label,
  placeholder,
  minWordsHint = 50,
  error,
  id = 'plot',
}: PlotTextareaProps) {
  const { user } = useAuth();
  const [isExpanded, setIsExpanded] = useState(false);
  const [hasRestored, setHasRestored] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const expandedTextareaRef = useRef<HTMLTextAreaElement>(null);

  // Chiave localStorage legata all'utente (se disponibile)
  const storageKey = user?.email
    ? `${STORAGE_KEY_PREFIX}.${user.email}`
    : STORAGE_KEY_PREFIX;

  // Restore da localStorage al mount (solo se value è vuoto)
  useEffect(() => {
    if (value || hasRestored) return;

    try {
      const saved = localStorage.getItem(storageKey);
      if (saved && saved.trim()) {
        onChange(saved);
        setHasRestored(true);
      }
    } catch (err) {
      console.warn('[PlotTextarea] Errore nel restore da localStorage:', err);
    }
  }, [value, storageKey, hasRestored, onChange]);

  // Autosave debounced (300ms)
  useEffect(() => {
    if (!value.trim() || disabled) return;

    const timeoutId = setTimeout(() => {
      try {
        localStorage.setItem(storageKey, value);
      } catch (err) {
        console.warn('[PlotTextarea] Errore nell\'autosave:', err);
      }
    }, 300);

    return () => clearTimeout(timeoutId);
  }, [value, storageKey, disabled]);

  // Calcola statistiche
  const wordCount = value.trim() ? value.trim().split(/\s+/).length : 0;
  const charCount = value.length;

  // Placeholder con esempio se non fornito
  const defaultPlaceholder = "Descrivi la trama del tuo libro... (es: Un giovane mago scopre di avere poteri straordinari e deve salvare il mondo da un'antica minaccia oscura. Durante il suo viaggio, incontra alleati inaspettati e scopre segreti sul suo passato che cambieranno per sempre il suo destino.)";
  const displayPlaceholder = placeholder || defaultPlaceholder;

  // Auto-resize del textarea principale
  useEffect(() => {
    if (textareaRef.current) {
      // Reset height per calcolare correttamente scrollHeight
      textareaRef.current.style.height = 'auto';
      // Imposta l'altezza in base al contenuto
      const scrollHeight = textareaRef.current.scrollHeight;
      textareaRef.current.style.height = `${scrollHeight}px`;
    }
  }, [value]);

  // Auto-resize del textarea espanso
  useEffect(() => {
    if (expandedTextareaRef.current && isExpanded) {
      // Reset height per calcolare correttamente scrollHeight
      expandedTextareaRef.current.style.height = 'auto';
      // Imposta l'altezza in base al contenuto, con un minimo
      const scrollHeight = expandedTextareaRef.current.scrollHeight;
      expandedTextareaRef.current.style.height = `${Math.max(scrollHeight, 400)}px`;
    }
  }, [value, isExpanded]);

  const handleOpenExpanded = () => {
    setIsExpanded(true);
  };

  const handleCloseExpanded = () => {
    setIsExpanded(false);
    // Focus sulla textarea normale dopo chiusura
    setTimeout(() => {
      textareaRef.current?.focus();
    }, 100);
  };

  const handleExpandedChange = (newValue: string) => {
    onChange(newValue);
  };

  // Keyboard handler per Esc nel modal
  useEffect(() => {
    if (!isExpanded) return;

    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        handleCloseExpanded();
      }
    };

    document.addEventListener('keydown', handleEsc);
    // Blocca scroll body
    document.body.style.overflow = 'hidden';

    return () => {
      document.removeEventListener('keydown', handleEsc);
      document.body.style.overflow = '';
    };
  }, [isExpanded]);

  // Focus sulla textarea espansa quando si apre
  useEffect(() => {
    if (isExpanded && expandedTextareaRef.current) {
      setTimeout(() => {
        expandedTextareaRef.current?.focus();
        // Posiziona il cursore alla fine
        const len = expandedTextareaRef.current.value.length;
        expandedTextareaRef.current.setSelectionRange(len, len);
      }, 100);
    }
  }, [isExpanded]);

  return (
    <>
      <div className="plot-textarea-wrapper">
        {label && (
          <label htmlFor={id}>
            {label}
          </label>
        )}
        <div className="plot-textarea-container">
          <textarea
            ref={textareaRef}
            id={id}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder={displayPlaceholder}
            disabled={disabled}
            rows={6}
            className={`plot-textarea ${error ? 'error' : ''}`}
          />
          <button
            type="button"
            onClick={handleOpenExpanded}
            disabled={disabled}
            className="plot-expand-btn"
            title="Espandi in modal"
          >
            ⛶ Espandi
          </button>
        </div>
        <div className="plot-textarea-footer">
          <div className="plot-counter">
            <span className="plot-word-count">{wordCount} parole</span>
            <span className="plot-char-count">{charCount} caratteri</span>
            {minWordsHint && wordCount > 0 && wordCount < minWordsHint && (
              <span className="plot-hint">
                (Consigliato almeno {minWordsHint} parole)
              </span>
            )}
          </div>
        </div>
        {error && <span className="error-message">{error}</span>}
      </div>

      {/* Modal Espanso */}
      {isExpanded && (
        <div className="plot-expanded-modal-overlay" onClick={handleCloseExpanded}>
          <div className="plot-expanded-modal" onClick={(e) => e.stopPropagation()}>
            <div className="plot-expanded-modal-header">
              <h3>{label || 'Trama'}</h3>
              <button
                type="button"
                onClick={handleCloseExpanded}
                className="plot-expanded-close-btn"
                title="Chiudi (Esc)"
              >
                ✕
              </button>
            </div>
            <div className="plot-expanded-modal-body">
              <textarea
                ref={expandedTextareaRef}
                value={value}
                onChange={(e) => handleExpandedChange(e.target.value)}
                placeholder={displayPlaceholder}
                disabled={disabled}
                className="plot-expanded-textarea"
              />
            </div>
            <div className="plot-expanded-modal-footer">
              <div className="plot-counter">
                <span className="plot-word-count">{wordCount} parole</span>
                <span className="plot-char-count">{charCount} caratteri</span>
                {minWordsHint && wordCount > 0 && wordCount < minWordsHint && (
                  <span className="plot-hint">
                    (Consigliato almeno {minWordsHint} parole)
                  </span>
                )}
              </div>
              <button
                type="button"
                onClick={handleCloseExpanded}
                className="plot-expanded-close-action-btn"
              >
                Chiudi
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

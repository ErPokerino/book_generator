import React, { useState, useEffect } from 'react';
import { getBookProgress, BookProgress, downloadBookPdf } from '../api/client';
import BookViewer from './BookViewer';
import './WritingStep.css';

interface WritingStepProps {
  sessionId: string;
  onComplete?: (progress: BookProgress) => void;
}

export default function WritingStep({ sessionId, onComplete }: WritingStepProps) {
  const [progress, setProgress] = useState<BookProgress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isPolling, setIsPolling] = useState(true);
  const [showBookViewer, setShowBookViewer] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);

  useEffect(() => {
    if (!sessionId || !isPolling) return;

    const pollProgress = async () => {
      try {
        const currentProgress = await getBookProgress(sessionId);
        setProgress(currentProgress);
        
        // Se completato o errore, ferma il polling
        if (currentProgress.is_complete || currentProgress.error) {
          setIsPolling(false);
          if (onComplete && currentProgress.is_complete) {
            onComplete(currentProgress);
          }
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Errore nel recupero del progresso');
        setIsPolling(false);
      }
    };

    // Polling ogni 2 secondi
    const intervalId = setInterval(pollProgress, 2000);
    
    // Prima chiamata immediata
    pollProgress();

    return () => clearInterval(intervalId);
  }, [sessionId, isPolling, onComplete]);

  if (error) {
    return (
      <div className="writing-step">
        <div className="error-container">
          <h3>Errore durante la scrittura</h3>
          <p>{error}</p>
        </div>
      </div>
    );
  }

  if (!progress) {
    return (
      <div className="writing-step">
        <div className="loading">
          <p>Caricamento stato di avanzamento...</p>
        </div>
      </div>
    );
  }

  // Se total_steps è 0, significa che il processo non è ancora partito o c'è un problema
  if (progress.total_steps === 0) {
    return (
      <div className="writing-step">
        <div className="loading">
          <h3>Inizializzazione in corso...</h3>
          <p>Sto preparando la scrittura del romanzo. Questo potrebbe richiedere alcuni secondi.</p>
          {progress.error && (
            <div className="error-message" style={{ marginTop: '1rem' }}>
              <strong>Errore:</strong> {progress.error}
            </div>
          )}
        </div>
      </div>
    );
  }

  const progressPercentage = progress.total_steps > 0 
    ? Math.round((progress.current_step / progress.total_steps) * 100)
    : 0;

  return (
    <div className="writing-step">
      <div className="writing-header">
        <h2>Scrittura del Romanzo in Corso</h2>
        {progress.is_complete && (
          <div className="completion-badge">✓ Completato!</div>
        )}
      </div>

      <div className="progress-container">
        <div className="progress-info">
          <span className="progress-text">
            {progress.is_complete 
              ? `Completato: ${progress.total_steps} sezioni scritte`
              : progress.current_section_name
                ? `Scrittura in corso: ${progress.current_section_name}...`
                : 'Preparazione...'}
          </span>
          <span className="progress-percentage">
            {progress.current_step} / {progress.total_steps}
          </span>
        </div>
        
        <div className="progress-bar-container">
          <div 
            className="progress-bar-fill"
            style={{ width: `${progressPercentage}%` }}
          />
        </div>
      </div>

      {progress.error && (
        <div className="error-message">
          <strong>Errore:</strong> {progress.error}
        </div>
      )}

      {progress.completed_chapters.length > 0 && (
        <div className="completed-chapters">
          <h3>Capitoli Completati ({progress.completed_chapters.length})</h3>
          <div className="chapters-list">
            {progress.completed_chapters.map((chapter, index) => (
              <div key={index} className="chapter-item">
                <h4>{chapter.title}</h4>
                <p className="chapter-preview">
                  {chapter.content.substring(0, 200)}...
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {progress.is_complete && (
        <div className="completion-message">
          <h3>🎉 Scrittura Completata!</h3>
          <p>Il romanzo è stato scritto completamente. Tutti i {progress.total_steps} capitoli sono stati generati.</p>
          <div className="completion-actions">
            <button
              onClick={() => setShowBookViewer(true)}
              className="view-book-button"
            >
              📖 Visualizza Libro Completo
            </button>
            <button
              onClick={async () => {
                if (!sessionId) {
                  alert('Errore: SessionId non disponibile.');
                  return;
                }
                
                try {
                  setIsDownloading(true);
                  console.log('[WritingStep] Avvio download PDF per sessione:', sessionId);
                  const blob = await downloadBookPdf(sessionId);
                  console.log('[WritingStep] PDF ricevuto, dimensione:', blob.size, 'bytes');
                  
                  if (blob.size === 0) {
                    throw new Error('Il PDF ricevuto è vuoto');
                  }
                  
                  const url = window.URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  // Usa il titolo dal progresso se disponibile, altrimenti un nome generico
                  const filename = `Libro_${sessionId.substring(0, 8)}.pdf`;
                  a.download = filename;
                  document.body.appendChild(a);
                  a.click();
                  console.log('[WritingStep] Download avviato, filename:', filename);
                  
                  setTimeout(() => {
                    window.URL.revokeObjectURL(url);
                    document.body.removeChild(a);
                  }, 100);
                } catch (err) {
                  console.error('[WritingStep] Errore nel download del PDF:', err);
                  alert(`Errore nel download del PDF: ${err instanceof Error ? err.message : 'Errore sconosciuto'}`);
                } finally {
                  setIsDownloading(false);
                }
              }}
              className="download-pdf-button"
              disabled={isDownloading}
            >
              {isDownloading ? '⏳ Download in corso...' : '📥 Scarica PDF'}
            </button>
          </div>
        </div>
      )}
    </div>
  );

  // Mostra il visualizzatore del libro se richiesto
  if (showBookViewer && sessionId) {
    return (
      <BookViewer
        sessionId={sessionId}
        onBack={() => setShowBookViewer(false)}
      />
    );
  }
}


import React, { useState, useEffect } from 'react';
import { getBookProgress, BookProgress, downloadBookPdf, regenerateBookCritique } from '../api/client';
import './WritingStep.css';

interface WritingStepProps {
  sessionId: string;
  onComplete?: (progress: BookProgress) => void;
}

export default function WritingStep({ sessionId, onComplete }: WritingStepProps) {
  const [progress, setProgress] = useState<BookProgress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isPolling, setIsPolling] = useState(true);
  const [isDownloading, setIsDownloading] = useState(false);
  const [isRetryingCritique, setIsRetryingCritique] = useState(false);

  useEffect(() => {
    if (!sessionId || !isPolling) return;

    const pollProgress = async () => {
      try {
        const currentProgress = await getBookProgress(sessionId);
        setProgress(currentProgress);

        const critiqueStatus = currentProgress.critique_status;
        const isCritiqueDone = critiqueStatus === 'completed' && !!currentProgress.critique;
        const isCritiqueFailed = critiqueStatus === 'failed';

        // Ferma il polling se:
        // - errore generale processo
        // - critica fallita (mostriamo errore + retry)
        // - critica completata
        if (currentProgress.error || isCritiqueFailed || isCritiqueDone) {
          setIsPolling(false);
          if (onComplete && isCritiqueDone) {
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

  const hasCritique = !!progress.critique;
  const critiqueStatus = progress.critique_status;
  const critiqueInProgress = critiqueStatus === 'running' || critiqueStatus === 'pending' || (progress.is_complete && !hasCritique && !critiqueStatus);
  const critiqueFailed = critiqueStatus === 'failed';
  const includeCritiqueStep = progress.is_complete;

  // Progress bar: aggiunge 1 step per la critica solo dopo completamento capitoli.
  // Finché la critica non è pronta, NON consideriamo completato lo step extra.
  const totalSteps = progress.total_steps + (includeCritiqueStep ? 1 : 0);
  const currentStep = progress.current_step + (includeCritiqueStep && hasCritique ? 1 : 0);

  const progressPercentage = totalSteps > 0 
    ? Math.round((currentStep / totalSteps) * 100)
    : 0;

  return (
    <div className="writing-step">
      <div className="writing-header">
        <h2>Scrittura del Romanzo in Corso</h2>
        {progress.is_complete && hasCritique && (
          <div className="completion-badge">✓ Completato!</div>
        )}
      </div>

      <div className="progress-container">
        <div className="progress-info">
          <span className="progress-text">
            {critiqueFailed
              ? 'Valutazione critica fallita'
              : critiqueInProgress
              ? 'Generazione valutazione critica in corso...'
              : progress.is_complete && hasCritique
              ? `Completato: ${progress.total_steps} sezioni scritte`
              : progress.current_section_name
                ? `Scrittura in corso: ${progress.current_section_name}...`
                : 'Preparazione...'}
          </span>
          <span className="progress-percentage">
            {currentStep} / {totalSteps}
          </span>
        </div>
        
        <div className="progress-bar-container">
          <div 
            className="progress-bar-fill"
            style={{ width: `${progressPercentage}%` }}
          />
        </div>
        {critiqueInProgress && (
          <div className="critique-loading-indicator">
            <span className="loading-spinner">⏳</span>
            <span>Generazione valutazione critica...</span>
          </div>
        )}

        {critiqueFailed && (
          <div className="critique-error-indicator">
            <div>
              <strong>Errore critica:</strong> {progress.critique_error || 'Errore sconosciuto'}
            </div>
            <button
              className="retry-critique-button"
              disabled={isRetryingCritique}
              onClick={async () => {
                try {
                  setIsRetryingCritique(true);
                  await regenerateBookCritique(sessionId);
                  setIsPolling(true);
                } catch (e) {
                  alert(`Errore nel retry della critica: ${e instanceof Error ? e.message : 'Errore sconosciuto'}`);
                } finally {
                  setIsRetryingCritique(false);
                }
              }}
            >
              {isRetryingCritique ? 'Riprovo...' : 'Riprova critica'}
            </button>
          </div>
        )}
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
                <div className="chapter-header">
                  <h4>{chapter.title}</h4>
                  {chapter.page_count > 0 && (
                    <span className="chapter-pages">{chapter.page_count} pagine</span>
                  )}
                </div>
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
          {hasCritique ? (
            <>
              <h3>🎉 Scrittura Completata!</h3>
              <p>Il romanzo è stato scritto completamente. Tutti i {progress.total_steps} capitoli sono stati generati.</p>
            </>
          ) : (
            <>
              <h3>📘 Scrittura completata</h3>
              <p>Capitoli generati. Sto completando la valutazione critica prima di chiudere il processo.</p>
            </>
          )}
          {progress.total_pages && (
            <p className="total-pages-info">
              <strong>Totale pagine:</strong> {progress.total_pages} pagine
            </p>
          )}
          <div className="completion-actions">
            <button
              onClick={async () => {
                if (!sessionId) {
                  alert('Errore: SessionId non disponibile.');
                  return;
                }
                
                try {
                  setIsDownloading(true);
                  console.log('[WritingStep] Avvio download PDF per sessione:', sessionId);
                  const { blob, filename } = await downloadBookPdf(sessionId);
                  console.log('[WritingStep] PDF ricevuto, dimensione:', blob.size, 'bytes');
                  
                  if (blob.size === 0) {
                    throw new Error('Il PDF ricevuto è vuoto');
                  }
                  
                  const url = window.URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
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
          {progress.critique && (
            <div className="critique-section">
              <h4>📚 Valutazione Critica</h4>
              <div className="critique-score">
                <span className="score-label">Valutazione:</span>
                <span className="score-value">{progress.critique.score.toFixed(1)}/10</span>
              </div>
              {progress.critique.summary && (
                <div className="critique-summary">
                  <strong>Sintesi:</strong>
                  <p>{progress.critique.summary}</p>
                </div>
              )}
              {progress.critique.pros && progress.critique.pros.length > 0 && (
                <div className="critique-pros">
                  <strong>Punti di forza:</strong>
                  <ul>
                    {progress.critique.pros.map((p, idx) => (
                      <li key={idx}>{p}</li>
                    ))}
                  </ul>
                </div>
              )}
              {progress.critique.cons && progress.critique.cons.length > 0 && (
                <div className="critique-cons">
                  <strong>Punti di debolezza:</strong>
                  <ul>
                    {progress.critique.cons.map((c, idx) => (
                      <li key={idx}>{c}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}


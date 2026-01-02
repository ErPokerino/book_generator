import React, { useState, useEffect } from 'react';
import { getBookProgress, BookProgress, regenerateBookCritique, getAppConfig, AppConfig, resumeBookGeneration } from '../api/client';
import AlertModal from './AlertModal';
import ExportDropdown from './ExportDropdown';
import './WritingStep.css';

interface WritingStepProps {
  sessionId: string;
  onComplete?: (progress: BookProgress) => void;
  onNewBook?: () => void;
}

export default function WritingStep({ sessionId, onComplete, onNewBook }: WritingStepProps) {
  const [progress, setProgress] = useState<BookProgress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isPolling, setIsPolling] = useState(true);
  const [isRetryingCritique, setIsRetryingCritique] = useState(false);
  const [isResuming, setIsResuming] = useState(false);
  const [appConfig, setAppConfig] = useState<AppConfig | null>(null);
  const [alertModal, setAlertModal] = useState<{ isOpen: boolean; title: string; message: string; variant?: 'error' | 'warning' | 'info' | 'success' }>({
    isOpen: false,
    title: '',
    message: '',
    variant: 'error',
  });

  const getScoreColor = (score: number): string => {
    // Score da 0 a 10
    const normalizedScore = Math.max(0, Math.min(10, score));
    
    if (normalizedScore <= 5) {
      // Rosso → Giallo (0-5)
      const ratio = normalizedScore / 5;
      const r = 220;
      const g = Math.round(53 + (180 - 53) * ratio);
      const b = Math.round(38 + (35 - 38) * ratio);
      return `rgb(${r}, ${g}, ${b})`;
    } else {
      // Giallo → Verde (5-10)
      const ratio = (normalizedScore - 5) / 5;
      const r = Math.round(220 - (220 - 16) * ratio);
      const g = Math.round(180 - (180 - 185) * ratio);
      const b = Math.round(35 + (129 - 35) * ratio);
      return `rgb(${r}, ${g}, ${b})`;
    }
  };

  // Carica la config app all'avvio
  useEffect(() => {
    getAppConfig().then(setAppConfig).catch(err => {
      console.warn('[WritingStep] Errore nel caricamento config app:', err);
      // Continua con valori di default
    });
  }, []);

  useEffect(() => {
    if (!sessionId || !isPolling) return;

    const pollProgress = async () => {
      try {
        const currentProgress = await getBookProgress(sessionId);
        // DEBUG: Log per verificare i valori ricevuti
        console.log('[WritingStep] Progress ricevuto:', {
          current_step: currentProgress.current_step,
          total_steps: currentProgress.total_steps,
          estimated_time_minutes: currentProgress.estimated_time_minutes,
          estimated_time_confidence: currentProgress.estimated_time_confidence,
          is_complete: currentProgress.is_complete
        });
        setProgress(currentProgress);

        const critiqueStatus = currentProgress.critique_status;
        const isCritiqueDone = critiqueStatus === 'completed' && !!currentProgress.critique;
        const isCritiqueFailed = critiqueStatus === 'failed';

        // Ferma il polling se:
        // - errore generale processo (ma NON se è paused - in quel caso mostriamo bottone ripresa)
        // - critica fallita (mostriamo errore + retry)
        // - critica completata
        const isPaused = currentProgress.is_paused === true;
        if (isPaused) {
          // Se è in pausa, ferma il polling ma non mostrare come errore fatale
          setIsPolling(false);
        } else if (currentProgress.error && !isPaused) {
          // Errore non gestito (non paused)
          setIsPolling(false);
        } else if (isCritiqueFailed || isCritiqueDone) {
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

    // Polling adattivo basato sulla config e sullo stato
    const getPollingInterval = (): number => {
      if (!appConfig) {
        return 2000; // Default
      }
      
      // Se in attesa critica, polling più lento
      if (progress?.is_complete && progress?.critique_status === 'pending') {
        return appConfig.frontend.polling_interval_critique || 5000;
      }
      
      return appConfig.frontend.polling_interval || 2000;
    };

    const pollingInterval = getPollingInterval();
    const intervalId = setInterval(pollProgress, pollingInterval);
    
    // Prima chiamata immediata
    pollProgress();

    return () => clearInterval(intervalId);
  }, [sessionId, isPolling, onComplete, appConfig, progress]);

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

        {/* Stima tempo rimanente - mostra sempre se disponibile e libro non completato */}
        {!progress.is_complete && progress.total_steps > 0 && (
          progress.estimated_time_minutes !== undefined && progress.estimated_time_minutes !== null ? (
            <div className="estimated-time">
              <span className="time-icon">⏱️</span>
              <span className="time-text">
                Tempo stimato: ~{Math.max(1, Math.round(progress.estimated_time_minutes))} minuti
                {progress.estimated_time_confidence === 'high' && ' (stima affidabile)'}
                {progress.estimated_time_confidence === 'medium' && ' (stima approssimativa)'}
                {progress.estimated_time_confidence === 'low' && ' (stima indicativa)'}
              </span>
            </div>
          ) : (
            <div className="estimated-time">
              <span className="time-icon">⏱️</span>
              <span className="time-text">Calcolo stima tempo in corso...</span>
            </div>
          )
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
                  setAlertModal({
                    isOpen: true,
                    title: 'Errore',
                    message: `Errore nel retry della critica: ${e instanceof Error ? e.message : 'Errore sconosciuto'}`,
                    variant: 'error',
                  });
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

      {progress.is_paused && progress.error && (
        <div className="error-message paused-message">
          <div>
            <strong>⚠️ Generazione in pausa</strong>
            <p>{progress.error}</p>
            <p style={{ fontSize: '0.9rem', color: '#666', marginTop: '0.5rem' }}>
              La generazione si è fermata dopo diversi tentativi. 
              Puoi riprendere la generazione dal capitolo fallito.
            </p>
          </div>
          <button
            className="resume-button"
            disabled={isResuming}
            onClick={async () => {
              try {
                setIsResuming(true);
                setError(null);
                await resumeBookGeneration(sessionId);
                // Riavvia il polling
                setIsPolling(true);
              } catch (e) {
                const errorMsg = e instanceof Error ? e.message : 'Errore sconosciuto';
                setError(`Errore nella ripresa: ${errorMsg}`);
                setAlertModal({
                  isOpen: true,
                  title: 'Errore',
                  message: `Errore nella ripresa della generazione: ${errorMsg}`,
                  variant: 'error',
                });
              } finally {
                setIsResuming(false);
              }
            }}
          >
            {isResuming ? 'Riprendo...' : '▶️ Riprendi Generazione'}
          </button>
        </div>
      )}

      {progress.error && !progress.is_paused && (
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
          {progress.writing_time_minutes && (
            <p className="writing-time-info">
              <strong>Totale tempo scrittura:</strong> {Math.round(progress.writing_time_minutes)} minuti
            </p>
          )}
          {progress.total_pages && (
            <p className="reading-time-info">
              <strong>Totale tempo lettura:</strong> {Math.ceil(progress.total_pages * 90 / 60)} minuti
            </p>
          )}
          {progress.estimated_cost != null && (
            <p className="estimated-cost-info">
              <strong>Costo stimato:</strong> €{progress.estimated_cost >= 0.01 ? progress.estimated_cost.toFixed(2) : progress.estimated_cost.toFixed(4)}
            </p>
          )}
          <div className="completion-actions">
            <ExportDropdown sessionId={sessionId} disabled={!progress?.is_complete} />
            {onNewBook && (
              <button
                onClick={onNewBook}
                className="new-book-button"
              >
                ✨ Genera Nuovo Romanzo
              </button>
            )}
          </div>
          {progress.critique && (
            <div className="critique-section">
              <h4>📚 Valutazione Critica</h4>
              <div className="critique-score">
                <span className="score-label">Valutazione:</span>
                <span 
                  className="score-value"
                  style={{ color: getScoreColor(progress.critique.score) }}
                >
                  {progress.critique.score.toFixed(1)}/10
                </span>
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

      <AlertModal
        isOpen={alertModal.isOpen}
        title={alertModal.title}
        message={alertModal.message}
        variant={alertModal.variant}
        onClose={() => setAlertModal({ isOpen: false, title: '', message: '' })}
      />
    </div>
  );
}


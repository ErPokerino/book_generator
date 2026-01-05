import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { getBookProgress, BookProgress, regenerateBookCritique, getAppConfig, AppConfig, resumeBookGeneration } from '../api/client';
import AlertModal from './AlertModal';
import ProgressBar from './ui/ProgressBar';
import FadeIn from './ui/FadeIn';
import { useToast } from '../hooks/useToast';
import './WritingStep.css';

interface WritingStepProps {
  sessionId: string;
  onComplete?: (progress: BookProgress) => void;
  onNewBook?: () => void;
}

export default function WritingStep({ sessionId, onComplete, onNewBook }: WritingStepProps) {
  const toast = useToast();
  const [progress, setProgress] = useState<BookProgress | null>(null);
  const [fatalError, setFatalError] = useState<string | null>(null);
  const [consecutiveFailures, setConsecutiveFailures] = useState(0);
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
  const latestProgressRef = useRef<BookProgress | null>(null);
  const consecutiveFailuresRef = useRef(0);

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
        latestProgressRef.current = currentProgress;
        consecutiveFailuresRef.current = 0;
        setConsecutiveFailures(0);

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
        const msg = err instanceof Error ? err.message : 'Errore nel recupero del progresso';
        // Non bloccare tutto al primo glitch: spesso è un micro-restart del backend o un timeout di rete.
        const next = consecutiveFailuresRef.current + 1;
        consecutiveFailuresRef.current = next;
        setConsecutiveFailures(next);
        
        // Mostra toast solo ogni 3 tentativi per evitare spam
        if (next % 3 === 1) {
          toast.error(`Connessione instabile (tentativo ${next}/10). Riprovo...`);
        }
        
        // Dopo molti tentativi falliti consecutivi, consideralo fatale.
        if (next >= 10) {
          setFatalError(msg);
          setIsPolling(false);
        }
      }
    };

    // Polling adattivo + backoff su errori di rete
    let cancelled = false;
    let timeoutId: number | null = null;

    const getBasePollingInterval = (current: BookProgress | null): number => {
      if (!appConfig) return 2000;
      if (current?.is_complete && current?.critique_status === 'pending') {
        return appConfig.frontend.polling_interval_critique || 5000;
      }
      return appConfig.frontend.polling_interval || 2000;
    };

    const scheduleNext = (delayMs: number) => {
      if (cancelled) return;
      timeoutId = window.setTimeout(async () => {
        await runOnce();
      }, delayMs);
    };

    const runOnce = async () => {
      if (cancelled) return;
      await pollProgress();

      // Se il polling è stato fermato dentro pollProgress (complete/errore/paused), non schedulare.
      if (cancelled) return;
      // Usa l'ultimo progress noto (se presente) per scegliere intervallo base.
      const base = getBasePollingInterval(latestProgressRef.current);
      // Backoff esponenziale su errori consecutivi (max 15s)
      const failures = consecutiveFailuresRef.current;
      const backoff = failures > 0 ? Math.min(15000, base * Math.pow(2, Math.min(failures, 3))) : base;
      scheduleNext(backoff);
    };

    runOnce();

    return () => {
      cancelled = true;
      if (timeoutId != null) window.clearTimeout(timeoutId);
    };
  }, [sessionId, isPolling, onComplete, appConfig]);

  if (fatalError) {
    return (
      <div className="writing-step">
        <div className="error-container">
          <h3>Errore durante la scrittura</h3>
          <p>{fatalError}</p>
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

  // Progress bar: i passi sono solo i capitoli/sezioni.
  // La critica è una fase separata: mentre è in corso, mostriamo N/N e la clessidra.
  void includeCritiqueStep; // mantenuto per compatibilità con logica UI esistente
  const totalSteps = progress.total_steps;
  const currentStep = Math.min(progress.current_step, totalSteps);

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
        
        <ProgressBar percentage={progressPercentage} />
        <AnimatePresence>
          {critiqueInProgress && (
            <motion.div
              className="critique-loading-indicator"
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.3 }}
            >
              <motion.span
                className="loading-spinner"
                animate={{ rotate: 360 }}
                transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
              >
                ⏳
              </motion.span>
              <span>Generazione valutazione critica...</span>
            </motion.div>
          )}
        </AnimatePresence>

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
                setFatalError(null);
                await resumeBookGeneration(sessionId);
                toast.success('Generazione ripresa con successo');
                // Riavvia il polling
                setIsPolling(true);
              } catch (e) {
                const errorMsg = e instanceof Error ? e.message : 'Errore sconosciuto';
                setFatalError(`Errore nella ripresa: ${errorMsg}`);
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
        <FadeIn>
          <div className="completed-chapters">
            <h3>Capitoli Completati ({progress.completed_chapters.length})</h3>
            <div className="chapters-list">
              <AnimatePresence mode="popLayout">
                {progress.completed_chapters.map((chapter, index) => (
                  <motion.div
                    key={`${chapter.title}-${index}`}
                    className="chapter-item"
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, height: 0 }}
                    transition={{ 
                      duration: 0.4,
                      delay: index * 0.05
                    }}
                    layout
                  >
                    <div className="chapter-header">
                      <h4>{chapter.title}</h4>
                      {chapter.page_count > 0 && (
                        <span className="chapter-pages">{chapter.page_count} pagine</span>
                      )}
                    </div>
                    <p className="chapter-preview">
                      {chapter.content.substring(0, 200)}...
                    </p>
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>
          </div>
        </FadeIn>
      )}

      <AnimatePresence>
        {progress.is_complete && (
          <motion.div
            className="completion-message"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
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
          </motion.div>
        )}
      </AnimatePresence>

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


import { useState, useEffect, useMemo, useRef } from 'react';
import { getBookProgress, BookProgress, regenerateBookCritique, getAppConfig, AppConfig, resumeBookGeneration } from '../api/client';
import AlertModal from './AlertModal';
import CritiqueBlock from './CritiqueBlock';
import GenerationStage from './GenerationStage';
import Button from './ui/Button';
import { useToast } from '../hooks/useToast';
import { elapsedMinutesBetween, formatElapsed, formatEstimateCost } from '../utils/estimateGeneration';
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
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;
  const consecutiveFailuresRef = useRef(0);
  const [nowMs, setNowMs] = useState(() => Date.now());

  // Carica la config app all'avvio
  useEffect(() => {
    getAppConfig().then(setAppConfig).catch(err => {
      console.warn('[WritingStep] Errore nel caricamento config app:', err);
      // Continua con valori di default
    });
  }, []);

  useEffect(() => {
    if (!progress || progress.is_complete || progress.is_paused) return;
    const timer = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [progress?.is_complete, progress?.is_paused, progress]);

  useEffect(() => {
    setProgress(null);
    setFatalError(null);
    latestProgressRef.current = null;
    consecutiveFailuresRef.current = 0;
    setIsPolling(true);
  }, [sessionId]);

  useEffect(() => {
    if (!sessionId || !isPolling) return;
    setFatalError(null);
    consecutiveFailuresRef.current = 0;

    const pollProgress = async () => {
      try {
        const currentProgress = await getBookProgress(sessionId);
        if (cancelled) return;
        setProgress(currentProgress);
        latestProgressRef.current = currentProgress;
        consecutiveFailuresRef.current = 0;

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
          cancelled = true;
          setIsPolling(false);
        } else if (currentProgress.error && !isPaused) {
          // Errore non gestito (non paused)
          cancelled = true;
          setIsPolling(false);
        } else if (isCritiqueFailed || isCritiqueDone) {
          cancelled = true;
          setIsPolling(false);
          if (isCritiqueDone) {
            onCompleteRef.current?.(currentProgress);
          }
        }
      } catch (err) {
        if (cancelled) return;
        const msg = err instanceof Error ? err.message : 'Errore nel recupero del progresso';
        // Non bloccare tutto al primo glitch: spesso è un micro-restart del backend o un timeout di rete.
        const next = consecutiveFailuresRef.current + 1;
        consecutiveFailuresRef.current = next;
        
        // Mostra toast solo ogni 3 tentativi per evitare spam
        if (next % 3 === 1) {
          toast.error(`Connessione instabile (tentativo ${next}/10). Riprovo...`);
        }
        
        // Dopo molti tentativi falliti consecutivi, consideralo fatale.
        if (next >= 10) {
          setFatalError(msg);
          cancelled = true;
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
  }, [sessionId, isPolling, appConfig, toast]);

  const elapsedMinutes = useMemo(() => {
    if (!progress) return null;
    return elapsedMinutesBetween(progress.started_at, nowMs) ?? progress.writing_time_minutes ?? null;
  }, [nowMs, progress]);

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

  const phaseLabel = critiqueFailed
    ? 'Valutazione critica fallita'
    : critiqueInProgress
      ? 'Valutazione critica in corso'
      : progress.is_complete && hasCritique
        ? 'Completato'
        : progress.current_section_name || 'Preparazione';

  const remainingEstimate = !progress.is_complete && progress.estimated_time_minutes != null
    ? `~${Math.max(1, Math.round(progress.estimated_time_minutes))} min`
    : null;

  return (
    <div className="writing-step">
      <GenerationStage
        title="Romanzo"
        phase={phaseLabel}
        elapsed={elapsedMinutes != null ? formatElapsed(elapsedMinutes) : null}
        cost={progress.estimated_cost != null ? formatEstimateCost(progress.estimated_cost) : null}
        estimate={remainingEstimate}
        progress={progressPercentage}
        actions={
          <>
            {progress.is_paused ? (
              <Button
                disabled={isResuming}
                onClick={async () => {
                  try {
                    setIsResuming(true);
                    setFatalError(null);
                    await resumeBookGeneration(sessionId);
                    toast.success('Generazione ripresa con successo');
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
                {isResuming ? 'Riprendo...' : 'Riprendi'}
              </Button>
            ) : null}
            {critiqueFailed ? (
              <Button
                variant="ghost"
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
              </Button>
            ) : null}
            {progress.is_complete && onNewBook ? (
              <Button variant="ghost" onClick={onNewBook}>
                Nuova opera
              </Button>
            ) : null}
          </>
        }
      >
        {progress.error ? (
          <p className="error-message">{progress.error}</p>
        ) : null}

        <ol className="generation-index">
          {progress.completed_chapters.map((chapter, index) => (
            <li key={`${chapter.title}-${index}`}>
              <span>{chapter.title}</span>
              <span>{chapter.page_count > 0 ? `${chapter.page_count} pagine` : 'pronto'}</span>
            </li>
          ))}
          {progress.current_section_name && !progress.is_complete ? (
            <li className="is-current">
              <span>{progress.current_section_name}</span>
              <span>{currentStep} / {totalSteps}</span>
            </li>
          ) : null}
          {critiqueInProgress || hasCritique || critiqueFailed ? (
            <li className={critiqueInProgress ? 'is-current' : undefined}>
              <span>Valutazione critica</span>
              <span>{hasCritique ? 'pronta' : critiqueFailed ? 'errore' : 'in corso'}</span>
            </li>
          ) : null}
        </ol>
      </GenerationStage>

      {progress.is_complete ? (
        <div>
          <p className="writing-complete-note">
            {hasCritique
              ? `Il romanzo è completo: ${progress.total_steps} sezioni scritte.`
              : 'Capitoli generati. Sto completando la valutazione critica.'}
          </p>
          <dl className="writing-complete-meta">
            {progress.total_pages ? (
              <div>
                <dt>Pagine</dt>
                <dd>{progress.total_pages}</dd>
              </div>
            ) : null}
            {progress.writing_time_minutes ? (
              <div>
                <dt>Tempo di scrittura</dt>
                <dd>{Math.round(progress.writing_time_minutes)} min</dd>
              </div>
            ) : null}
            {progress.total_pages ? (
              <div>
                <dt>Tempo di lettura</dt>
                <dd>{Math.ceil((progress.total_pages * 90) / 60)} min</dd>
              </div>
            ) : null}
          </dl>
          {progress.critique ? <CritiqueBlock critique={progress.critique} /> : null}
        </div>
      ) : null}

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


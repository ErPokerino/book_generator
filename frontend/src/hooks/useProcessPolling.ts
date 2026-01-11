import { useState, useEffect, useRef } from 'react';
import { ProcessProgress } from '../api/client';
import { getAppConfig, AppConfig } from '../api/client';
import { useToast } from './useToast';

interface UseProcessPollingOptions {
  sessionId: string | null;
  progressEndpoint: (sessionId: string) => Promise<ProcessProgress>;
  pollingInterval?: number;
  onComplete?: (progress: ProcessProgress) => void;
  onError?: (error: string) => void;
  enabled?: boolean;
}

export function useProcessPolling({
  sessionId,
  progressEndpoint,
  pollingInterval = 2000,
  onComplete,
  onError,
  enabled = true,
}: UseProcessPollingOptions) {
  const [progress, setProgress] = useState<ProcessProgress | null>(null);
  const [fatalError, setFatalError] = useState<string | null>(null);
  const [consecutiveFailures, setConsecutiveFailures] = useState(0);
  const [isPolling, setIsPolling] = useState(true);
  const [appConfig, setAppConfig] = useState<AppConfig | null>(null);
  const toast = useToast();
  const latestProgressRef = useRef<ProcessProgress | null>(null);
  const consecutiveFailuresRef = useRef(0);
  const stoppedRef = useRef(false); // Ref per tracciare stop del polling in modo sincrono
  const completedCalledRef = useRef(false); // Evita chiamate multiple di onComplete

  // Carica la config app all'avvio
  useEffect(() => {
    getAppConfig().then(setAppConfig).catch(err => {
      console.warn('[useProcessPolling] Errore nel caricamento config app:', err);
    });
  }, []);

  // Reset dei ref quando cambia sessionId (nuovo processo)
  useEffect(() => {
    if (sessionId) {
      stoppedRef.current = false;
      completedCalledRef.current = false;
      setIsPolling(true);
    }
  }, [sessionId]);

  useEffect(() => {
    if (!sessionId || !isPolling || !enabled) return;

    const pollProgress = async () => {
      try {
        const currentProgress = await progressEndpoint(sessionId);
        setProgress(currentProgress);
        latestProgressRef.current = currentProgress;
        consecutiveFailuresRef.current = 0;
        setConsecutiveFailures(0);

        // Ferma il polling se completato o fallito
        if (currentProgress.status === 'completed') {
          stoppedRef.current = true;
          setIsPolling(false);
          // Chiama onComplete solo una volta
          if (onComplete && !completedCalledRef.current) {
            completedCalledRef.current = true;
            onComplete(currentProgress);
          }
        } else if (currentProgress.status === 'failed') {
          stoppedRef.current = true;
          setIsPolling(false);
          if (onError) {
            onError(currentProgress.error || 'Processo fallito');
          }
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Errore nel recupero del progresso';
        const next = consecutiveFailuresRef.current + 1;
        consecutiveFailuresRef.current = next;
        setConsecutiveFailures(next);
        
        // Mostra toast solo ogni 3 tentativi per evitare spam
        if (next % 3 === 1) {
          toast.error(`Connessione instabile (tentativo ${next}/10). Riprovo...`);
        }
        
        // Dopo molti tentativi falliti consecutivi, consideralo fatale
        if (next >= 10) {
          setFatalError(msg);
          setIsPolling(false);
          if (onError) {
            onError(msg);
          }
        }
      }
    };

    // Polling adattivo + backoff su errori di rete
    let cancelled = false;
    let timeoutId: number | null = null;

    const getBasePollingInterval = (): number => {
      if (appConfig?.frontend?.polling_interval) {
        return appConfig.frontend.polling_interval;
      }
      return pollingInterval;
    };

    const scheduleNext = (delayMs: number) => {
      if (cancelled) return;
      timeoutId = window.setTimeout(async () => {
        await runOnce();
      }, delayMs);
    };

    const runOnce = async () => {
      if (cancelled || stoppedRef.current) return;
      await pollProgress();

      // Se il polling è stato fermato dentro pollProgress, non schedulare
      if (cancelled || stoppedRef.current) return;
      
      // Usa intervallo base o config
      const base = getBasePollingInterval();
      // Backoff esponenziale su errori consecutivi (max 15s)
      const failures = consecutiveFailuresRef.current;
      const backoff = failures > 0 
        ? Math.min(15000, base * Math.pow(2, Math.min(failures, 3))) 
        : base;
      scheduleNext(backoff);
    };

    runOnce();

    return () => {
      cancelled = true;
      if (timeoutId != null) window.clearTimeout(timeoutId);
    };
  }, [sessionId, isPolling, enabled, progressEndpoint, onComplete, onError, appConfig, pollingInterval, toast]);

  return {
    progress,
    fatalError,
    consecutiveFailures,
    isPolling,
    setIsPolling,
  };
}

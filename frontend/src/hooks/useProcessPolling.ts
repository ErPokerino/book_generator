import { useState, useEffect, useRef } from 'react';
import { getAppConfig, type ProcessProgress } from '../api/client';
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
  pollingInterval,
  onComplete,
  onError,
  enabled = true,
}: UseProcessPollingOptions) {
  const [progress, setProgress] = useState<ProcessProgress | null>(null);
  const [fatalError, setFatalError] = useState<string | null>(null);
  const [consecutiveFailures, setConsecutiveFailures] = useState(0);
  const [isPolling, setIsPolling] = useState(true);
  const configuredInterval = useRef(2000);
  const toast = useToast();
  const callbacks = useRef({ progressEndpoint, onComplete, onError, toast, pollingInterval });
  callbacks.current = { progressEndpoint, onComplete, onError, toast, pollingInterval };

  useEffect(() => {
    let cancelled = false;
    getAppConfig().then(config => {
      if (!cancelled) configuredInterval.current = config.frontend?.polling_interval ?? 2000;
    }).catch(() => {});
    return () => { cancelled = true; };
  }, []);

  // Riabilitare lo stesso processo (es. Riprova) avvia un nuovo ciclo.
  useEffect(() => {
    setProgress(null);
    setFatalError(null);
    setConsecutiveFailures(0);
    setIsPolling(true);
  }, [sessionId, enabled]);

  useEffect(() => {
    if (!sessionId || !enabled || !isPolling) return;
    let cancelled = false;
    let failures = 0;
    let timeoutId: number | undefined;
    setFatalError(null);
    setConsecutiveFailures(0);

    const runOnce = async () => {
      let current: ProcessProgress;
      try {
        current = await callbacks.current.progressEndpoint(sessionId);
      } catch (error) {
        if (cancelled) return;
        failures += 1;
        setConsecutiveFailures(failures);
        if (failures >= 10) {
          const message = error instanceof Error ? error.message : 'Errore nel recupero del progresso';
          setFatalError(message);
          setIsPolling(false);
          callbacks.current.onError?.(message);
          return;
        }
        if (failures % 3 === 1) {
          callbacks.current.toast.error(`Connessione instabile (tentativo ${failures}/10). Riprovo...`);
        }
        scheduleNext();
        return;
      }

      // Una risposta del ciclo precedente non può aggiornare la nuova sessione.
      if (cancelled) return;
      setProgress(current);
      failures = 0;
      setConsecutiveFailures(0);
      if (current.status === 'completed') {
        setIsPolling(false);
        callbacks.current.onComplete?.(current);
        return;
      }
      if (['failed', 'paused', 'cancelled'].includes(current.status)) {
        setIsPolling(false);
        callbacks.current.onError?.(current.error || 'Processo interrotto');
        return;
      }
      scheduleNext();
    };

    const scheduleNext = () => {
      if (cancelled) return;
      const base = Math.max(1, callbacks.current.pollingInterval ?? configuredInterval.current);
      const delay = failures ? Math.min(15000, base * 2 ** Math.min(failures, 3)) : base;
      timeoutId = window.setTimeout(() => { void runOnce(); }, delay);
    };

    void runOnce();
    return () => {
      cancelled = true;
      window.clearTimeout(timeoutId);
    };
  }, [sessionId, enabled, isPolling]);

  return { progress, fatalError, consecutiveFailures, isPolling: !!sessionId && enabled && isPolling, setIsPolling };
}

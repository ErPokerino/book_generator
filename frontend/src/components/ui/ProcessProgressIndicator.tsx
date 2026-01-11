import { ProcessProgress } from '../../api/client';
import ProgressBar from './ProgressBar';
import { AlertCircle, CheckCircle, XCircle, Loader2 } from 'lucide-react';
import './ProcessProgressIndicator.css';

interface ProcessProgressIndicatorProps {
  progress: ProcessProgress | null;
  processName: string;
  onRetry?: () => void;
  onDismiss?: () => void;
}

export default function ProcessProgressIndicator({
  progress,
  processName,
  onRetry,
  onDismiss,
}: ProcessProgressIndicatorProps) {
  if (!progress) {
    return (
      <div className="process-progress-indicator">
        <div className="process-progress-loading">
          <Loader2 className="process-progress-icon" size={20} />
          <span>Inizializzazione {processName}...</span>
        </div>
      </div>
    );
  }

  const { status, current_step, total_steps, progress_percentage, error, estimated_time_seconds } = progress;

  // Calcola percentuale
  const percentage = progress_percentage !== undefined
    ? progress_percentage
    : (current_step !== undefined && total_steps !== undefined && total_steps > 0)
      ? (current_step / total_steps) * 100
      : status === 'completed' ? 100 : status === 'pending' ? 0 : 50;

  // Formatta tempo stimato
  const formatEstimatedTime = (seconds?: number): string => {
    if (!seconds) return '';
    if (seconds < 60) return `~${Math.round(seconds)}s`;
    const minutes = Math.round(seconds / 60);
    return `~${minutes} min`;
  };

  // Stato testuale
  const getStatusText = (): string => {
    switch (status) {
      case 'pending':
        return `In attesa di avviare ${processName}...`;
      case 'running':
        if (current_step !== undefined && total_steps !== undefined && total_steps > 0) {
          return `${processName} in corso... ${current_step}/${total_steps}`;
        }
        return `${processName} in corso...`;
      case 'completed':
        return `${processName} completato!`;
      case 'failed':
        return `Errore durante ${processName}`;
      default:
        return `${processName}...`;
    }
  };

  return (
    <div className="process-progress-indicator">
      <div className="process-progress-header">
        <div className="process-progress-status">
          {status === 'running' && <Loader2 className="process-progress-icon spinning" size={20} />}
          {status === 'completed' && <CheckCircle className="process-progress-icon success" size={20} />}
          {status === 'failed' && <XCircle className="process-progress-icon error" size={20} />}
          {status === 'pending' && <Loader2 className="process-progress-icon" size={20} />}
          <span className="process-progress-text">{getStatusText()}</span>
        </div>
        {estimated_time_seconds && status === 'running' && (
          <span className="process-progress-time">{formatEstimatedTime(estimated_time_seconds)}</span>
        )}
        {onDismiss && status !== 'running' && (
          <button
            type="button"
            onClick={onDismiss}
            className="process-progress-dismiss"
            aria-label="Chiudi"
          >
            ×
          </button>
        )}
      </div>

      {(status === 'running' || status === 'pending') && (
        <div className="process-progress-bar-wrapper">
          <ProgressBar percentage={percentage} />
        </div>
      )}

      {status === 'failed' && error && (
        <div className="process-progress-error">
          <AlertCircle size={16} />
          <span>{error}</span>
          {onRetry && (
            <button
              type="button"
              onClick={onRetry}
              className="process-progress-retry"
            >
              Riprova
            </button>
          )}
        </div>
      )}

      {status === 'completed' && (
        <div className="process-progress-success">
          <CheckCircle size={16} />
          <span>Processo completato con successo</span>
        </div>
      )}
    </div>
  );
}

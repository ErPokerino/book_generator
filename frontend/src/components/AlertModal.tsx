import { useEffect } from 'react';
import './AlertModal.css';

interface AlertModalProps {
  isOpen: boolean;
  title: string;
  message: string;
  buttonText?: string;
  onClose: () => void;
  variant?: 'error' | 'warning' | 'info' | 'success';
}

export default function AlertModal({
  isOpen,
  title,
  message,
  buttonText = 'OK',
  onClose,
  variant = 'info',
}: AlertModalProps) {
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

  if (!isOpen) return null;

  return (
    <div className="alert-modal-overlay" onClick={onClose}>
      <div className="alert-modal-content" onClick={(e) => e.stopPropagation()}>
        <div className={`alert-modal-header alert-modal-${variant}`}>
          <h3>{title}</h3>
        </div>
        
        <div className="alert-modal-body">
          <p>{message}</p>
        </div>

        <div className="alert-modal-footer">
          <button
            className={`alert-modal-button alert-modal-${variant}`}
            onClick={onClose}
          >
            {buttonText}
          </button>
        </div>
      </div>
    </div>
  );
}

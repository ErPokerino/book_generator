import React, { useState } from 'react';
import './DraftChat.css';

interface DraftChatProps {
  onSendFeedback: (feedback: string) => void;
  onValidate: () => void;
  isLoading: boolean;
  error: string | null;
}

export default function DraftChat({ onSendFeedback, onValidate, isLoading, error }: DraftChatProps) {
  const [feedback, setFeedback] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (feedback.trim()) {
      onSendFeedback(feedback.trim());
      setFeedback('');
    }
  };

  return (
    <div className="draft-chat">
      <div className="chat-header">
        <h3>Richiedi Modifiche</h3>
        <p className="chat-subtitle">Indica le modifiche che desideri apportare alla bozza</p>
      </div>

      {error && (
        <div className="error-banner">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="chat-form">
        <textarea
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          placeholder="Es: Vorrei che il finale fosse più aperto, oppure: Aggiungi più dettagli sul protagonista nella prima parte..."
          rows={4}
          disabled={isLoading}
          className="chat-input"
        />
        <div className="chat-actions">
          <button
            type="button"
            onClick={onValidate}
            disabled={isLoading}
            className="validate-button"
          >
            {isLoading ? 'Validazione...' : '✓ Valida Bozza'}
          </button>
          <button
            type="submit"
            disabled={isLoading || !feedback.trim()}
            className="send-button"
          >
            {isLoading ? 'Invio...' : 'Invia Modifiche'}
          </button>
        </div>
      </form>
    </div>
  );
}


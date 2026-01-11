import { useState, FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { forgotPassword } from '../api/client';
import { useToast } from '../hooks/useToast';
import './ForgotPasswordPage.css';

// In development mode, mostriamo il token direttamente
// In production, si invierebbe via email
const isDevelopment = import.meta.env.DEV;

export default function ForgotPasswordPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [resetToken, setResetToken] = useState<string | null>(null);
  const [tokenInput, setTokenInput] = useState('');
  const toast = useToast();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setIsLoading(true);

    try {
      console.log('[ForgotPassword] Inviando richiesta per:', email);
      const response = await forgotPassword(email);
      console.log('[ForgotPassword] Risposta:', response);
      setIsSubmitted(true);
      toast.success('Email inviata! Controlla la tua casella di posta.');
      
      // In dev mode, il backend restituisce il token nella risposta
      if (isDevelopment && response.token) {
        setResetToken(response.token);
      }
    } catch (err) {
      console.error('[ForgotPassword] Errore:', err);
      toast.error(err instanceof Error ? err.message : 'Errore nell\'invio della richiesta');
    } finally {
      setIsLoading(false);
    }
  };

  const handleTokenSubmit = (e: FormEvent) => {
    e.preventDefault();
    const token = resetToken || tokenInput;
    if (token) {
      navigate(`/reset-password?token=${encodeURIComponent(token)}`);
    }
  };

  if (isSubmitted) {
    return (
      <div className="auth-page">
        <div className="auth-container">
          <div className="auth-header">
            <h1>📚 NarrAI</h1>
            <h2>Reset Password</h2>
          </div>

          {isDevelopment && resetToken ? (
            // In dev mode, mostra il token direttamente
            <div className="auth-success-message">
              <p>Token generato per il reset password:</p>
              <div className="token-display">
                <code>{resetToken}</code>
              </div>
              <button 
                onClick={() => navigate(`/reset-password?token=${encodeURIComponent(resetToken)}`)}
                className="auth-submit-button"
                style={{ marginTop: '1rem' }}
              >
                Procedi al Reset
              </button>
            </div>
          ) : (
            // Modalità normale: inserisci token manualmente
            <form onSubmit={handleTokenSubmit} className="auth-form">
              <div className="auth-success-message">
                <p>Se l'email inserita è registrata, riceverai un token per reimpostare la password.</p>
              </div>

              <div className="auth-field">
                <label htmlFor="token">Token di Reset</label>
                <input
                  id="token"
                  type="text"
                  value={tokenInput}
                  onChange={(e) => setTokenInput(e.target.value)}
                  required
                  placeholder="Incolla qui il token ricevuto"
                />
              </div>

              <button 
                type="submit" 
                className="auth-submit-button"
                disabled={!tokenInput.trim()}
              >
                Procedi al Reset
              </button>
            </form>
          )}

          <div className="auth-links">
            <button
              type="button"
              onClick={() => navigate('/login')}
              className="auth-link-button"
            >
              Torna al login
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-page">
      <div className="auth-container">
        <div className="auth-header">
          <h1>📚 NarrAI</h1>
          <h2>Password dimenticata?</h2>
        </div>

        <form onSubmit={handleSubmit} className="auth-form">
          <p className="auth-description">
            Inserisci la tua email e {isDevelopment 
              ? 'riceverai un token per reimpostare la password.' 
              : 'ti invieremo le istruzioni per reimpostare la password.'}
          </p>

          <div className="auth-field">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              placeholder="nome@esempio.com"
              disabled={isLoading}
            />
          </div>

          <button type="submit" className="auth-submit-button" disabled={isLoading}>
            {isLoading ? 'Invio in corso...' : 'Richiedi Reset'}
          </button>

          <div className="auth-links">
            <button
              type="button"
              onClick={onNavigateToLogin}
              className="auth-link-button"
              disabled={isLoading}
            >
              Torna al login
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

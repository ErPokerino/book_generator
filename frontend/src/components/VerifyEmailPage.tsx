import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { checkVerificationToken, verifyEmail } from '../api/client';
import './LoginPage.css';

type VerificationStatus = 'loading' | 'ready' | 'verifying' | 'success' | 'already_verified' | 'error';

export default function VerifyEmailPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
  const [status, setStatus] = useState<VerificationStatus>('loading');
  const [message, setMessage] = useState('');
  const [verifiedEmail, setVerifiedEmail] = useState('');
  const [isVerifying, setIsVerifying] = useState(false);

  // Step 1: Controlla il token al caricamento (senza invalidarlo)
  useEffect(() => {
    const checkToken = async () => {
      if (!token) {
        setStatus('error');
        setMessage('Token di verifica mancante.');
        return;
      }

      try {
        const result = await checkVerificationToken(token);
        setVerifiedEmail(result.email);
        
        if (result.already_verified) {
          // Utente già verificato - mostra messaggio positivo
          setStatus('already_verified');
          setMessage(result.message);
        } else if (result.valid) {
          // Token valido - mostra pulsante per confermare
          setStatus('ready');
          setMessage(result.message);
        } else {
          // Token non valido
          setStatus('error');
          setMessage('Token non valido o scaduto.');
        }
      } catch (err) {
        setStatus('error');
        setMessage(err instanceof Error ? err.message : 'Errore nella verifica del token');
      }
    };

    checkToken();
  }, [token]);

  // Step 2: Conferma verifica quando l'utente clicca il pulsante
  const handleConfirmVerification = async () => {
    if (!token || isVerifying) return;

    setIsVerifying(true);
    setStatus('verifying');

    try {
      const result = await verifyEmail(token);
      setStatus('success');
      setMessage(result.message);
    } catch (err) {
      setStatus('error');
      setMessage(err instanceof Error ? err.message : 'Errore nella verifica email');
    } finally {
      setIsVerifying(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-container">
        <div className="auth-header">
          <h1>📚 NarrAI</h1>
          <h2>Verifica Email</h2>
        </div>

        <div className="verification-message">
          {status === 'loading' && (
            <>
              <div className="verification-icon">⏳</div>
              <p className="verification-text">Controllo token in corso...</p>
            </>
          )}

          {status === 'ready' && (
            <>
              <div className="verification-icon">✉️</div>
              <p className="verification-text">{message}</p>
              {verifiedEmail && (
                <p className="verification-email" style={{ marginTop: '1rem', color: 'var(--text-secondary)' }}>
                  {verifiedEmail}
                </p>
              )}
              <p className="verification-instructions" style={{ marginTop: '1rem' }}>
                Clicca sul pulsante qui sotto per confermare la verifica del tuo account.
              </p>
            </>
          )}

          {status === 'verifying' && (
            <>
              <div className="verification-icon">⏳</div>
              <p className="verification-text">Verifica in corso...</p>
            </>
          )}

          {status === 'success' && (
            <>
              <div className="verification-icon">✅</div>
              <p className="verification-text">{message}</p>
              {verifiedEmail && (
                <p className="verification-email">{verifiedEmail}</p>
              )}
              <p className="verification-instructions">
                Ora puoi accedere con le tue credenziali.
              </p>
            </>
          )}

          {status === 'already_verified' && (
            <>
              <div className="verification-icon">✅</div>
              <p className="verification-text" style={{ color: 'var(--success-color, #10b981)' }}>
                {message}
              </p>
              {verifiedEmail && (
                <p className="verification-email">{verifiedEmail}</p>
              )}
              <p className="verification-instructions">
                Il tuo account è già stato verificato. Puoi procedere al login.
              </p>
            </>
          )}

          {status === 'error' && (
            <>
              <div className="verification-icon">❌</div>
              <p className="verification-text" style={{ color: 'var(--accent)' }}>
                {message}
              </p>
              <p className="verification-instructions">
                Il link potrebbe essere scaduto o non valido.
                <br />
                Prova a richiedere un nuovo link dalla pagina di login.
              </p>
            </>
          )}
        </div>

        <div className="auth-links" style={{ marginTop: '2rem' }}>
          {status === 'ready' && (
            <button
              type="button"
              onClick={handleConfirmVerification}
              className="auth-submit-button"
              style={{ width: '100%' }}
              disabled={isVerifying}
            >
              {isVerifying ? 'Verifica in corso...' : 'Conferma Verifica Email'}
            </button>
          )}
          
          {(status === 'success' || status === 'already_verified' || status === 'error') && (
            <button
              type="button"
              onClick={() => navigate('/login')}
              className="auth-submit-button"
              style={{ width: '100%' }}
            >
              {status === 'error' ? 'Torna al Login' : 'Vai al Login'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

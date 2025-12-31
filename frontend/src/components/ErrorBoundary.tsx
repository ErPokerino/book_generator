import React, { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
    };
  }

  static getDerivedStateFromError(error: Error): State {
    // Aggiorna lo stato in modo che il prossimo render mostri l'UI di fallback
    return {
      hasError: true,
      error,
      errorInfo: null,
    };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    // Log dell'errore per il debugging
    console.error('[ErrorBoundary] Errore catturato:', error);
    console.error('[ErrorBoundary] ErrorInfo:', errorInfo);
    
    this.setState({
      error,
      errorInfo,
    });
  }

  render() {
    if (this.state.hasError) {
      // Se è fornito un fallback personalizzato, usalo
      if (this.props.fallback) {
        return this.props.fallback;
      }

      // Altrimenti mostra il messaggio di errore di default
      return (
        <div style={{
          padding: '2rem',
          margin: '1rem',
          border: '1px solid #ef4444',
          borderRadius: '8px',
          backgroundColor: '#fee2e2',
          color: '#991b1b',
        }}>
          <h2 style={{ marginTop: 0, color: '#dc2626' }}>⚠️ Errore nel Rendering</h2>
          <p style={{ marginBottom: '1rem' }}>
            Si è verificato un errore durante la visualizzazione del contenuto.
          </p>
          {this.state.error && (
            <details style={{ marginTop: '1rem' }}>
              <summary style={{ cursor: 'pointer', fontWeight: 'bold', marginBottom: '0.5rem' }}>
                Dettagli tecnici (clicca per espandere)
              </summary>
              <pre style={{
                padding: '1rem',
                backgroundColor: '#fff',
                border: '1px solid #dc2626',
                borderRadius: '4px',
                overflow: 'auto',
                fontSize: '0.85rem',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}>
                <strong>Errore:</strong> {this.state.error.toString()}
                {this.state.errorInfo && (
                  <>
                    {'\n\n'}
                    <strong>Stack Trace:</strong>
                    {'\n'}
                    {this.state.errorInfo.componentStack}
                  </>
                )}
              </pre>
            </details>
          )}
          <button
            onClick={() => {
              this.setState({
                hasError: false,
                error: null,
                errorInfo: null,
              });
              window.location.reload();
            }}
            style={{
              marginTop: '1rem',
              padding: '0.5rem 1rem',
              backgroundColor: '#dc2626',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              fontWeight: '500',
            }}
          >
            Ricarica la pagina
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

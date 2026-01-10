import { useState, useEffect } from 'react';
import { X, UserPlus, Search, Users } from 'lucide-react';
import { shareBook, searchUser, getConnections, UserSearchResponse } from '../api/client';
import { useToast } from '../hooks/useToast';
import './ShareBookModal.css';

interface ShareBookModalProps {
  isOpen: boolean;
  sessionId: string;
  bookTitle: string;
  onClose: () => void;
  onSuccess?: () => void; // Callback dopo condivisione riuscita
}

export default function ShareBookModal({ isOpen, sessionId, bookTitle, onClose, onSuccess }: ShareBookModalProps) {
  const toast = useToast();
  const [email, setEmail] = useState('');
  const [searchResult, setSearchResult] = useState<UserSearchResponse | null>(null);
  const [searching, setSearching] = useState(false);
  const [sharing, setSharing] = useState(false);
  const [connections, setConnections] = useState<Array<{ id: string; name: string; email: string }>>([]);
  const [showConnections, setShowConnections] = useState(false);

  // Carica connessioni accettate quando il modal si apre
  useEffect(() => {
    if (!isOpen) {
      setEmail('');
      setSearchResult(null);
      setConnections([]);
      setShowConnections(false);
      return;
    }

    const loadConnections = async () => {
      try {
        const response = await getConnections('accepted', 50, 0);
        // Estrai info utente dalle connessioni
        const connectionsList = response.connections.map(conn => {
          // Determina l'altro utente (non current_user)
          // Per ora mostriamo solo ID, ma potremmo migliorare con un endpoint che restituisce info utente
          return {
            id: conn.from_user_id || conn.to_user_id,
            name: conn.from_user_name || conn.to_user_name || conn.from_user_email || conn.to_user_email || 'Utente',
            email: conn.from_user_email || conn.to_user_email || '',
          };
        }).filter(conn => conn.email); // Solo connessioni con email
        setConnections(connectionsList);
      } catch (error) {
        console.error('Errore nel caricamento connessioni:', error);
      }
    };

    loadConnections();
  }, [isOpen]);

  // Gestione ESC
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

  const handleSearch = async () => {
    if (!email.trim()) {
      toast.error('Inserisci un\'email per cercare');
      return;
    }

    try {
      setSearching(true);
      const result = await searchUser(email.trim());
      setSearchResult(result);
      setShowConnections(false);
    } catch (error) {
      toast.error(`Errore nella ricerca: ${error instanceof Error ? error.message : 'Errore sconosciuto'}`);
      setSearchResult(null);
    } finally {
      setSearching(false);
    }
  };

  const handleShare = async () => {
    if (!searchResult?.found || !searchResult.user?.email) {
      toast.error('Cerca prima un utente valido');
      return;
    }

    if (!searchResult.is_connected) {
      toast.error('Devi essere connesso con questo utente prima di condividere un libro');
      return;
    }

    try {
      setSharing(true);
      await shareBook(sessionId, searchResult.user.email);
      toast.success(`Libro "${bookTitle}" condiviso con ${searchResult.user.name}`);
      onClose();
      if (onSuccess) {
        onSuccess();
      }
    } catch (error) {
      toast.error(`Errore nella condivisione: ${error instanceof Error ? error.message : 'Errore sconosciuto'}`);
    } finally {
      setSharing(false);
    }
  };

  const handleSelectConnection = (connectionEmail: string, connectionName: string) => {
    setEmail(connectionEmail);
    setShowConnections(false);
    // Ricerca automatica
    handleSearch();
  };

  if (!isOpen) return null;

  return (
    <div className="share-book-modal-overlay" onClick={onClose}>
      <div className="share-book-modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="share-book-modal-header">
          <h2>Condividi Libro</h2>
          <button className="share-book-modal-close" onClick={onClose} aria-label="Chiudi">
            <X size={20} />
          </button>
        </div>

        <div className="share-book-modal-body">
          <div className="share-book-info">
            <p className="share-book-title">📖 {bookTitle}</p>
            <p className="share-book-hint">Condividi questo libro con un utente connesso</p>
          </div>

          <div className="share-book-search-section">
            <div className="share-book-search-bar">
              <Search size={18} className="search-icon" />
              <input
                type="email"
                placeholder="Cerca utente per email..."
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value);
                  setSearchResult(null);
                  if (e.target.value.trim()) {
                    setShowConnections(false);
                  }
                }}
                onFocus={() => {
                  if (connections.length > 0 && email.trim() === '') {
                    setShowConnections(true);
                  }
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    handleSearch();
                  }
                }}
                className="share-book-search-input"
                disabled={sharing}
              />
              <button
                className="share-book-search-button"
                onClick={handleSearch}
                disabled={searching || !email.trim() || sharing}
              >
                {searching ? 'Cercando...' : 'Cerca'}
              </button>
            </div>

            {/* Lista connessioni suggerite */}
            {showConnections && connections.length > 0 && email.trim() === '' && (
              <div className="share-book-connections-suggestions">
                <div className="suggestions-header">
                  <Users size={16} />
                  <span>Le tue connessioni</span>
                </div>
                <div className="suggestions-list">
                  {connections.map((conn) => (
                    <button
                      key={conn.id}
                      className="suggestion-item"
                      onClick={() => handleSelectConnection(conn.email, conn.name)}
                    >
                      <div className="suggestion-info">
                        <span className="suggestion-name">{conn.name}</span>
                        <span className="suggestion-email">{conn.email}</span>
                      </div>
                      <UserPlus size={16} />
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Risultato ricerca */}
            {searchResult && (
              <div className="share-book-search-result">
                {searchResult.found ? (
                  <div className="share-book-user-card">
                    <div className="share-book-user-info">
                      <h4>{searchResult.user?.name}</h4>
                      <p className="share-book-user-email">{searchResult.user?.email}</p>
                    </div>

                    {searchResult.is_connected ? (
                      <div className="share-book-user-status">
                        <span className="status-badge connected">Connesso</span>
                      </div>
                    ) : (
                      <div className="share-book-user-status">
                        <span className="status-badge error">Non connesso</span>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="share-book-no-results">
                    <p>Utente non trovato</p>
                    <p className="no-results-hint">Verifica che l'email sia corretta e che l'utente sia registrato</p>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        <div className="share-book-modal-footer">
          <button
            className="share-book-modal-button share-book-modal-cancel"
            onClick={onClose}
            disabled={sharing}
          >
            Annulla
          </button>
          <button
            className="share-book-modal-button share-book-modal-confirm"
            onClick={handleShare}
            disabled={sharing || !searchResult?.found || !searchResult?.is_connected}
          >
            {sharing ? 'Condivisione...' : 'Condividi'}
          </button>
        </div>
      </div>
    </div>
  );
}

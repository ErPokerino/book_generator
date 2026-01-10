import { useState, useEffect, useMemo } from 'react';
import { X, UserPlus, Search, Users } from 'lucide-react';
import { shareBook, searchUser, getConnections, UserSearchResponse, User } from '../api/client';
import { useToast } from '../hooks/useToast';
import { useAuth } from '../contexts/AuthContext';
import './ShareBookModal.css';

interface ShareBookModalProps {
  isOpen: boolean;
  sessionId: string;
  bookTitle: string;
  onClose: () => void;
  onSuccess?: () => void; // Callback dopo condivisione riuscita
}

// Funzione helper per rimuovere asterischi markdown dal titolo
function stripMarkdownBold(text: string): string {
  return text.replace(/\*\*/g, '');
}

export default function ShareBookModal({ isOpen, sessionId, bookTitle, onClose, onSuccess }: ShareBookModalProps) {
  const toast = useToast();
  const { user: currentUser } = useAuth();
  const [email, setEmail] = useState('');
  const [searchResult, setSearchResult] = useState<UserSearchResponse | null>(null);
  const [searching, setSearching] = useState(false);
  const [sharing, setSharing] = useState(false);
  const [connections, setConnections] = useState<Array<{ id: string; name: string; email: string }>>([]);
  const [showConnections, setShowConnections] = useState(false);
  const [selectedConnectionId, setSelectedConnectionId] = useState<string | null>(null);
  
  // Rimuovi asterischi markdown dal titolo
  const cleanBookTitle = useMemo(() => stripMarkdownBold(bookTitle), [bookTitle]);
  
  // Filtra connessioni in base al testo inserito per autocompletamento
  const filteredConnections = useMemo(() => {
    if (!email.trim()) {
      return connections;
    }
    
    const searchTerm = email.trim().toLowerCase();
    return connections.filter(conn => 
      conn.email.toLowerCase().includes(searchTerm) || 
      conn.name.toLowerCase().includes(searchTerm)
    );
  }, [connections, email]);

  // Carica connessioni accettate quando il modal si apre
  useEffect(() => {
    if (!isOpen) {
      setEmail('');
      setSearchResult(null);
      setConnections([]);
      setShowConnections(false);
      setSelectedConnectionId(null);
      return;
    }

    const loadConnections = async () => {
      try {
        const response = await getConnections('accepted', 50, 0);
        const currentUserEmail = currentUser?.email?.toLowerCase();
        const currentUserId = currentUser?.id;
        
        if (!currentUserEmail || !currentUserId) {
          setConnections([]);
          return;
        }
        
        // Estrai info utente dalle connessioni, escludendo l'utente corrente
        const connectionsMap = new Map<string, { id: string; name: string; email: string }>();
        
        response.connections.forEach(conn => {
          // Determina quale utente è l'altro (non current_user)
          const fromEmail = conn.from_user_email?.toLowerCase();
          const toEmail = conn.to_user_email?.toLowerCase();
          
          let otherUser: { id: string; name: string; email: string } | null = null;
          
          // Se from_user è l'utente corrente, prendi to_user
          if (fromEmail === currentUserEmail && toEmail && toEmail !== currentUserEmail && conn.to_user_id !== currentUserId) {
            otherUser = {
              id: conn.to_user_id,
              name: conn.to_user_name || conn.to_user_email || 'Utente',
              email: conn.to_user_email || '',
            };
          }
          // Se to_user è l'utente corrente, prendi from_user
          else if (toEmail === currentUserEmail && fromEmail && fromEmail !== currentUserEmail && conn.from_user_id !== currentUserId) {
            otherUser = {
              id: conn.from_user_id,
              name: conn.from_user_name || conn.from_user_email || 'Utente',
              email: conn.from_user_email || '',
            };
          }
          
          // Aggiungi alla mappa solo se è un utente valido e diverso da se stesso (per email e ID)
          if (otherUser && otherUser.email && otherUser.id && 
              otherUser.email.toLowerCase() !== currentUserEmail && 
              otherUser.id !== currentUserId) {
            // Usa email come chiave per evitare duplicati
            if (!connectionsMap.has(otherUser.email.toLowerCase())) {
              connectionsMap.set(otherUser.email.toLowerCase(), otherUser);
            }
          }
        });
        
        // Converti la mappa in array
        const connectionsList = Array.from(connectionsMap.values());
        setConnections(connectionsList);
      } catch (error) {
        console.error('Errore nel caricamento connessioni:', error);
      }
    };

    loadConnections();
  }, [isOpen, currentUser?.email]);

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
      toast.success(`Libro "${cleanBookTitle}" condiviso con ${searchResult.user.name}`);
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

  const handleSelectConnection = (connectionEmail: string, connectionName: string, connectionId: string) => {
    setEmail(connectionEmail);
    setShowConnections(false);
    setSelectedConnectionId(connectionId);
    
    // Crea direttamente il risultato senza chiamare l'API, dato che la connessione è già accettata
    const userSearchResult: UserSearchResponse = {
      found: true,
      user: {
        id: connectionId,
        email: connectionEmail,
        name: connectionName,
        role: 'user', // Default, non abbiamo questa info dalla connessione
        is_active: true, // Default, assumiamo attivo se connesso
        is_verified: true, // Default, assumiamo verificato se connesso
        created_at: '', // Non necessario per la condivisione
      },
      is_connected: true, // È una connessione accettata, quindi è connesso
      has_pending_request: false, // Non c'è richiesta pendente, è accettata
      pending_request_from_me: false, // Non necessario per condivisione
      connection_id: connectionId,
    };
    
    setSearchResult(userSearchResult);
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
            <p className="share-book-title">📖 {cleanBookTitle}</p>
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
                  const newValue = e.target.value;
                  setEmail(newValue);
                  setSearchResult(null);
                  // Mostra suggerimenti mentre l'utente digita se ci sono connessioni filtrate
                  if (newValue.trim()) {
                    const searchTerm = newValue.trim().toLowerCase();
                    const filtered = connections.filter(conn => 
                      conn.email.toLowerCase().includes(searchTerm) || 
                      conn.name.toLowerCase().includes(searchTerm)
                    );
                    setShowConnections(filtered.length > 0);
                  } else {
                    setShowConnections(connections.length > 0);
                  }
                }}
                onFocus={() => {
                  // Mostra suggerimenti quando l'input riceve focus
                  const hasConnections = email.trim() 
                    ? filteredConnections.length > 0 
                    : connections.length > 0;
                  if (hasConnections && !searchResult) {
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

            {/* Lista connessioni suggerite - mostra durante la digitazione per autocompletamento */}
            {showConnections && filteredConnections.length > 0 && (
              <div className="share-book-connections-suggestions">
                <div className="suggestions-header">
                  <Users size={16} />
                  <span>
                    {email.trim() ? `${filteredConnections.length} connessione${filteredConnections.length !== 1 ? 'i' : ''} trovata${filteredConnections.length !== 1 ? 'e' : ''}` : 'Le tue connessioni'}
                  </span>
                </div>
                <div className="suggestions-list">
                  {filteredConnections.map((conn) => (
                    <button
                      key={conn.email}
                      className="suggestion-item"
                      onClick={() => handleSelectConnection(conn.email, conn.name, conn.id)}
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

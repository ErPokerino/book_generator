import { useState, useEffect } from 'react';
import { Search, UserPlus, Check, X, Users, Mail, Gift, Send } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  searchUser,
  getConnections,
  getPendingRequests,
  sendConnectionRequest,
  acceptConnection,
  deleteConnection,
  sendReferral,
  getReferrals,
  getReferralStats,
  UserSearchResponse,
  Connection,
  ConnectionResponse,
  Referral,
  ReferralStats,
} from '../api/client';
import { useToast } from '../hooks/useToast';
import { useAuth } from '../contexts/AuthContext';
import { useNotifications } from '../contexts/NotificationContext';
import './ConnectionsView.css';

type TabType = 'search' | 'pending' | 'connections' | 'invite';

export default function ConnectionsView() {
  const { user } = useAuth();
  const { refreshNotifications } = useNotifications();
  const toast = useToast();
  const [activeTab, setActiveTab] = useState<TabType>('search');
  const [searchEmail, setSearchEmail] = useState('');
  const [searchResult, setSearchResult] = useState<UserSearchResponse | null>(null);
  const [searching, setSearching] = useState(false);
  const [pendingConnections, setPendingConnections] = useState<Connection[]>([]);
  const [acceptedConnections, setAcceptedConnections] = useState<Connection[]>([]);
  const [loadingPending, setLoadingPending] = useState(false);
  const [loadingConnections, setLoadingConnections] = useState(false);
  // Referral state
  const [referralEmail, setReferralEmail] = useState('');
  const [sendingReferral, setSendingReferral] = useState(false);
  const [referrals, setReferrals] = useState<Referral[]>([]);
  const [referralStats, setReferralStats] = useState<ReferralStats | null>(null);
  const [loadingReferrals, setLoadingReferrals] = useState(false);

  // Carica richieste pendenti e connessioni accettate quando si cambia tab
  useEffect(() => {
    if (activeTab === 'pending') {
      loadPendingRequests();
    } else if (activeTab === 'connections') {
      loadAcceptedConnections();
    } else if (activeTab === 'invite') {
      loadReferrals();
      loadReferralStats();
    }
  }, [activeTab]);
  
  const loadReferrals = async () => {
    try {
      setLoadingReferrals(true);
      const data = await getReferrals(50, 0);
      
      // Filtra per mostrare solo l'ultimo invito per email (raggruppa per email e prendi quello più recente)
      const referralsMap = new Map<string, Referral>();
      
      data.forEach(referral => {
        const email = referral.invited_email.toLowerCase();
        const existing = referralsMap.get(email);
        
        // Se non esiste o questo è più recente, usa questo
        if (!existing || new Date(referral.created_at) > new Date(existing.created_at)) {
          referralsMap.set(email, referral);
        }
      });
      
      // Converti la mappa in array e ordina per data (più recente prima)
      const uniqueReferrals = Array.from(referralsMap.values()).sort((a, b) => 
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );
      
      setReferrals(uniqueReferrals);
    } catch (error) {
      toast.error(`Errore nel caricamento inviti: ${error instanceof Error ? error.message : 'Errore sconosciuto'}`);
    } finally {
      setLoadingReferrals(false);
    }
  };
  
  const loadReferralStats = async () => {
    try {
      const stats = await getReferralStats();
      setReferralStats(stats);
    } catch (error) {
      console.error('Errore caricamento statistiche referral:', error);
      // Non mostrare errore all'utente per statistiche
    }
  };
  
  const handleSendReferral = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!referralEmail.trim()) {
      toast.error('Inserisci un\'email per invitare');
      return;
    }
    
    // Validazione base email
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(referralEmail.trim())) {
      toast.error('Email non valida');
      return;
    }
    
    try {
      setSendingReferral(true);
      await sendReferral(referralEmail.trim());
      toast.success(`Invito inviato a ${referralEmail.trim()}`);
      setReferralEmail('');
      
      // Ricarica inviti e statistiche
      await loadReferrals();
      await loadReferralStats();
    } catch (error) {
      toast.error(`Errore nell'invio invito: ${error instanceof Error ? error.message : 'Errore sconosciuto'}`);
    } finally {
      setSendingReferral(false);
    }
  };

  const loadPendingRequests = async () => {
    try {
      setLoadingPending(true);
      const response = await getPendingRequests(false); // Tutte (incoming + outgoing)
      setPendingConnections(response.connections);
    } catch (error) {
      toast.error(`Errore nel caricamento richieste pendenti: ${error instanceof Error ? error.message : 'Errore sconosciuto'}`);
    } finally {
      setLoadingPending(false);
    }
  };

  const loadAcceptedConnections = async () => {
    try {
      setLoadingConnections(true);
      const response = await getConnections('accepted', 100, 0);
      setAcceptedConnections(response.connections);
    } catch (error) {
      toast.error(`Errore nel caricamento connessioni: ${error instanceof Error ? error.message : 'Errore sconosciuto'}`);
    } finally {
      setLoadingConnections(false);
    }
  };

  const handleSearch = async () => {
    if (!searchEmail.trim()) {
      toast.error('Inserisci un\'email per cercare');
      return;
    }

    try {
      setSearching(true);
      const result = await searchUser(searchEmail.trim());
      setSearchResult(result);
    } catch (error) {
      toast.error(`Errore nella ricerca: ${error instanceof Error ? error.message : 'Errore sconosciuto'}`);
      setSearchResult(null);
    } finally {
      setSearching(false);
    }
  };

  const handleSendRequest = async (email: string) => {
    try {
      await sendConnectionRequest(email);
      toast.success('Richiesta di connessione inviata');
      setSearchResult(null);
      setSearchEmail('');
      
      // Aggiorna notifiche
      await refreshNotifications();
      
      // Ricarica richieste pendenti se siamo nella tab giusta
      if (activeTab === 'pending') {
        await loadPendingRequests();
      }
    } catch (error) {
      toast.error(`Errore nell'invio richiesta: ${error instanceof Error ? error.message : 'Errore sconosciuto'}`);
    }
  };

  const handleAcceptConnection = async (connectionId: string) => {
    try {
      await acceptConnection(connectionId);
      toast.success('Richiesta di connessione accettata');
      
      // Aggiorna notifiche
      await refreshNotifications();
      
      // Ricarica le liste
      await loadPendingRequests();
      await loadAcceptedConnections();
      
      // Cambia tab alle connessioni per vedere la nuova
      setActiveTab('connections');
    } catch (error) {
      toast.error(`Errore nell'accettazione: ${error instanceof Error ? error.message : 'Errore sconosciuto'}`);
    }
  };

  const handleDeleteConnection = async (connectionId: string) => {
    try {
      await deleteConnection(connectionId);
      toast.success('Connessione rimossa');
      
      // Ricarica le liste
      await loadPendingRequests();
      await loadAcceptedConnections();
      
      // Se era un risultato di ricerca, ricarica
      if (searchResult?.connection_id === connectionId) {
        setSearchResult(null);
      }
    } catch (error) {
      toast.error(`Errore nella rimozione: ${error instanceof Error ? error.message : 'Errore sconosciuto'}`);
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('it-IT', { day: 'numeric', month: 'short', year: 'numeric' });
  };

  // Separa richieste pendenti in incoming e outgoing
  const incomingPending = pendingConnections.filter(c => c.to_user_id === user?.id);
  const outgoingPending = pendingConnections.filter(c => c.from_user_id === user?.id);

  return (
    <div className="connections-view">
      <div className="connections-header">
        <h2>Connetti con altri utenti</h2>
        <p className="connections-subtitle">Cerca utenti, gestisci richieste e visualizza le tue connessioni</p>
      </div>

      {/* Tabs */}
      <div className="connections-tabs">
        <button
          className={`connections-tab ${activeTab === 'search' ? 'active' : ''}`}
          onClick={() => setActiveTab('search')}
        >
          <Search size={18} />
          <span>Cerca Utenti</span>
        </button>
        <button
          className={`connections-tab ${activeTab === 'pending' ? 'active' : ''}`}
          onClick={() => setActiveTab('pending')}
        >
          <Mail size={18} />
          <span>Richieste Pendenti</span>
          {incomingPending.length > 0 && (
            <span className="tab-badge">{incomingPending.length}</span>
          )}
        </button>
        <button
          className={`connections-tab ${activeTab === 'connections' ? 'active' : ''}`}
          onClick={() => setActiveTab('connections')}
        >
          <Users size={18} />
          <span>Le Mie Connessioni</span>
        </button>
        <button
          className={`connections-tab ${activeTab === 'invite' ? 'active' : ''}`}
          onClick={() => setActiveTab('invite')}
        >
          <Gift size={18} />
          <span>Invita un Amico</span>
        </button>
      </div>

      {/* Tab Content */}
      <div className="connections-content">
        <AnimatePresence mode="wait">
          {activeTab === 'search' && (
            <motion.div
              key="search"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.2 }}
              className="tab-content"
            >
              <div className="user-search-section">
                <div className="search-bar">
                  <input
                    type="email"
                    placeholder="Cerca per email (es: utente@example.com)"
                    value={searchEmail}
                    onChange={(e) => setSearchEmail(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        handleSearch();
                      }
                    }}
                    className="search-input"
                  />
                  <button
                    className="search-button"
                    onClick={handleSearch}
                    disabled={searching || !searchEmail.trim()}
                  >
                    {searching ? 'Cercando...' : 'Cerca'}
                  </button>
                </div>

                {searchResult && (
                  <div className="search-result">
                    {searchResult.found ? (
                      <div className="user-card">
                        <div className="user-card-header">
                          <div className="user-info">
                            <h3>{searchResult.user?.name}</h3>
                            <p className="user-email">{searchResult.user?.email}</p>
                          </div>
                          <div className="user-status">
                            {searchResult.is_connected && (
                              <span className="status-badge connected">Connesso</span>
                            )}
                            {searchResult.has_pending_request && !searchResult.is_connected && (
                              <span className="status-badge pending">Richiesta in attesa</span>
                            )}
                          </div>
                        </div>

                        <div className="user-card-actions">
                          {searchResult.is_connected ? (
                            <button
                              className="action-button danger"
                              onClick={() => searchResult.connection_id && handleDeleteConnection(searchResult.connection_id)}
                            >
                              <X size={16} />
                              Rimuovi Connessione
                            </button>
                          ) : searchResult.has_pending_request ? (
                            searchResult.pending_request_from_me ? (
                              <button
                                className="action-button danger"
                                onClick={() => searchResult.connection_id && handleDeleteConnection(searchResult.connection_id)}
                              >
                                <X size={16} />
                                Annulla Richiesta
                              </button>
                            ) : (
                              <button
                                className="action-button success"
                                onClick={() => searchResult.connection_id && handleAcceptConnection(searchResult.connection_id)}
                              >
                                <Check size={16} />
                                Accetta Richiesta
                              </button>
                            )
                          ) : (
                            <button
                              className="action-button primary"
                              onClick={() => searchResult.user?.email && handleSendRequest(searchResult.user.email)}
                            >
                              <UserPlus size={16} />
                              Invia Richiesta
                            </button>
                          )}
                        </div>
                      </div>
                    ) : (
                      <div className="no-results">
                        <p>Utente non trovato</p>
                        <p className="no-results-hint">Verifica che l'email sia corretta e che l'utente sia registrato</p>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </motion.div>
          )}

          {activeTab === 'pending' && (
            <motion.div
              key="pending"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.2 }}
              className="tab-content"
            >
              {loadingPending ? (
                <div className="loading-state">Caricamento richieste pendenti...</div>
              ) : (
                <div className="pending-requests">
                  {/* Richieste in arrivo */}
                  {incomingPending.length > 0 && (
                    <div className="pending-section">
                      <h3>Richieste in arrivo ({incomingPending.length})</h3>
                      <div className="connections-list">
                        {incomingPending.map((connection) => (
                          <ConnectionCard
                            key={connection.id}
                            connection={connection}
                            currentUserId={user?.id || ''}
                            onAccept={() => handleAcceptConnection(connection.id)}
                            onDelete={() => handleDeleteConnection(connection.id)}
                            direction="incoming"
                          />
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Richieste in uscita */}
                  {outgoingPending.length > 0 && (
                    <div className="pending-section">
                      <h3>Richieste inviate ({outgoingPending.length})</h3>
                      <div className="connections-list">
                        {outgoingPending.map((connection) => (
                          <ConnectionCard
                            key={connection.id}
                            connection={connection}
                            currentUserId={user?.id || ''}
                            onAccept={() => {}}
                            onDelete={() => handleDeleteConnection(connection.id)}
                            direction="outgoing"
                          />
                        ))}
                      </div>
                    </div>
                  )}

                  {pendingConnections.length === 0 && (
                    <div className="empty-state">
                      <Mail size={48} />
                      <p>Nessuna richiesta pendente</p>
                    </div>
                  )}
                </div>
              )}
            </motion.div>
          )}

          {activeTab === 'connections' && (
            <motion.div
              key="connections"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.2 }}
              className="tab-content"
            >
              {loadingConnections ? (
                <div className="loading-state">Caricamento connessioni...</div>
              ) : acceptedConnections.length > 0 ? (
                <div className="connections-list">
                  {acceptedConnections.map((connection) => {
                    return (
                      <ConnectionCard
                        key={connection.id}
                        connection={connection}
                        currentUserId={user?.id || ''}
                        onAccept={() => {}}
                        onDelete={() => handleDeleteConnection(connection.id)}
                        direction="accepted"
                      />
                    );
                  })}
                </div>
              ) : (
                <div className="empty-state">
                  <Users size={48} />
                  <p>Nessuna connessione ancora</p>
                  <p className="empty-state-hint">Cerca altri utenti per iniziare a connetterti</p>
                </div>
              )}
            </motion.div>
          )}

          {activeTab === 'invite' && (
            <motion.div
              key="invite"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.2 }}
              className="tab-content"
            >
              <div className="referral-section">
                <div className="referral-header">
                  <h3>Invita un Amico su NarrAI</h3>
                  <p className="referral-description">
                    Condividi NarrAI con i tuoi amici e colleghi! Invitali via email a registrarsi e inizia a collaborare insieme.
                  </p>
                </div>

                {/* Statistiche */}
                {referralStats && (
                  <div className="referral-stats">
                    <div className="stat-card">
                      <div className="stat-value">{referralStats.total_sent}</div>
                      <div className="stat-label">Inviti Inviati</div>
                    </div>
                    <div className="stat-card success">
                      <div className="stat-value">{referralStats.total_registered}</div>
                      <div className="stat-label">Registrati</div>
                    </div>
                    <div className="stat-card pending">
                      <div className="stat-value">{referralStats.pending}</div>
                      <div className="stat-label">In Attesa</div>
                    </div>
                  </div>
                )}

                {/* Form Invito */}
                <form onSubmit={handleSendReferral} className="referral-form">
                  <div className="referral-input-group">
                    <label htmlFor="referral-email">Email dell'amico da invitare</label>
                    <div className="referral-input-wrapper">
                      <input
                        id="referral-email"
                        type="email"
                        placeholder="amico@example.com"
                        value={referralEmail}
                        onChange={(e) => setReferralEmail(e.target.value)}
                        className="referral-input"
                        disabled={sendingReferral}
                      />
                      <button
                        type="submit"
                        className="referral-send-button"
                        disabled={sendingReferral || !referralEmail.trim()}
                      >
                        {sendingReferral ? (
                          <>
                            <span className="spinner-small"></span>
                            Invio...
                          </>
                        ) : (
                          <>
                            <Send size={16} />
                            Invia Invito
                          </>
                        )}
                      </button>
                    </div>
                    <p className="referral-hint">
                      L'invito verrà inviato via email con un link per registrarsi su NarrAI
                    </p>
                  </div>
                </form>

                {/* Lista Inviti */}
                {loadingReferrals ? (
                  <div className="loading-state">Caricamento inviti...</div>
                ) : referrals.length > 0 ? (
                  <div className="referrals-list">
                    <h4>Inviti Inviati</h4>
                    <div className="referrals-table">
                      {referrals.map((referral) => (
                        <div key={referral.id} className="referral-item">
                          <div className="referral-item-info">
                            <div className="referral-email">{referral.invited_email}</div>
                            <div className="referral-date">
                              Invitato il: {new Date(referral.created_at).toLocaleDateString('it-IT', {
                                day: 'numeric',
                                month: 'short',
                                year: 'numeric',
                                hour: '2-digit',
                                minute: '2-digit',
                              })}
                            </div>
                          </div>
                          <div className="referral-item-status">
                            {referral.status === 'pending' && (
                              <span className="status-badge pending">In Attesa</span>
                            )}
                            {referral.status === 'registered' && (
                              <span className="status-badge success">
                                <Check size={14} />
                                Registrato
                              </span>
                            )}
                            {referral.status === 'expired' && (
                              <span className="status-badge expired">Scaduto</span>
                            )}
                            {referral.registered_at && (
                              <div className="referral-registered-date">
                                Registrato il: {new Date(referral.registered_at).toLocaleDateString('it-IT')}
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="empty-state">
                    <Gift size={48} />
                    <p>Nessun invito inviato ancora</p>
                    <p className="empty-state-hint">Invia il tuo primo invito usando il form qui sopra</p>
                  </div>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

// Componente ConnectionCard
interface ConnectionCardProps {
  connection: Connection;
  currentUserId: string;
  onAccept: () => void;
  onDelete: () => void;
  direction: 'incoming' | 'outgoing' | 'accepted';
}

function ConnectionCard({ connection, currentUserId, onAccept, onDelete, direction }: ConnectionCardProps) {
  const isIncoming = direction === 'incoming';
  const isOutgoing = direction === 'outgoing';
  const isAccepted = direction === 'accepted';
  
  // Determina informazioni dell'altro utente basandosi sulla direzione
  let otherUserName: string;
  let otherUserEmail: string;
  
  if (isIncoming) {
    // Richiesta in arrivo: l'altro utente è il mittente (from_user)
    otherUserName = connection.from_user_name || connection.from_user_email || connection.from_user_id.substring(0, 8) + '...';
    otherUserEmail = connection.from_user_email || connection.from_user_id.substring(0, 8) + '...';
  } else if (isOutgoing) {
    // Richiesta inviata: l'altro utente è il destinatario (to_user)
    otherUserName = connection.to_user_name || connection.to_user_email || connection.to_user_id.substring(0, 8) + '...';
    otherUserEmail = connection.to_user_email || connection.to_user_id.substring(0, 8) + '...';
  } else {
    // Connessione accettata: determina quale utente è l'altro
    const isFromUser = connection.from_user_id === currentUserId;
    otherUserName = isFromUser
      ? (connection.to_user_name || connection.to_user_email || connection.to_user_id.substring(0, 8) + '...')
      : (connection.from_user_name || connection.from_user_email || connection.from_user_id.substring(0, 8) + '...');
    otherUserEmail = isFromUser
      ? (connection.to_user_email || connection.to_user_id.substring(0, 8) + '...')
      : (connection.from_user_email || connection.from_user_id.substring(0, 8) + '...');
  }

  return (
    <div className="connection-card">
      <div className="connection-card-content">
        <div className="connection-info">
          <div className="connection-user-info">
            <h4 className="connection-user-name">{otherUserName}</h4>
            <p className="connection-user-email">{otherUserEmail}</p>
          </div>
          {isAccepted && (
            <div className="connection-status accepted">
              <Check size={16} />
              <span>Connesso</span>
            </div>
          )}
          {isIncoming && (
            <div className="connection-status pending">
              <Mail size={16} />
              <span>Richiesta in arrivo</span>
            </div>
          )}
          {isOutgoing && (
            <div className="connection-status outgoing">
              <Mail size={16} />
              <span>Richiesta inviata</span>
            </div>
          )}
          <div className="connection-meta">
            <p className="connection-date">Dal: {new Date(connection.created_at).toLocaleDateString('it-IT')}</p>
          </div>
        </div>

        <div className="connection-actions">
          {isIncoming && (
            <>
              <button className="action-button success" onClick={onAccept}>
                <Check size={16} />
                Accetta
              </button>
              <button className="action-button danger" onClick={onDelete}>
                <X size={16} />
                Rifiuta
              </button>
            </>
          )}
          {(isOutgoing || isAccepted) && (
            <button className="action-button danger" onClick={onDelete}>
              <X size={16} />
              {isOutgoing ? 'Annulla' : 'Rimuovi'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

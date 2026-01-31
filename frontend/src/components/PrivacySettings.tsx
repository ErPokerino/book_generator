import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { getGdprDataSummary, exportUserData, deleteAccount, GdprDataSummary } from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { useToast } from '../hooks/useToast';
import './PrivacySettings.css';

export default function PrivacySettings() {
  const navigate = useNavigate();
  const { logout } = useAuth();
  const toast = useToast();
  
  const [loading, setLoading] = useState(true);
  const [dataSummary, setDataSummary] = useState<GdprDataSummary | null>(null);
  const [exporting, setExporting] = useState(false);
  
  // Delete account form
  const [password, setPassword] = useState('');
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    loadDataSummary();
  }, []);

  const loadDataSummary = async () => {
    try {
      setLoading(true);
      const data = await getGdprDataSummary();
      setDataSummary(data);
    } catch (error) {
      toast.error('Errore nel caricamento dei dati');
      console.error('Error loading data summary:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleExport = async () => {
    try {
      setExporting(true);
      const blob = await exportUserData();
      
      // Crea link per download
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `narrai_export_${new Date().toISOString().split('T')[0]}.zip`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      
      toast.success('Export completato! Il download e iniziato.');
    } catch (error) {
      toast.error('Errore durante l\'export dei dati');
      console.error('Error exporting data:', error);
    } finally {
      setExporting(false);
    }
  };

  const handleDeleteAccount = async () => {
    if (!password) {
      toast.error('Inserisci la password per confermare');
      return;
    }
    
    if (!confirmDelete) {
      toast.error('Devi confermare la cancellazione');
      return;
    }
    
    try {
      setDeleting(true);
      await deleteAccount({ password, confirm: true });
      
      toast.success('Account eliminato con successo');
      
      // Logout e redirect
      await logout();
      navigate('/login');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Errore durante la cancellazione');
      console.error('Error deleting account:', error);
    } finally {
      setDeleting(false);
    }
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleDateString('it-IT', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    });
  };

  if (loading) {
    return (
      <div className="privacy-settings-page">
        <div className="privacy-settings-container">
          <div className="privacy-loading">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
            </svg>
            <p>Caricamento dati...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="privacy-settings-page">
      <div className="privacy-settings-container">
        <header className="privacy-settings-header">
          <h1>Impostazioni Privacy</h1>
          <p>Gestisci i tuoi dati personali e la tua privacy</p>
        </header>

        {/* User Info Card */}
        <div className="privacy-settings-card">
          <div className="privacy-card-header">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
              <circle cx="12" cy="7" r="4" />
            </svg>
            <h2>I tuoi dati</h2>
          </div>
          <div className="privacy-card-body">
            {dataSummary && (
              <>
                <div className="privacy-user-info">
                  <div className="privacy-info-row">
                    <span className="privacy-info-label">Email</span>
                    <span className="privacy-info-value">{dataSummary.user.email}</span>
                  </div>
                  <div className="privacy-info-row">
                    <span className="privacy-info-label">Nome</span>
                    <span className="privacy-info-value">{dataSummary.user.name}</span>
                  </div>
                  <div className="privacy-info-row">
                    <span className="privacy-info-label">Registrato il</span>
                    <span className="privacy-info-value">{formatDate(dataSummary.user.created_at)}</span>
                  </div>
                  <div className="privacy-info-row">
                    <span className="privacy-info-label">Privacy accettata il</span>
                    <span className="privacy-info-value">{formatDate(dataSummary.user.privacy_accepted_at)}</span>
                  </div>
                </div>
                
                <div className="privacy-data-counts">
                  <div className="privacy-count-item">
                    <span className="privacy-count-number">{dataSummary.data_counts.books}</span>
                    <span className="privacy-count-label">Libri</span>
                  </div>
                  <div className="privacy-count-item">
                    <span className="privacy-count-number">{dataSummary.data_counts.connections}</span>
                    <span className="privacy-count-label">Connessioni</span>
                  </div>
                  <div className="privacy-count-item">
                    <span className="privacy-count-number">{dataSummary.data_counts.notifications}</span>
                    <span className="privacy-count-label">Notifiche</span>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>

        {/* Export Card */}
        <div className="privacy-settings-card">
          <div className="privacy-card-header">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="7 10 12 15 17 10" />
              <line x1="12" y1="15" x2="12" y2="3" />
            </svg>
            <h2>Scarica i tuoi dati</h2>
          </div>
          <div className="privacy-card-body">
            <div className="privacy-export-section">
              <p>
                Ai sensi dell'Art. 20 del GDPR (Diritto alla portabilita), puoi scaricare 
                una copia di tutti i tuoi dati personali in formato strutturato (JSON).
                Il download include il tuo profilo, i libri creati, le connessioni e le notifiche.
              </p>
              <button 
                className="privacy-export-btn"
                onClick={handleExport}
                disabled={exporting}
              >
                {exporting ? (
                  <>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ animation: 'spin 1s linear infinite' }}>
                      <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
                    </svg>
                    Export in corso...
                  </>
                ) : (
                  <>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                      <polyline points="7 10 12 15 17 10" />
                      <line x1="12" y1="15" x2="12" y2="3" />
                    </svg>
                    Scarica i miei dati
                  </>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Delete Account Card */}
        <div className="privacy-settings-card">
          <div className="privacy-card-header">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="3 6 5 6 21 6" />
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
              <line x1="10" y1="11" x2="10" y2="17" />
              <line x1="14" y1="11" x2="14" y2="17" />
            </svg>
            <h2>Elimina account</h2>
          </div>
          <div className="privacy-card-body">
            <div className="privacy-delete-section">
              <div className="privacy-delete-warning">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                  <line x1="12" y1="9" x2="12" y2="13" />
                  <line x1="12" y1="17" x2="12.01" y2="17" />
                </svg>
                <p>
                  <strong>Attenzione:</strong> Questa azione e irreversibile. Verranno eliminati 
                  permanentemente il tuo account, tutti i libri creati, i PDF, le copertine e 
                  tutte le connessioni. I libri condivisi con altri utenti verranno anonimizzati.
                </p>
              </div>
              
              <div className="privacy-delete-form">
                <div>
                  <label htmlFor="delete-password">Inserisci la tua password per confermare:</label>
                  <input
                    id="delete-password"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="La tua password"
                    disabled={deleting}
                  />
                </div>
                
                <label className="privacy-confirm-checkbox">
                  <input
                    type="checkbox"
                    checked={confirmDelete}
                    onChange={(e) => setConfirmDelete(e.target.checked)}
                    disabled={deleting}
                  />
                  <span>
                    Confermo di voler eliminare permanentemente il mio account e tutti i dati associati
                  </span>
                </label>
                
                <button
                  className="privacy-delete-btn"
                  onClick={handleDeleteAccount}
                  disabled={deleting || !password || !confirmDelete}
                >
                  {deleting ? (
                    <>
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ animation: 'spin 1s linear infinite' }}>
                        <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
                      </svg>
                      Eliminazione in corso...
                    </>
                  ) : (
                    <>
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <polyline points="3 6 5 6 21 6" />
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                      </svg>
                      Elimina il mio account
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Legal Links */}
        <div className="privacy-settings-card">
          <div className="privacy-card-header">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="16" y1="13" x2="8" y2="13" />
              <line x1="16" y1="17" x2="8" y2="17" />
              <polyline points="10 9 9 9 8 9" />
            </svg>
            <h2>Documenti legali</h2>
          </div>
          <div className="privacy-card-body">
            <div className="privacy-links">
              <Link to="/privacy">Privacy Policy</Link>
              <Link to="/cookies">Cookie Policy</Link>
              <Link to="/terms">Termini di Servizio</Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

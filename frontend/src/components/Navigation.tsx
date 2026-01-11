import { useState, useEffect } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { UserPlus } from 'lucide-react';
import './Navigation.css';
import { useAuth } from '../contexts/AuthContext';
import ConfirmModal from './ConfirmModal';
import NotificationBell from './NotificationBell';
import { getPendingConnectionsCount } from '../api/client';

export default function Navigation() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);
  const [pendingConnectionsCount, setPendingConnectionsCount] = useState(0);

  // Carica conteggio richieste pendenti incoming
  useEffect(() => {
    if (!user) {
      setPendingConnectionsCount(0);
      return;
    }

    const loadPendingCount = async () => {
      try {
        const response = await getPendingConnectionsCount();
        setPendingConnectionsCount(response.pending_count);
      } catch (error) {
        console.error('Errore nel recupero conteggio richieste pendenti:', error);
      }
    };

    loadPendingCount();

    // Polling ogni 30 secondi per aggiornare il badge
    const interval = setInterval(loadPendingCount, 30000);

    return () => clearInterval(interval);
  }, [user]);

  const handleLogoutClick = () => {
    setShowLogoutConfirm(true);
  };

  const handleLogoutConfirm = async () => {
    await handleLogoutAndRedirect();
  };

  const handleLogoutCancel = () => {
    setShowLogoutConfirm(false);
  };

  const handleLogoutAndRedirect = async () => {
    setShowLogoutConfirm(false);
    setIsLoggingOut(true);
    try {
      await logout();
      navigate('/login');
    } catch (error) {
      console.error('Errore nel logout:', error);
      setIsLoggingOut(false);
    }
  };


  return (
    <nav className="main-navigation">
      <div className="nav-brand">
        <h1>📚 NarrAI</h1>
      </div>
      
      {/* Desktop Navigation Links */}
      <div className="nav-desktop-links">
        <div className="nav-links">
          <NavLink
            to="/library"
            className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
          >
            Libreria
          </NavLink>
          <NavLink
            to="/new"
            className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
          >
            Nuovo Libro
          </NavLink>
          <NavLink
            to="/benchmark"
            className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
          >
            Valuta
          </NavLink>
          {user?.role === 'admin' && (
            <NavLink
              to="/analytics"
              className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
            >
              Analisi
            </NavLink>
          )}
          <NavLink
            to="/connections"
            className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
            style={{ position: 'relative' }}
          >
            <UserPlus size={18} style={{ marginRight: '0.5rem' }} />
            Connetti
            {pendingConnectionsCount > 0 && (
              <span className="nav-link-badge">{pendingConnectionsCount > 99 ? '99+' : pendingConnectionsCount}</span>
            )}
          </NavLink>
        </div>
        
        {user && (
          <div className="nav-user">
            <NotificationBell />
            <span className="nav-user-name">{user.name}</span>
            {user.role === 'admin' && (
              <span className="nav-user-badge">Admin</span>
            )}
            <button
              className="nav-logout-button"
              onClick={handleLogoutClick}
              disabled={isLoggingOut}
              title="Logout"
            >
              {isLoggingOut ? 'Uscita...' : 'Esci'}
            </button>
          </div>
        )}
      </div>

      {/* Mobile: Solo NotificationBell */}
      <div className="nav-mobile-only">
        <NotificationBell />
      </div>

      <ConfirmModal
        isOpen={showLogoutConfirm}
        title="Conferma Logout"
        message="Sei sicuro di voler uscire?"
        confirmText="Esci"
        cancelText="Annulla"
        onConfirm={handleLogoutConfirm}
        onCancel={handleLogoutCancel}
        variant="info"
      />
    </nav>
  );
}


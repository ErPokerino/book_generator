import { useState } from 'react';
import './Navigation.css';
import { useAuth } from '../contexts/AuthContext';
import ConfirmModal from './ConfirmModal';

interface NavigationProps {
  currentView: 'library' | 'newBook' | 'benchmark' | 'analytics';
  onNavigate: (view: 'library' | 'newBook' | 'benchmark' | 'analytics') => void;
}

export default function Navigation({ currentView, onNavigate }: NavigationProps) {
  const { user, logout } = useAuth();
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);

  const handleLogoutClick = () => {
    setShowLogoutConfirm(true);
  };

  const handleLogoutConfirm = async () => {
    setShowLogoutConfirm(false);
    setIsLoggingOut(true);
    try {
      await logout();
    } catch (error) {
      console.error('Errore nel logout:', error);
      setIsLoggingOut(false);
    }
  };

  const handleLogoutCancel = () => {
    setShowLogoutConfirm(false);
  };

  return (
    <nav className="main-navigation">
      <div className="nav-brand">
        <h1>📚 NarrAI</h1>
      </div>
      <div className="nav-links">
        <button
          className={`nav-link ${currentView === 'library' ? 'active' : ''}`}
          onClick={() => onNavigate('library')}
        >
          Libreria
        </button>
        <button
          className={`nav-link ${currentView === 'newBook' ? 'active' : ''}`}
          onClick={() => onNavigate('newBook')}
        >
          Nuovo Libro
        </button>
        <button
          className={`nav-link ${currentView === 'benchmark' ? 'active' : ''}`}
          onClick={() => onNavigate('benchmark')}
        >
          Valuta
        </button>
        {user?.role === 'admin' && (
          <button
            className={`nav-link ${currentView === 'analytics' ? 'active' : ''}`}
            onClick={() => onNavigate('analytics')}
          >
            Analisi
          </button>
        )}
      </div>
      {user && (
        <div className="nav-user">
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


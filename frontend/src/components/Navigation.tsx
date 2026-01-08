import { useState, useEffect } from 'react';
import { Menu, X } from 'lucide-react';
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
  const [isMobileMenuOpen, setMobileMenuOpen] = useState(false);

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

  const handleResetOnboarding = () => {
    localStorage.removeItem('narrai_onboarding_carousel');
    localStorage.removeItem('narrai_onboarding_tooltips');
    window.location.reload();
  };

  const toggleMobileMenu = () => {
    setMobileMenuOpen(!isMobileMenuOpen);
  };

  const closeMobileMenu = () => {
    setMobileMenuOpen(false);
  };

  const handleNavigate = (view: 'library' | 'newBook' | 'benchmark' | 'analytics') => {
    onNavigate(view);
    closeMobileMenu();
  };

  // Chiudi menu con ESC
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isMobileMenuOpen) {
        closeMobileMenu();
      }
    };

    if (isMobileMenuOpen) {
      document.addEventListener('keydown', handleEscape);
      // Previeni scroll quando menu è aperto
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }

    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.body.style.overflow = '';
    };
  }, [isMobileMenuOpen]);

  return (
    <nav className="main-navigation">
      <div className="nav-brand">
        <h1>📚 NarrAI</h1>
      </div>
      
      <button 
        className="nav-menu-toggle"
        onClick={toggleMobileMenu}
        aria-label="Menu"
        aria-expanded={isMobileMenuOpen}
      >
        {isMobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
      </button>

      {isMobileMenuOpen && (
        <div className="nav-menu-overlay" onClick={closeMobileMenu} />
      )}

      <div className={`nav-links ${isMobileMenuOpen ? 'mobile-open' : ''}`}>
        <button
          className={`nav-link ${currentView === 'library' ? 'active' : ''}`}
          onClick={() => handleNavigate('library')}
        >
          Libreria
        </button>
        <button
          className={`nav-link ${currentView === 'newBook' ? 'active' : ''}`}
          onClick={() => handleNavigate('newBook')}
        >
          Nuovo Libro
        </button>
        <button
          className={`nav-link ${currentView === 'benchmark' ? 'active' : ''}`}
          onClick={() => handleNavigate('benchmark')}
        >
          Valuta
        </button>
        {user?.role === 'admin' && (
          <button
            className={`nav-link ${currentView === 'analytics' ? 'active' : ''}`}
            onClick={() => handleNavigate('analytics')}
          >
            Analisi
          </button>
        )}
      </div>
      
      {user && (
        <div className={`nav-user ${isMobileMenuOpen ? 'mobile-open' : ''}`}>
          <span className="nav-user-name">{user.name}</span>
          {user.role === 'admin' && (
            <span className="nav-user-badge">Admin</span>
          )}
          <button
            className="nav-logout-button"
            onClick={handleResetOnboarding}
            title="Reset Onboarding (per test)"
            style={{ 
              marginRight: '0.5rem',
              fontSize: '0.75rem',
              padding: '0.25rem 0.5rem',
              opacity: 0.7
            }}
          >
            🔄 Reset Onboarding
          </button>
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


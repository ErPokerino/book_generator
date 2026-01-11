import { useState, useEffect, useRef } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { BookOpen, PlusCircle, BarChart3, UserPlus, User, Bell, LogOut, TrendingUp } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { useNotifications } from '../contexts/NotificationContext';
import { getPendingConnectionsCount } from '../api/client';
import ConfirmModal from './ConfirmModal';
import './BottomNavigation.css';

export default function BottomNavigation() {
  const { user, logout } = useAuth();
  const { unreadCount } = useNotifications();
  const navigate = useNavigate();
  const [pendingConnectionsCount, setPendingConnectionsCount] = useState(0);
  const [isProfileMenuOpen, setIsProfileMenuOpen] = useState(false);
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const profileMenuRef = useRef<HTMLDivElement>(null);

  // Carica conteggio richieste pendenti
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
    const interval = setInterval(loadPendingCount, 30000);
    return () => clearInterval(interval);
  }, [user]);

  // Chiudi menu profilo se si clicca fuori
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (profileMenuRef.current && !profileMenuRef.current.contains(event.target as Node)) {
        setIsProfileMenuOpen(false);
      }
    };

    if (isProfileMenuOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isProfileMenuOpen]);

  const handleLogoutClick = () => {
    setIsProfileMenuOpen(false);
    setShowLogoutConfirm(true);
  };

  const handleLogoutConfirm = async () => {
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

  const handleLogoutCancel = () => {
    setShowLogoutConfirm(false);
  };

  const handleProfileClick = () => {
    setIsProfileMenuOpen(!isProfileMenuOpen);
  };

  const handleNavigateToNotifications = () => {
    setIsProfileMenuOpen(false);
    // Naviga a una pagina notifiche o mostra dropdown notifiche
    // Per ora, chiudiamo solo il menu
  };

  const handleNavigateToAnalytics = () => {
    setIsProfileMenuOpen(false);
    navigate('/analytics');
  };

  if (!user) {
    return null;
  }

  return (
    <>
      <nav className="bottom-navigation">
        <NavLink
          to="/library"
          className={({ isActive }) => `bottom-nav-item ${isActive ? 'active' : ''}`}
        >
          <BookOpen size={24} />
          <span className="bottom-nav-label">Libreria</span>
        </NavLink>

        <NavLink
          to="/new"
          className={({ isActive }) => `bottom-nav-item ${isActive ? 'active' : ''}`}
        >
          <PlusCircle size={24} />
          <span className="bottom-nav-label">Nuovo</span>
        </NavLink>

        <NavLink
          to="/benchmark"
          className={({ isActive }) => `bottom-nav-item ${isActive ? 'active' : ''}`}
        >
          <BarChart3 size={24} />
          <span className="bottom-nav-label">Valuta</span>
        </NavLink>

        <NavLink
          to="/connections"
          className={({ isActive }) => `bottom-nav-item ${isActive ? 'active' : ''}`}
        >
          <div className="bottom-nav-icon-wrapper">
            <UserPlus size={24} />
            {pendingConnectionsCount > 0 && (
              <span className="bottom-nav-badge">{pendingConnectionsCount > 99 ? '99+' : pendingConnectionsCount}</span>
            )}
          </div>
          <span className="bottom-nav-label">Connetti</span>
        </NavLink>

        <div className="bottom-nav-item bottom-nav-profile" ref={profileMenuRef}>
          <button
            type="button"
            onClick={handleProfileClick}
            className={`bottom-nav-profile-button ${isProfileMenuOpen ? 'active' : ''}`}
            aria-label="Profilo"
          >
            <div className="bottom-nav-icon-wrapper">
              <Bell size={24} />
              {unreadCount > 0 && (
                <span className="bottom-nav-badge">{unreadCount > 99 ? '99+' : unreadCount}</span>
              )}
            </div>
            <span className="bottom-nav-label">Profilo</span>
          </button>

          {isProfileMenuOpen && (
            <div className="bottom-nav-profile-menu">
              <div className="profile-menu-header">
                <span className="profile-menu-name">{user.name}</span>
                {user.role === 'admin' && (
                  <span className="profile-menu-badge">Admin</span>
                )}
              </div>
              <div className="profile-menu-divider" />
              {user.role === 'admin' && (
                <button
                  type="button"
                  onClick={handleNavigateToAnalytics}
                  className="profile-menu-item"
                >
                  <TrendingUp size={18} />
                  <span>Analisi</span>
                </button>
              )}
              <button
                type="button"
                onClick={handleLogoutClick}
                className="profile-menu-item profile-menu-item-danger"
                disabled={isLoggingOut}
              >
                <LogOut size={18} />
                <span>{isLoggingOut ? 'Uscita...' : 'Esci'}</span>
              </button>
            </div>
          )}
        </div>
      </nav>

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
    </>
  );
}

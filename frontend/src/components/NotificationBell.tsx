import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { Bell, Check, CheckCheck, X } from 'lucide-react';
import { useNotifications } from '../contexts/NotificationContext';
import './NotificationBell.css';

export default function NotificationBell() {
  const {
    unreadCount,
    notifications,
    isLoading,
    fetchNotifications,
    markAsRead,
    markAllAsRead,
    deleteNotification,
  } = useNotifications();

  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [dropdownPosition, setDropdownPosition] = useState({ top: 0, right: 0 });
  const buttonRef = useRef<HTMLButtonElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Carica notifiche quando si apre il dropdown
  useEffect(() => {
    if (isDropdownOpen && notifications.length === 0) {
      fetchNotifications(50, 0, false);
    }
  }, [isDropdownOpen, notifications.length, fetchNotifications]);

  // Calcola posizione dropdown
  useEffect(() => {
    const updateDropdownPosition = () => {
      if (buttonRef.current) {
        const rect = buttonRef.current.getBoundingClientRect();
        setDropdownPosition({
          top: rect.bottom + 8,
          right: window.innerWidth - rect.right,
        });
      }
    };

    if (isDropdownOpen) {
      updateDropdownPosition();
      window.addEventListener('scroll', updateDropdownPosition, true);
      window.addEventListener('resize', updateDropdownPosition);
    }

    return () => {
      window.removeEventListener('scroll', updateDropdownPosition, true);
      window.removeEventListener('resize', updateDropdownPosition);
    };
  }, [isDropdownOpen]);

  // Chiudi dropdown se si clicca fuori
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node;
      const isButtonClick = buttonRef.current?.contains(target);
      const isDropdownClick = dropdownRef.current?.contains(target);

      if (!isButtonClick && !isDropdownClick && isDropdownOpen) {
        setIsDropdownOpen(false);
      }
    };

    if (isDropdownOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isDropdownOpen]);

  const handleToggleDropdown = () => {
    setIsDropdownOpen(!isDropdownOpen);
  };

  const handleMarkAsRead = async (notificationId: string) => {
    try {
      await markAsRead(notificationId);
    } catch (error) {
      console.error('Errore nel marcare notifica come letta:', error);
    }
  };

  const handleMarkAllAsRead = async () => {
    try {
      await markAllAsRead();
    } catch (error) {
      console.error('Errore nel marcare tutte le notifiche come lette:', error);
    }
  };

  const handleDelete = async (notificationId: string) => {
    try {
      await deleteNotification(notificationId);
    } catch (error) {
      console.error('Errore nell\'eliminazione notifica:', error);
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Adesso';
    if (diffMins < 60) return `${diffMins} min fa`;
    if (diffHours < 24) return `${diffHours} h fa`;
    if (diffDays < 7) return `${diffDays} gg fa`;
    return date.toLocaleDateString('it-IT', { day: 'numeric', month: 'short' });
  };

  return (
    <div className="notification-bell-container">
      <button
        ref={buttonRef}
        className={`notification-bell-button ${isDropdownOpen ? 'active' : ''}`}
        onClick={handleToggleDropdown}
        aria-label="Notifiche"
        aria-expanded={isDropdownOpen}
      >
        <Bell size={20} />
        {unreadCount > 0 && (
          <span className="notification-badge">{unreadCount > 99 ? '99+' : unreadCount}</span>
        )}
      </button>

      {isDropdownOpen &&
        createPortal(
          <div
            ref={dropdownRef}
            className="notification-dropdown"
            style={{
              position: 'fixed',
              top: dropdownPosition.top,
              right: dropdownPosition.right,
            }}
          >
            <div className="notification-dropdown-header">
              <h3>Notifiche</h3>
              {unreadCount > 0 && (
                <button
                  className="notification-mark-all-read"
                  onClick={handleMarkAllAsRead}
                  disabled={isLoading}
                  title="Segna tutte come lette"
                >
                  <CheckCheck size={16} />
                  <span>Segna tutte lette</span>
                </button>
              )}
            </div>

            <div className="notification-list">
              {isLoading && notifications.length === 0 ? (
                <div className="notification-empty">Caricamento...</div>
              ) : notifications.length === 0 ? (
                <div className="notification-empty">Nessuna notifica</div>
              ) : (
                notifications.map((notification) => (
                  <div
                    key={notification.id}
                    className={`notification-item ${!notification.is_read ? 'unread' : ''}`}
                  >
                    <div className="notification-item-content">
                      <div className="notification-item-header">
                        <h4 className="notification-title">{notification.title}</h4>
                        <div className="notification-item-actions">
                          {!notification.is_read && (
                            <button
                              className="notification-action-button"
                              onClick={() => handleMarkAsRead(notification.id)}
                              title="Segna come letta"
                            >
                              <Check size={14} />
                            </button>
                          )}
                          <button
                            className="notification-action-button"
                            onClick={() => handleDelete(notification.id)}
                            title="Elimina"
                          >
                            <X size={14} />
                          </button>
                        </div>
                      </div>
                      <p className="notification-message">{notification.message}</p>
                      <span className="notification-time">{formatDate(notification.created_at)}</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>,
          document.body
        )}
    </div>
  );
}

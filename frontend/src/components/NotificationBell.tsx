import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { Bell, Check, CheckCheck, X, CheckCircle, XCircle } from 'lucide-react';
import { useNotifications } from '../contexts/NotificationContext';
import { acceptBookShare, declineBookShare } from '../api/client';
import { useToast } from '../hooks/useToast';
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
    refreshNotifications,
  } = useNotifications();

  const toastHook = useToast();
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [dropdownPosition, setDropdownPosition] = useState({ top: 0, right: 0 });
  const [processingShares, setProcessingShares] = useState<Set<string>>(new Set());
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

  const handleAcceptBookShare = async (shareId: string, notificationId: string) => {
    if (processingShares.has(shareId)) return;

    try {
      setProcessingShares(prev => new Set(prev).add(shareId));
      await acceptBookShare(shareId);
      toastHook.success('Libro aggiunto alla libreria');
      
      // Marca notifica come letta (aggiorna stato locale e server)
      await markAsRead(notificationId);
      
      // Aggiorna notifiche per avere lo stato più recente dal server
      await refreshNotifications();
      
      // Emetti evento custom per aggiornare la libreria
      window.dispatchEvent(new CustomEvent('library-refresh'));
    } catch (error) {
      console.error('Errore nell\'accettazione condivisione:', error);
      toastHook.error(error instanceof Error ? error.message : 'Errore nell\'accettazione della condivisione');
    } finally {
      setProcessingShares(prev => {
        const next = new Set(prev);
        next.delete(shareId);
        return next;
      });
    }
  };

  const handleDeclineBookShare = async (shareId: string, notificationId: string) => {
    if (processingShares.has(shareId)) return;

    try {
      setProcessingShares(prev => new Set(prev).add(shareId));
      await declineBookShare(shareId);
      toastHook.success('Condivisione rifiutata');
      
      // Rimuovi notifica dalla lista (non serve marcare come letta prima di eliminare)
      await deleteNotification(notificationId);
      
      // Aggiorna notifiche per aggiornare conteggio non lette
      await refreshNotifications();
    } catch (error) {
      console.error('Errore nel rifiuto condivisione:', error);
      toastHook.error(error instanceof Error ? error.message : 'Errore nel rifiuto della condivisione');
    } finally {
      setProcessingShares(prev => {
        const next = new Set(prev);
        next.delete(shareId);
        return next;
      });
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
                notifications.map((notification) => {
                  const isBookShared = notification.type === 'book_shared';
                  const shareId = notification.data?.share_id as string | undefined;
                  const isProcessing = shareId ? processingShares.has(shareId) : false;

                  return (
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
                                disabled={isProcessing}
                              >
                                <Check size={14} />
                              </button>
                            )}
                            <button
                              className="notification-action-button"
                              onClick={() => handleDelete(notification.id)}
                              title="Elimina"
                              disabled={isProcessing}
                            >
                              <X size={14} />
                            </button>
                          </div>
                        </div>
                        <p className="notification-message">{notification.message}</p>
                        
                        {/* Pulsanti Accetta/Rifiuta per notifiche book_shared */}
                        {isBookShared && shareId && !notification.is_read && (
                          <div className="notification-book-share-actions">
                            <button
                              className="notification-accept-button"
                              onClick={() => handleAcceptBookShare(shareId, notification.id)}
                              disabled={isProcessing}
                              title="Accetta e aggiungi alla libreria"
                            >
                              <CheckCircle size={16} />
                              <span>Accetta</span>
                            </button>
                            <button
                              className="notification-decline-button"
                              onClick={() => handleDeclineBookShare(shareId, notification.id)}
                              disabled={isProcessing}
                              title="Rifiuta condivisione"
                            >
                              <XCircle size={16} />
                              <span>Rifiuta</span>
                            </button>
                          </div>
                        )}
                        
                        <span className="notification-time">{formatDate(notification.created_at)}</span>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>,
          document.body
        )}
    </div>
  );
}

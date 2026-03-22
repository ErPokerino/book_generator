import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bell, Check, CheckCheck, CheckCircle, X, XCircle } from 'lucide-react';
import { acceptBookShare, declineBookShare } from '../api/client';
import { useNotifications } from '../contexts/NotificationContext';
import { useToast } from '../hooks/useToast';
import EmptyState from './ui/EmptyState';

interface NotificationInboxPanelProps {
  variant?: 'dropdown' | 'page';
  onClose?: () => void;
}

export default function NotificationInboxPanel({
  variant = 'dropdown',
  onClose,
}: NotificationInboxPanelProps) {
  const navigate = useNavigate();
  const toast = useToast();
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
  const [processingShares, setProcessingShares] = useState<Set<string>>(new Set());

  const fetchLimit = useMemo(() => (variant === 'dropdown' ? 50 : 100), [variant]);

  useEffect(() => {
    void fetchNotifications(fetchLimit, 0, false);
  }, [fetchNotifications, fetchLimit]);

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
      console.error("Errore nell'eliminazione notifica:", error);
    }
  };

  const handleAcceptBookShare = async (shareId: string, notificationId: string) => {
    if (processingShares.has(shareId)) return;

    try {
      setProcessingShares((prev) => new Set(prev).add(shareId));
      await acceptBookShare(shareId);
      toast.success('Libro aggiunto alla libreria');
      await markAsRead(notificationId);
      await refreshNotifications();
      window.dispatchEvent(new CustomEvent('library-refresh'));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Errore nell'accettazione della condivisione");
    } finally {
      setProcessingShares((prev) => {
        const next = new Set(prev);
        next.delete(shareId);
        return next;
      });
    }
  };

  const handleDeclineBookShare = async (shareId: string, notificationId: string) => {
    if (processingShares.has(shareId)) return;

    try {
      setProcessingShares((prev) => new Set(prev).add(shareId));
      await declineBookShare(shareId);
      toast.success('Condivisione rifiutata');
      await deleteNotification(notificationId);
      await refreshNotifications();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Errore nel rifiuto della condivisione');
    } finally {
      setProcessingShares((prev) => {
        const next = new Set(prev);
        next.delete(shareId);
        return next;
      });
    }
  };

  const handleOpenInbox = () => {
    onClose?.();
    navigate('/notifications');
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
    <div className={`notification-inbox-panel notification-inbox-panel-${variant}`}>
      <div className="notification-dropdown-header">
        <h3>{variant === 'page' ? 'Centro notifiche' : 'Notifiche'}</h3>
        <div className="notification-panel-header-actions">
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
          {variant === 'dropdown' && (
            <button
              type="button"
              className="notification-mark-all-read"
              onClick={handleOpenInbox}
            >
              <Bell size={16} />
              <span>Apri inbox</span>
            </button>
          )}
          {onClose && (
            <button
              type="button"
              className="notification-dismiss-button"
              onClick={onClose}
              aria-label="Chiudi notifiche"
            >
              <X size={16} />
            </button>
          )}
        </div>
      </div>

      <div className="notification-list">
        {isLoading && notifications.length === 0 ? (
          <div className="notification-empty">Caricamento...</div>
        ) : notifications.length === 0 ? (
          <div className="notification-empty notification-empty-panel">
            <EmptyState
              icon={<Bell size={20} />}
              title="Nessuna notifica"
              description="Qui troverai richieste di condivisione, completamenti e aggiornamenti importanti."
            />
          </div>
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
    </div>
  );
}

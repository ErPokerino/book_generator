import { createContext, useContext, useState, useEffect, ReactNode, useCallback, useRef } from 'react';
import {
  Notification,
  getUnreadCount,
  getNotifications,
  markNotificationRead,
  markAllNotificationsRead,
  deleteNotification as apiDeleteNotification,
  getPendingConnectionsCount,
} from '../api/client';
import { useAuth } from './AuthContext';

interface NotificationContextType {
  unreadCount: number;
  pendingConnectionsCount: number;
  notifications: Notification[];
  isLoading: boolean;
  fetchUnreadCount: () => Promise<void>;
  fetchPendingConnectionsCount: () => Promise<void>;
  fetchNotifications: (limit?: number, skip?: number, unreadOnly?: boolean) => Promise<void>;
  markAsRead: (notificationId: string) => Promise<void>;
  markAllAsRead: () => Promise<void>;
  deleteNotification: (notificationId: string) => Promise<void>;
  refreshNotifications: () => Promise<void>;
}

const NotificationContext = createContext<NotificationContextType | undefined>(undefined);

export function useNotifications() {
  const context = useContext(NotificationContext);
  if (context === undefined) {
    throw new Error('useNotifications must be used within a NotificationProvider');
  }
  return context;
}

interface NotificationProviderProps {
  children: ReactNode;
}

export function NotificationProvider({ children }: NotificationProviderProps) {
  const { isAuthenticated } = useAuth();
  const [unreadCount, setUnreadCount] = useState(0);
  const [pendingConnectionsCount, setPendingConnectionsCount] = useState(0);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const pollingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchActivitySnapshotSafe = useCallback(async () => {
    if (!isAuthenticated) return;

    try {
      const [unreadResult, pendingResult] = await Promise.allSettled([
        getUnreadCount(),
        getPendingConnectionsCount(),
      ]);

      if (unreadResult.status === 'fulfilled') {
        setUnreadCount(unreadResult.value.unread_count);
      } else if (unreadResult.reason instanceof Error && unreadResult.reason.message.includes('401')) {
        console.warn('[NotificationContext] Sessione scaduta, polling interrotto');
        if (pollingIntervalRef.current) {
          clearInterval(pollingIntervalRef.current);
          pollingIntervalRef.current = null;
        }
        return;
      } else if (unreadResult.status === 'rejected') {
        console.error('[NotificationContext] Errore nel recupero conteggio notifiche:', unreadResult.reason);
      }

      if (pendingResult.status === 'fulfilled') {
        setPendingConnectionsCount(pendingResult.value.pending_count);
      } else if (pendingResult.reason instanceof Error && pendingResult.reason.message.includes('401')) {
        console.warn('[NotificationContext] Sessione scaduta, polling connessioni interrotto');
        if (pollingIntervalRef.current) {
          clearInterval(pollingIntervalRef.current);
          pollingIntervalRef.current = null;
        }
      } else if (pendingResult.status === 'rejected') {
        console.error('[NotificationContext] Errore nel recupero richieste pendenti:', pendingResult.reason);
      }
    } catch (error: unknown) {
      console.error('[NotificationContext] Errore nel recupero snapshot attività:', error);
    }
  }, [isAuthenticated]);

  // Polling periodico per aggiornare il conteggio attività (ogni 30 secondi)
  useEffect(() => {
    if (!isAuthenticated) {
      setUnreadCount(0);
      setPendingConnectionsCount(0);
      setNotifications([]);
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
      return;
    }

    void fetchActivitySnapshotSafe();

    pollingIntervalRef.current = setInterval(() => {
      void fetchActivitySnapshotSafe();
    }, 30000);

    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
    };
  }, [isAuthenticated, fetchActivitySnapshotSafe]);

  const fetchUnreadCount = useCallback(async () => {
    if (!isAuthenticated) return;

    try {
      setIsLoading(true);
      const response = await getUnreadCount();
      setUnreadCount(response.unread_count);
    } catch (error) {
      console.error('[NotificationContext] Errore nel recupero conteggio notifiche:', error);
      throw error;
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated]);

  const fetchPendingConnectionsCount = useCallback(async () => {
    if (!isAuthenticated) return;

    try {
      const response = await getPendingConnectionsCount();
      setPendingConnectionsCount(response.pending_count);
    } catch (error) {
      console.error('[NotificationContext] Errore nel recupero richieste pendenti:', error);
      throw error;
    }
  }, [isAuthenticated]);

  const fetchNotifications = useCallback(
    async (limit: number = 50, skip: number = 0, unreadOnly: boolean = false) => {
      if (!isAuthenticated) return;

      try {
        setIsLoading(true);
        const response = await getNotifications(limit, skip, unreadOnly);
        setNotifications(response.notifications);
        setUnreadCount(response.unread_count); // Aggiorna anche il conteggio
      } catch (error) {
        console.error('[NotificationContext] Errore nel recupero notifiche:', error);
        throw error;
      } finally {
        setIsLoading(false);
      }
    },
    [isAuthenticated]
  );

  const markAsRead = useCallback(
    async (notificationId: string) => {
      if (!isAuthenticated) return;

      try {
        await markNotificationRead(notificationId);
        
        // Aggiorna stato locale
        setNotifications((prev) =>
          prev.map((n) => (n.id === notificationId ? { ...n, is_read: true } : n))
        );
        
        // Aggiorna conteggio se la notifica era non letta
        setUnreadCount((prev) => Math.max(0, prev - 1));
        
        // Refresh conteggio per sicurezza
        await fetchActivitySnapshotSafe();
      } catch (error) {
        console.error('[NotificationContext] Errore nel marcare notifica come letta:', error);
        throw error;
      }
    },
    [isAuthenticated, fetchActivitySnapshotSafe]
  );

  const markAllAsRead = useCallback(async () => {
    if (!isAuthenticated) return;

    try {
      setIsLoading(true);
      await markAllNotificationsRead();
      
      // Aggiorna stato locale
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnreadCount(0);
      
      // Refresh per sicurezza
      await fetchActivitySnapshotSafe();
    } catch (error) {
      console.error('[NotificationContext] Errore nel marcare tutte le notifiche come lette:', error);
      throw error;
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated, fetchActivitySnapshotSafe]);

  const deleteNotification = useCallback(
    async (notificationId: string) => {
      if (!isAuthenticated) return;

      try {
        await apiDeleteNotification(notificationId);
        
        // Rimuovi dalla lista locale
        const deletedNotification = notifications.find((n) => n.id === notificationId);
        setNotifications((prev) => prev.filter((n) => n.id !== notificationId));
        
        // Aggiorna conteggio se la notifica era non letta
        if (deletedNotification && !deletedNotification.is_read) {
          setUnreadCount((prev) => Math.max(0, prev - 1));
        }
        
        // Refresh conteggio per sicurezza
        await fetchActivitySnapshotSafe();
      } catch (error) {
        console.error('[NotificationContext] Errore nell\'eliminazione notifica:', error);
        throw error;
      }
    },
    [isAuthenticated, notifications, fetchActivitySnapshotSafe]
  );

  const refreshNotifications = useCallback(async () => {
    if (!isAuthenticated) return;
    await fetchNotifications();
    await fetchActivitySnapshotSafe();
  }, [isAuthenticated, fetchNotifications, fetchActivitySnapshotSafe]);

  const value: NotificationContextType = {
    unreadCount,
    pendingConnectionsCount,
    notifications,
    isLoading,
    fetchUnreadCount,
    fetchPendingConnectionsCount,
    fetchNotifications,
    markAsRead,
    markAllAsRead,
    deleteNotification,
    refreshNotifications,
  };

  return <NotificationContext.Provider value={value}>{children}</NotificationContext.Provider>;
}

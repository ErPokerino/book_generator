import { createContext, useContext, useState, useEffect, ReactNode, useCallback, useRef } from 'react';
import {
  Notification,
  getUnreadCount,
  getNotifications,
  markNotificationRead,
  markAllNotificationsRead,
  deleteNotification as apiDeleteNotification,
} from '../api/client';
import { useAuth } from './AuthContext';

interface NotificationContextType {
  unreadCount: number;
  notifications: Notification[];
  isLoading: boolean;
  fetchUnreadCount: () => Promise<void>;
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
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Polling periodico per aggiornare il conteggio non lette (ogni 30 secondi)
  useEffect(() => {
    if (!isAuthenticated) {
      // Reset se non autenticato
      setUnreadCount(0);
      setNotifications([]);
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
      return;
    }

    // Fetch iniziale
    fetchUnreadCountSafe();

    // Avvia polling ogni 30 secondi
    pollingIntervalRef.current = setInterval(() => {
      fetchUnreadCountSafe();
    }, 30000); // 30 secondi

    // Cleanup al dismount o quando isAuthenticated cambia
    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
    };
  }, [isAuthenticated]);

  const fetchUnreadCountSafe = useCallback(async () => {
    if (!isAuthenticated) return;

    try {
      const response = await getUnreadCount();
      setUnreadCount(response.unread_count);
    } catch (error: unknown) {
      // Se errore 401, ferma il polling (sessione scaduta)
      if (error instanceof Error && error.message.includes('401')) {
        console.warn('[NotificationContext] Sessione scaduta, polling interrotto');
        if (pollingIntervalRef.current) {
          clearInterval(pollingIntervalRef.current);
          pollingIntervalRef.current = null;
        }
      } else {
        console.error('[NotificationContext] Errore nel recupero conteggio notifiche:', error);
      }
      // Non bloccare l'app se fallisce, mantieni il valore precedente
    }
  }, [isAuthenticated]);

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
        await fetchUnreadCountSafe();
      } catch (error) {
        console.error('[NotificationContext] Errore nel marcare notifica come letta:', error);
        throw error;
      }
    },
    [isAuthenticated, fetchUnreadCountSafe]
  );

  const markAllAsRead = useCallback(async () => {
    if (!isAuthenticated) return;

    try {
      setIsLoading(true);
      const response = await markAllNotificationsRead();
      
      // Aggiorna stato locale
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnreadCount(0);
      
      // Refresh per sicurezza
      await fetchUnreadCountSafe();
    } catch (error) {
      console.error('[NotificationContext] Errore nel marcare tutte le notifiche come lette:', error);
      throw error;
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated, fetchUnreadCountSafe]);

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
        await fetchUnreadCountSafe();
      } catch (error) {
        console.error('[NotificationContext] Errore nell\'eliminazione notifica:', error);
        throw error;
      }
    },
    [isAuthenticated, notifications, fetchUnreadCountSafe]
  );

  const refreshNotifications = useCallback(async () => {
    if (!isAuthenticated) return;
    await fetchNotifications();
    await fetchUnreadCountSafe();
  }, [isAuthenticated, fetchNotifications, fetchUnreadCountSafe]);

  const value: NotificationContextType = {
    unreadCount,
    notifications,
    isLoading,
    fetchUnreadCount,
    fetchNotifications,
    markAsRead,
    markAllAsRead,
    deleteNotification,
    refreshNotifications,
  };

  return <NotificationContext.Provider value={value}>{children}</NotificationContext.Provider>;
}

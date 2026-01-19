import { createContext, useContext, useState, useEffect, ReactNode, useCallback } from 'react';
import { User, login as apiLogin, register as apiRegister, logout as apiLogout, getCurrentUser } from '../api/client';

// Event per segnalare sessione scaduta (401)
export const SESSION_EXPIRED_EVENT = 'session-expired';

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Gestisce l'evento di sessione scaduta
  const handleSessionExpired = useCallback(() => {
    console.warn('[AuthContext] Sessione scaduta, logout automatico');
    setUser(null);
  }, []);

  // Ascolta l'evento di sessione scaduta
  useEffect(() => {
    window.addEventListener(SESSION_EXPIRED_EVENT, handleSessionExpired);
    return () => {
      window.removeEventListener(SESSION_EXPIRED_EVENT, handleSessionExpired);
    };
  }, [handleSessionExpired]);

  // Check sessione esistente all'avvio
  useEffect(() => {
    checkSession();
  }, []);

  const checkSession = async () => {
    try {
      setIsLoading(true);
      const currentUser = await getCurrentUser();
      setUser(currentUser);
    } catch (error) {
      console.error('[AuthContext] Errore nel check sessione:', error);
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  };

  const login = async (email: string, password: string) => {
    try {
      const response = await apiLogin({ email, password });
      setUser(response.user);
    } catch (error) {
      console.error('[AuthContext] Errore nel login:', error);
      throw error;
    }
  };

  const register = async (email: string, password: string, name: string) => {
    try {
      const newUser = await apiRegister({ email, password, name });
      // Dopo la registrazione, fai login automatico
      const loginResponse = await apiLogin({ email, password });
      setUser(loginResponse.user);
    } catch (error) {
      console.error('[AuthContext] Errore nella registrazione:', error);
      throw error;
    }
  };

  const logout = async () => {
    try {
      await apiLogout();
      setUser(null);
    } catch (error) {
      console.error('[AuthContext] Errore nel logout:', error);
      // Rimuovi utente anche se il logout fallisce
      setUser(null);
    }
  };

  const value: AuthContextType = {
    user,
    isAuthenticated: !!user,
    isLoading,
    login,
    register,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

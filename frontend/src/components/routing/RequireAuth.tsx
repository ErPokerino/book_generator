import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';

interface RequireAuthProps {
  children: React.ReactNode;
}

/**
 * Wrapper per proteggere route che richiedono autenticazione.
 * Redirect a /login se non autenticato, salvando la location per redirect post-login.
 */
export default function RequireAuth({ children }: RequireAuthProps) {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div style={{ 
        display: 'flex', 
        justifyContent: 'center', 
        alignItems: 'center', 
        minHeight: '100vh',
        fontSize: '1.125rem',
        color: 'var(--text-secondary)'
      }}>
        Caricamento...
      </div>
    );
  }

  if (!isAuthenticated) {
    // Salva la location corrente per redirect dopo login
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
}

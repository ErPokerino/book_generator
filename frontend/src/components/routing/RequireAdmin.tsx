import { Navigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import RequireAuth from './RequireAuth';

interface RequireAdminProps {
  children: React.ReactNode;
}

/**
 * Wrapper per proteggere route che richiedono ruolo admin.
 * Estende RequireAuth e verifica anche che l'utente sia admin.
 */
export default function RequireAdmin({ children }: RequireAdminProps) {
  const { user } = useAuth();

  return (
    <RequireAuth>
      {user?.role === 'admin' ? (
        <>{children}</>
      ) : (
        <Navigate to="/library" replace />
      )}
    </RequireAuth>
  );
}

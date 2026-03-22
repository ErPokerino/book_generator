import { Bell, UserPlus } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import NotificationInboxPanel from './NotificationInboxPanel';
import PageHeader from './ui/PageHeader';
import { useNotifications } from '../contexts/NotificationContext';
import './NotificationsPage.css';

export default function NotificationsPage() {
  const navigate = useNavigate();
  const { unreadCount, pendingConnectionsCount } = useNotifications();

  return (
    <div className="notifications-page">
      <PageHeader
        eyebrow="Activity Center"
        title="Notifiche e richieste"
        description="Un unico punto per condivisioni, completamenti, aggiornamenti e richieste in attesa."
        actions={(
          <button
            type="button"
            className="notifications-page-action"
            onClick={() => navigate('/connections')}
          >
            <UserPlus size={18} />
            <span>Gestisci connessioni</span>
          </button>
        )}
      />

      <div className="notifications-summary-grid">
        <article className="notifications-summary-card">
          <div className="notifications-summary-icon">
            <Bell size={20} />
          </div>
          <div>
            <span className="notifications-summary-label">Non lette</span>
            <strong className="notifications-summary-value">{unreadCount}</strong>
          </div>
        </article>

        <article className="notifications-summary-card">
          <div className="notifications-summary-icon notifications-summary-icon-warm">
            <UserPlus size={20} />
          </div>
          <div>
            <span className="notifications-summary-label">Richieste pendenti</span>
            <strong className="notifications-summary-value">{pendingConnectionsCount}</strong>
          </div>
        </article>
      </div>

      <section className="notifications-panel-shell">
        <NotificationInboxPanel variant="page" />
      </section>
    </div>
  );
}

import { ReactNode } from 'react';
import './EmptyState.css';

interface EmptyStateProps {
  title: string;
  description: string;
  icon?: ReactNode;
  action?: ReactNode;
}

export default function EmptyState({ title, description, icon, action }: EmptyStateProps) {
  return (
    <div className="empty-state-panel" role="status" aria-live="polite">
      {icon && <div className="empty-state-panel-icon">{icon}</div>}
      <div className="empty-state-panel-copy">
        <h3>{title}</h3>
        <p>{description}</p>
      </div>
      {action && <div className="empty-state-panel-action">{action}</div>}
    </div>
  );
}

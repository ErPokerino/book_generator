import { ReactNode } from 'react';
import './PageHeader.css';

interface PageHeaderProps {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
  align?: 'start' | 'center';
}

export default function PageHeader({
  eyebrow,
  title,
  description,
  actions,
  align = 'start',
}: PageHeaderProps) {
  return (
    <header className={`page-header page-header-${align}`}>
      <div className="page-header-copy">
        {eyebrow && <span className="page-header-eyebrow">{eyebrow}</span>}
        <h1 className="page-header-title">{title}</h1>
        {description && <p className="page-header-description">{description}</p>}
      </div>
      {actions && <div className="page-header-actions">{actions}</div>}
    </header>
  );
}

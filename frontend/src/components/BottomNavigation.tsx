import { useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { BookOpen, PenLine, MoreHorizontal } from 'lucide-react';
import './BottomNavigation.css';

export default function BottomNavigation() {
  const location = useLocation();
  const [toolsOpen, setToolsOpen] = useState(false);
  const toolsActive = location.pathname === '/benchmark' || location.pathname === '/analytics';
  const createActive = location.pathname === '/new' || location.pathname === '/manga';

  return (
    <nav className="bottom-navigation" aria-label="Mobile">
      <NavLink to="/library" className={({ isActive }) => `bottom-nav-item${isActive ? ' active' : ''}`}>
        <BookOpen size={20} strokeWidth={1.6} />
        <span className="bottom-nav-label">Opere</span>
      </NavLink>

      <NavLink to="/new" className={`bottom-nav-item${createActive ? ' active' : ''}`}>
        <PenLine size={20} strokeWidth={1.6} />
        <span className="bottom-nav-label">Crea</span>
      </NavLink>

      <div className="bottom-nav-tools">
        <button
          type="button"
          className={`bottom-nav-item${toolsActive ? ' active' : ''}`}
          aria-expanded={toolsOpen}
          aria-haspopup="menu"
          onClick={() => setToolsOpen((open) => !open)}
        >
          <MoreHorizontal size={20} strokeWidth={1.6} />
          <span className="bottom-nav-label">Strumenti</span>
        </button>
        {toolsOpen ? (
          <div className="bottom-nav-tools-menu" role="menu">
            <NavLink to="/benchmark" role="menuitem" onClick={() => setToolsOpen(false)}>
              Valuta
            </NavLink>
            <NavLink to="/analytics" role="menuitem" onClick={() => setToolsOpen(false)}>
              Analisi
            </NavLink>
          </div>
        ) : null}
      </div>
    </nav>
  );
}

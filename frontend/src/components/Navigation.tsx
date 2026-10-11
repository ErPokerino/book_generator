import { NavLink, useLocation } from 'react-router-dom';
import './Navigation.css';
import { Settings } from 'lucide-react';

export default function Navigation() {
  const location = useLocation();
  const createActive = location.pathname.startsWith('/new') || location.pathname === '/comics' || location.pathname === '/manga';

  return (
    <nav className="main-navigation" aria-label="Principale">
      <NavLink to="/library" className="nav-brand" aria-label="NarrAI, vai alle opere">
        <img src="/logo-mark.svg" alt="" className="nav-mark" />
        <span className="nav-wordmark">NarrAI</span>
      </NavLink>

      <div className="nav-right"><div className="nav-desktop-links">
        <NavLink to="/library" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
          Opere
        </NavLink>
        <NavLink to="/new" className={`nav-link nav-link-create${createActive ? ' active' : ''}`}>
          Crea
        </NavLink>
        <NavLink to="/benchmark" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
          Valuta
        </NavLink>
        <NavLink to="/analytics" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
          Analisi
        </NavLink>
      </div><NavLink to="/settings" className="ui-icon-button" aria-label="Impostazioni" title="Impostazioni"><Settings size={19} /></NavLink></div>
    </nav>
  );
}

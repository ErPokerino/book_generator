import { NavLink } from 'react-router-dom';
import './Navigation.css';

export default function Navigation() {
  return (
    <nav className="main-navigation">
      <div className="nav-brand">
        <img
          src="/logo-narrai.png"
          alt="NarrAI"
          className="nav-logo"
        />
      </div>

      {/* Desktop Navigation Links */}
      <div className="nav-desktop-links">
        <div className="nav-links">
          <NavLink
            to="/library"
            className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
          >
            Libreria
          </NavLink>
          <NavLink
            to="/new"
            className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
          >
            Nuovo Libro
          </NavLink>
          <NavLink
            to="/manga"
            className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
          >
            Manga
          </NavLink>
          <NavLink
            to="/benchmark"
            className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
          >
            Valuta
          </NavLink>
          <NavLink
            to="/analytics"
            className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
          >
            Analisi
          </NavLink>
        </div>
      </div>
    </nav>
  );
}

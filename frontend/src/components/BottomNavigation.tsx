import { NavLink } from 'react-router-dom';
import { BookOpen, PlusCircle, BarChart3, TrendingUp, Sparkles } from 'lucide-react';
import './BottomNavigation.css';

export default function BottomNavigation() {
  return (
    <nav className="bottom-navigation">
      <NavLink
        to="/library"
        className={({ isActive }) => `bottom-nav-item ${isActive ? 'active' : ''}`}
      >
        <BookOpen size={24} />
        <span className="bottom-nav-label">Libreria</span>
      </NavLink>

      <NavLink
        to="/new"
        className={({ isActive }) => `bottom-nav-item ${isActive ? 'active' : ''}`}
      >
        <PlusCircle size={24} />
        <span className="bottom-nav-label">Nuovo</span>
      </NavLink>

      <NavLink
        to="/manga"
        className={({ isActive }) => `bottom-nav-item ${isActive ? 'active' : ''}`}
      >
        <Sparkles size={24} />
        <span className="bottom-nav-label">Manga</span>
      </NavLink>

      <NavLink
        to="/benchmark"
        className={({ isActive }) => `bottom-nav-item ${isActive ? 'active' : ''}`}
      >
        <BarChart3 size={24} />
        <span className="bottom-nav-label">Valuta</span>
      </NavLink>

      <NavLink
        to="/analytics"
        className={({ isActive }) => `bottom-nav-item ${isActive ? 'active' : ''}`}
      >
        <TrendingUp size={24} />
        <span className="bottom-nav-label">Analisi</span>
      </NavLink>
    </nav>
  );
}

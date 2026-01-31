import { Link } from 'react-router-dom';
import { clearCookieConsent } from './CookieBanner';
import './Footer.css';

export default function Footer() {
  const currentYear = new Date().getFullYear();

  const handleManageCookies = () => {
    clearCookieConsent();
    window.location.reload();
  };

  return (
    <footer className="app-footer">
      <div className="footer-container">
        <nav className="footer-links">
          <Link to="/privacy" className="footer-link">
            Privacy Policy
          </Link>
          <span className="footer-separator">|</span>
          <Link to="/cookies" className="footer-link">
            Cookie Policy
          </Link>
          <span className="footer-separator">|</span>
          <Link to="/terms" className="footer-link">
            Termini di Servizio
          </Link>
          <span className="footer-separator">|</span>
          <button 
            className="footer-manage-cookies"
            onClick={handleManageCookies}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="3" />
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
            </svg>
            Gestione Cookie
          </button>
        </nav>
        <p className="footer-copyright">
          {currentYear} NarrAI. Tutti i diritti riservati.
        </p>
      </div>
    </footer>
  );
}

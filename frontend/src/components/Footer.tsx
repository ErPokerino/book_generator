import './Footer.css';

export default function Footer() {
  const currentYear = new Date().getFullYear();

  return (
    <footer className="app-footer">
      <div className="footer-container">
        <p className="footer-copyright">
          {currentYear} NarrAI. Tutti i diritti riservati.
        </p>
      </div>
    </footer>
  );
}

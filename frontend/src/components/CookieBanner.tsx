import { useState, useEffect } from 'react';
import './CookieBanner.css';

const COOKIE_CONSENT_KEY = 'cookie_consent';
const COOKIE_CONSENT_VERSION = '1'; // Increment when policy changes significantly

interface CookieConsent {
  necessary: boolean; // Always true, cannot be disabled
  functional: boolean;
  version: string;
  timestamp: string;
}

const defaultConsent: CookieConsent = {
  necessary: true,
  functional: true,
  version: COOKIE_CONSENT_VERSION,
  timestamp: new Date().toISOString(),
};

export function getCookieConsent(): CookieConsent | null {
  try {
    const stored = localStorage.getItem(COOKIE_CONSENT_KEY);
    if (!stored) return null;
    
    const consent = JSON.parse(stored) as CookieConsent;
    
    // If version changed, ask for consent again
    if (consent.version !== COOKIE_CONSENT_VERSION) {
      return null;
    }
    
    return consent;
  } catch {
    return null;
  }
}

export function saveCookieConsent(consent: CookieConsent): void {
  localStorage.setItem(COOKIE_CONSENT_KEY, JSON.stringify({
    ...consent,
    version: COOKIE_CONSENT_VERSION,
    timestamp: new Date().toISOString(),
  }));
}

export function clearCookieConsent(): void {
  localStorage.removeItem(COOKIE_CONSENT_KEY);
}

interface CookieBannerProps {
  onConsentChange?: (consent: CookieConsent) => void;
}

export default function CookieBanner({ onConsentChange }: CookieBannerProps) {
  const [showBanner, setShowBanner] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [consent, setConsent] = useState<CookieConsent>(defaultConsent);

  useEffect(() => {
    const existingConsent = getCookieConsent();
    if (!existingConsent) {
      setShowBanner(true);
    } else {
      setConsent(existingConsent);
    }
  }, []);

  const handleAcceptAll = () => {
    const fullConsent: CookieConsent = {
      necessary: true,
      functional: true,
      version: COOKIE_CONSENT_VERSION,
      timestamp: new Date().toISOString(),
    };
    saveCookieConsent(fullConsent);
    setConsent(fullConsent);
    setShowBanner(false);
    onConsentChange?.(fullConsent);
  };

  const handleAcceptNecessary = () => {
    const minimalConsent: CookieConsent = {
      necessary: true,
      functional: false,
      version: COOKIE_CONSENT_VERSION,
      timestamp: new Date().toISOString(),
    };
    saveCookieConsent(minimalConsent);
    setConsent(minimalConsent);
    setShowBanner(false);
    onConsentChange?.(minimalConsent);
  };

  const handleSaveSettings = () => {
    saveCookieConsent(consent);
    setShowSettings(false);
    setShowBanner(false);
    onConsentChange?.(consent);
  };

  if (!showBanner && !showSettings) {
    return null;
  }

  return (
    <>
      {showBanner && !showSettings && (
        <div className="cookie-banner-overlay">
          <div className="cookie-banner">
            <div className="cookie-banner-header">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <path d="M8 12h.01M12 12h.01M16 12h.01" />
              </svg>
              <h3>Utilizziamo i cookie</h3>
            </div>
            
            <div className="cookie-banner-content">
              <p>
                Utilizziamo cookie tecnici necessari per il funzionamento del sito. 
                Per maggiori informazioni, consulta la nostra{' '}
                <a href="/cookies">Cookie Policy</a> e la{' '}
                <a href="/privacy">Privacy Policy</a>.
              </p>
            </div>

            <div className="cookie-banner-actions">
              <button className="cookie-btn cookie-btn-accept" onClick={handleAcceptAll}>
                Accetta tutti
              </button>
              <button className="cookie-btn cookie-btn-necessary" onClick={handleAcceptNecessary}>
                Solo necessari
              </button>
              <button className="cookie-btn cookie-btn-settings" onClick={() => setShowSettings(true)}>
                Personalizza
              </button>
            </div>
          </div>
        </div>
      )}

      {showSettings && (
        <div className="cookie-settings-overlay" onClick={() => setShowSettings(false)}>
          <div className="cookie-settings-modal" onClick={(e) => e.stopPropagation()}>
            <div className="cookie-settings-header">
              <h3>Impostazioni Cookie</h3>
              <button className="cookie-settings-close" onClick={() => setShowSettings(false)}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M18 6L6 18M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="cookie-settings-body">
              <div className="cookie-category">
                <div className="cookie-category-header">
                  <span className="cookie-category-title">Cookie Necessari</span>
                  <span className="cookie-category-badge always">Sempre attivi</span>
                </div>
                <p>
                  Questi cookie sono essenziali per il funzionamento del sito. 
                  Includono il cookie di sessione per l'autenticazione. 
                  Non possono essere disattivati.
                </p>
              </div>

              <div className="cookie-category">
                <div className="cookie-category-header">
                  <span className="cookie-category-title">Cookie Funzionali</span>
                  <label className="cookie-toggle">
                    <input
                      type="checkbox"
                      checked={consent.functional}
                      onChange={(e) => setConsent({ ...consent, functional: e.target.checked })}
                    />
                    <span className="cookie-toggle-slider"></span>
                  </label>
                </div>
                <p>
                  Questi cookie permettono funzionalita aggiuntive come il salvataggio 
                  delle preferenze, lo stato dell'onboarding e il ripristino delle sessioni 
                  di scrittura. Memorizzati nel localStorage del browser.
                </p>
              </div>

              <div className="cookie-category">
                <div className="cookie-category-header">
                  <span className="cookie-category-title">Google Fonts</span>
                  <span className="cookie-category-badge">Terze parti</span>
                </div>
                <p>
                  Utilizziamo Google Fonts per i font del sito. Google potrebbe raccogliere 
                  il tuo indirizzo IP durante il caricamento dei font. Consulta la{' '}
                  <a href="https://policies.google.com/privacy" target="_blank" rel="noopener noreferrer">
                    Privacy Policy di Google
                  </a>.
                </p>
              </div>
            </div>

            <div className="cookie-settings-footer">
              <button className="cookie-btn cookie-btn-necessary" onClick={handleAcceptNecessary}>
                Solo necessari
              </button>
              <button className="cookie-btn cookie-btn-accept" onClick={handleSaveSettings}>
                Salva preferenze
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

// Export a button component to open cookie settings from footer
export function ManageCookiesButton() {
  const handleClick = () => {
    // Remove consent to show banner again
    clearCookieConsent();
    // Force page reload to show banner
    window.location.reload();
  };

  return (
    <button className="manage-cookies-link" onClick={handleClick}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <circle cx="12" cy="12" r="3" />
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
      </svg>
      Gestione Cookie
    </button>
  );
}

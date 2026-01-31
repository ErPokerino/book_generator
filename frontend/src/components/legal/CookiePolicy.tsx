import { Link } from 'react-router-dom';
import './LegalPage.css';

export default function CookiePolicy() {
  const lastUpdated = '31 Gennaio 2026';

  return (
    <div className="legal-page">
      <div className="legal-container">
        <Link to="/" className="legal-back-link">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M19 12H5M12 19l-7-7 7-7" />
          </svg>
          Torna alla home
        </Link>

        <header className="legal-header">
          <h1>Cookie Policy</h1>
          <div className="legal-meta">
            <span>Ultimo aggiornamento: {lastUpdated}</span>
          </div>
        </header>

        <div className="legal-content">
          <div className="legal-highlight">
            <p>
              Questa Cookie Policy spiega cosa sono i cookie, quali tipologie utilizziamo 
              su <strong>NarrAI</strong> e come puoi gestire le tue preferenze, in conformita 
              alla Direttiva ePrivacy (2002/58/CE) e al GDPR.
            </p>
          </div>

          <h2>1. Cosa Sono i Cookie</h2>
          <p>
            I cookie sono piccoli file di testo che vengono memorizzati sul tuo dispositivo 
            (computer, tablet, smartphone) quando visiti un sito web. Servono a far funzionare 
            correttamente il sito, a migliorare l'esperienza utente e, in alcuni casi, a fornire 
            informazioni ai proprietari del sito.
          </p>
          <p>
            Oltre ai cookie tradizionali, utilizziamo anche tecnologie simili come il 
            <strong> localStorage</strong>, che permette di memorizzare dati localmente nel tuo browser.
          </p>

          <h2>2. Cookie Tecnici (Necessari)</h2>
          <p>
            Questi cookie sono essenziali per il funzionamento del sito e non possono essere 
            disattivati. Non richiedono il tuo consenso ai sensi dell'Art. 5(3) della Direttiva ePrivacy 
            in quanto strettamente necessari per la fornitura del servizio richiesto.
          </p>

          <table className="legal-table">
            <thead>
              <tr>
                <th>Nome</th>
                <th>Tipo</th>
                <th>Finalita</th>
                <th>Durata</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><code>session_id</code></td>
                <td>Cookie HTTP</td>
                <td>Autenticazione e mantenimento della sessione utente</td>
                <td>7 giorni</td>
              </tr>
            </tbody>
          </table>

          <h3>Caratteristiche di sicurezza del cookie di sessione:</h3>
          <ul>
            <li><strong>HttpOnly:</strong> Non accessibile tramite JavaScript (protezione XSS)</li>
            <li><strong>Secure:</strong> Trasmesso solo su connessioni HTTPS</li>
            <li><strong>SameSite=Lax:</strong> Protezione contro attacchi CSRF</li>
          </ul>

          <h2>3. Local Storage (Tecnico)</h2>
          <p>
            Utilizziamo il localStorage del browser per memorizzare preferenze e dati 
            necessari al funzionamento dell'applicazione. Questi dati rimangono sul tuo 
            dispositivo e non vengono trasmessi ai nostri server.
          </p>

          <table className="legal-table">
            <thead>
              <tr>
                <th>Chiave</th>
                <th>Finalita</th>
                <th>Durata</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><code>current_book_session_id</code></td>
                <td>Ripristino della sessione di scrittura in corso</td>
                <td>Persistente fino a cancellazione</td>
              </tr>
              <tr>
                <td><code>dynamicForm.formData</code></td>
                <td>Salvataggio temporaneo dei dati del form</td>
                <td>Persistente fino a cancellazione</td>
              </tr>
              <tr>
                <td><code>dynamicForm.showAdvanced</code></td>
                <td>Preferenza visualizzazione opzioni avanzate</td>
                <td>Persistente</td>
              </tr>
              <tr>
                <td><code>onboarding.carousel</code></td>
                <td>Stato completamento tutorial iniziale</td>
                <td>Persistente</td>
              </tr>
              <tr>
                <td><code>onboarding.tooltips</code></td>
                <td>Tooltip visualizzati durante l'onboarding</td>
                <td>Persistente</td>
              </tr>
              <tr>
                <td><code>plot_autosave_*</code></td>
                <td>Salvataggio automatico della trama in scrittura</td>
                <td>Persistente fino a cancellazione</td>
              </tr>
              <tr>
                <td><code>cookie_consent</code></td>
                <td>Preferenze sui cookie espresse dall'utente</td>
                <td>1 anno</td>
              </tr>
            </tbody>
          </table>

          <h2>4. Cookie di Terze Parti</h2>
          <p>
            Il nostro sito utilizza servizi di terze parti che potrebbero impostare i propri cookie:
          </p>

          <h3>4.1 Google Fonts</h3>
          <p>
            Utilizziamo Google Fonts per caricare i font "Outfit" e "Playfair Display". 
            Quando visiti il nostro sito, il tuo browser si connette ai server di Google 
            per scaricare i file dei font.
          </p>
          <ul>
            <li><strong>Dati raccolti:</strong> Indirizzo IP, informazioni sul browser</li>
            <li><strong>Finalita:</strong> Caching e ottimizzazione del caricamento font</li>
            <li><strong>Base giuridica:</strong> Legittimo interesse</li>
            <li><strong>Informativa:</strong> <a href="https://policies.google.com/privacy" target="_blank" rel="noopener noreferrer">
              Google Privacy Policy
            </a></li>
          </ul>

          <h2>5. Come Gestire i Cookie</h2>
          
          <h3>5.1 Tramite il nostro sito</h3>
          <p>
            Puoi gestire le tue preferenze sui cookie cliccando sul pulsante "Gestione Cookie" 
            presente nel footer del sito o modificando le impostazioni dal banner dei cookie.
          </p>

          <h3>5.2 Tramite il browser</h3>
          <p>
            Puoi gestire o eliminare i cookie attraverso le impostazioni del tuo browser. 
            Ecco i link alle guide dei principali browser:
          </p>
          <ul>
            <li>
              <a href="https://support.google.com/chrome/answer/95647" target="_blank" rel="noopener noreferrer">
                Google Chrome
              </a>
            </li>
            <li>
              <a href="https://support.mozilla.org/it/kb/protezione-antitracciamento-avanzata-firefox-desktop" target="_blank" rel="noopener noreferrer">
                Mozilla Firefox
              </a>
            </li>
            <li>
              <a href="https://support.apple.com/it-it/guide/safari/sfri11471/mac" target="_blank" rel="noopener noreferrer">
                Safari
              </a>
            </li>
            <li>
              <a href="https://support.microsoft.com/it-it/microsoft-edge/eliminare-i-cookie-in-microsoft-edge-63947406-40ac-c3b8-57b9-2a946a29ae09" target="_blank" rel="noopener noreferrer">
                Microsoft Edge
              </a>
            </li>
          </ul>

          <h3>5.3 Cancellare il localStorage</h3>
          <p>
            Per cancellare i dati memorizzati nel localStorage, puoi:
          </p>
          <ol>
            <li>Aprire gli Strumenti per sviluppatori del browser (F12)</li>
            <li>Andare nella scheda "Applicazione" o "Storage"</li>
            <li>Selezionare "Local Storage" e cancellare i dati per il nostro dominio</li>
          </ol>

          <div className="legal-highlight">
            <p>
              <strong>Nota:</strong> Disabilitando i cookie tecnici o cancellando il localStorage, 
              alcune funzionalita del sito potrebbero non funzionare correttamente. 
              Ad esempio, potresti dover effettuare nuovamente l'accesso o perdere le 
              preferenze salvate.
            </p>
          </div>

          <h2>6. Aggiornamenti</h2>
          <p>
            Questa Cookie Policy puo essere aggiornata periodicamente per riflettere 
            modifiche nelle nostre pratiche o per altri motivi operativi, legali o normativi. 
            Ti invitiamo a consultarla regolarmente.
          </p>

          <h2>7. Contatti</h2>
          <p>
            Per domande relative a questa Cookie Policy o alla gestione dei cookie, contattaci:
          </p>
          <ul>
            <li><strong>Email:</strong> privacy@narrai.it</li>
          </ul>

          <div className="legal-footer">
            <p>
              Vedi anche: <Link to="/privacy">Privacy Policy</Link> | <Link to="/terms">Termini di Servizio</Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

import { Link } from 'react-router-dom';
import './LegalPage.css';

export default function PrivacyPolicy() {
  const lastUpdated = '31 Gennaio 2026';
  const effectiveDate = '31 Gennaio 2026';

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
          <h1>Privacy Policy</h1>
          <div className="legal-meta">
            <span>Ultimo aggiornamento: {lastUpdated}</span>
            <span>In vigore dal: {effectiveDate}</span>
          </div>
        </header>

        <div className="legal-content">
          <div className="legal-highlight">
            <p>
              <strong>NarrAI</strong> si impegna a proteggere la tua privacy. Questa informativa 
              descrive come raccogliamo, utilizziamo e proteggiamo i tuoi dati personali in 
              conformita al Regolamento Generale sulla Protezione dei Dati (GDPR - Regolamento UE 2016/679).
            </p>
          </div>

          <h2>1. Titolare del Trattamento</h2>
          <p>
            Il Titolare del trattamento dei dati personali e:
          </p>
          <ul>
            <li><strong>Denominazione:</strong> NarrAI</li>
            <li><strong>Email di contatto:</strong> privacy@narrai.it</li>
            <li><strong>Indirizzo:</strong> [Inserire indirizzo legale]</li>
          </ul>
          <p>
            Per qualsiasi richiesta relativa alla privacy o all'esercizio dei tuoi diritti, 
            puoi contattarci all'indirizzo email indicato sopra.
          </p>

          <h2>2. Dati Personali Raccolti</h2>
          <p>
            Raccogliamo le seguenti categorie di dati personali:
          </p>

          <h3>2.1 Dati di Registrazione</h3>
          <table className="legal-table">
            <thead>
              <tr>
                <th>Dato</th>
                <th>Finalita</th>
                <th>Base Giuridica</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Nome</td>
                <td>Personalizzazione del servizio, comunicazioni</td>
                <td>Esecuzione del contratto</td>
              </tr>
              <tr>
                <td>Indirizzo email</td>
                <td>Autenticazione, comunicazioni di servizio</td>
                <td>Esecuzione del contratto</td>
              </tr>
              <tr>
                <td>Password (hash crittografico)</td>
                <td>Sicurezza dell'account</td>
                <td>Esecuzione del contratto</td>
              </tr>
            </tbody>
          </table>

          <h3>2.2 Dati di Utilizzo del Servizio</h3>
          <table className="legal-table">
            <thead>
              <tr>
                <th>Dato</th>
                <th>Finalita</th>
                <th>Base Giuridica</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Contenuti dei libri (trame, bozze, capitoli)</td>
                <td>Generazione e memorizzazione dei tuoi libri</td>
                <td>Esecuzione del contratto</td>
              </tr>
              <tr>
                <td>Crediti di utilizzo</td>
                <td>Gestione del servizio e limiti d'uso</td>
                <td>Esecuzione del contratto</td>
              </tr>
              <tr>
                <td>Timestamp di attivita</td>
                <td>Funzionalita del servizio, ripristino sessioni</td>
                <td>Esecuzione del contratto</td>
              </tr>
            </tbody>
          </table>

          <h3>2.3 Dati Relazionali</h3>
          <table className="legal-table">
            <thead>
              <tr>
                <th>Dato</th>
                <th>Finalita</th>
                <th>Base Giuridica</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Connessioni con altri utenti</td>
                <td>Funzionalita di condivisione libri</td>
                <td>Esecuzione del contratto</td>
              </tr>
              <tr>
                <td>Condivisioni di libri</td>
                <td>Condivisione contenuti tra utenti connessi</td>
                <td>Esecuzione del contratto</td>
              </tr>
              <tr>
                <td>Inviti referral</td>
                <td>Programma di inviti e tracking</td>
                <td>Consenso</td>
              </tr>
            </tbody>
          </table>

          <h2>3. Finalita e Basi Giuridiche del Trattamento</h2>
          <p>Trattiamo i tuoi dati personali per le seguenti finalita:</p>

          <h3>3.1 Esecuzione del Contratto (Art. 6.1.b GDPR)</h3>
          <ul>
            <li>Creazione e gestione del tuo account</li>
            <li>Fornitura del servizio di generazione libri tramite AI</li>
            <li>Memorizzazione e accesso ai tuoi libri</li>
            <li>Gestione delle connessioni e condivisioni tra utenti</li>
            <li>Invio di comunicazioni di servizio (verifica email, reset password)</li>
          </ul>

          <h3>3.2 Legittimo Interesse (Art. 6.1.f GDPR)</h3>
          <ul>
            <li>Sicurezza del servizio e prevenzione frodi</li>
            <li>Miglioramento del servizio basato su statistiche aggregate</li>
            <li>Debug e risoluzione problemi tecnici</li>
          </ul>

          <h3>3.3 Consenso (Art. 6.1.a GDPR)</h3>
          <ul>
            <li>Invio di comunicazioni promozionali (se attivato)</li>
            <li>Partecipazione al programma referral</li>
          </ul>

          <h2>4. Condivisione dei Dati con Terze Parti</h2>
          <p>
            I tuoi dati possono essere condivisi con i seguenti fornitori di servizi 
            (sub-responsabili del trattamento):
          </p>

          <table className="legal-table">
            <thead>
              <tr>
                <th>Fornitore</th>
                <th>Servizio</th>
                <th>Dati Condivisi</th>
                <th>Localizzazione</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Google Cloud (Gemini AI)</td>
                <td>Generazione contenuti tramite AI</td>
                <td>Trame, bozze, contenuti libri</td>
                <td>UE/USA*</td>
              </tr>
              <tr>
                <td>Google Cloud Storage</td>
                <td>Archiviazione file</td>
                <td>PDF libri, immagini copertina</td>
                <td>UE</td>
              </tr>
              <tr>
                <td>Google Cloud Text-to-Speech</td>
                <td>Sintesi vocale critica letteraria</td>
                <td>Testo della critica</td>
                <td>UE/USA*</td>
              </tr>
              <tr>
                <td>Provider SMTP</td>
                <td>Invio email</td>
                <td>Email, nome</td>
                <td>UE</td>
              </tr>
              <tr>
                <td>Google Fonts</td>
                <td>Caricamento font</td>
                <td>Indirizzo IP</td>
                <td>USA*</td>
              </tr>
            </tbody>
          </table>

          <p>
            <small>
              * Per i trasferimenti verso gli Stati Uniti, ci avvaliamo delle Clausole 
              Contrattuali Standard (SCC) approvate dalla Commissione Europea e del 
              Data Privacy Framework UE-USA ove applicabile.
            </small>
          </p>

          <h2>5. Periodo di Conservazione dei Dati</h2>
          <p>Conserviamo i tuoi dati per i seguenti periodi:</p>

          <table className="legal-table">
            <thead>
              <tr>
                <th>Tipo di Dato</th>
                <th>Periodo di Conservazione</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Dati account</td>
                <td>Fino alla cancellazione dell'account</td>
              </tr>
              <tr>
                <td>Libri e contenuti</td>
                <td>Fino alla cancellazione dell'account o del singolo libro</td>
              </tr>
              <tr>
                <td>Sessioni di autenticazione</td>
                <td>7 giorni</td>
              </tr>
              <tr>
                <td>Token di verifica/reset</td>
                <td>24 ore</td>
              </tr>
              <tr>
                <td>Notifiche lette</td>
                <td>90 giorni</td>
              </tr>
              <tr>
                <td>Inviti referral pendenti</td>
                <td>30 giorni</td>
              </tr>
              <tr>
                <td>Log di audit</td>
                <td>2 anni</td>
              </tr>
            </tbody>
          </table>

          <h2>6. I Tuoi Diritti</h2>
          <p>
            In conformita al GDPR, hai i seguenti diritti sui tuoi dati personali:
          </p>

          <h3>6.1 Diritto di Accesso (Art. 15)</h3>
          <p>
            Hai il diritto di ottenere conferma che sia o meno in corso un trattamento 
            di dati personali che ti riguardano e, in tal caso, di ottenere l'accesso a tali dati.
          </p>

          <h3>6.2 Diritto di Rettifica (Art. 16)</h3>
          <p>
            Hai il diritto di ottenere la rettifica dei dati personali inesatti che ti riguardano 
            e l'integrazione dei dati incompleti.
          </p>

          <h3>6.3 Diritto alla Cancellazione (Art. 17)</h3>
          <p>
            Hai il diritto di ottenere la cancellazione dei tuoi dati personali ("diritto all'oblio"). 
            Puoi esercitare questo diritto dalla pagina <Link to="/settings/privacy">Impostazioni Privacy</Link>.
          </p>

          <h3>6.4 Diritto alla Portabilita (Art. 20)</h3>
          <p>
            Hai il diritto di ricevere i dati personali che ti riguardano in un formato strutturato, 
            di uso comune e leggibile da dispositivo automatico (JSON). 
            Puoi scaricare i tuoi dati dalla pagina <Link to="/settings/privacy">Impostazioni Privacy</Link>.
          </p>

          <h3>6.5 Diritto di Opposizione (Art. 21)</h3>
          <p>
            Hai il diritto di opporti al trattamento dei tuoi dati personali per motivi connessi 
            alla tua situazione particolare.
          </p>

          <h3>6.6 Diritto di Reclamo</h3>
          <p>
            Hai il diritto di proporre reclamo all'autorita di controllo competente. 
            In Italia, l'autorita e il <a href="https://www.garanteprivacy.it" target="_blank" rel="noopener noreferrer">
            Garante per la Protezione dei Dati Personali</a>.
          </p>

          <h2>7. Sicurezza dei Dati</h2>
          <p>
            Adottiamo misure tecniche e organizzative appropriate per proteggere i tuoi dati:
          </p>
          <ul>
            <li><strong>Crittografia password:</strong> Le password sono memorizzate con hash bcrypt</li>
            <li><strong>Cookie sicuri:</strong> Cookie di sessione con flag HttpOnly, Secure e SameSite</li>
            <li><strong>Connessioni cifrate:</strong> Tutte le comunicazioni avvengono tramite HTTPS</li>
            <li><strong>Accesso limitato:</strong> I dati sono accessibili solo al personale autorizzato</li>
          </ul>

          <h2>8. Trattamenti Automatizzati</h2>
          <p>
            NarrAI utilizza intelligenza artificiale (Google Gemini) per generare contenuti 
            (trame, bozze, capitoli, critiche letterarie). Questo trattamento:
          </p>
          <ul>
            <li>Non produce decisioni con effetti giuridici o significativi analoghi</li>
            <li>E basato esclusivamente sui contenuti che fornisci volontariamente</li>
            <li>Non comporta profilazione per finalita di marketing</li>
          </ul>

          <h2>9. Minori</h2>
          <p>
            Il servizio e destinato a utenti di almeno 16 anni. Non raccogliamo consapevolmente 
            dati di minori di 16 anni. Se ritieni che abbiamo raccolto dati di un minore, 
            contattaci immediatamente.
          </p>

          <h2>10. Modifiche alla Privacy Policy</h2>
          <p>
            Ci riserviamo il diritto di modificare questa informativa. In caso di modifiche 
            sostanziali, ti informeremo via email o tramite notifica nell'applicazione. 
            L'uso continuato del servizio dopo le modifiche costituisce accettazione delle stesse.
          </p>

          <h2>11. Contatti</h2>
          <p>
            Per qualsiasi domanda o richiesta relativa a questa informativa o al trattamento 
            dei tuoi dati personali, puoi contattarci a:
          </p>
          <ul>
            <li><strong>Email:</strong> privacy@narrai.it</li>
          </ul>

          <div className="legal-footer">
            <p>
              Vedi anche: <Link to="/cookies">Cookie Policy</Link> | <Link to="/terms">Termini di Servizio</Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

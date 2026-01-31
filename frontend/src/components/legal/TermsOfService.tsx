import { Link } from 'react-router-dom';
import './LegalPage.css';

export default function TermsOfService() {
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
          <h1>Termini di Servizio</h1>
          <div className="legal-meta">
            <span>Ultimo aggiornamento: {lastUpdated}</span>
            <span>In vigore dal: {effectiveDate}</span>
          </div>
        </header>

        <div className="legal-content">
          <div className="legal-highlight">
            <p>
              Benvenuto su <strong>NarrAI</strong>. Utilizzando il nostro servizio, 
              accetti i seguenti Termini di Servizio. Ti preghiamo di leggerli attentamente.
            </p>
          </div>

          <h2>1. Descrizione del Servizio</h2>
          <p>
            NarrAI e una piattaforma che utilizza intelligenza artificiale per assistere 
            gli utenti nella creazione di libri e contenuti narrativi. Il servizio include:
          </p>
          <ul>
            <li>Generazione di bozze e strutture narrative basate su input dell'utente</li>
            <li>Scrittura automatica di capitoli tramite modelli di AI</li>
            <li>Generazione di copertine e formattazione in vari formati (PDF, EPUB, DOCX)</li>
            <li>Critica letteraria automatizzata</li>
            <li>Funzionalita di condivisione tra utenti</li>
          </ul>

          <h2>2. Registrazione e Account</h2>
          
          <h3>2.1 Requisiti di Eta</h3>
          <p>
            Per utilizzare NarrAI devi avere almeno <strong>16 anni</strong>. 
            Se hai tra i 14 e i 16 anni, puoi utilizzare il servizio solo con il 
            consenso verificabile di un genitore o tutore legale.
          </p>

          <h3>2.2 Informazioni Account</h3>
          <p>
            Al momento della registrazione, ti impegni a:
          </p>
          <ul>
            <li>Fornire informazioni accurate e veritiere</li>
            <li>Mantenere riservate le tue credenziali di accesso</li>
            <li>Notificarci immediatamente qualsiasi uso non autorizzato del tuo account</li>
            <li>Non creare account multipli per eludere limiti o restrizioni</li>
          </ul>

          <h3>2.3 Sicurezza dell'Account</h3>
          <p>
            Sei responsabile di tutte le attivita che avvengono tramite il tuo account. 
            NarrAI non sara responsabile per eventuali perdite derivanti dall'uso non 
            autorizzato del tuo account.
          </p>

          <h2>3. Utilizzo del Servizio</h2>

          <h3>3.1 Uso Consentito</h3>
          <p>Ti impegni a utilizzare NarrAI esclusivamente per:</p>
          <ul>
            <li>Creare contenuti narrativi per uso personale o commerciale legittimo</li>
            <li>Condividere libri con altri utenti della piattaforma</li>
            <li>Esportare e pubblicare i contenuti creati</li>
          </ul>

          <h3>3.2 Uso Vietato</h3>
          <p>E' espressamente vietato utilizzare il servizio per:</p>
          <ul>
            <li>Creare contenuti illegali, diffamatori, osceni o che incitano all'odio</li>
            <li>Generare contenuti che violano diritti di proprieta intellettuale di terzi</li>
            <li>Produrre materiale pedopornografico o che sfrutta minori</li>
            <li>Creare spam, malware o contenuti fraudolenti</li>
            <li>Tentare di aggirare i sistemi di sicurezza o i limiti del servizio</li>
            <li>Rivendere o sublicenziare l'accesso al servizio senza autorizzazione</li>
            <li>Utilizzare bot o sistemi automatizzati non autorizzati</li>
          </ul>

          <h3>3.3 Sistema di Crediti</h3>
          <p>
            L'utilizzo del servizio e basato su un sistema di crediti. I crediti:
          </p>
          <ul>
            <li>Vengono consumati durante la generazione dei libri</li>
            <li>Variano in base al modello AI selezionato (Flash, Pro, Ultra)</li>
            <li>Non sono trasferibili ad altri utenti</li>
            <li>Possono essere resettati periodicamente secondo le nostre policy</li>
          </ul>

          <h2>4. Proprieta Intellettuale</h2>

          <h3>4.1 I Tuoi Contenuti</h3>
          <p>
            Mantieni la piena proprieta di tutti i contenuti originali che inserisci 
            nella piattaforma (trame, idee, personaggi da te creati). Ci concedi una 
            licenza limitata, non esclusiva e revocabile per elaborare tali contenuti 
            al solo fine di fornirti il servizio.
          </p>

          <h3>4.2 Contenuti Generati dall'AI</h3>
          <p>
            I contenuti generati dall'intelligenza artificiale sulla base dei tuoi input:
          </p>
          <ul>
            <li>Ti vengono concessi in licenza per qualsiasi uso, personale o commerciale</li>
            <li>Puoi pubblicarli, modificarli e distribuirli liberamente</li>
            <li>Non garantiamo l'originalita assoluta dei contenuti generati</li>
            <li>Sei responsabile di verificare che non violino diritti di terzi prima della pubblicazione</li>
          </ul>

          <h3>4.3 Proprieta di NarrAI</h3>
          <p>
            Il software, il design, i loghi, i marchi e tutti gli altri elementi della 
            piattaforma NarrAI rimangono di nostra esclusiva proprieta. Non ti e concesso 
            alcun diritto su tali elementi oltre a quanto strettamente necessario per 
            l'utilizzo del servizio.
          </p>

          <h2>5. Limitazioni dell'AI</h2>

          <div className="legal-highlight">
            <p>
              <strong>Importante:</strong> NarrAI utilizza modelli di intelligenza artificiale 
              che, per loro natura, possono produrre contenuti imprecisi, incoerenti o 
              inappropriati. L'utente e responsabile della revisione e approvazione finale 
              di tutti i contenuti generati prima della pubblicazione.
            </p>
          </div>

          <p>Riconosciamo che l'AI puo:</p>
          <ul>
            <li>Generare informazioni fattuali errate</li>
            <li>Produrre contenuti che involontariamente assomigliano a opere esistenti</li>
            <li>Creare incoerenze narrative</li>
            <li>Occasionalmente generare contenuti non appropriati nonostante i filtri</li>
          </ul>

          <h2>6. Garanzie e Responsabilita</h2>

          <h3>6.1 Servizio "As Is"</h3>
          <p>
            Il servizio e fornito "cosi com'e" e "come disponibile", senza garanzie di 
            alcun tipo, esplicite o implicite. Non garantiamo che il servizio sia sempre 
            disponibile, privo di errori o che soddisfi le tue esigenze specifiche.
          </p>

          <h3>6.2 Limitazione di Responsabilita</h3>
          <p>
            Nella misura massima consentita dalla legge, NarrAI non sara responsabile per:
          </p>
          <ul>
            <li>Danni indiretti, incidentali, speciali o consequenziali</li>
            <li>Perdita di profitti, dati o opportunita commerciali</li>
            <li>Contenuti generati dall'AI che risultino inappropriati o errati</li>
            <li>Interruzioni del servizio o perdita di dati</li>
          </ul>

          <h3>6.3 Indennizzo</h3>
          <p>
            Accetti di manlevare e tenere indenne NarrAI da qualsiasi reclamo, danno o 
            spesa derivante dal tuo uso del servizio in violazione di questi Termini.
          </p>

          <h2>7. Sospensione e Terminazione</h2>

          <h3>7.1 Da Parte Nostra</h3>
          <p>
            Ci riserviamo il diritto di sospendere o terminare il tuo account in caso di:
          </p>
          <ul>
            <li>Violazione di questi Termini di Servizio</li>
            <li>Uso abusivo o fraudolento del servizio</li>
            <li>Richiesta da parte di autorita competenti</li>
            <li>Inattivita prolungata (dopo preavviso)</li>
          </ul>

          <h3>7.2 Da Parte Tua</h3>
          <p>
            Puoi cancellare il tuo account in qualsiasi momento dalla pagina 
            <Link to="/settings/privacy"> Impostazioni Privacy</Link>. La cancellazione comporta 
            l'eliminazione definitiva di tutti i tuoi dati secondo quanto previsto nella 
            nostra <Link to="/privacy">Privacy Policy</Link>.
          </p>

          <h3>7.3 Effetti della Terminazione</h3>
          <p>
            Alla terminazione dell'account:
          </p>
          <ul>
            <li>Perderai l'accesso a tutti i libri memorizzati</li>
            <li>I crediti non utilizzati andranno persi</li>
            <li>I libri condivisi con altri utenti potrebbero essere anonimizzati</li>
          </ul>

          <h2>8. Modifiche ai Termini</h2>
          <p>
            Ci riserviamo il diritto di modificare questi Termini di Servizio in qualsiasi 
            momento. Le modifiche saranno comunicate tramite:
          </p>
          <ul>
            <li>Email all'indirizzo registrato</li>
            <li>Notifica nell'applicazione</li>
            <li>Aggiornamento della data "Ultimo aggiornamento" in questa pagina</li>
          </ul>
          <p>
            L'uso continuato del servizio dopo la notifica delle modifiche costituisce 
            accettazione dei nuovi termini.
          </p>

          <h2>9. Legge Applicabile e Foro Competente</h2>
          <p>
            Questi Termini sono regolati dalla legge italiana. Per qualsiasi controversia 
            derivante da o connessa a questi Termini o all'uso del servizio, sara competente 
            in via esclusiva il Foro di [Citta da inserire], fatti salvi i diritti inderogabili 
            del consumatore di adire il foro del proprio luogo di residenza o domicilio.
          </p>

          <h2>10. Risoluzione Alternativa delle Controversie</h2>
          <p>
            In conformita all'Art. 14 del Regolamento UE 524/2013, ti informiamo che la 
            Commissione Europea mette a disposizione una piattaforma per la risoluzione 
            online delle controversie (ODR) accessibile al seguente link: 
            <a href="https://ec.europa.eu/consumers/odr" target="_blank" rel="noopener noreferrer">
              https://ec.europa.eu/consumers/odr
            </a>
          </p>

          <h2>11. Disposizioni Generali</h2>

          <h3>11.1 Intero Accordo</h3>
          <p>
            Questi Termini, insieme alla Privacy Policy e alla Cookie Policy, costituiscono 
            l'intero accordo tra te e NarrAI riguardo all'uso del servizio.
          </p>

          <h3>11.2 Separabilita</h3>
          <p>
            Se una qualsiasi disposizione di questi Termini dovesse risultare invalida o 
            inapplicabile, le restanti disposizioni rimarranno pienamente valide ed efficaci.
          </p>

          <h3>11.3 Rinuncia</h3>
          <p>
            Il mancato esercizio di un diritto previsto da questi Termini non costituisce 
            rinuncia a tale diritto.
          </p>

          <h2>12. Contatti</h2>
          <p>
            Per qualsiasi domanda relativa a questi Termini di Servizio:
          </p>
          <ul>
            <li><strong>Email:</strong> legal@narrai.it</li>
          </ul>

          <div className="legal-footer">
            <p>
              Vedi anche: <Link to="/privacy">Privacy Policy</Link> | <Link to="/cookies">Cookie Policy</Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

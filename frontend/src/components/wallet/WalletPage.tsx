import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useToast } from '../../hooks/useToast';
import { 
  getCreditBalance, 
  getCreditPackages, 
  purchasePackage,
  getCreditTransactions,
  CreditBalanceResponse,
  CreditPackage,
  CreditTransaction
} from '../../api/client';
import PageHeader from '../ui/PageHeader';
import EmptyState from '../ui/EmptyState';
import './WalletPage.css';

export default function WalletPage() {
  const toast = useToast();
  
  const [loading, setLoading] = useState(true);
  const [balance, setBalance] = useState<CreditBalanceResponse | null>(null);
  const [packages, setPackages] = useState<CreditPackage[]>([]);
  const [transactions, setTransactions] = useState<CreditTransaction[]>([]);
  const [transactionsTotal, setTransactionsTotal] = useState(0);
  const [purchasing, setPurchasing] = useState<string | null>(null);
  const [showAllTransactions, setShowAllTransactions] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      
      // Carica dati in parallelo
      const [balanceData, packagesData, transactionsData] = await Promise.all([
        getCreditBalance(),
        getCreditPackages(),
        getCreditTransactions(0, 5)
      ]);
      
      setBalance(balanceData);
      setPackages(packagesData.packages);
      setTransactions(transactionsData.transactions);
      setTransactionsTotal(transactionsData.total);
    } catch (error) {
      toast.error('Errore nel caricamento dei dati');
      console.error('Error loading wallet data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handlePurchase = async (packageId: string) => {
    try {
      setPurchasing(packageId);
      
      const result = await purchasePackage(packageId);
      
      if (result.success) {
        toast.success(result.message);
        // Ricarica dati
        await loadData();
      } else {
        toast.error(result.message || 'Errore durante l\'acquisto');
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Errore durante l\'acquisto');
      console.error('Error purchasing package:', error);
    } finally {
      setPurchasing(null);
    }
  };

  const loadMoreTransactions = async () => {
    try {
      const data = await getCreditTransactions(0, 50);
      setTransactions(data.transactions);
      setTransactionsTotal(data.total);
      setShowAllTransactions(true);
    } catch (error) {
      toast.error('Errore nel caricamento dello storico');
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('it-IT', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const formatNextReset = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('it-IT', {
      weekday: 'long',
      day: 'numeric',
      month: 'long'
    });
  };

  const getTransactionIcon = (type: string) => {
    switch (type) {
      case 'purchase': return '💳';
      case 'consumption': return '📖';
      case 'bonus': return '🎁';
      case 'refund': return '↩️';
      case 'reset': return '🔄';
      default: return '💰';
    }
  };

  const getTransactionClass = (amount: number) => {
    return amount >= 0 ? 'positive' : 'negative';
  };

  const flashCost = balance?.mode_costs?.flash ?? 1;
  const proCost = balance?.mode_costs?.pro ?? 3;
  const ultraCost = balance?.mode_costs?.ultra ?? 5;

  if (loading) {
    return (
      <div className="wallet-page">
        <div className="wallet-loading">
          <div className="spinner"></div>
          <p>Caricamento...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="wallet-page">
      <PageHeader
        eyebrow="Wallet"
        title="Crediti e punti"
        description="Controlla il saldo, confronta i costi di generazione e valuta il pacchetto piu adatto prima di avviare un nuovo libro."
        actions={(
          <Link to="/settings/privacy" className="wallet-settings-link">
            Impostazioni account
          </Link>
        )}
      />

      <section className="wallet-overview-grid">
        <div className="balance-card">
          <div className="balance-icon">💎</div>
          <div className="balance-info">
            <span className="balance-label">Saldo attuale</span>
            <span className="balance-value">{balance?.credits ?? 0}</span>
            <span className="balance-unit">crediti</span>
          </div>
          <div className="balance-reset">
            <span className="reset-label">Prossimo reset gratuito</span>
            <span className="reset-date">
              {balance?.next_reset_at ? formatNextReset(balance.next_reset_at) : 'N/A'}
            </span>
          </div>
        </div>

        <div className="wallet-guide-card">
          <div className="wallet-guide-header">
            <span className="wallet-guide-badge">Guida rapida</span>
            <h2>Come leggere il wallet</h2>
          </div>
          <div className="wallet-guide-list">
            <div className="wallet-guide-item">
              <strong>Flash</strong>
              <span>Per bozze veloci e test rapidi.</span>
            </div>
            <div className="wallet-guide-item">
              <strong>Pro</strong>
              <span>Buon equilibrio fra costo e qualita narrativa.</span>
            </div>
            <div className="wallet-guide-item">
              <strong>Ultra</strong>
              <span>Per i casi in cui vuoi il massimo approfondimento.</span>
            </div>
          </div>
          <p className="wallet-guide-note">
            {packages.every((pkg) => pkg.price_eur === 0)
              ? 'I pacchetti sono attualmente in modalita sandbox: puoi validare l\'esperienza senza pagamento reale.'
              : 'Il costo viene addebitato solo quando avvii la scrittura del libro.'}
          </p>
        </div>
      </section>

      {/* Statistiche */}
      {(balance?.total_purchased || balance?.total_consumed) ? (
        <div className="balance-stats">
          <div className="stat-item">
            <span className="stat-value">{balance?.total_purchased ?? 0}</span>
            <span className="stat-label">Acquistati</span>
          </div>
          <div className="stat-item">
            <span className="stat-value">{balance?.total_consumed ?? 0}</span>
            <span className="stat-label">Utilizzati</span>
          </div>
        </div>
      ) : null}

      {/* Costi per modalità */}
      <section className="mode-costs">
        <div className="wallet-section-header">
          <h2>Confronto modalita</h2>
          <p>Vedi subito quante generazioni puoi permetterti con il saldo attuale.</p>
        </div>
        <div className="costs-grid">
          <div className="cost-item flash">
            <span className="mode-name">Flash</span>
            <span className="mode-cost">{flashCost} credito</span>
            <span className="mode-detail">{Math.floor((balance?.credits ?? 0) / flashCost)} avvii con il saldo attuale</span>
          </div>
          <div className="cost-item pro">
            <span className="mode-name">Pro</span>
            <span className="mode-cost">{proCost} crediti</span>
            <span className="mode-detail">{Math.floor((balance?.credits ?? 0) / proCost)} avvii con il saldo attuale</span>
          </div>
          <div className="cost-item ultra">
            <span className="mode-name">Ultra</span>
            <span className="mode-cost">{ultraCost} crediti</span>
            <span className="mode-detail">{Math.floor((balance?.credits ?? 0) / ultraCost)} avvii con il saldo attuale</span>
          </div>
        </div>
      </section>

      {/* Pacchetti crediti */}
      <section className="packages-section">
        <div className="wallet-section-header">
          <h2>Ricarica crediti</h2>
          <p>Confronta subito capienza, bonus e valore pratico per ogni modalita.</p>
        </div>
        
        <div className="packages-grid">
          {packages.map((pkg) => {
            const totalCredits = pkg.credits + pkg.bonus_credits;
            const flashRuns = Math.floor(totalCredits / flashCost);
            const proRuns = Math.floor(totalCredits / proCost);
            const ultraRuns = Math.floor(totalCredits / ultraCost);

            return (
              <div key={pkg.id} className={`package-card ${pkg.id}`}>
                <div className="package-topline">
                  <div className="package-icon">{pkg.icon || '📦'}</div>
                  <span className="package-tag">{pkg.price_eur === 0 ? 'Sandbox' : 'Pacchetto'}</span>
                </div>
                <h3 className="package-name">{pkg.name}</h3>
                <div className="package-credits">
                  <span className="credits-amount">{totalCredits}</span>
                  <span className="credits-label">crediti totali</span>
                  {pkg.bonus_credits > 0 && (
                    <span className="bonus-badge">+{pkg.bonus_credits} bonus</span>
                  )}
                </div>
                {pkg.description && (
                  <p className="package-description">{pkg.description}</p>
                )}
                <div className="package-price">
                  {pkg.price_eur === 0 ? (
                    <span className="price-free">Gratis</span>
                  ) : (
                    <span className="price-amount">€{pkg.price_eur.toFixed(2)}</span>
                  )}
                </div>
                <div className="package-value-grid">
                  <span>Flash: {flashRuns}</span>
                  <span>Pro: {proRuns}</span>
                  <span>Ultra: {ultraRuns}</span>
                </div>
                <button
                  className="purchase-button"
                  onClick={() => handlePurchase(pkg.id)}
                  disabled={purchasing !== null}
                >
                  {purchasing === pkg.id ? (
                    <span className="purchasing">Acquisto...</span>
                  ) : (
                    <span>Ottieni</span>
                  )}
                </button>
              </div>
            );
          })}
        </div>
      </section>

      {/* Storico transazioni */}
      <section className="transactions-section">
        <div className="wallet-section-header">
          <h2>Storico transazioni</h2>
          <p>Ultimi movimenti del saldo, con dettaglio di acquisti e consumi.</p>
        </div>
        
        {transactions.length === 0 ? (
          <div className="transactions-empty">
            <EmptyState
              title="Nessuna transazione ancora"
              description="Quando inizierai ad acquistare o consumare crediti, lo storico comparira qui."
            />
          </div>
        ) : (
          <>
            <div className="transactions-list">
              {transactions.map((tx) => (
                <div key={tx.id} className="transaction-item">
                  <div className="transaction-icon">{getTransactionIcon(tx.type)}</div>
                  <div className="transaction-info">
                    <span className="transaction-description">{tx.description}</span>
                    <span className="transaction-date">{formatDate(tx.created_at)}</span>
                  </div>
                  <div className={`transaction-amount ${getTransactionClass(tx.amount)}`}>
                    {tx.amount >= 0 ? '+' : ''}{tx.amount}
                  </div>
                </div>
              ))}
            </div>
            
            {!showAllTransactions && transactionsTotal > 5 && (
              <button 
                className="load-more-button"
                onClick={loadMoreTransactions}
              >
                Mostra tutte ({transactionsTotal} transazioni)
              </button>
            )}
          </>
        )}
      </section>
    </div>
  );
}

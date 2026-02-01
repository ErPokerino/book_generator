import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
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
import './WalletPage.css';

export default function WalletPage() {
  const { user } = useAuth();
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
      <header className="wallet-header">
        <h1>Crediti</h1>
        <p className="wallet-subtitle">Gestisci i tuoi crediti per la generazione di libri</p>
      </header>

      {/* Saldo crediti */}
      <section className="balance-section">
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
        <div className="mode-costs">
          <h3>Costo per generazione</h3>
          <div className="costs-grid">
            <div className="cost-item flash">
              <span className="mode-name">Flash</span>
              <span className="mode-cost">{balance?.mode_costs?.flash ?? 1} credito</span>
            </div>
            <div className="cost-item pro">
              <span className="mode-name">Pro</span>
              <span className="mode-cost">{balance?.mode_costs?.pro ?? 3} crediti</span>
            </div>
            <div className="cost-item ultra">
              <span className="mode-name">Ultra</span>
              <span className="mode-cost">{balance?.mode_costs?.ultra ?? 5} crediti</span>
            </div>
          </div>
        </div>
      </section>

      {/* Pacchetti crediti */}
      <section className="packages-section">
        <h2>Ricarica crediti</h2>
        <p className="packages-subtitle">Scegli un pacchetto per ricaricare i tuoi crediti</p>
        
        <div className="packages-grid">
          {packages.map((pkg) => (
            <div key={pkg.id} className={`package-card ${pkg.id}`}>
              <div className="package-icon">{pkg.icon || '📦'}</div>
              <h3 className="package-name">{pkg.name}</h3>
              <div className="package-credits">
                <span className="credits-amount">{pkg.credits}</span>
                <span className="credits-label">crediti</span>
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
          ))}
        </div>
      </section>

      {/* Storico transazioni */}
      <section className="transactions-section">
        <h2>Storico transazioni</h2>
        
        {transactions.length === 0 ? (
          <div className="transactions-empty">
            <p>Nessuna transazione ancora</p>
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

      {/* Link alle impostazioni */}
      <section className="wallet-footer">
        <Link to="/settings/privacy" className="settings-link">
          Impostazioni account →
        </Link>
      </section>
    </div>
  );
}

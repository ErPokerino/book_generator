import { useState, useEffect } from 'react';
import { getLibraryStats, getAdvancedStats, getUsersStats, LibraryStats, AdvancedStats, UsersStats } from '../api/client';
import Dashboard from './Dashboard';
import ModelComparisonTable from './ModelComparisonTable';
import { SkeletonBox, SkeletonText, SkeletonChart } from './Skeleton';
import { useToast } from '../hooks/useToast';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import './AnalyticsView.css';

export default function AnalyticsView() {
  const toast = useToast();
  const [stats, setStats] = useState<LibraryStats | null>(null);
  const [advancedStats, setAdvancedStats] = useState<AdvancedStats | null>(null);
  const [usersStats, setUsersStats] = useState<UsersStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadStats = async () => {
      try {
        setLoading(true);
        const [statsData, advancedData, usersData] = await Promise.all([
          getLibraryStats(),
          getAdvancedStats(),
          getUsersStats(),
        ]);
        setStats(statsData);
        setAdvancedStats(advancedData);
        setUsersStats(usersData);
      } catch (err) {
        toast.error(err instanceof Error ? err.message : 'Errore nel caricamento delle statistiche');
      } finally {
        setLoading(false);
      }
    };

    loadStats();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Esegui solo al mount

  // Formatta date per i grafici temporali
  const formatBooksOverTimeData = () => {
    if (!advancedStats || !advancedStats.books_over_time) return [];
    return Object.entries(advancedStats.books_over_time).map(([date, count]) => ({
      date: new Date(date).toLocaleDateString('it-IT', { day: '2-digit', month: '2-digit' }),
      libri: count,
    }));
  };

  const formatScoreTrendData = () => {
    if (!advancedStats || !advancedStats.score_trend_over_time) return [];
    return Object.entries(advancedStats.score_trend_over_time).map(([date, score]) => ({
      date: new Date(date).toLocaleDateString('it-IT', { day: '2-digit', month: '2-digit' }),
      voto: score,
    }));
  };

  if (loading) {
    return (
      <div className="analytics-view">
        <h1 className="analytics-title">📊 Analisi e Statistiche</h1>
        
        {/* Skeleton Statistiche Base */}
        <section className="analytics-section">
          <h2 className="section-title">Statistiche Base</h2>
          <div className="stats-grid-skeleton">
            {Array.from({ length: 6 }).map((_, index) => (
              <div key={index} className="stat-card-skeleton">
                <SkeletonBox width="100%" height="1rem" className="skeleton-stat-label" />
                <SkeletonBox width="60%" height="2rem" className="skeleton-stat-value" style={{ marginTop: '0.75rem' }} />
              </div>
            ))}
          </div>
        </section>

        {/* Skeleton Tendenze Temporali */}
        <section className="analytics-section">
          <h2 className="section-title">Tendenze Temporali</h2>
          <div className="chart-container">
            <SkeletonBox width="200px" height="1.5rem" className="skeleton-chart-subtitle" style={{ marginBottom: '1rem' }} />
            <SkeletonChart height="300px" />
          </div>
        </section>
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="analytics-view">
        <div className="empty-state">
          <p>Nessun dato disponibile per le analisi.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="analytics-view">
      <h1 className="analytics-title">📊 Analisi e Statistiche</h1>
      
      {/* Statistiche Base */}
      <section className="analytics-section">
        <h2 className="section-title">Statistiche Base</h2>
        <Dashboard stats={stats} />
      </section>

      {/* Tendenze Temporali */}
      {advancedStats && (
        <section className="analytics-section">
          <h2 className="section-title">Tendenze Temporali</h2>
          
          {/* Grafico Libri Creati nel Tempo */}
          {Object.keys(advancedStats.books_over_time || {}).length > 0 && (
            <div className="chart-container">
              <h3 className="chart-subtitle">Libri Creati nel Tempo</h3>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart
                  data={formatBooksOverTimeData()}
                  margin={{ top: 5, right: 30, left: 20, bottom: 60 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-light)" />
                  <XAxis
                    dataKey="date"
                    angle={-45}
                    textAnchor="end"
                    height={80}
                    tick={{ fill: 'var(--text-secondary)', fontSize: 12 }}
                  />
                  <YAxis
                    tick={{ fill: 'var(--text-secondary)', fontSize: 12 }}
                    domain={[0, 'dataMax + 1']}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'var(--surface)',
                      border: '1px solid var(--border-light)',
                      borderRadius: 'var(--radius-md)',
                    }}
                  />
                  <Legend />
                  <Line
                    type="monotone"
                    dataKey="libri"
                    stroke="#2563eb"
                    strokeWidth={2}
                    dot={{ fill: '#2563eb', r: 4 }}
                    activeDot={{ r: 6 }}
                    name="Libri creati"
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Grafico Trend Voto nel Tempo */}
          {Object.keys(advancedStats.score_trend_over_time || {}).length > 0 && (
            <div className="chart-container" style={{ marginTop: '2rem' }}>
              <h3 className="chart-subtitle">Trend Voto Medio nel Tempo</h3>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart
                  data={formatScoreTrendData()}
                  margin={{ top: 5, right: 30, left: 20, bottom: 60 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-light)" />
                  <XAxis
                    dataKey="date"
                    angle={-45}
                    textAnchor="end"
                    height={80}
                    tick={{ fill: 'var(--text-secondary)', fontSize: 12 }}
                  />
                  <YAxis
                    tick={{ fill: 'var(--text-secondary)', fontSize: 12 }}
                    domain={[0, 10]}
                  />
                  <Tooltip
                    formatter={(value: number) => [`${value.toFixed(2)}/10`, 'Voto medio']}
                    contentStyle={{
                      backgroundColor: 'var(--surface)',
                      border: '1px solid var(--border-light)',
                      borderRadius: 'var(--radius-md)',
                    }}
                  />
                  <Legend />
                  <Line
                    type="monotone"
                    dataKey="voto"
                    stroke="#f59e0b"
                    strokeWidth={2}
                    dot={{ fill: '#f59e0b', r: 4 }}
                    activeDot={{ r: 6 }}
                    name="Voto medio"
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </section>
      )}

      {/* Confronto Modelli */}
      {advancedStats && advancedStats.model_comparison.length > 0 && (
        <section className="analytics-section">
          <h2 className="section-title">Confronto Modelli</h2>
          <p className="section-description">
            Tabella comparativa dettagliata dei modelli LLM utilizzati. Clicca sulle colonne per ordinare.
          </p>
          <ModelComparisonTable models={advancedStats.model_comparison} />
        </section>
      )}

      {/* Statistiche Utenti */}
      {usersStats && (
        <section className="analytics-section">
          <h2 className="section-title">Statistiche Utenti</h2>
          <div style={{ marginBottom: '2rem' }}>
            <div style={{
              display: 'inline-block',
              padding: '1rem 2rem',
              background: 'linear-gradient(135deg, var(--primary-dark), var(--primary-light))',
              borderRadius: 'var(--radius-md)',
              color: 'white',
              fontSize: '1.1rem',
              fontWeight: 600,
            }}>
              👥 Totale Utenti: {usersStats.total_users}
            </div>
          </div>
          
          {usersStats.users_with_books.length > 0 && (
            <div style={{ overflowX: 'auto' }}>
              <table style={{
                width: '100%',
                borderCollapse: 'collapse',
                marginTop: '1rem',
              }}>
                <thead>
                  <tr style={{
                    background: 'var(--surface-elevated)',
                    borderBottom: '2px solid var(--border)',
                  }}>
                    <th style={{
                      padding: '0.75rem 1rem',
                      textAlign: 'left',
                      fontWeight: 600,
                      color: 'var(--text-primary)',
                    }}>Nome</th>
                    <th style={{
                      padding: '0.75rem 1rem',
                      textAlign: 'left',
                      fontWeight: 600,
                      color: 'var(--text-primary)',
                    }}>Email</th>
                    <th style={{
                      padding: '0.75rem 1rem',
                      textAlign: 'right',
                      fontWeight: 600,
                      color: 'var(--text-primary)',
                    }}>Libri Generati</th>
                  </tr>
                </thead>
                <tbody>
                  {usersStats.users_with_books.map((user) => (
                    <tr
                      key={user.user_id}
                      style={{
                        borderBottom: '1px solid var(--border-light)',
                      }}
                    >
                      <td style={{
                        padding: '0.75rem 1rem',
                        color: 'var(--text-primary)',
                      }}>{user.name}</td>
                      <td style={{
                        padding: '0.75rem 1rem',
                        color: 'var(--text-secondary)',
                        fontSize: '0.9rem',
                      }}>{user.email}</td>
                      <td style={{
                        padding: '0.75rem 1rem',
                        textAlign: 'right',
                        fontWeight: 600,
                        color: 'var(--accent)',
                      }}>{user.books_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </div>
  );
}

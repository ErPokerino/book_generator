import { useState, useEffect } from 'react';
import { getLibraryStats, getAdvancedStats, LibraryStats, AdvancedStats } from '../api/client';
import Dashboard from './Dashboard';
import ModelComparisonTable from './ModelComparisonTable';
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
  const [stats, setStats] = useState<LibraryStats | null>(null);
  const [advancedStats, setAdvancedStats] = useState<AdvancedStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadStats = async () => {
      try {
        setLoading(true);
        setError(null);
        const [statsData, advancedData] = await Promise.all([
          getLibraryStats(),
          getAdvancedStats(),
        ]);
        setStats(statsData);
        setAdvancedStats(advancedData);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Errore nel caricamento delle statistiche');
      } finally {
        setLoading(false);
      }
    };

    loadStats();
  }, []);

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
        <div className="loading-message">Caricamento analisi...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="analytics-view">
        <div className="error-message">
          <p>Errore: {error}</p>
          <button onClick={() => window.location.reload()}>Ricarica</button>
        </div>
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
    </div>
  );
}

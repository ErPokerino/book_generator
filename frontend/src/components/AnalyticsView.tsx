import { useState, useEffect } from 'react';
import { getLibraryStats, getAdvancedStats, LibraryStats, AdvancedStats } from '../api/client';
import Dashboard from './Dashboard';
import ModelComparisonTable from './ModelComparisonTable';
import { SkeletonBox, SkeletonChart } from './Skeleton';
import { useToast } from '../hooks/useToast';
import PageHeader from './ui/PageHeader';
import EmptyState from './ui/EmptyState';
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
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadStats = async () => {
      try {
        setLoading(true);
        const [statsData, advancedData] = await Promise.all([
          getLibraryStats(),
          getAdvancedStats(),
        ]);
        setStats(statsData);
        setAdvancedStats(advancedData);
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
      <div className="analytics-view page-shell">
        <PageHeader
          title="Analisi"
          description="Volumi e andamento della libreria locale."
        />
        
        {/* Skeleton Statistiche Base */}
        <section className="analytics-section">
          <h2 className="section-title">Statistiche Base</h2>
          <div className="stats-grid-skeleton">
            {Array.from({ length: 6 }).map((_, index) => (
              <div key={index} className="stat-card-skeleton">
                <SkeletonBox width="100%" height="1rem" className="skeleton-stat-label" />
                <SkeletonBox width="60%" height="2rem" className="skeleton-stat-value" />
              </div>
            ))}
          </div>
        </section>

        {/* Skeleton Tendenze Temporali */}
        <section className="analytics-section">
          <h2 className="section-title">Tendenze Temporali</h2>
          <div className="chart-container">
            <SkeletonBox width="200px" height="1.5rem" className="skeleton-chart-subtitle" />
            <SkeletonChart height="300px" />
          </div>
        </section>
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="analytics-view">
        <EmptyState
          title="Nessun dato disponibile"
          description="Le metriche appariranno qui non appena saranno disponibili libri da analizzare."
        />
      </div>
    );
  }

  return (
    <div className="analytics-view page-shell">
      <PageHeader
        title="Analisi"
        description="Volumi e andamento della libreria locale."
      />

      <section className="analytics-section">
        <h2 className="section-title">Statistiche</h2>
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
                    stroke="var(--accent)"
                    strokeWidth={2}
                    dot={{ fill: 'var(--ink)', r: 3 }}
                    activeDot={{ r: 5 }}
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
                    formatter={(value: number | string | undefined) => [
                      typeof value === 'number' ? value.toFixed(2) : (value ?? 'N/A'),
                      'Voto medio',
                    ]}
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
                    stroke="var(--ink)"
                    strokeWidth={2}
                    dot={{ fill: 'var(--accent)', r: 3 }}
                    activeDot={{ r: 5 }}
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

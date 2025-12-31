import { useState } from 'react';
import { LibraryStats } from '../api/client';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import './Dashboard.css';

interface DashboardProps {
  stats: LibraryStats;
}

export default function Dashboard({ stats }: DashboardProps) {
  const [chartView, setChartView] = useState<'book' | 'page'>('book');

  const formatTime = (minutes: number) => {
    if (minutes < 60) {
      return `${minutes.toFixed(0)} min`;
    }
    const hours = Math.floor(minutes / 60);
    const mins = Math.floor(minutes % 60);
    return `${hours}h ${mins}min`;
  };

  const formatTimeShort = (minutes: number) => {
    if (minutes < 1) {
      return `${(minutes * 60).toFixed(0)} sec`;
    }
    if (minutes < 60) {
      return `${minutes.toFixed(1)} min`;
    }
    const hours = Math.floor(minutes / 60);
    const mins = Math.floor(minutes % 60);
    if (mins === 0) {
      return `${hours}h`;
    }
    return `${hours}h ${mins}min`;
  };

  return (
    <div className="dashboard">
      <h2 className="dashboard-title">Statistiche Libreria</h2>
      
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-label">Libri Totali</div>
          <div className="stat-value">{stats.total_books}</div>
        </div>

        <div className="stat-card">
          <div className="stat-label">Completati</div>
          <div className="stat-value">{stats.completed_books}</div>
        </div>

        <div className="stat-card">
          <div className="stat-label">In Corso</div>
          <div className="stat-value">{stats.in_progress_books}</div>
        </div>

        <div className="stat-card">
          <div className="stat-label">Voto Medio</div>
          <div className="stat-value">
            {stats.average_score !== null && stats.average_score !== undefined 
              ? `${stats.average_score.toFixed(1)}/10`
              : 'N/A'}
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-label">Pagine Medie</div>
          <div className="stat-value">{stats.average_pages.toFixed(1)}</div>
        </div>

        <div className="stat-card">
          <div className="stat-label">Tempo Medio</div>
          <div className="stat-value">{formatTime(stats.average_writing_time_minutes)}</div>
        </div>
      </div>

      {Object.keys(stats.books_by_model).length > 0 && (
        <div className="stats-section">
          <h3>Distribuzione per Modello</h3>
          <div className="stats-bars">
            {Object.entries(stats.books_by_model)
              .sort(([, a], [, b]) => b - a)
              .map(([model, count]) => (
                <div key={model} className="stat-bar-item">
                  <div className="stat-bar-label">{model}</div>
                  <div className="stat-bar-container">
                    <div 
                      className="stat-bar-fill"
                      style={{ 
                        width: `${(count / stats.total_books) * 100}%` 
                      }}
                    >
                      {count}
                    </div>
                  </div>
                </div>
              ))}
          </div>
        </div>
      )}

      {Object.keys(stats.average_score_by_model).length > 0 && (
        <div className="stats-section">
          <h3>Voto Medio per Modello</h3>
          <div className="stats-bars">
            {Object.entries(stats.average_score_by_model)
              .sort(([, a], [, b]) => b - a)
              .map(([model, avgScore]) => (
                <div key={model} className="stat-bar-item">
                  <div className="stat-bar-label">{model}</div>
                  <div className="stat-bar-container">
                    <div 
                      className="stat-bar-fill score-model-bar"
                      style={{ 
                        width: `${(avgScore / 10) * 100}%` 
                      }}
                    >
                      {avgScore.toFixed(1)}/10
                    </div>
                  </div>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Grafico Tempo di Generazione per Modello */}
      {((stats.average_writing_time_by_model && Object.keys(stats.average_writing_time_by_model).length > 0) ||
        (stats.average_time_per_page_by_model && Object.keys(stats.average_time_per_page_by_model).length > 0)) && (
        <div className="stats-section">
          <div className="chart-header">
            <h3>Tempo di Generazione per Modello</h3>
            <div className="chart-toggle">
              <button
                className={`toggle-btn ${chartView === 'book' ? 'active' : ''}`}
                onClick={() => setChartView('book')}
              >
                Tempo Libro
              </button>
              <button
                className={`toggle-btn ${chartView === 'page' ? 'active' : ''}`}
                onClick={() => setChartView('page')}
              >
                Tempo per Pagina
              </button>
            </div>
          </div>
          <div className="chart-container">
            <ResponsiveContainer width="100%" height={300}>
              <BarChart
                data={
                  chartView === 'book'
                    ? Object.entries(stats.average_writing_time_by_model || {})
                        .map(([model, time]) => ({ model, time }))
                        .sort((a, b) => b.time - a.time)
                    : Object.entries(stats.average_time_per_page_by_model || {})
                        .map(([model, time]) => ({ model, time }))
                        .sort((a, b) => b.time - a.time)
                }
                margin={{ top: 20, right: 30, left: 20, bottom: 60 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-light)" />
                <XAxis
                  dataKey="model"
                  angle={-45}
                  textAnchor="end"
                  height={80}
                  tick={{ fill: 'var(--text-secondary)', fontSize: 12 }}
                />
                <YAxis
                  tick={{ fill: 'var(--text-secondary)', fontSize: 12 }}
                  tickFormatter={(value) => formatTimeShort(value)}
                />
                <Tooltip
                  formatter={(value: number) => [
                    formatTimeShort(value),
                    chartView === 'book' ? 'Tempo medio libro' : 'Tempo medio per pagina'
                  ]}
                  contentStyle={{
                    backgroundColor: 'var(--surface)',
                    border: '1px solid var(--border-light)',
                    borderRadius: 'var(--radius-md)',
                    color: 'var(--text-primary)',
                  }}
                />
                <Legend />
                <Bar
                  dataKey="time"
                  fill="url(#colorGradient)"
                  radius={[8, 8, 0, 0]}
                  name={chartView === 'book' ? 'Tempo medio (min)' : 'Tempo medio per pagina (min)'}
                />
                <defs>
                  <linearGradient id="colorGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#e94560" />
                    <stop offset="100%" stopColor="#e94560" stopOpacity={0.7} />
                  </linearGradient>
                </defs>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Grafico Pagine Medie per Modello */}
      {stats.average_pages_by_model && Object.keys(stats.average_pages_by_model).length > 0 && (
        <div className="stats-section">
          <h3>Pagine Medie per Modello</h3>
          <div className="chart-container">
            <ResponsiveContainer width="100%" height={300}>
              <BarChart
                data={Object.entries(stats.average_pages_by_model || {})
                  .map(([model, pages]) => ({ model, pages: parseFloat(String(pages)) || 0 }))
                  .sort((a, b) => b.pages - a.pages)}
                margin={{ top: 20, right: 30, left: 20, bottom: 60 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-light)" />
                <XAxis
                  dataKey="model"
                  angle={-45}
                  textAnchor="end"
                  height={80}
                  tick={{ fill: 'var(--text-secondary)', fontSize: 12 }}
                />
                <YAxis
                  tick={{ fill: 'var(--text-secondary)', fontSize: 12 }}
                  domain={[0, 'dataMax + 10']}
                />
                <Tooltip
                  formatter={(value: number) => [`${value.toFixed(1)} pagine`, 'Pagine medie']}
                  contentStyle={{
                    backgroundColor: 'var(--surface)',
                    border: '1px solid var(--border-light)',
                    borderRadius: 'var(--radius-md)',
                    color: 'var(--text-primary)',
                  }}
                />
                <Legend />
                <Bar
                  dataKey="pages"
                  fill="#2563eb"
                  radius={[8, 8, 0, 0]}
                  name="Pagine medie"
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {Object.keys(stats.score_distribution).length > 0 && (
        <div className="stats-section">
          <h3>Distribuzione Voti</h3>
          <div className="stats-bars">
            {['0-2', '2-4', '4-6', '6-8', '8-10'].map(range => {
              const count = stats.score_distribution[range] || 0;
              const totalScores = Object.values(stats.score_distribution).reduce((a, b) => a + b, 0);
              return (
                <div key={range} className="stat-bar-item">
                  <div className="stat-bar-label">{range}</div>
                  <div className="stat-bar-container">
                    <div 
                      className="stat-bar-fill score-bar"
                      style={{ 
                        width: totalScores > 0 ? `${(count / totalScores) * 100}%` : '0%'
                      }}
                    >
                      {count}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}


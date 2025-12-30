import { LibraryStats } from '../api/client';
import './Dashboard.css';

interface DashboardProps {
  stats: LibraryStats;
}

export default function Dashboard({ stats }: DashboardProps) {
  const formatTime = (minutes: number) => {
    if (minutes < 60) {
      return `${minutes.toFixed(0)} min`;
    }
    const hours = Math.floor(minutes / 60);
    const mins = Math.floor(minutes % 60);
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

      {Object.keys(stats.books_by_genre).length > 0 && (
        <div className="stats-section">
          <h3>Distribuzione per Genere</h3>
          <div className="stats-bars">
            {Object.entries(stats.books_by_genre)
              .sort(([, a], [, b]) => b - a)
              .map(([genre, count]) => (
                <div key={genre} className="stat-bar-item">
                  <div className="stat-bar-label">{genre}</div>
                  <div className="stat-bar-container">
                    <div 
                      className="stat-bar-fill genre-bar"
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


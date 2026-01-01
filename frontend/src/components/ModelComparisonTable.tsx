import { useState } from 'react';
import { ModelComparisonEntry } from '../api/client';
import './ModelComparisonTable.css';

interface ModelComparisonTableProps {
  models: ModelComparisonEntry[];
}

type SortField = 'model' | 'completed_books' | 'average_score' | 'average_pages' | 'average_cost' | 'average_writing_time' | 'average_time_per_page';
type SortDirection = 'asc' | 'desc';

export default function ModelComparisonTable({ models }: ModelComparisonTableProps) {
  const [sortField, setSortField] = useState<SortField>('model');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');

  if (!models || models.length === 0) {
    return (
      <div className="model-comparison-empty">
        <p>Nessun dato disponibile per il confronto modelli.</p>
      </div>
    );
  }

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  const sortedModels = [...models].sort((a, b) => {
    let aValue: any = a[sortField];
    let bValue: any = b[sortField];

    // Gestisci valori null/undefined
    if (aValue == null) aValue = sortField === 'model' ? '' : -Infinity;
    if (bValue == null) bValue = sortField === 'model' ? '' : -Infinity;

    if (sortField === 'model') {
      return sortDirection === 'asc' 
        ? aValue.localeCompare(bValue)
        : bValue.localeCompare(aValue);
    }

    return sortDirection === 'asc' 
      ? (aValue as number) - (bValue as number)
      : (bValue as number) - (aValue as number);
  });

  // Trova i valori migliori per evidenziare
  const bestScore = Math.max(...models.map(m => m.average_score || 0).filter(s => s > 0));
  const bestPages = Math.max(...models.map(m => m.average_pages).filter(p => p > 0));
  const minCost = Math.min(...models.map(m => m.average_cost || Infinity).filter(c => c !== Infinity && c > 0));
  const minWritingTime = Math.min(...models.map(m => m.average_writing_time).filter(t => t > 0));
  const minTimePerPage = Math.min(...models.map(m => m.average_time_per_page).filter(t => t > 0));

  const formatTime = (minutes: number): string => {
    if (minutes < 1) {
      return `${(minutes * 60).toFixed(0)} sec`;
    }
    if (minutes < 60) {
      return `${minutes.toFixed(1)} min`;
    }
    const hours = Math.floor(minutes / 60);
    const mins = Math.floor(minutes % 60);
    return mins > 0 ? `${hours}h ${mins}min` : `${hours}h`;
  };

  const getScoreBarWidth = (score: number | undefined): number => {
    if (score == null || score <= 0) return 0;
    return (score / 10) * 100;
  };

  const getScoreColor = (score: number | undefined): string => {
    if (score == null || score <= 0) return '#999';
    const normalizedScore = Math.max(0, Math.min(10, score));
    if (normalizedScore <= 5) {
      const ratio = normalizedScore / 5;
      const r = 220;
      const g = Math.round(53 + (180 - 53) * ratio);
      const b = Math.round(38 + (35 - 38) * ratio);
      return `rgb(${r}, ${g}, ${b})`;
    } else {
      const ratio = (normalizedScore - 5) / 5;
      const r = Math.round(220 - (220 - 16) * ratio);
      const g = Math.round(180 - (180 - 185) * ratio);
      const b = Math.round(35 + (129 - 35) * ratio);
      return `rgb(${r}, ${g}, ${b})`;
    }
  };

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) return <span className="sort-icon">⇅</span>;
    return <span className="sort-icon">{sortDirection === 'asc' ? '↑' : '↓'}</span>;
  };

  return (
    <div className="model-comparison-table-wrapper">
      <table className="model-comparison-table">
        <thead>
          <tr>
            <th onClick={() => handleSort('model')} className="sortable">
              Modello <SortIcon field="model" />
            </th>
            <th onClick={() => handleSort('completed_books')} className="sortable">
              Libri <SortIcon field="completed_books" />
            </th>
            <th onClick={() => handleSort('average_score')} className="sortable">
              Voto Medio <SortIcon field="average_score" />
            </th>
            <th onClick={() => handleSort('average_pages')} className="sortable">
              Pagine Medie <SortIcon field="average_pages" />
            </th>
            <th onClick={() => handleSort('average_cost')} className="sortable">
              Costo Medio <SortIcon field="average_cost" />
            </th>
            <th onClick={() => handleSort('average_writing_time')} className="sortable">
              Tempo Scrittura <SortIcon field="average_writing_time" />
            </th>
            <th onClick={() => handleSort('average_time_per_page')} className="sortable">
              Tempo/Pagina <SortIcon field="average_time_per_page" />
            </th>
          </tr>
        </thead>
        <tbody>
          {sortedModels.map((model) => (
            <tr key={model.model}>
              <td className="model-name">{model.model}</td>
              <td>{model.completed_books}</td>
              <td>
                {model.average_score != null && model.average_score > 0 ? (
                  <div className={`score-cell ${model.average_score === bestScore ? 'best-value' : ''}`}>
                    <div className="score-bar-container">
                      <div
                        className="score-bar"
                        style={{
                          width: `${getScoreBarWidth(model.average_score)}%`,
                          backgroundColor: getScoreColor(model.average_score),
                        }}
                      />
                      <span className="score-text">
                        {model.average_score.toFixed(1)}/10
                      </span>
                    </div>
                  </div>
                ) : (
                  <span className="no-data">N/A</span>
                )}
              </td>
              <td>
                {model.average_pages > 0 ? (
                  <span className={model.average_pages === bestPages ? 'best-value' : ''}>
                    {model.average_pages.toFixed(1)}
                  </span>
                ) : (
                  <span className="no-data">N/A</span>
                )}
              </td>
              <td>
                {model.average_cost != null && model.average_cost > 0 ? (
                  <span className={model.average_cost === minCost ? 'best-value' : ''}>
                    €{model.average_cost.toFixed(1)}
                  </span>
                ) : (
                  <span className="no-data">N/A</span>
                )}
              </td>
              <td>
                {model.average_writing_time > 0 ? (
                  <span className={model.average_writing_time === minWritingTime ? 'best-value' : ''}>
                    {formatTime(model.average_writing_time)}
                  </span>
                ) : (
                  <span className="no-data">N/A</span>
                )}
              </td>
              <td>
                {model.average_time_per_page > 0 ? (
                  <span className={model.average_time_per_page === minTimePerPage ? 'best-value' : ''}>
                    {formatTime(model.average_time_per_page)}
                  </span>
                ) : (
                  <span className="no-data">N/A</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

import { useState } from 'react';
import { LibraryFilters } from '../api/client';
import './FilterBar.css';

interface FilterBarProps {
  onFiltersChange: (filters: LibraryFilters) => void;
  availableModes: string[];  // Modalità disponibili (Flash, Pro, Ultra)
  availableGenres: string[];
}

export default function FilterBar({ onFiltersChange, availableModes, availableGenres }: FilterBarProps) {
  const [filters, setFilters] = useState<LibraryFilters>({
    status: 'all',
    sort_by: 'created_at',
    sort_order: 'desc',
  });
  const [searchText, setSearchText] = useState('');

  const handleFilterChange = (key: keyof LibraryFilters, value: string) => {
    const newFilters = {
      ...filters,
      [key]: value === '' || value === 'all' ? undefined : value,
    };
    setFilters(newFilters);
    onFiltersChange(newFilters);
  };

  const handleSearch = (value: string) => {
    setSearchText(value);
    const newFilters = {
      ...filters,
      search: value.trim() || undefined,
    };
    setFilters(newFilters);
    onFiltersChange(newFilters);
  };

  const clearFilters = () => {
    const newFilters = {
      status: 'all',
      sort_by: 'created_at',
      sort_order: 'desc',
    };
    setFilters(newFilters);
    setSearchText('');
    onFiltersChange(newFilters);
  };

  return (
    <div className="filter-bar">
      <div className="filter-group">
        <label htmlFor="status-filter">Stato:</label>
        <select
          id="status-filter"
          value={filters.status || 'all'}
          onChange={(e) => handleFilterChange('status', e.target.value)}
        >
          <option value="all">Tutti</option>
          <option value="draft">Bozza</option>
          <option value="outline">Struttura</option>
          <option value="writing">In Scrittura</option>
          <option value="paused">In Pausa</option>
          <option value="complete">Completati</option>
        </select>
      </div>

      <div className="filter-group">
        <label htmlFor="mode-filter">Modalità:</label>
        <select
          id="mode-filter"
          value={filters.mode || 'all'}
          onChange={(e) => handleFilterChange('mode', e.target.value)}
        >
          <option value="all">Tutte le modalità</option>
          {availableModes.map(mode => (
            <option key={mode} value={mode}>{mode}</option>
          ))}
        </select>
      </div>

      <div className="filter-group">
        <label htmlFor="genre-filter">Genere:</label>
        <select
          id="genre-filter"
          value={filters.genre || 'all'}
          onChange={(e) => handleFilterChange('genre', e.target.value)}
        >
          <option value="all">Tutti i generi</option>
          {availableGenres.map(genre => (
            <option key={genre} value={genre}>{genre}</option>
          ))}
        </select>
      </div>

      <div className="filter-group search-group">
        <label htmlFor="search-input">Cerca:</label>
        <input
          id="search-input"
          type="text"
          placeholder="Titolo o autore..."
          value={searchText}
          onChange={(e) => handleSearch(e.target.value)}
        />
      </div>

      <div className="filter-group">
        <label htmlFor="sort-by">Ordina per:</label>
        <select
          id="sort-by"
          value={filters.sort_by || 'created_at'}
          onChange={(e) => handleFilterChange('sort_by', e.target.value)}
        >
          <option value="created_at">Data creazione</option>
          <option value="updated_at">Ultima modifica</option>
          <option value="title">Titolo</option>
          <option value="score">Voto</option>
          <option value="cost">Costo</option>
          <option value="total_pages">Pagine</option>
        </select>
      </div>

      <div className="filter-group">
        <label htmlFor="sort-order">Ordine:</label>
        <select
          id="sort-order"
          value={filters.sort_order || 'desc'}
          onChange={(e) => handleFilterChange('sort_order', e.target.value as 'asc' | 'desc')}
        >
          <option value="desc">Discendente</option>
          <option value="asc">Ascendente</option>
        </select>
      </div>

      <button className="clear-filters-btn" onClick={clearFilters}>
        Pulisci filtri
      </button>
    </div>
  );
}


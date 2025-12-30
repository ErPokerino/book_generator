import { useState, useEffect, useRef } from 'react';
import { 
  getLibrary, 
  getLibraryStats, 
  LibraryEntry, 
  LibraryFilters, 
  LibraryStats,
  fetchConfig,
  ConfigResponse
} from '../api/client';
import Dashboard from './Dashboard';
import FilterBar from './FilterBar';
import BookCard from './BookCard';
import WritingStep from './WritingStep';
import './LibraryView.css';

interface LibraryViewProps {
  onReadBook?: (sessionId: string) => void;
}

export default function LibraryView({ onReadBook }: LibraryViewProps) {
  const [books, setBooks] = useState<LibraryEntry[]>([]);
  const [stats, setStats] = useState<LibraryStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [config, setConfig] = useState<ConfigResponse | null>(null);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const filtersRef = useRef<LibraryFilters>({});
  const isFirstLoad = useRef(true);

  // Carica configurazione per avere modelli e generi disponibili
  useEffect(() => {
    fetchConfig()
      .then(setConfig)
      .catch(err => {
        console.error('Errore nel caricamento config:', err);
        // Non blocchiamo il caricamento della libreria se la config fallisce
        // La config è solo per i filtri
      });
  }, []);

  const loadLibrary = async (currentFilters?: LibraryFilters, isRefresh = false) => {
    try {
      if (isRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setError(null);
      const filtersToUse = currentFilters ?? filtersRef.current;
      
      // Timeout di 30 secondi per le chiamate API
      const apiPromise = Promise.all([
        getLibrary(filtersToUse),
        getLibraryStats(),
      ]);
      
      const timeoutPromise = new Promise<never>((_, reject) => 
        setTimeout(() => reject(new Error('Timeout: le richieste API stanno impiegando troppo tempo')), 30000)
      );
      
      const [libraryResponse, statsData] = await Promise.race([
        apiPromise,
        timeoutPromise,
      ]);
      
      setBooks(libraryResponse.books);
      setStats(statsData);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Errore nel caricamento della libreria';
      setError(errorMessage);
      console.error('Errore nel caricamento libreria:', err);
      // Assicuriamoci di avere valori default anche in caso di errore
      setBooks([]);
      if (!stats) {
        // Mantieni stats null se non riusciamo a caricarli
      }
    } finally {
      // Sempre disabilita il loading, anche in caso di errore
      if (isRefresh) {
        setRefreshing(false);
      } else {
        setLoading(false);
      }
    }
  };

  // Carica la libreria solo al primo render
  useEffect(() => {
    if (isFirstLoad.current) {
      isFirstLoad.current = false;
      loadLibrary();
    }
  }, []);

  const handleFiltersChange = (newFilters: LibraryFilters) => {
    filtersRef.current = newFilters;
    loadLibrary(newFilters, true);
  };

  const handleDelete = (sessionId: string) => {
    setBooks(prev => prev.filter(book => book.session_id !== sessionId));
    // Ricarica stats dopo eliminazione
    getLibraryStats().then(setStats).catch(console.error);
  };

  const handleContinue = (sessionId: string) => {
    setSelectedSessionId(sessionId);
  };

  const handleBackFromWriting = () => {
    setSelectedSessionId(null);
    loadLibrary(filtersRef.current, true);
  };

  // Se abbiamo selezionato una sessione per continuare, mostra WritingStep
  if (selectedSessionId) {
    return (
      <div className="library-view">
        <button className="back-to-library-btn" onClick={handleBackFromWriting}>
          ← Torna alla Libreria
        </button>
        <WritingStep 
          sessionId={selectedSessionId}
          onComplete={handleBackFromWriting}
          onNewBook={handleBackFromWriting}
        />
      </div>
    );
  }

  // Estrai modelli e generi disponibili dalla configurazione
  const availableModels = config?.llm_models || [];
  const availableGenres = config?.fields
    .find(f => f.id === 'genre')
    ?.options?.map(opt => opt.value) || [];

  if (loading) {
    return (
      <div className="library-view">
        <div className="loading-message">Caricamento libreria...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="library-view">
        <div className="error-message">
          <p>Errore: {error}</p>
          <button onClick={loadLibrary}>Riprova</button>
        </div>
      </div>
    );
  }

  return (
    <div className="library-view">
      {stats && <Dashboard stats={stats} />}
      
      <FilterBar
        onFiltersChange={handleFiltersChange}
        availableModels={availableModels}
        availableGenres={availableGenres}
      />

      {refreshing && (
        <div className="refreshing-indicator">
          <span>Aggiornamento in corso...</span>
        </div>
      )}

      <div className="library-header">
        <h2>I Tuoi Libri ({books.length})</h2>
      </div>

      {books.length === 0 ? (
        <div className="empty-library">
          <p>Nessun libro trovato con i filtri selezionati.</p>
        </div>
      ) : (
        <div className="books-grid">
          {books.map(book => (
            <BookCard
              key={book.session_id}
              book={book}
              onDelete={handleDelete}
              onContinue={handleContinue}
              onRead={book.status === 'complete' ? onReadBook : undefined}
            />
          ))}
        </div>
      )}
    </div>
  );
}

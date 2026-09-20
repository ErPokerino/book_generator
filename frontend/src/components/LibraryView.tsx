import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  getLibrary,
  LibraryEntry,
  LibraryFilters,
  fetchConfig,
  ConfigResponse,
} from '../api/client';
import FilterBar from './FilterBar';
import BookCard from './BookCard';
import WritingStep from './WritingStep';
import CritiqueModal from './CritiqueModal';
import { SkeletonCard } from './Skeleton';
import { useToast } from '../hooks/useToast';
import PageHeader from './ui/PageHeader';
import EmptyState from './ui/EmptyState';
import Button from './ui/Button';
import './LibraryView.css';

export default function LibraryView() {
  const navigate = useNavigate();
  const toast = useToast();
  const [books, setBooks] = useState<LibraryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [config, setConfig] = useState<ConfigResponse | null>(null);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [critiqueModalSessionId, setCritiqueModalSessionId] = useState<string | null>(null);
  const [totalBooks, setTotalBooks] = useState(0);  // Totale libri disponibili dal server
  const [loadError, setLoadError] = useState<string | null>(null);
  const filtersRef = useRef<LibraryFilters>({});
  const requestVersion = useRef(0);
  const activeRequest = useRef<AbortController | null>(null);
  const loadMoreRef = useRef<HTMLDivElement>(null);
  const isLoadingRef = useRef(false);  // Previene chiamate duplicate
  const pageSize = 10;  // Ridotto a 10 per caricamenti più veloci

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

  const loadLibrary = useCallback(async (currentFilters?: LibraryFilters, isRefresh = false, append = false, currentBooksCount = 0) => {
    // Previeni chiamate duplicate
    if (isLoadingRef.current && append) {
      return;
    }
    
    const version = ++requestVersion.current;
    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;
    const timeoutId = window.setTimeout(() => controller.abort(), 30000);
    try {
      isLoadingRef.current = true;
      setLoadError(null);
      
      if (isRefresh) {
        setRefreshing(true);
      } else if (!append) {
        setLoading(true);
      } else {
        setLoadingMore(true);
      }
      const filtersToUse = { ...(currentFilters ?? filtersRef.current) };
      
      // Per il primo caricamento o refresh, reset paginazione
      if (!append) {
        filtersToUse.skip = 0;
        filtersToUse.limit = pageSize;
      } else {
        // Per il caricamento incrementale, usa il conteggio passato
        filtersToUse.skip = currentBooksCount;
        filtersToUse.limit = pageSize;
      }
      
      const libraryResponse = await getLibrary(filtersToUse, controller.signal);
      if (version !== requestVersion.current) return;

      // Salva il totale dal server
      setTotalBooks(libraryResponse.total);
      
      if (append) {
        // Aggiungi i nuovi libri a quelli esistenti, evitando duplicati
        setBooks(prev => {
          const existingIds = new Set(prev.map(b => b.session_id));
          const newBooks = libraryResponse.books.filter(b => !existingIds.has(b.session_id));
          return [...prev, ...newBooks];
        });
      } else {
        // Sostituisci i libri esistenti
        setBooks(libraryResponse.books);
      }
      
      // Aggiorna stato hasMore
      setHasMore(libraryResponse.has_more ?? false);
    } catch (err) {
      if (version !== requestVersion.current) return;
      const errorMessage = controller.signal.aborted ? 'La libreria non risponde. Riprova.' : err instanceof Error ? err.message : 'Errore nel caricamento della libreria';
      toast.error(errorMessage);
      setLoadError(errorMessage);
      setHasMore(false);
      console.error('Errore nel caricamento libreria:', err);
    } finally {
      window.clearTimeout(timeoutId);
      if (version === requestVersion.current) {
        isLoadingRef.current = false;
        setRefreshing(false);
        setLoading(false);
        setLoadingMore(false);
      }
    }
  }, [toast]);

  const loadMoreBooks = useCallback(() => {
    if (hasMore && !isLoadingRef.current) {
      void loadLibrary(filtersRef.current, false, true, books.length);
    }
  }, [hasMore, loadLibrary, books.length]);

  useEffect(() => {
    void loadLibrary();
    return () => {
      requestVersion.current += 1;
      activeRequest.current?.abort();
    };
  }, [loadLibrary]);

  const handleFiltersChange = (newFilters: LibraryFilters) => {
    filtersRef.current = newFilters;
    setHasMore(true);  // Reset hasMore quando cambiano i filtri
    loadLibrary(newFilters, true, false);  // Reset lista (non append)
  };

  // IntersectionObserver per rilevare quando la sentinella entra nel viewport
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMore && !loadingMore && !loading && !refreshing) {
          loadMoreBooks();
        }
      },
      { threshold: 0.1 }
    );
    
    const currentRef = loadMoreRef.current;
    if (currentRef) {
      observer.observe(currentRef);
    }
    
    return () => {
      if (currentRef) {
        observer.unobserve(currentRef);
      }
      observer.disconnect();
    };
  }, [hasMore, loadingMore, loading, refreshing, loadMoreBooks]);

  // Listener per evento custom di refresh libreria
  useEffect(() => {
    const handleLibraryRefresh = () => {
      // Ricarica la libreria quando viene emesso l'evento library-refresh
      // Usa filtersRef.current direttamente per evitare problemi di dependency
      if (!isLoadingRef.current) {
        loadLibrary(filtersRef.current, true, false);
      }
    };

    window.addEventListener('library-refresh', handleLibraryRefresh);

    return () => {
      window.removeEventListener('library-refresh', handleLibraryRefresh);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loadLibrary]);

  const handleDelete = (sessionId: string) => {
    setBooks(prev => prev.filter(book => book.session_id !== sessionId));
    setTotalBooks(total => Math.max(0, total - 1));
  };

  const openMangaSession = (sessionId: string) => {
    localStorage.setItem('current_manga_session_id', sessionId);
    navigate(`/manga?session=${sessionId}`);
  };

  const handleContinue = (book: LibraryEntry) => {
    if (book.content_type === 'manga') {
      openMangaSession(book.session_id);
      return;
    }
    setSelectedSessionId(book.session_id);
  };

  const handleBackFromWriting = () => {
    setSelectedSessionId(null);
    loadLibrary(filtersRef.current, true);
  };

  const handleShowCritique = (book: LibraryEntry) => {
    setCritiqueModalSessionId(book.session_id);
  };

  const handleCloseCritiqueModal = () => {
    setCritiqueModalSessionId(null);
  };

  const handleResume = (book: LibraryEntry) => {
    if (book.content_type === 'manga') {
      openMangaSession(book.session_id);
      return;
    }
    localStorage.setItem('current_book_session_id', book.session_id);
    navigate('/new');
  };
  
  const handleReadBook = (book: LibraryEntry) => {
    if (book.content_type === 'manga') {
      openMangaSession(book.session_id);
      return;
    }
    navigate(`/book/${book.session_id}`);
  };

  // Se abbiamo selezionato una sessione per continuare, mostra WritingStep
  if (selectedSessionId) {
    return (
      <div className="page-shell library-view">
        <button type="button" className="back-to-library-btn" onClick={handleBackFromWriting}>
          Torna alle opere
        </button>
        <WritingStep
          sessionId={selectedSessionId}
          onComplete={handleBackFromWriting}
          onNewBook={handleBackFromWriting}
        />
      </div>
    );
  }

  // Modalità disponibili (fisso, non più dalla configurazione)
  const availableModes = ['Standard', 'Ultra'];
  const availableGenres = config?.fields
    .find(f => f.id === 'genre')
    ?.options?.map(opt => opt.value) || [];
  const hasActiveFilters = ['search', 'status', 'mode', 'genre'].some(key => {
    const value = filtersRef.current[key as keyof LibraryFilters];
    return value && value !== 'all';
  });

  if (loading) {
    return (
      <div className="page-shell library-view">
        <PageHeader title="Opere" description="I libri e i manga generati in questo studio." />
        <div className="books-grid">
          {Array.from({ length: 6 }).map((_, index) => (
            <SkeletonCard key={index} />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="page-shell library-view">
      <PageHeader
        title="Opere"
        description={totalBooks > 0 ? `${totalBooks} in archivio.` : undefined}
        actions={
          <Button type="button" variant="ghost" className="library-create-action" onClick={() => navigate('/new')}>
            Crea
          </Button>
        }
      />
      <FilterBar
        onFiltersChange={handleFiltersChange}
        availableModes={availableModes}
        availableGenres={availableGenres}
      />

      {refreshing ? <p className="refreshing-indicator">Aggiornamento</p> : null}
      {loadError && books.length > 0 ? (
        <div role="alert">{loadError} <Button type="button" onClick={() => void loadLibrary(undefined, true)}>Riprova</Button></div>
      ) : null}

      {loadError && books.length === 0 ? (
        <EmptyState title="Libreria non disponibile" description={loadError}
          action={<Button type="button" onClick={() => void loadLibrary()}>Riprova</Button>} />
      ) : books.length === 0 ? (
        <EmptyState
          title={hasActiveFilters ? 'Nessun risultato' : 'Nessuna opera ancora'}
          description={
            hasActiveFilters
              ? 'Prova a cambiare i filtri di ricerca.'
              : 'Crea un libro o un manga. Le opere sono salvate su questo dispositivo; la generazione usa servizi AI online.'
          }
          action={
            !hasActiveFilters ? (
              <Button type="button" onClick={() => navigate('/new')}>
                Crea un’opera
              </Button>
            ) : undefined
          }
        />
      ) : (
        <div className="books-grid">
          {books.map((book) => (
            <BookCard
              key={book.session_id}
              book={book}
              onDelete={handleDelete}
              onContinue={handleContinue}
              onResume={handleResume}
              onRead={book.status === 'complete' ? handleReadBook : undefined}
              onShowCritique={handleShowCritique}
            />
          ))}
        </div>
      )}

      <div ref={loadMoreRef} className="load-more-sentinel">
        {loadingMore ? <p>Caricamento</p> : null}
      </div>

      {critiqueModalSessionId && (
        <CritiqueModal
          sessionId={critiqueModalSessionId}
          bookTitle={books.find((b) => b.session_id === critiqueModalSessionId)?.title || 'Libro'}
          isOpen={true}
          onClose={handleCloseCritiqueModal}
        />
      )}
    </div>
  );
}

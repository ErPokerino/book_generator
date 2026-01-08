import { useState, useEffect, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  getLibrary, 
  LibraryEntry, 
  LibraryFilters,
  fetchConfig,
  ConfigResponse
} from '../api/client';
import FilterBar from './FilterBar';
import BookCard from './BookCard';
import WritingStep from './WritingStep';
import CritiqueModal from './CritiqueModal';
import { SkeletonCard } from './Skeleton';
import { useToast } from '../hooks/useToast';
import OnboardingTooltip from './Onboarding/OnboardingTooltip';
import './LibraryView.css';

interface LibraryViewProps {
  onReadBook?: (sessionId: string) => void;
  onNavigateToNewBook?: () => void;
}

export default function LibraryView({ onReadBook, onNavigateToNewBook }: LibraryViewProps) {
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
  const filtersRef = useRef<LibraryFilters>({});
  const isFirstLoad = useRef(true);
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

  const loadLibrary = async (currentFilters?: LibraryFilters, isRefresh = false, append = false, currentBooksCount = 0) => {
    // Previeni chiamate duplicate
    if (isLoadingRef.current && append) {
      return;
    }
    
    try {
      isLoadingRef.current = true;
      
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
      
      // Timeout di 30 secondi per le chiamate API
      const apiPromise = getLibrary(filtersToUse);
      
      const timeoutPromise = new Promise<never>((_, reject) => 
        setTimeout(() => reject(new Error('Timeout: le richieste API stanno impiegando troppo tempo')), 30000)
      );
      
      const libraryResponse = await Promise.race([
        apiPromise,
        timeoutPromise,
      ]);
      
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
      const errorMessage = err instanceof Error ? err.message : 'Errore nel caricamento della libreria';
      toast.error(errorMessage);
      console.error('Errore nel caricamento libreria:', err);
      // Assicuriamoci di avere valori default anche in caso di errore
      if (!append) {
        setBooks([]);
        setHasMore(false);
        setTotalBooks(0);
      }
    } finally {
      isLoadingRef.current = false;
      // Sempre disabilita il loading, anche in caso di errore
      if (isRefresh) {
        setRefreshing(false);
      } else if (!append) {
        setLoading(false);
      } else {
        setLoadingMore(false);
      }
    }
  };

  const loadMoreBooks = useCallback(() => {
    if (!loadingMore && hasMore && !isLoadingRef.current) {
      // Usa una funzione setter per ottenere il valore aggiornato di books
      setBooks(prevBooks => {
        // Solo se ci sono libri da caricare
        if (prevBooks.length < totalBooks || hasMore) {
          loadLibrary(filtersRef.current, false, true, prevBooks.length);
        }
        return prevBooks;  // Non modifica lo stato, solo legge
      });
    }
  }, [loadingMore, hasMore, totalBooks]);

  // Carica la libreria solo al primo render
  useEffect(() => {
    if (isFirstLoad.current) {
      isFirstLoad.current = false;
      loadLibrary();
    }
  }, []);

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

  const handleDelete = (sessionId: string) => {
    setBooks(prev => prev.filter(book => book.session_id !== sessionId));
  };

  const handleContinue = (sessionId: string) => {
    setSelectedSessionId(sessionId);
  };

  const handleBackFromWriting = () => {
    setSelectedSessionId(null);
    loadLibrary(filtersRef.current, true);
  };

  const handleShowCritique = (sessionId: string) => {
    setCritiqueModalSessionId(sessionId);
  };

  const handleCloseCritiqueModal = () => {
    setCritiqueModalSessionId(null);
  };

  const handleResume = (sessionId: string) => {
    // Salva sessionId in localStorage per permettere il ripristino
    localStorage.setItem('current_book_session_id', sessionId);
    // Naviga a "Nuovo Libro"
    if (onNavigateToNewBook) {
      onNavigateToNewBook();
    }
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

  // Modalità disponibili (fisso, non più dalla configurazione)
  const availableModes = ['Flash', 'Pro', 'Ultra'];
  const availableGenres = config?.fields
    .find(f => f.id === 'genre')
    ?.options?.map(opt => opt.value) || [];

  if (loading) {
    return (
      <div className="library-view">
        <FilterBar 
          onFiltersChange={handleFiltersChange}
          availableModes={availableModes}
          availableGenres={availableGenres}
        />
        <div className="books-grid">
          {Array.from({ length: 6 }).map((_, index) => (
            <SkeletonCard key={index} />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="library-view">
      <FilterBar
        onFiltersChange={handleFiltersChange}
        availableModes={availableModes}
        availableGenres={availableGenres}
      />

      {refreshing && (
        <div className="refreshing-indicator">
          <span>Aggiornamento in corso...</span>
        </div>
      )}

      <div className="library-header">
        <h2>I Tuoi Libri ({books.length}{totalBooks > 0 && books.length < totalBooks ? ` di ${totalBooks}` : ''})</h2>
      </div>

      {books.length === 0 && !loading ? (
        <OnboardingTooltip
          id="library-first"
          message="I tuoi libri appariranno qui. Crea il tuo primo libro per iniziare!"
          position="top"
        >
          <div className="empty-library">
            <p>{totalBooks === 0 ? 'Nessun libro ancora. Crea il tuo primo libro!' : 'Nessun libro trovato con i filtri selezionati.'}</p>
          </div>
        </OnboardingTooltip>
      ) : (
        <>
          <motion.div 
            className="books-grid"
            initial="hidden"
            animate="visible"
            variants={{
              visible: {
                transition: {
                  staggerChildren: 0.05
                }
              }
            }}
          >
            <AnimatePresence mode="popLayout">
              {books.map(book => (
                <motion.div
                  key={book.session_id}
                  variants={{
                    hidden: { opacity: 0, y: 20 },
                    visible: { opacity: 1, y: 0 }
                  }}
                  exit={{ opacity: 0, scale: 0.9 }}
                  transition={{ duration: 0.3 }}
                  layout
                >
                  <BookCard
                    book={book}
                    onDelete={handleDelete}
                    onContinue={handleContinue}
                    onResume={handleResume}
                    onRead={book.status === 'complete' ? onReadBook : undefined}
                    onShowCritique={handleShowCritique}
                  />
                </motion.div>
              ))}
            </AnimatePresence>
          </motion.div>
          
          {/* Elemento sentinella per infinite scroll */}
          <div ref={loadMoreRef} className="load-more-sentinel">
            {loadingMore && (
              <div className="loading-more-indicator">
                <span>Caricamento altri libri...</span>
              </div>
            )}
            {!hasMore && books.length > 0 && (
              <div className="no-more-books">
                <p>Non ci sono altri libri da mostrare.</p>
              </div>
            )}
          </div>
        </>
      )}

      {critiqueModalSessionId && (
        <CritiqueModal
          sessionId={critiqueModalSessionId}
          bookTitle={books.find(b => b.session_id === critiqueModalSessionId)?.title || 'Libro'}
          isOpen={true}
          onClose={handleCloseCritiqueModal}
        />
      )}
    </div>
  );
}

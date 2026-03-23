import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getCompleteBook, BookResponse, getCoverImageUrl } from '../api/client';
import { SkeletonBox, SkeletonChapter } from './Skeleton';
import { useToast } from '../hooks/useToast';
import PageTransition from './ui/PageTransition';
import AudioPlayer from './AudioPlayer';
import './BookReader.css';

export default function BookReader() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  
  if (!sessionId) {
    navigate('/library');
    return null;
  }
  
  const handleClose = () => {
    navigate('/library');
  };
  const toast = useToast();
  const [book, setBook] = useState<BookResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentChapterIndex, setCurrentChapterIndex] = useState(-1); // -1 = copertina, 0+ = capitoli
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [showToc, setShowToc] = useState(false);
  const [fontSize, setFontSize] = useState(18);
  const [coverImageUrl, setCoverImageUrl] = useState<string | null>(null);

  useEffect(() => {
    const loadBook = async () => {
      try {
        setLoading(true);
        setError(null);
        const bookData = await getCompleteBook(sessionId);
        setBook(bookData);
        // Usa URL diretto invece di scaricare come blob
        setCoverImageUrl(getCoverImageUrl(sessionId));
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Errore nel caricamento del libro';
        setError(errorMessage);
        toast.error(errorMessage);
      } finally {
        setLoading(false);
      }
    };

    loadBook();
  }, [sessionId]);

  useEffect(() => {
    if (book && !coverImageUrl && currentChapterIndex === -1) {
      setCurrentChapterIndex(0);
    }
  }, [book, coverImageUrl, currentChapterIndex]);

  // Helper functions (defined before useCallbacks that use them)
  const scrollToTop = () => {
    const readerContent = document.querySelector('.reader-content');
    if (readerContent) {
      readerContent.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen();
      setIsFullscreen(true);
    } else {
      document.exitFullscreen();
      setIsFullscreen(false);
    }
  };

  const goToChapter = (index: number) => {
    setCurrentChapterIndex(index);
    setShowToc(false);
    scrollToTop();
  };

  const goToCover = () => {
    setCurrentChapterIndex(-1);
    setShowToc(false);
    scrollToTop();
  };

  const increaseFontSize = () => {
    setFontSize(prev => Math.min(prev + 2, 28));
  };

  const decreaseFontSize = () => {
    setFontSize(prev => Math.max(prev - 2, 12));
  };

  const normalizeDisplayTitle = (rawTitle: string): string => {
    let title = rawTitle.trim();

    const wrappers = [
      /^\*\*(.+)\*\*$/,
      /^__(.+)__$/,
      /^\*(.+)\*$/,
      /^_(.+)_$/,
      /^#+\s*(.+)$/,
    ];

    let changed = true;
    while (changed) {
      changed = false;
      for (const pattern of wrappers) {
        const match = title.match(pattern);
        if (match) {
          title = match[1].trim();
          changed = true;
        }
      }
    }

    return title;
  };

  const formatContent = (content: string): string => {
    // Converte i newline in paragrafi HTML
    return content
      .split('\n\n')
      .filter(p => p.trim())
      .map(p => `<p>${p.trim().replace(/\n/g, '<br/>')}</p>`)
      .join('');
  };

  // Navigation functions with useCallback
  const goToPreviousChapter = useCallback(() => {
    if (currentChapterIndex === -1) return; // Alla copertina, non si può andare indietro
    if (currentChapterIndex === 0 && coverImageUrl) {
      // Dal primo capitolo, vai alla copertina
      setCurrentChapterIndex(-1);
    } else if (currentChapterIndex > 0) {
      setCurrentChapterIndex(prev => prev - 1);
    } else {
      return;
    }
    scrollToTop();
  }, [currentChapterIndex, coverImageUrl]);

  const goToNextChapter = useCallback(() => {
    if (!book) return;
    if (currentChapterIndex === -1) {
      // Dalla copertina, vai al primo capitolo
      setCurrentChapterIndex(0);
    } else if (currentChapterIndex < book.chapters.length - 1) {
      setCurrentChapterIndex(prev => prev + 1);
    }
    scrollToTop();
  }, [book, currentChapterIndex]);

  // Keyboard navigation (uses goToPreviousChapter, goToNextChapter, toggleFullscreen)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!book) return;
      
      switch (e.key) {
        case 'ArrowLeft':
          goToPreviousChapter();
          break;
        case 'ArrowRight':
          goToNextChapter();
          break;
        case 'Escape':
          if (isFullscreen) {
            toggleFullscreen();
          } else {
            handleClose();
          }
          break;
        case 'f':
        case 'F':
          if (e.ctrlKey || e.metaKey) {
            e.preventDefault();
            toggleFullscreen();
          }
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [book, currentChapterIndex, isFullscreen, handleClose, goToPreviousChapter, goToNextChapter]);

  if (loading) {
    return (
      <div className={`book-reader ${isFullscreen ? 'fullscreen' : ''}`}>
        <header className="reader-header">
          <div className="header-left">
            <SkeletonBox width="80px" height="2rem" borderRadius="var(--radius-md)" />
          </div>
          <div className="header-right">
            <SkeletonBox width="100px" height="2rem" borderRadius="var(--radius-md)" />
          </div>
        </header>
        <div className="reader-content">
          <SkeletonChapter />
        </div>
      </div>
    );
  }

  if (error || !book) {
    return (
      <div className={`book-reader ${isFullscreen ? 'fullscreen' : ''}`}>
        <div className="reader-error">
          <span className="error-icon">⚠️</span>
          <p>{error || 'Libro non trovato'}</p>
          <button onClick={handleClose} className="back-btn">
            ← Torna alla Libreria
          </button>
        </div>
      </div>
    );
  }

  const hasCover = Boolean(coverImageUrl);
  const isShowingCover = hasCover && currentChapterIndex === -1;
  const currentChapter = isShowingCover ? null : book.chapters[Math.max(currentChapterIndex, 0)];
  const totalPages = book.chapters.length + (coverImageUrl ? 1 : 0);
  const progress = coverImageUrl 
    ? ((currentChapterIndex + 2) / totalPages) * 100
    : ((currentChapterIndex + 1) / book.chapters.length) * 100;
  const readingProgress = Math.max(0, Math.min(100, Math.round(progress)));
  const currentLocation = isShowingCover ? 'Copertina' : `Capitolo ${currentChapterIndex + 1}`;
  const displayTitle = normalizeDisplayTitle(book.title);
  const estimatedMinutes = typeof book.writing_time_minutes === 'number' && book.writing_time_minutes > 0
    ? Math.max(1, Math.round(book.writing_time_minutes))
    : null;

  return (
    <PageTransition>
      <div className={`book-reader ${isFullscreen ? 'fullscreen' : ''}`}>
        {/* Header */}
        <header className="reader-header">
          <div className="header-left">
            <button onClick={handleClose} className="close-btn" title="Chiudi (Esc)">
              ← Chiudi
            </button>
          <div className="book-info">
            <h1 className="book-title">{displayTitle}</h1>
            <span className="book-author">di {book.author}</span>
          </div>
        </div>
        
        <div className="header-controls">
          <button 
            onClick={() => setShowToc(!showToc)} 
            className={`toc-btn ${showToc ? 'active' : ''}`}
            title="Indice"
          >
            📑 Indice
          </button>
          
          <div className="font-controls">
            <button onClick={decreaseFontSize} title="Riduci testo" disabled={fontSize <= 12}>
              A-
            </button>
            <span className="font-size">{fontSize}px</span>
            <button onClick={increaseFontSize} title="Ingrandisci testo" disabled={fontSize >= 28}>
              A+
            </button>
          </div>
          
          <button onClick={toggleFullscreen} className="fullscreen-btn" title="Schermo intero (Ctrl+F)">
            {isFullscreen ? '⛶' : '⛶'}
          </button>
        </div>
      </header>

      {/* Progress bar */}
      <div className="reading-progress">
        <div className="progress-fill" style={{ width: `${progress}%` }}></div>
      </div>
      <div className="reader-progress-meta">
        <span>{currentLocation}</span>
        <span>{readingProgress}% completato</span>
        <span>Testo {fontSize}px</span>
      </div>

      {/* Table of Contents Sidebar */}
      {showToc && (
        <aside className="toc-sidebar">
          <div className="toc-header">
            <h2>Indice</h2>
            <button onClick={() => setShowToc(false)} className="close-toc">×</button>
          </div>
          <nav className="toc-list">
            {coverImageUrl && (
              <button
                onClick={goToCover}
                className={`toc-item ${currentChapterIndex === -1 ? 'active' : ''}`}
              >
                <span className="chapter-number">📖</span>
                <span className="chapter-title">Copertina</span>
              </button>
            )}
            {book.chapters.map((chapter, index) => (
              <button
                key={index}
                onClick={() => goToChapter(index)}
                className={`toc-item ${index === currentChapterIndex ? 'active' : ''}`}
              >
                <span className="chapter-number">{index + 1}</span>
                <span className="chapter-title">{chapter.title}</span>
                {chapter.page_count > 0 && (
                  <span className="chapter-pages">{chapter.page_count} pg</span>
                )}
              </button>
            ))}
          </nav>
        </aside>
      )}

      {/* Main Content */}
      <main className={`reader-content ${showToc ? 'with-toc' : ''}`}>
        {isShowingCover && coverImageUrl ? (
          <div className="cover-page">
            <div className="cover-page-shell">
              <img src={coverImageUrl} alt={`Copertina di ${displayTitle}`} className="cover-image" />
              <aside className="cover-summary">
                <span className="cover-summary-eyebrow">Esperienza di lettura</span>
                <h2>{displayTitle}</h2>
                <p>di {book.author}</p>
                <div className="cover-summary-stats">
                  <span>{book.chapters.length} capitoli</span>
                  <span>{typeof book.total_pages === 'number' && book.total_pages > 0 ? `${book.total_pages} pagine` : 'Pagine in aggiornamento'}</span>
                  <span>{estimatedMinutes ? `${estimatedMinutes} min stimati` : 'Tempo di lettura non disponibile'}</span>
                </div>
                <button type="button" className="cover-summary-action" onClick={goToNextChapter}>
                  Inizia dal primo capitolo
                </button>
              </aside>
            </div>
          </div>
        ) : currentChapter ? (
          <article className="chapter" style={{ fontSize: `${fontSize}px` }}>
            <header className="chapter-header">
              <span className="chapter-label">Capitolo {currentChapterIndex + 1} di {book.chapters.length}</span>
              <h2 className="chapter-title">{currentChapter.title}</h2>
              <div className="chapter-audio-container" style={{ marginTop: '1rem', marginBottom: '2rem' }}>
                <AudioPlayer 
                  sessionId={sessionId!} 
                  type="chapter" 
                  chapterIndex={currentChapterIndex} 
                />
              </div>
            </header>
            
            <div 
              className="chapter-text"
              dangerouslySetInnerHTML={{ __html: formatContent(currentChapter.content) }}
            />
          </article>
        ) : null}
      </main>

      {/* Navigation Footer */}
      <footer className="reader-footer">
        <button 
          onClick={goToPreviousChapter}
          disabled={currentChapterIndex === -1 || (!hasCover && currentChapterIndex === 0)}
          className="nav-btn prev-btn"
        >
          {hasCover && currentChapterIndex === 0 ? '← Copertina' : '← Capitolo precedente'}
        </button>
        
        <div className="chapter-indicator">
          {isShowingCover ? (
            <span>Copertina</span>
          ) : (
            <span>{currentChapterIndex + 1} / {book.chapters.length}</span>
          )}
        </div>
        
        <button 
          onClick={goToNextChapter}
          disabled={!isShowingCover && currentChapterIndex === book.chapters.length - 1}
          className="nav-btn next-btn"
        >
          {isShowingCover ? 'Primo capitolo →' : 'Capitolo successivo →'}
        </button>
        </footer>
      </div>
    </PageTransition>
  );
}


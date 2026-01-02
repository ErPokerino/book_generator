import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { getCompleteBook, BookResponse } from '../api/client';
import AlertModal from './AlertModal';
import ExportDropdown from './ExportDropdown';
import './BookViewer.css';

interface BookViewerProps {
  sessionId: string;
  onBack?: () => void;
}

export default function BookViewer({ sessionId, onBack }: BookViewerProps) {
  const [book, setBook] = useState<BookResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedChapterIndex, setSelectedChapterIndex] = useState<number>(0);
  const [alertModal, setAlertModal] = useState<{ isOpen: boolean; title: string; message: string; variant?: 'error' | 'warning' | 'info' | 'success' }>({
    isOpen: false,
    title: '',
    message: '',
    variant: 'error',
  });

  useEffect(() => {
    loadBook();
  }, [sessionId]);

  const loadBook = async () => {
    try {
      setLoading(true);
      setError(null);
      console.log('[BookViewer] Caricamento libro per sessione:', sessionId);
      const bookData = await getCompleteBook(sessionId);
      console.log('[BookViewer] Libro caricato:', {
        title: bookData.title,
        author: bookData.author,
        chaptersCount: bookData.chapters.length
      });
      setBook(bookData);
      setSelectedChapterIndex(0);
    } catch (err) {
      console.error('[BookViewer] Errore nel caricamento del libro:', err);
      const errorMessage = err instanceof Error ? err.message : 'Errore nel caricamento del libro';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };


  if (loading) {
    return (
      <div className="book-viewer">
        <div className="loading">
          <p>Caricamento del libro...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="book-viewer">
        <div className="error-container">
          <h3>Errore</h3>
          <p>{error}</p>
          {onBack && (
            <button onClick={onBack} className="back-button">
              ← Indietro
            </button>
          )}
        </div>
      </div>
    );
  }

  if (!book || book.chapters.length === 0) {
    return (
      <div className="book-viewer">
        <div className="error-container">
          <h3>Nessun contenuto disponibile</h3>
          <p>Il libro non contiene capitoli.</p>
          {onBack && (
            <button onClick={onBack} className="back-button">
              ← Indietro
            </button>
          )}
        </div>
      </div>
    );
  }

  const currentChapter = book.chapters[selectedChapterIndex];

  return (
    <div className="book-viewer">
      {onBack && (
        <button onClick={onBack} className="back-button">
          ← Indietro
        </button>
      )}
      
      <div className="book-header">
        <h1 className="book-title">{book.title}</h1>
        <p className="book-author">di {book.author}</p>
        {book.total_pages && (
          <p className="book-pages">Totale: {book.total_pages} pagine</p>
        )}
        {book.writing_time_minutes && (
          <p className="book-time">Tempo scrittura: {Math.round(book.writing_time_minutes)} minuti</p>
        )}
        <div className="book-actions">
          <ExportDropdown sessionId={sessionId} />
        </div>
      </div>

      <div className="book-content-container">
        <div className="book-toc">
          <h3>Indice</h3>
          <ul className="toc-list">
            {book.chapters.map((chapter, index) => (
              <li 
                key={index}
                className={index === selectedChapterIndex ? 'active' : ''}
              >
                <button
                  onClick={() => setSelectedChapterIndex(index)}
                  className="toc-item"
                >
                  <span className="toc-item-title">{index + 1}. {chapter.title}</span>
                  {chapter.page_count > 0 && (
                    <span className="toc-item-pages">{chapter.page_count} pag.</span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </div>

        <div className="book-chapter-container">
          <div className="chapter-header">
            <div className="chapter-title-container">
              <h2 className="chapter-title">
                {selectedChapterIndex + 1}. {currentChapter.title}
              </h2>
              {currentChapter.page_count > 0 && (
                <span className="chapter-page-count">{currentChapter.page_count} pagine</span>
              )}
            </div>
            <div className="chapter-navigation">
              <button
                onClick={() => setSelectedChapterIndex(Math.max(0, selectedChapterIndex - 1))}
                disabled={selectedChapterIndex === 0}
                className="nav-button"
              >
                ← Capitolo Precedente
              </button>
              <span className="chapter-counter">
                {selectedChapterIndex + 1} / {book.chapters.length}
              </span>
              <button
                onClick={() => setSelectedChapterIndex(Math.min(book.chapters.length - 1, selectedChapterIndex + 1))}
                disabled={selectedChapterIndex === book.chapters.length - 1}
                className="nav-button"
              >
                Capitolo Successivo →
              </button>
            </div>
          </div>

          <div className="chapter-content">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {currentChapter.content}
            </ReactMarkdown>
          </div>
        </div>
      </div>

      {book.critique && (
        <div className="book-critique">
          <h3>📚 Valutazione Critica</h3>
          <div className="critique-score">
            <span className="score-label">Valutazione:</span>
            <span className="score-value">{book.critique.score.toFixed(1)}/10</span>
          </div>
          {book.critique.summary && (
            <div className="critique-summary">
              <strong>Sintesi:</strong>
              <p>{book.critique.summary}</p>
            </div>
          )}
          {book.critique.pros && book.critique.pros.length > 0 && (
            <div className="critique-pros">
              <strong>Punti di forza:</strong>
              <ul>
                {book.critique.pros.map((p, idx) => (
                  <li key={idx}>{p}</li>
                ))}
              </ul>
            </div>
          )}
          {book.critique.cons && book.critique.cons.length > 0 && (
            <div className="critique-cons">
              <strong>Punti di debolezza:</strong>
              <ul>
                {book.critique.cons.map((c, idx) => (
                  <li key={idx}>{c}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      <AlertModal
        isOpen={alertModal.isOpen}
        title={alertModal.title}
        message={alertModal.message}
        variant={alertModal.variant}
        onClose={() => setAlertModal({ isOpen: false, title: '', message: '' })}
      />
    </div>
  );
}


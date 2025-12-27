import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { getCompleteBook, downloadBookPdf, BookResponse } from '../api/client';
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
  const [isDownloading, setIsDownloading] = useState(false);

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

  const handleDownloadPdf = async () => {
    try {
      setIsDownloading(true);
      console.log('[BookViewer] Avvio download PDF per sessione:', sessionId);
      
      const blob = await downloadBookPdf(sessionId);
      console.log('[BookViewer] PDF ricevuto, dimensione:', blob.size, 'bytes');
      
      if (blob.size === 0) {
        throw new Error('Il PDF ricevuto è vuoto');
      }
      
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const filename = book?.title 
        ? `${book.title.replace(/[^a-z0-9]/gi, '_')}.pdf`
        : `Libro_${sessionId.substring(0, 8)}.pdf`;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      console.log('[BookViewer] Download avviato, filename:', filename);
      
      setTimeout(() => {
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      }, 100);
    } catch (err) {
      console.error('[BookViewer] Errore nel download del PDF:', err);
      const errorMessage = err instanceof Error ? err.message : 'Errore sconosciuto';
      alert(`Errore nel download del PDF: ${errorMessage}`);
    } finally {
      setIsDownloading(false);
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
        <div className="book-actions">
          <button 
            onClick={handleDownloadPdf} 
            className="download-pdf-button"
            disabled={isDownloading}
          >
            {isDownloading ? '⏳ Download in corso...' : '📥 Scarica PDF'}
          </button>
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
                  {index + 1}. {chapter.title}
                </button>
              </li>
            ))}
          </ul>
        </div>

        <div className="book-chapter-container">
          <div className="chapter-header">
            <h2 className="chapter-title">
              {selectedChapterIndex + 1}. {currentChapter.title}
            </h2>
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
    </div>
  );
}


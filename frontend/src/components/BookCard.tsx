import { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { MoreVertical } from 'lucide-react';
import toast from 'react-hot-toast';
import { LibraryEntry, deleteBook, regenerateCover } from '../api/client';
import ConfirmModal from './ConfirmModal';
import ExportDropdown from './ExportDropdown';
import './BookCard.css';

const API_BASE = '/api';

interface BookCardProps {
  book: LibraryEntry;
  onDelete: (sessionId: string) => void;
  onContinue?: (book: LibraryEntry) => void;
  onResume?: (book: LibraryEntry) => void;
  onRead?: (book: LibraryEntry) => void;
  onShowCritique?: (book: LibraryEntry) => void;
}

export default function BookCard({ book, onDelete, onContinue, onResume, onRead, onShowCritique }: BookCardProps) {
  const [regenerating, setRegenerating] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [showRegenerateConfirm, setShowRegenerateConfirm] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [menuPosition, setMenuPosition] = useState({ top: 0, right: 0 });
  const toggleRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const isManga = book.content_type === 'manga';

  const formatMangaType = (type?: string) => {
    const labels: Record<string, string> = {
      shonen: 'Shonen',
      shojo: 'Shojo',
      seinen: 'Seinen',
      josei: 'Josei',
      kodomo: 'Kodomo',
    };
    return type ? labels[type] ?? type : null;
  };

  const handleRegenerateCover = async () => {
    if (isManga) return;
    setShowRegenerateConfirm(true);
  };

  const confirmRegenerateCover = async () => {
    setShowRegenerateConfirm(false);
    try {
      setRegenerating(true);
      await regenerateCover(book.session_id);
      toast.success('Copertina rigenerata con successo');
      // Ricarica la pagina per vedere la nuova copertina
      window.location.reload();
    } catch (error) {
      toast.error(`Errore nella rigenerazione della copertina: ${error instanceof Error ? error.message : 'Errore sconosciuto'}`);
      setRegenerating(false);
    }
  };


  const handleDelete = () => {
    setShowDeleteConfirm(true);
  };

  const confirmDelete = async () => {
    setShowDeleteConfirm(false);
    try {
      await deleteBook(book.session_id);
      toast.success(isManga ? 'Manga eliminato con successo' : 'Libro eliminato con successo');
      onDelete(book.session_id);
    } catch (error) {
      toast.error(`Errore nell'eliminazione: ${error instanceof Error ? error.message : 'Errore sconosciuto'}`);
    }
  };

  const getStatusLabel = (status: string) => {
    const labels: Record<string, string> = {
      draft: 'Bozza',
      outline: 'Struttura',
      writing: 'In Scrittura',
      paused: 'In Pausa',
      complete: 'Completato',
    };
    return labels[status] || status;
  };

  // Rimuove la formattazione Markdown dal testo (asterischi, underscore, backtick)
  const stripMarkdownFormatting = (text: string): string => {
    if (!text) return text;
    return text
      .replace(/\*\*\*(.+?)\*\*\*/g, '$1') // ***bold italic*** → bold italic
      .replace(/\*\*(.+?)\*\*/g, '$1')     // **bold** → bold
      .replace(/\*(.+?)\*/g, '$1')         // *italic* → italic
      .replace(/___(.+?)___/g, '$1')       // ___bold italic___ → bold italic
      .replace(/__(.+?)__/g, '$1')         // __bold__ → bold
      .replace(/_(.+?)_/g, '$1')           // _italic_ → italic
      .replace(/`(.+?)`/g, '$1');          // `code` → code
  };

  // Calcola colore del voto su scala graduata: rosso (basso) → giallo (medio) → verde (alto)
  const getScoreColor = (score: number): string => {
    // Score da 0 a 10
    const normalizedScore = Math.max(0, Math.min(10, score));
    
    if (normalizedScore <= 5) {
      // Rosso (220, 53, 38) → Giallo (255, 193, 7) per 0-5
      const ratio = normalizedScore / 5;
      const r = Math.round(220 + (255 - 220) * ratio); // 220 → 255
      const g = Math.round(53 + (193 - 53) * ratio);   // 53 → 193
      const b = Math.round(38 - (38 - 7) * ratio);     // 38 → 7
      return `rgb(${r}, ${g}, ${b})`;
    } else {
      // Giallo (255, 193, 7) → Verde (34, 197, 94) per 5-10
      const ratio = (normalizedScore - 5) / 5;
      const r = Math.round(255 - (255 - 34) * ratio);  // 255 → 34
      const g = Math.round(193 + (197 - 193) * ratio); // 193 → 197
      const b = Math.round(7 + (94 - 7) * ratio);      // 7 → 94
      return `rgb(${r}, ${g}, ${b})`;
    }
  };

  // Gestione menu dropdown
  useEffect(() => {
    const updateMenuPosition = () => {
      if (toggleRef.current) {
        const rect = toggleRef.current.getBoundingClientRect();
        setMenuPosition({
          top: rect.bottom + 8,
          right: window.innerWidth - rect.right,
        });
      }
    };

    if (isMenuOpen) {
      updateMenuPosition();
      window.addEventListener('scroll', updateMenuPosition, true);
      window.addEventListener('resize', updateMenuPosition);
    }

    return () => {
      window.removeEventListener('scroll', updateMenuPosition, true);
      window.removeEventListener('resize', updateMenuPosition);
    };
  }, [isMenuOpen]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as HTMLElement;
      const isToggleClick = toggleRef.current?.contains(target);
      const isMenuClick = menuRef.current?.contains(target);
      // Riconosci anche i click sul sotto-menu di ExportDropdown (Portal separato)
      const isExportMenuClick = target.closest('[data-export-menu]') !== null;

      if (!isToggleClick && !isMenuClick && !isExportMenuClick) {
        setIsMenuOpen(false);
      }
    };

    if (isMenuOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isMenuOpen]);

  const handleToggleMenu = () => {
    setIsMenuOpen(!isMenuOpen);
  };

  const handleMenuAction = (action: () => void) => {
    setIsMenuOpen(false);
    action();
  };

  const coverImageUrl = book.cover_url || (
    book.cover_image_path
      ? `${API_BASE}/library/cover/${book.session_id}`
      : null
  );

  return (
    <div className="book-card">
      <div className="book-card-cover">
        {coverImageUrl ? (
          <img src={coverImageUrl} alt={book.title} />
        ) : (
          <div className="book-card-placeholder">{isManga ? '🎴' : '📖'}</div>
        )}
      </div>
      
      <div className="book-card-content">
        <div className="book-card-header">
          <div className="book-title-block">
            <h3 className="book-title work-title">{stripMarkdownFormatting(book.title)}</h3>
            <p className="book-card-meta-line">
              {isManga ? 'Manga' : 'Libro'}
              {book.total_pages ? ` · ${book.total_pages} pagine` : ''}
              {` · ${getStatusLabel(book.status)}`}
            </p>
          </div>
          <button
            ref={toggleRef}
            className="ui-icon-button book-card-toggle"
            onClick={handleToggleMenu}
            aria-label="Altre azioni"
            aria-expanded={isMenuOpen}
          >
            <MoreVertical size={18} />
          </button>
        </div>
        
        <div className={`book-card-info ${isExpanded ? 'expanded' : 'compact'}`}>
          {/* Info essenziali - sempre visibili */}
          <div className="book-card-info-essential">
            <p className="book-model">Modalità: {book.llm_model}</p>
            {isManga ? (
              book.manga_type && <p className="book-genre">Tipo: {formatMangaType(book.manga_type)}</p>
            ) : (
              book.genre && <p className="book-genre">Genere: {book.genre}</p>
            )}
            {book.total_pages && (
              <p className="book-pages">Pagine: {book.total_pages}</p>
            )}
            {!isManga && book.critique_score != null && (
              <p className="book-score">
                Voto: <span 
                  className="score-value" 
                  style={{ color: getScoreColor(book.critique_score) }}
                >
                  {book.critique_score.toFixed(1)}
                </span>
              </p>
            )}
          </div>
          
          {/* Info dettagliate - visibili solo quando espanso */}
          <div className={`book-card-info-details ${isExpanded ? 'expanded' : ''}`}>
            {!isManga && <p className="book-author">Autore: {book.author || 'N/A'}</p>}
            {!isManga && book.completed_chapters > 0 && (
              <p className="book-chapters">
                Capitoli: {book.completed_chapters}/{book.total_chapters}
              </p>
            )}
            {isManga && book.total_pages && (
              <p className="book-chapters">
                Pagine generate: {book.completed_pages ?? 0}/{book.total_pages}
              </p>
            )}
            {book.writing_time_minutes && (
              <p className="book-time">
                Tempo generazione: {Math.round(book.writing_time_minutes)} min
              </p>
            )}
            {book.total_pages && book.total_pages > 0 && (
              <p className="book-reading-time">
                Tempo lettura: {(() => {
                  const readingMinutes = Math.ceil(book.total_pages * 90 / 60); // 90 secondi per pagina
                  if (readingMinutes < 60) {
                    return `${readingMinutes} min`;
                  }
                  const hours = Math.floor(readingMinutes / 60);
                  const mins = readingMinutes % 60;
                  return mins > 0 ? `${hours}h ${mins}min` : `${hours}h`;
                })()}
              </p>
            )}
            {book.estimated_cost != null && (
              <p className="book-cost">
                Consumi API: ≈ €{book.estimated_cost >= 0.01 ? book.estimated_cost.toFixed(2) : book.estimated_cost.toFixed(4)}
              </p>
            )}
          </div>
        </div>

        <div className="book-card-actions">
          {book.status === 'complete' && onRead ? (
            <button type="button" className="action-btn read-btn" onClick={() => onRead(book)}>
              Leggi
            </button>
          ) : null}
          {(book.status === 'writing' || book.status === 'paused' || (!isManga && book.status === 'complete')) && onContinue ? (
            <button type="button" className="action-btn continue-btn" onClick={() => onContinue(book)}>
              {isManga ? 'Continua' : 'Apri studio'}
            </button>
          ) : null}
          {(book.status === 'draft' || book.status === 'outline') && onResume ? (
            <button type="button" className="action-btn resume-btn" onClick={() => onResume(book)}>
              Continua
            </button>
          ) : null}
        </div>

        <div className="book-card-meta">
          <span className="book-date">
            Creato: {new Date(book.created_at).toLocaleDateString('it-IT')}
          </span>
        </div>
      </div>

      <ConfirmModal
        isOpen={showDeleteConfirm}
        title="Conferma eliminazione"
        message={`Sei sicuro di voler eliminare "${stripMarkdownFormatting(book.title)}"?`}
        confirmText="Elimina"
        cancelText="Annulla"
        variant="danger"
        onConfirm={confirmDelete}
        onCancel={() => setShowDeleteConfirm(false)}
      />

      <ConfirmModal
        isOpen={showRegenerateConfirm}
        title="Rigenera copertina"
        message={`Vuoi rigenerare la copertina per "${stripMarkdownFormatting(book.title)}"?`}
        confirmText="Rigenera"
        cancelText="Annulla"
        variant="info"
        onConfirm={confirmRegenerateCover}
        onCancel={() => setShowRegenerateConfirm(false)}
      />

      {/* Menu Dropdown */}
      {isMenuOpen && createPortal(
        <div
          ref={menuRef}
          className="book-card-menu"
          style={{
            position: 'fixed',
            top: menuPosition.top,
            right: menuPosition.right,
          }}
        >
          {/* Sezione Dettagli */}
          <div className="book-card-menu-section">
            <button
              className="book-card-menu-item"
              onClick={() => handleMenuAction(() => setIsExpanded(!isExpanded))}
            >
              {isExpanded ? 'Nascondi dettagli' : 'Mostra dettagli'}
            </button>
          </div>

          {/* Sezione Azioni (solo se complete) */}
          {book.status === 'complete' && (
            <div className="book-card-menu-section">
              {!isManga && book.status === 'complete' && (
                <button
                  className="book-card-menu-item book-card-menu-item-regenerate"
                  onClick={() => handleMenuAction(handleRegenerateCover)}
                  disabled={regenerating}
                >
                  {regenerating ? 'Rigenerazione...' : 'Rigenera copertina'}
                </button>
              )}
              {book.status === 'complete' && (
                <div className="book-card-menu-export">
                  <ExportDropdown sessionId={book.session_id} contentType={book.content_type} />
                </div>
              )}
            </div>
          )}
          <div className="book-card-menu-section">
            {!isManga && onShowCritique && book.critique_score != null ? (
              <button
                className="book-card-menu-item"
                onClick={() => handleMenuAction(() => onShowCritique(book))}
              >
                Valutazione
              </button>
            ) : null}
            <button
              className="book-card-menu-item"
              onClick={() => handleMenuAction(handleDelete)}
            >
              Elimina
            </button>
          </div>
        </div>,
        document.body
      )}

    </div>
  );
}


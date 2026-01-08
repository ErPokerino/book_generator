import { useState } from 'react';
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
  onContinue?: (sessionId: string) => void;
  onResume?: (sessionId: string) => void;
  onRead?: (sessionId: string) => void;
  onShowCritique?: (sessionId: string) => void;
}

export default function BookCard({ book, onDelete, onContinue, onResume, onRead, onShowCritique }: BookCardProps) {
  const [regenerating, setRegenerating] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [showRegenerateConfirm, setShowRegenerateConfirm] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);

  const handleRegenerateCover = async () => {
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
      toast.success('Libro eliminato con successo');
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

  const getStatusClass = (status: string) => {
    return `status-badge status-${status}`;
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
      // Rosso → Giallo (0-5)
      const ratio = normalizedScore / 5;
      const r = 220;
      const g = Math.round(53 + (180 - 53) * ratio);
      const b = Math.round(38 + (35 - 38) * ratio);
      return `rgb(${r}, ${g}, ${b})`;
    } else {
      // Giallo → Verde (5-10)
      const ratio = (normalizedScore - 5) / 5;
      const r = Math.round(220 - (220 - 16) * ratio);
      const g = Math.round(180 - (180 - 185) * ratio);
      const b = Math.round(35 + (129 - 35) * ratio);
      return `rgb(${r}, ${g}, ${b})`;
    }
  };

  const coverImageUrl = book.cover_image_path 
    ? `${API_BASE}/library/cover/${book.session_id}`
    : null;

  return (
    <div className="book-card">
      <div className="book-card-cover">
        {coverImageUrl ? (
          <img src={coverImageUrl} alt={book.title} />
        ) : (
          <div className="book-card-placeholder">📖</div>
        )}
      </div>
      
      <div className="book-card-content">
        <div className="book-card-header">
          <h3 className="book-title">{stripMarkdownFormatting(book.title)}</h3>
          <div className="book-card-header-actions">
            <span className={getStatusClass(book.status)}>
              {getStatusLabel(book.status)}
            </span>
            <button
              className={`book-card-toggle ${isExpanded ? 'expanded' : ''}`}
              onClick={() => setIsExpanded(!isExpanded)}
              aria-label={isExpanded ? 'Nascondi dettagli' : 'Mostra dettagli'}
              aria-expanded={isExpanded}
            >
              <MoreVertical size={18} />
            </button>
          </div>
        </div>
        
        <div className={`book-card-info ${isExpanded ? 'expanded' : 'compact'}`}>
          {/* Info essenziali - sempre visibili */}
          <div className="book-card-info-essential">
            <p className="book-model">Modalità: {book.llm_model}</p>
            {book.genre && <p className="book-genre">Genere: {book.genre}</p>}
            {book.total_pages && (
              <p className="book-pages">Pagine: {book.total_pages}</p>
            )}
            {book.critique_score != null && (
              <p className="book-score">
                Voto: <span 
                  className="score-value" 
                  style={{ color: getScoreColor(book.critique_score) }}
                >
                  {book.critique_score.toFixed(1)}/10
                </span>
              </p>
            )}
          </div>
          
          {/* Info dettagliate - visibili solo quando espanso */}
          <div className={`book-card-info-details ${isExpanded ? 'expanded' : ''}`}>
            <p className="book-author">Autore: {book.author || 'N/A'}</p>
            {book.completed_chapters > 0 && (
              <p className="book-chapters">
                Capitoli: {book.completed_chapters}/{book.total_chapters}
              </p>
            )}
            <p className="book-created-date">
              Data generazione: {new Date(book.created_at).toLocaleDateString('it-IT', { 
                day: '2-digit', 
                month: '2-digit', 
                year: 'numeric'
              })}
            </p>
            {book.writing_time_minutes && (
              <p className="book-time">
                Tempo scrittura: {Math.round(book.writing_time_minutes)} min
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
                Costo stimato: €{book.estimated_cost >= 0.01 ? book.estimated_cost.toFixed(2) : book.estimated_cost.toFixed(4)}
              </p>
            )}
          </div>
        </div>

        <div className="book-card-actions">
          {book.status === 'complete' && book.critique_score != null && onShowCritique && (
            <button className="action-btn critique-btn" onClick={() => onShowCritique(book.session_id)}>
              📝 Critica
            </button>
          )}
          {book.status === 'complete' && !book.cover_image_path && (
            <button 
              className="action-btn regenerate-cover-btn" 
              onClick={handleRegenerateCover}
              disabled={regenerating}
            >
              {regenerating ? '⏳ Rigenerazione...' : '🖼️ Rigenera Copertina'}
            </button>
          )}
          {book.status === 'complete' && onRead && (
            <button className="action-btn read-btn" onClick={() => onRead(book.session_id)}>
              📖 Leggi
            </button>
          )}
          {book.status === 'complete' && (
            <ExportDropdown sessionId={book.session_id} />
          )}
          {(book.status === 'writing' || book.status === 'paused') && onContinue && (
            <button className="action-btn continue-btn" onClick={() => onContinue(book.session_id)}>
              ▶️ Continua
            </button>
          )}
          {(book.status === 'draft' || book.status === 'outline') && onResume && (
            <button className="action-btn resume-btn" onClick={() => onResume(book.session_id)}>
              ▶️ Riprendi
            </button>
          )}
          <button className="action-btn delete-btn" onClick={handleDelete}>
            🗑️ Elimina
          </button>
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

    </div>
  );
}


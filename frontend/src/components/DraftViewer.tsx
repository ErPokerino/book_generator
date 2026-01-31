import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './DraftViewer.css';

interface DraftViewerProps {
  draftText: string;
  title?: string;
  version: number;
  onManualEdit?: (newText: string, newTitle?: string) => void;
  isLoading?: boolean;
}

// Funzione per rimuovere marker markdown dal titolo
const sanitizeTitle = (title: string): string => {
  return title
    .replace(/^\*\*|\*\*$/g, '')  // Rimuove ** all'inizio e alla fine
    .replace(/^__|\__$/g, '')      // Rimuove __ all'inizio e alla fine
    .replace(/^\*|\*$/g, '')       // Rimuove * singoli
    .replace(/^_|_$/g, '')         // Rimuove _ singoli
    .replace(/\*\*/g, '')          // Rimuove tutti i ** nel mezzo
    .replace(/__/g, '')            // Rimuove tutti gli __ nel mezzo
    .trim();
};

export default function DraftViewer({ draftText, title, version, onManualEdit, isLoading }: DraftViewerProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editedText, setEditedText] = useState(draftText);
  const [editedTitle, setEditedTitle] = useState(title || '');

  // Sincronizza lo stato quando cambiano le props
  useEffect(() => {
    setEditedText(draftText);
    setEditedTitle(title || '');
  }, [draftText, title]);

  const handleToggleEdit = () => {
    if (isEditing) {
      // Annulla le modifiche
      setEditedText(draftText);
      setEditedTitle(title || '');
    }
    setIsEditing(!isEditing);
  };

  const handleSave = () => {
    if (onManualEdit) {
      onManualEdit(editedText, editedTitle || undefined);
    }
    setIsEditing(false);
  };

  const hasChanges = editedText !== draftText || editedTitle !== (title || '');

  return (
    <div className="draft-viewer">
      <div className="draft-header">
        <h2>Bozza Estesa della Trama</h2>
        <div className="draft-header-actions">
          <span className="draft-version">Versione {version}</span>
          {onManualEdit && (
            <button
              className={`edit-toggle-button ${isEditing ? 'editing' : ''}`}
              onClick={handleToggleEdit}
              disabled={isLoading}
              title={isEditing ? 'Annulla modifiche' : 'Modifica manualmente'}
            >
              {isEditing ? 'Annulla' : 'Modifica'}
            </button>
          )}
        </div>
      </div>
      
      {isEditing ? (
        <>
          <div className="draft-title-edit">
            <label htmlFor="draft-title-input">Titolo:</label>
            <input
              id="draft-title-input"
              type="text"
              value={editedTitle}
              onChange={(e) => setEditedTitle(e.target.value)}
              placeholder="Inserisci il titolo del libro..."
              disabled={isLoading}
            />
          </div>
          <div className="draft-content draft-content-edit">
            <textarea
              className="draft-edit-textarea"
              value={editedText}
              onChange={(e) => setEditedText(e.target.value)}
              placeholder="Inserisci il contenuto della bozza in formato Markdown..."
              disabled={isLoading}
            />
          </div>
          <div className="draft-edit-actions">
            <button
              className="draft-save-button"
              onClick={handleSave}
              disabled={isLoading || !hasChanges}
            >
              {isLoading ? 'Salvataggio...' : 'Salva Modifiche'}
            </button>
            <button
              className="draft-cancel-button"
              onClick={handleToggleEdit}
              disabled={isLoading}
            >
              Annulla
            </button>
          </div>
        </>
      ) : (
        <>
          {title && (
            <div className="draft-title">
              <h1>{sanitizeTitle(title)}</h1>
            </div>
          )}
          <div className="draft-content">
            <div className="draft-markdown">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {draftText}
              </ReactMarkdown>
            </div>
          </div>
        </>
      )}
    </div>
  );
}



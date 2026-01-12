import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './DraftViewer.css';

interface DraftViewerProps {
  draftText: string;
  title?: string;
  version: number;
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

export default function DraftViewer({ draftText, title, version }: DraftViewerProps) {
  return (
    <div className="draft-viewer">
      <div className="draft-header">
        <h2>Bozza Estesa della Trama</h2>
        <span className="draft-version">Versione {version}</span>
      </div>
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
    </div>
  );
}



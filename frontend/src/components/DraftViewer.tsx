import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './DraftViewer.css';

interface DraftViewerProps {
  draftText: string;
  title?: string;
  version: number;
}

export default function DraftViewer({ draftText, title, version }: DraftViewerProps) {
  return (
    <div className="draft-viewer">
      <div className="draft-header">
        <h2>Bozza Estesa della Trama</h2>
        <span className="draft-version">Versione {version}</span>
      </div>
      {title && (
        <div className="draft-title">
          <h1>{title}</h1>
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



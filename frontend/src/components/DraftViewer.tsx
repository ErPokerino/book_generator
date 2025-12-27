import React from 'react';
import './DraftViewer.css';

interface DraftViewerProps {
  draftText: string;
  version: number;
}

export default function DraftViewer({ draftText, version }: DraftViewerProps) {
  return (
    <div className="draft-viewer">
      <div className="draft-header">
        <h2>Bozza Estesa della Trama</h2>
        <span className="draft-version">Versione {version}</span>
      </div>
      <div className="draft-content">
        <pre className="draft-text">{draftText}</pre>
      </div>
    </div>
  );
}


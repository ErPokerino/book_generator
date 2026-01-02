import { useState, useRef, useEffect } from 'react';
import { exportBook } from '../api/client';
import './ExportDropdown.css';

interface ExportDropdownProps {
  sessionId: string;
  disabled?: boolean;
  className?: string;
}

export default function ExportDropdown({ sessionId, disabled = false, className = '' }: ExportDropdownProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [exportingFormat, setExportingFormat] = useState<'pdf' | 'epub' | 'docx' | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  const handleExport = async (format: 'pdf' | 'epub' | 'docx') => {
    setIsOpen(false);
    setIsExporting(true);
    setExportingFormat(format);

    try {
      console.log(`[ExportDropdown] Inizio export ${format} per sessione ${sessionId}`);
      const { blob, filename } = await exportBook(sessionId, format);
      
      if (!blob || blob.size === 0) {
        throw new Error('Il file ricevuto è vuoto');
      }
      
      console.log(`[ExportDropdown] File ricevuto: ${filename}, dimensione: ${blob.size} bytes`);
      
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      
      // Cleanup dopo un breve delay
      setTimeout(() => {
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      }, 100);
      
      console.log(`[ExportDropdown] Download avviato per ${filename}`);
    } catch (error) {
      console.error(`[ExportDropdown] Errore nell'export ${format}:`, error);
      const errorMessage = error instanceof Error ? error.message : 'Errore sconosciuto';
      alert(`Errore nell'export ${format}:\n\n${errorMessage}\n\nVerifica che:\n- Il backend sia in esecuzione\n- Il libro sia completato\n- La sessione sia valida`);
    } finally {
      setIsExporting(false);
      setExportingFormat(null);
    }
  };

  const getFormatLabel = (format: 'pdf' | 'epub' | 'docx') => {
    switch (format) {
      case 'pdf':
        return 'PDF';
      case 'epub':
        return 'EPUB';
      case 'docx':
        return 'DOCX';
      default:
        return format.toUpperCase();
    }
  };

  return (
    <div className={`export-dropdown ${className}`} ref={dropdownRef}>
      <button
        className="export-dropdown-button"
        onClick={() => !disabled && setIsOpen(!isOpen)}
        disabled={disabled || isExporting}
      >
        {isExporting ? (
          <>
            <span>⏳ Esportazione {exportingFormat ? getFormatLabel(exportingFormat) : ''}...</span>
          </>
        ) : (
          <>
            <span>📥 Esporta</span>
            <span className="dropdown-arrow">▼</span>
          </>
        )}
      </button>
      
      {isOpen && !disabled && !isExporting && (
        <div className="export-dropdown-menu">
          <button
            className="export-option"
            onClick={() => handleExport('pdf')}
          >
            <span className="format-icon">📄</span>
            <span>PDF</span>
          </button>
          <button
            className="export-option"
            onClick={() => handleExport('epub')}
          >
            <span className="format-icon">📚</span>
            <span>EPUB</span>
          </button>
          <button
            className="export-option"
            onClick={() => handleExport('docx')}
          >
            <span className="format-icon">📝</span>
            <span>DOCX</span>
          </button>
        </div>
      )}
    </div>
  );
}

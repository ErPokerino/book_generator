import { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
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
  const [menuPosition, setMenuPosition] = useState({ top: 0, left: 0 });
  const buttonRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  // Calcola la posizione del menu e aggiorna su scroll/resize
  useEffect(() => {
    const updatePosition = () => {
      if (buttonRef.current) {
        const rect = buttonRef.current.getBoundingClientRect();
        const menuWidth = 140; // Larghezza minima del menu
        const viewportWidth = window.innerWidth;
        
        // Se il pulsante è nella metà sinistra dello schermo, allinea a sinistra
        // Altrimenti allinea a destra
        let left: number;
        if (rect.left < viewportWidth / 2) {
          // Allinea a sinistra del pulsante
          left = rect.left;
        } else {
          // Allinea a destra del pulsante
          left = rect.right - menuWidth;
        }
        
        // Assicurati che il menu non esca dallo schermo
        left = Math.max(8, Math.min(left, viewportWidth - menuWidth - 8));
        
        setMenuPosition({
          top: rect.bottom + 8, // 8px di gap
          left: left,
        });
      }
    };

    if (isOpen) {
      updatePosition();
      window.addEventListener('scroll', updatePosition, true); // true per capture phase
      window.addEventListener('resize', updatePosition);
    }

    return () => {
      window.removeEventListener('scroll', updatePosition, true);
      window.removeEventListener('resize', updatePosition);
    };
  }, [isOpen]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node;
      const isButtonClick = buttonRef.current?.contains(target);
      const isMenuClick = menuRef.current?.contains(target);
      
      if (!isButtonClick && !isMenuClick) {
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

  // Render del menu tramite Portal (fuori dal DOM della card)
  const renderMenu = () => {
    if (!isOpen || disabled || isExporting) return null;

    return createPortal(
      <div 
        className="export-dropdown-menu export-dropdown-menu-portal"
        ref={menuRef}
        style={{
          position: 'fixed',
          top: menuPosition.top,
          left: menuPosition.left,
        }}
      >
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
      </div>,
      document.body
    );
  };

  return (
    <div className={`export-dropdown ${className}`}>
      <button
        ref={buttonRef}
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
      
      {renderMenu()}
    </div>
  );
}

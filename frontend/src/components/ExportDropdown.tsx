import { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import toast from 'react-hot-toast';
import { downloadMangaPdf, exportBook } from '../api/client';
import { ESSAY_API } from '../essay/api';
import { Download, ChevronDown, FileText, BookOpen, Pencil } from 'lucide-react';
import { downloadFilename } from '../utils/downloadFilename';
import './ExportDropdown.css';

interface ExportDropdownProps {
  sessionId: string;
  contentType?: 'book' | 'essay' | 'manga';
  disabled?: boolean;
  className?: string;
}

export default function ExportDropdown({
  sessionId,
  contentType = 'book',
  disabled = false,
  className = '',
}: ExportDropdownProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [exportingFormat, setExportingFormat] = useState<'pdf' | 'epub' | 'docx' | null>(null);
  const [menuPosition, setMenuPosition] = useState({ top: 0, left: 0 });
  const buttonRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const isManga = contentType === 'manga';

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
          top: rect.bottom + 8, // 8px di gap, menu si apre verso il basso
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
      const target = event.target as HTMLElement;
      const isButtonClick = buttonRef.current?.contains(target);
      // Usa data attribute per identificare il menu (più affidabile con Portal)
      const isMenuClick = target.closest('[data-export-menu]') !== null;
      
      if (!isButtonClick && !isMenuClick) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      // Usa setTimeout per permettere al click di essere processato prima
      const timeoutId = setTimeout(() => {
        document.addEventListener('mousedown', handleClickOutside);
      }, 0);
      
      return () => {
        clearTimeout(timeoutId);
        document.removeEventListener('mousedown', handleClickOutside);
      };
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
      let result;
      if (contentType === 'essay') {
        const response = await fetch(`${ESSAY_API}essays/${sessionId}/export/${format}`);
        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.detail || 'Esportazione non disponibile');
        }
        result = {blob: await response.blob(), filename:downloadFilename(response.headers.get('Content-Disposition'), `Saggio_${sessionId.substring(0,8)}.${format}`)};
      } else result = isManga ? await downloadMangaPdf(sessionId) : await exportBook(sessionId, format);
      const { blob, filename } = result;
      
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
      toast.success(`${format.toUpperCase()} esportato con successo!`);
    } catch (error) {
      console.error(`[ExportDropdown] Errore nell'export ${format}:`, error);
      const errorMessage = error instanceof Error ? error.message : 'Errore sconosciuto';
      toast.error(`Errore nell'export ${format.toUpperCase()}: ${errorMessage}`);
    } finally {
      setIsExporting(false);
      setExportingFormat(null);
    }
  };

  const getFormatLabel = (format: string) => {
    switch (format) {
      case 'pdf':
        return 'PDF';
      case 'epub':
        return 'EPUB';
      case 'docx':
        return 'DOCX';
    }
    return format.toUpperCase();
  };

  // Render del menu tramite Portal (fuori dal DOM della card)
  const renderMenu = () => {
    if (isManga || !isOpen || disabled || isExporting) return null;

    return createPortal(
      <div 
        className="export-dropdown-menu export-dropdown-menu-portal"
        ref={menuRef}
        data-export-menu="true"
        style={{
          position: 'fixed',
          top: menuPosition.top,
          left: menuPosition.left,
        }}
      >
        <button
          className="export-option"
          onClick={(e) => {
            e.stopPropagation();
            handleExport('pdf');
          }}
        >
          <FileText size={18} aria-hidden="true"/>
          <span>PDF</span>
        </button>
        <button
          className="export-option"
          onClick={(e) => {
            e.stopPropagation();
            handleExport('epub');
          }}
        >
          <BookOpen size={18} aria-hidden="true"/>
          <span>EPUB</span>
        </button>
        <button
          className="export-option"
          onClick={(e) => {
            e.stopPropagation();
            handleExport('docx');
          }}
        >
          <Pencil size={18} aria-hidden="true"/>
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
        type="button"
        className="export-dropdown-button"
        aria-expanded={isManga ? undefined : isOpen}
        onClick={() => {
          if (disabled || isExporting) return;
          if (isManga) {
            handleExport('pdf');
            return;
          }
          setIsOpen(!isOpen);
        }}
        disabled={disabled || isExporting}
      >
        {isExporting ? (
          <>
            <span>Esportazione {exportingFormat ? getFormatLabel(exportingFormat) : ''}…</span>
          </>
        ) : (
          <>
            <Download size={16} aria-hidden="true"/><span>{isManga ? 'Scarica PDF' : 'Esporta'}</span>
            {!isManga && <ChevronDown className="dropdown-arrow" size={15} aria-hidden="true"/>}
          </>
        )}
      </button>
      
      {renderMenu()}
    </div>
  );
}

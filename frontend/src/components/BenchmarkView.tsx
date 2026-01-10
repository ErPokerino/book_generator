import { useState, useRef } from 'react';
import { analyzeExternalPdf, LiteraryCritique } from '../api/client';
import { useToast } from '../hooks/useToast';
import './BenchmarkView.css';

// Calcola colore del voto su scala graduata: rosso (basso) → giallo (medio) → verde (alto)
const getScoreColor = (score: number): string => {
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

export default function BenchmarkView() {
  const toast = useToast();
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState<string>('');
  const [author, setAuthor] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [critique, setCritique] = useState<LiteraryCritique | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (!selectedFile) {
      setFile(null);
      return;
    }

    // Validazione file
    if (!selectedFile.name.toLowerCase().endsWith('.pdf')) {
      toast.error('Il file deve essere un PDF (.pdf)');
      setFile(null);
      return;
    }

    if (selectedFile.size > MAX_FILE_SIZE) {
      toast.error(`File troppo grande. Dimensione massima: ${(MAX_FILE_SIZE / (1024 * 1024)).toFixed(0)}MB`);
      setFile(null);
      return;
    }

    setFile(selectedFile);
    // Suggerisci titolo dal nome file
    if (!title && selectedFile.name) {
      const suggestedTitle = selectedFile.name.replace('.pdf', '').replace(/_/g, ' ');
      setTitle(suggestedTitle);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!file) {
      toast.error('Seleziona un file PDF');
      return;
    }

    setLoading(true);
    setCritique(null);
    
    const loadingToast = toast.loading('Analisi PDF in corso...');

    try {
      // Timeout di 10 minuti (600 secondi) per l'analisi PDF
      // L'analisi può richiedere tempo per PDF grandi
      const timeoutMs = 10 * 60 * 1000; // 10 minuti
      
      const timeoutPromise = new Promise<never>((_, reject) => 
        setTimeout(() => reject(new Error('Timeout: l\'analisi sta impiegando troppo tempo. Il PDF potrebbe essere troppo grande o complesso.')), timeoutMs)
      );
      
      const result = await Promise.race([
        analyzeExternalPdf(
          file,
          title.trim() || undefined,
          author.trim() || undefined
        ),
        timeoutPromise,
      ]);
      
      setCritique(result);
      toast.dismiss(loadingToast);
      toast.success('Analisi completata con successo!');
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Errore durante l\'analisi del PDF';
      toast.dismiss(loadingToast);
      toast.error(errorMessage);
      console.error('Errore nell\'analisi PDF:', err);
    } finally {
      // Sempre disabilita il loading, anche in caso di errore
      setLoading(false);
    }
  };

  const handleReset = () => {
    setFile(null);
    setTitle('');
    setAuthor('');
    setCritique(null);
    // Reset file input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleButtonClick = () => {
    // Trigger click sull'input file nascosto
    fileInputRef.current?.click();
  };

  return (
    <div className="benchmark-view">
      <div className="benchmark-container">
        <h2 className="benchmark-title">Valuta un Libro</h2>
        <p className="benchmark-description">
          Carica un PDF per farlo valutare dal critico letterario.
          Ottieni una valutazione completa con punteggio, punti di forza e aree di miglioramento.
        </p>

        <form onSubmit={handleSubmit} className="benchmark-form">
          <div className="form-group">
            <span className="form-label">
              File PDF <span className="required">*</span>
            </span>
            <div className="file-input-wrapper">
              <input
                ref={fileInputRef}
                id="pdf-file-input"
                type="file"
                accept=".pdf,application/pdf"
                onChange={handleFileChange}
                className="file-input-hidden"
                disabled={loading}
              />
              {/* Usiamo una label come trigger - funziona nativamente su tutti i browser */}
              <label 
                htmlFor="pdf-file-input" 
                className={`file-input-label ${loading ? 'disabled' : ''}`}
              >
                📁 Scegli File PDF
              </label>
              {file ? (
                <div className="file-info">
                  <span className="file-name">✓ {file.name}</span>
                  <span className="file-size">
                    ({(file.size / (1024 * 1024)).toFixed(2)} MB)
                  </span>
                </div>
              ) : (
                <span className="file-placeholder">Nessun file selezionato</span>
              )}
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="title-input" className="form-label">
              Titolo (opzionale)
            </label>
            <input
              id="title-input"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Titolo del libro"
              className="text-input"
              disabled={loading}
            />
          </div>

          <div className="form-group">
            <label htmlFor="author-input" className="form-label">
              Autore (opzionale)
            </label>
            <input
              id="author-input"
              type="text"
              value={author}
              onChange={(e) => setAuthor(e.target.value)}
              placeholder="Nome dell'autore"
              className="text-input"
              disabled={loading}
            />
          </div>


          <div className="form-actions">
            <button
              type="submit"
              className="btn-primary"
              disabled={!file || loading}
            >
              {loading ? 'Analisi in corso...' : 'Analizza PDF'}
            </button>
            {(file || critique) && (
              <button
                type="button"
                onClick={handleReset}
                className="btn-secondary"
                disabled={loading}
              >
                Reset
              </button>
            )}
          </div>
        </form>

        {loading && (
          <div className="loading-indicator">
            <div className="spinner"></div>
            <p>Analisi del PDF in corso... Questo potrebbe richiedere alcuni minuti.</p>
          </div>
        )}

        {critique && (
          <div className="critique-result">
            <h3 className="result-title">Risultato Valutazione</h3>
            
            <div className="score-section">
              <div className="score-value" style={{ color: getScoreColor(critique.score) }}>
                {critique.score.toFixed(1)}
              </div>
              <div className="score-label">/ 10</div>
            </div>

            {critique.summary && (
              <div className="summary-section">
                <h4>Sintesi</h4>
                <p>{critique.summary}</p>
              </div>
            )}

            {critique.pros && critique.pros.length > 0 && (
              <div className="pros-section">
                <h4>Punti di Forza</h4>
                <ul>
                  {critique.pros.map((pro, index) => (
                    <li key={index}>{pro}</li>
                  ))}
                </ul>
              </div>
            )}

            {critique.cons && critique.cons.length > 0 && (
              <div className="cons-section">
                <h4>Punti di Debolezza</h4>
                <ul>
                  {critique.cons.map((con, index) => (
                    <li key={index}>{con}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}


import { useState, useRef } from 'react';
import { analyzeExternalPdf, LiteraryCritique } from '../api/client';
import { useToast } from '../hooks/useToast';
import CritiqueBlock from './CritiqueBlock';
import PageHeader from './ui/PageHeader';
import Button from './ui/Button';
import './BenchmarkView.css';

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

  return (
    <div className="page-shell benchmark-view">
      <PageHeader
        title="Valuta"
        description="Carica un PDF. Ottieni punteggio, punti di forza e debolezze."
      />

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
              <label
                htmlFor="pdf-file-input"
                className={`file-input-label ${loading ? 'disabled' : ''}`}
              >
                {file ? file.name : 'Scegli un PDF'}
              </label>
              {file ? (
                <div className="file-info">
                  <span className="file-size">
                    {(file.size / (1024 * 1024)).toFixed(2)} MB
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
            <Button type="submit" disabled={!file || loading}>
              {loading ? 'Analisi in corso...' : 'Analizza PDF'}
            </Button>
            {(file || critique) && (
              <Button
                type="button"
                variant="ghost"
                onClick={handleReset}
                disabled={loading}
              >
                Reset
              </Button>
            )}
          </div>
        </form>

        {loading && (
          <p className="loading-indicator">Analisi del PDF in corso. Può richiedere alcuni minuti.</p>
        )}

        {critique ? <CritiqueBlock critique={critique} /> : null}
    </div>
  );
}


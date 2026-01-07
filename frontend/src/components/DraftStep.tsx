import React, { useState, useEffect } from 'react';
import { generateDraft, modifyDraft, validateDraft, generateOutline, DraftResponse, DraftModificationRequest, DraftValidationRequest, OutlineResponse, SubmissionRequest, QuestionAnswer } from '../api/client';
import DraftViewer from './DraftViewer';
import DraftChat from './DraftChat';
import './DraftStep.css';

interface DraftStepProps {
  sessionId: string;
  formData: SubmissionRequest;
  questionAnswers: QuestionAnswer[];
  onDraftValidated: (draft: DraftResponse, outline: OutlineResponse | null) => void;
  onBack?: () => void;
  onOutlineGenerationStart?: () => void;
  initialDraft?: DraftResponse | null; // Bozza esistente da ripristinare
}

export default function DraftStep({ sessionId, formData, questionAnswers, onDraftValidated, onBack, onOutlineGenerationStart, initialDraft }: DraftStepProps) {
  const [draft, setDraft] = useState<DraftResponse | null>(initialDraft || null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isModifying, setIsModifying] = useState(false);
  const [isValidating, setIsValidating] = useState(false);
  const [isGeneratingOutline, setIsGeneratingOutline] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Se c'è un initialDraft, usa quello (ripristino sessione)
    // Altrimenti genera la bozza iniziale quando il componente viene montato
    if (initialDraft && !draft) {
      setDraft(initialDraft);
    } else if (!draft && !isGenerating) {
      handleGenerateDraft();
    }
  }, [initialDraft]);

  const handleGenerateDraft = async () => {
    setIsGenerating(true);
    setError(null);
    
    try {
      const response = await generateDraft({
        form_data: formData,
        question_answers: questionAnswers,
        session_id: sessionId,
      });
      setDraft(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Errore nella generazione della bozza');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleModifyDraft = async (feedback: string) => {
    if (!draft) return;

    setIsModifying(true);
    setError(null);

    try {
      const request: DraftModificationRequest = {
        session_id: sessionId,
        user_feedback: feedback,
        current_version: draft.version,
      };
      const response = await modifyDraft(request);
      setDraft(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Errore nella modifica della bozza');
    } finally {
      setIsModifying(false);
    }
  };

  const handleValidateDraft = async () => {
    if (!draft) return;

    setIsValidating(true);
    setError(null);

    try {
      const request: DraftValidationRequest = {
        session_id: sessionId,
        validated: true,
      };
      await validateDraft(request);
      
      // Notifica che inizia la generazione dell'outline (per aggiornare lo step indicator)
      onOutlineGenerationStart?.();
      
      // Dopo la validazione, mostra loading per generazione outline
      setIsValidating(false);
      setIsGeneratingOutline(true);
      
      // Genera automaticamente l'outline dopo la validazione
      let outline: OutlineResponse | null = null;
      try {
        console.log('[DEBUG] Inizio generazione outline per sessione:', sessionId);
        outline = await generateOutline({ session_id: sessionId });
        console.log('[DEBUG] Outline generato con successo:', outline);
        console.log('[DEBUG] Outline text length:', outline?.outline_text?.length || 0);
      } catch (outlineErr) {
        console.error('[ERROR] Errore nella generazione della struttura:', outlineErr);
        if (outlineErr instanceof Error) {
          console.error('[ERROR] Messaggio:', outlineErr.message);
          console.error('[ERROR] Stack:', outlineErr.stack);
          // Mostra il messaggio di errore all'utente, specialmente per timeout
          setError(outlineErr.message);
        }
        // Non blocchiamo il flusso se l'outline fallisce, ma mostriamo l'errore
      } finally {
        setIsGeneratingOutline(false);
      }
      
      onDraftValidated(draft, outline);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Errore nella validazione della bozza');
      setIsValidating(false);
      setIsGeneratingOutline(false);
    }
  };

  if (isGenerating) {
    return (
      <div className="draft-step-loading">
        <h2>Generazione Bozza Estesa</h2>
        <p>Sto generando la bozza estesa della trama...</p>
        <p style={{ fontSize: '0.9rem', color: '#666', marginTop: '0.5rem' }}>
          Questo richiederà circa un minuto
        </p>
      </div>
    );
  }

  if (isGeneratingOutline) {
    return (
      <div className="draft-step-loading">
        <h2>Generazione Struttura del Libro</h2>
        <p>Sto generando la struttura del libro...</p>
        <p style={{ fontSize: '0.9rem', color: '#666', marginTop: '0.5rem' }}>
          Questo richiederà circa un minuto
        </p>
      </div>
    );
  }

  if (!draft) {
    return (
      <div className="draft-step-error">
        <h2>Errore</h2>
        <p>Impossibile caricare la bozza.</p>
        {error && <p className="error-text">{error}</p>}
        <button onClick={handleGenerateDraft}>Riprova</button>
      </div>
    );
  }

  const isLoading = isModifying || isValidating;

  return (
    <div className="draft-step">
      {onBack && (
        <button onClick={onBack} className="back-button" disabled={isLoading}>
          ← Indietro
        </button>
      )}
      <div className="draft-step-content">
        <div className="draft-viewer-container">
          <DraftViewer draftText={draft.draft_text} title={draft.title} version={draft.version} />
        </div>
        <div className="draft-chat-container">
          <DraftChat
            onSendFeedback={handleModifyDraft}
            onValidate={handleValidateDraft}
            isLoading={isLoading}
            error={error}
          />
        </div>
      </div>
    </div>
  );
}



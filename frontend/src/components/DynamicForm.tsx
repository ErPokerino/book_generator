import { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { fetchConfig, submitForm, generateQuestions, downloadPdf, getOutline, startBookGeneration, FieldConfig, SubmissionRequest, SubmissionResponse, Question, QuestionAnswer } from '../api/client';
import QuestionsStep from './QuestionsStep';
import DraftStep from './DraftStep';
import WritingStep from './WritingStep';
import './DynamicForm.css';

export default function DynamicForm() {
  const [config, setConfig] = useState<{ llm_models: string[]; fields: FieldConfig[] } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [formData, setFormData] = useState<Record<string, string>>({});
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({});
  const [submitted, setSubmitted] = useState<SubmissionResponse | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [questions, setQuestions] = useState<Question[] | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [formPayload, setFormPayload] = useState<SubmissionRequest | null>(null);
  const [isGeneratingQuestions, setIsGeneratingQuestions] = useState(false);
  const [answersSubmitted, setAnswersSubmitted] = useState(false);
  const [questionAnswers, setQuestionAnswers] = useState<QuestionAnswer[]>([]);
  const [currentStep, setCurrentStep] = useState<'form' | 'questions' | 'draft' | 'summary' | 'writing'>('form');
  const [validatedDraft, setValidatedDraft] = useState<{ title?: string; text: string } | null>(null);
  const [outline, setOutline] = useState<string | null>(null);
  const [isStartingWriting, setIsStartingWriting] = useState(false);

  useEffect(() => {
    loadConfig();
  }, []);

  // Se siamo nel summary e non abbiamo l'outline, prova a recuperarlo.
  // Deve stare qui (top-level) per rispettare le Rules of Hooks (niente hook dentro if/return).
  useEffect(() => {
    if (currentStep !== 'summary') return;
    if (!sessionId) return;
    if (outline) return;

    const fetchOutline = async () => {
      try {
        const retrievedOutline = await getOutline(sessionId);
        if (retrievedOutline?.outline_text) {
          console.log('[DEBUG] Outline recuperato nel summary:', retrievedOutline.outline_text.length);
          setOutline(retrievedOutline.outline_text);
        }
      } catch (err) {
        console.error('[DEBUG] Impossibile recuperare outline:', err);
      }
    };

    fetchOutline();
  }, [currentStep, sessionId, outline]);

  const loadConfig = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchConfig();
      setConfig(data);
      
      // Inizializza formData con valori vuoti
      const initialData: Record<string, string> = {};
      data.fields.forEach(field => {
        initialData[field.id] = '';
      });
      setFormData(initialData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Errore nel caricamento della configurazione');
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (fieldId: string, value: string) => {
    setFormData(prev => ({ ...prev, [fieldId]: value }));
    // Rimuovi errore di validazione quando l'utente modifica il campo
    if (validationErrors[fieldId]) {
      setValidationErrors(prev => {
        const newErrors = { ...prev };
        delete newErrors[fieldId];
        return newErrors;
      });
    }
  };

  const validateForm = (): boolean => {
    if (!config) return false;
    
    const errors: Record<string, string> = {};
    
    config.fields.forEach(field => {
      if (field.required && !formData[field.id]?.trim()) {
        errors[field.id] = `${field.label} è obbligatorio`;
      }
    });
    
    setValidationErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!config || !validateForm()) {
      return;
    }

    setIsSubmitting(true);
    setError(null);
    setSubmitted(null);
    setQuestions(null);

    try {
      // Costruisce il payload secondo lo schema SubmissionRequest
      const payload: SubmissionRequest = {
        llm_model: formData.llm_model || '',
        plot: formData.plot || '',
      };

      // Aggiunge solo i campi opzionali che sono stati compilati
      const optionalFields = [
        'genre', 'subgenre', 'theme', 'protagonist', 'character_arc',
        'point_of_view', 'narrative_voice', 'style', 'temporal_structure',
        'pace', 'realism', 'ambiguity', 'intentionality', 'author', 'user_name'
      ];

      optionalFields.forEach(fieldId => {
        if (formData[fieldId]?.trim()) {
          (payload as any)[fieldId] = formData[fieldId].trim();
        }
      });
      
      // Aggiungi sempre user_name anche se vuoto, per mostrarlo nel riepilogo
      if (formData.user_name !== undefined) {
        (payload as any).user_name = formData.user_name || '';
      }

      // Valida il form
      const response = await submitForm(payload);
      setFormPayload(payload);

      // Genera le domande
      setIsGeneratingQuestions(true);
      try {
        const questionsResponse = await generateQuestions(payload);
        setQuestions(questionsResponse.questions);
        setSessionId(questionsResponse.session_id);
        setIsGeneratingQuestions(false);
        setCurrentStep('questions'); // Passa allo step delle domande
      } catch (err) {
        setIsGeneratingQuestions(false);
        setError(err instanceof Error ? err.message : 'Errore nella generazione delle domande');
        throw err; // Rilancia per evitare di procedere
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Errore nell\'invio del form');
      setIsGeneratingQuestions(false);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleQuestionsComplete = (answers: QuestionAnswer[]) => {
    setQuestionAnswers(answers); // Salva le risposte
    setAnswersSubmitted(true);
    // Passa allo step della bozza
    setCurrentStep('draft');
  };

  const handleDraftValidated = async (draft: any, outlineData: any) => {
    // Salva la bozza validata e l'outline
    setValidatedDraft({
      title: draft.title,
      text: draft.draft_text,
    });
    
    // Log per debug
    console.log('[DEBUG DynamicForm] Draft validato:', draft);
    console.log('[DEBUG DynamicForm] Outline data ricevuta:', outlineData);
    console.log('[DEBUG DynamicForm] SessionId:', sessionId);
    
    if (outlineData && outlineData.outline_text) {
      setOutline(outlineData.outline_text);
      console.log('[DEBUG DynamicForm] Outline salvato nello state, length:', outlineData.outline_text.length);
    } else {
      console.warn('[DEBUG DynamicForm] Nessun outline ricevuto, provo a recuperarlo...');
      // Prova a recuperare l'outline se non è stato passato
      if (sessionId) {
        try {
          const { getOutline } = await import('../api/client');
          const retrievedOutline = await getOutline(sessionId);
          if (retrievedOutline && retrievedOutline.outline_text) {
            setOutline(retrievedOutline.outline_text);
            console.log('[DEBUG DynamicForm] Outline recuperato con successo');
          } else {
            setOutline(null);
          }
        } catch (err) {
          console.error('[DEBUG DynamicForm] Errore nel recupero outline:', err);
          setOutline(null);
        }
      } else {
        setOutline(null);
      }
    }
    
    // Dopo la validazione della bozza, mostra il riepilogo finale
    setSubmitted({
      success: true,
      message: 'Configurazione completata! Bozza validata. Pronto per la fase di scrittura.',
      data: formPayload || undefined,
    });
    setCurrentStep('summary');
  };

  const handleBackToForm = () => {
    setQuestions(null);
    setSessionId(null);
    setAnswersSubmitted(false);
    setSubmitted(null);
  };

  const renderInfoIcon = (description?: string) => {
    if (!description) return null;
    
    return (
      <span className="info-icon" title={description}>
        ℹ️
      </span>
    );
  };

  const renderField = (field: FieldConfig) => {
    const fieldError = validationErrors[field.id];
    const fieldValue = formData[field.id] || '';

    if (field.type === 'select') {
      return (
        <div key={field.id} className="form-field">
          <label htmlFor={field.id}>
            {field.label}
            {field.required && <span className="required"> *</span>}
            {renderInfoIcon(field.description)}
          </label>
          <select
            id={field.id}
            value={fieldValue}
            onChange={(e) => handleChange(field.id, e.target.value)}
            className={fieldError ? 'error' : ''}
          >
            <option value="">-- Seleziona --</option>
            {field.options?.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label || opt.value}
              </option>
            ))}
          </select>
          {fieldError && <span className="error-message">{fieldError}</span>}
        </div>
      );
    }

    if (field.type === 'text') {
      // Usa input normale per campi che non sono "plot", textarea solo per "plot"
      const isMultiline = field.id === 'plot';
      
      return (
        <div key={field.id} className="form-field">
          <label htmlFor={field.id}>
            {field.label}
            {field.required && <span className="required"> *</span>}
            {renderInfoIcon(field.description)}
          </label>
          {isMultiline ? (
            <textarea
              id={field.id}
              value={fieldValue}
              onChange={(e) => handleChange(field.id, e.target.value)}
              placeholder={field.placeholder}
              rows={6}
              className={fieldError ? 'error' : ''}
            />
          ) : (
            <input
              type="text"
              id={field.id}
              value={fieldValue}
              onChange={(e) => handleChange(field.id, e.target.value)}
              placeholder={field.placeholder}
              className={fieldError ? 'error' : ''}
            />
          )}
          {fieldError && <span className="error-message">{fieldError}</span>}
        </div>
      );
    }

    return null;
  };

  if (loading) {
    return <div className="loading">Caricamento configurazione...</div>;
  }

  if (error && !config) {
    return (
      <div className="error-container">
        <p>Errore: {error}</p>
        <button onClick={loadConfig}>Riprova</button>
      </div>
    );
  }

  // Mostra le domande se generate
  if (currentStep === 'questions' && questions && sessionId) {
    return (
      <QuestionsStep
        questions={questions}
        sessionId={sessionId}
        onComplete={handleQuestionsComplete}
        onBack={handleBackToForm}
      />
    );
  }

  // Mostra lo step della bozza
  if (currentStep === 'draft' && sessionId && formPayload) {
    return (
      <DraftStep
        sessionId={sessionId}
        formData={formPayload}
        questionAnswers={questionAnswers}
        onDraftValidated={handleDraftValidated}
        onBack={() => setCurrentStep('questions')}
      />
    );
  }

  // Mostra riepilogo finale dopo la validazione della bozza
  if (currentStep === 'summary' && submitted && answersSubmitted) {
    // Crea una mappa per i label dei campi
    const fieldLabelMap: Record<string, string> = {};
    if (config) {
      config.fields.forEach(field => {
        fieldLabelMap[field.id] = field.label;
      });
    }

    // Helper per ottenere il label di un campo
    const getFieldLabel = (fieldId: string): string => {
      return fieldLabelMap[fieldId] || fieldId;
    };

    // Helper per formattare il valore
    const formatValue = (value: any): string => {
      if (value === null || value === undefined || value === '') {
        return '—';
      }
      return String(value);
    };

    return (
      <div className="submission-success">
        <h2>Configurazione completata con successo!</h2>
        <p>{submitted.message}</p>
        
        {error && <div className="error-banner">{error}</div>}
        
        <div className="submission-summary">
          <h3>Riepilogo configurazione:</h3>
          
          {submitted.data && (
            <div className="summary-section">
              <h4>Dati del form iniziale:</h4>
              <dl className="summary-list">
                {/* Mostra sempre Nome Autore per primo, anche se vuoto o mancante */}
                <div className="summary-item">
                  <dt>Nome Autore:</dt>
                  <dd>{formatValue(submitted.data.user_name || formData.user_name || '—')}</dd>
                </div>
                
                {/* Poi mostra gli altri campi, escludendo user_name già mostrato */}
                {Object.entries(submitted.data)
                  .filter(([key]) => key !== 'user_name') // Escludi user_name già mostrato
                  .map(([key, value]) => {
                    // Per gli altri campi, salta se vuoti
                    if (value === null || value === undefined || value === '') {
                      return null;
                    }
                    return (
                      <div key={key} className="summary-item">
                        <dt>{getFieldLabel(key)}:</dt>
                        <dd>{formatValue(value)}</dd>
                      </div>
                    );
                  })}
              </dl>
            </div>
          )}

          {questionAnswers.length > 0 && (
            <div className="summary-section">
              <h4>Risposte alle domande preliminari:</h4>
              <dl className="summary-list">
                {questionAnswers.map((qa, index) => {
                  if (!qa.answer) return null;
                  // Cerca la domanda corrispondente per ottenere il testo
                  const question = questions?.find(q => q.id === qa.question_id);
                  const questionText = question?.text || qa.question_id;
                  return (
                    <div key={index} className="summary-item">
                      <dt>{questionText}:</dt>
                      <dd>{qa.answer}</dd>
                    </div>
                  );
                })}
              </dl>
            </div>
          )}

          {validatedDraft && (
            <div className="summary-section">
              <h4>Bozza Estesa della Trama:</h4>
              {validatedDraft.title && (
                <h5 className="draft-title-summary">{validatedDraft.title}</h5>
              )}
              <div className="draft-markdown-container">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {validatedDraft.text}
                </ReactMarkdown>
              </div>
            </div>
          )}

          <div className="summary-section">
            <h4>Struttura del Romanzo:</h4>
            {outline ? (
              <div className="draft-markdown-container">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {outline}
                </ReactMarkdown>
              </div>
            ) : (
              <p style={{ color: '#666', fontStyle: 'italic', padding: '1rem' }}>
                La struttura non è ancora disponibile. Se hai appena validato la bozza, potrebbe essere in generazione.
              </p>
            )}
          </div>
        </div>
        <div className="summary-actions">
          {sessionId && (
            <button 
              onClick={async () => {
                try {
                  console.log('Tentativo di download PDF per sessione:', sessionId);
                  const blob = await downloadPdf(sessionId);
                  console.log('PDF ricevuto, dimensione:', blob.size, 'bytes');
                  
                  if (blob.size === 0) {
                    throw new Error('Il PDF ricevuto è vuoto');
                  }
                  
                  const url = window.URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  a.download = validatedDraft?.title 
                    ? `${validatedDraft.title.replace(/[^a-z0-9]/gi, '_')}.pdf`
                    : `Romanzo_${sessionId.substring(0, 8)}.pdf`;
                  document.body.appendChild(a);
                  a.click();
                  
                  // Cleanup dopo un breve delay
                  setTimeout(() => {
                    window.URL.revokeObjectURL(url);
                    document.body.removeChild(a);
                  }, 100);
                } catch (err) {
                  console.error('Errore nel download del PDF:', err);
                  const errorMessage = err instanceof Error ? err.message : 'Errore sconosciuto nel download del PDF';
                  alert(`Errore: ${errorMessage}\n\nVerifica che:\n- La sessione sia ancora valida\n- Il backend sia in esecuzione\n- La bozza sia stata validata`);
                }
              }}
              className="download-pdf-button"
            >
              📥 Scarica PDF
            </button>
          )}
          <button 
            onClick={async () => {
              console.log('[DEBUG] Cliccato Inizia Scrittura Romanzo');
              console.log('[DEBUG] sessionId:', sessionId);
              console.log('[DEBUG] outline:', outline ? 'presente' : 'assente');
              
              if (!sessionId) {
                alert('Errore: SessionId non disponibile.');
                return;
              }
              
              if (!outline) {
                alert('Errore: La struttura del romanzo non è ancora disponibile.');
                return;
              }
              
              try {
                setError(null);
                setIsStartingWriting(true);
                console.log('[DEBUG] Chiamata startBookGeneration...');
                const response = await startBookGeneration({ session_id: sessionId });
                console.log('[DEBUG] Risposta:', response);
                setCurrentStep('writing');
              } catch (err) {
                console.error('[DEBUG] Errore:', err);
                setError(err instanceof Error ? err.message : 'Errore nell\'avvio della scrittura del libro');
              } finally {
                setIsStartingWriting(false);
              }
            }}
            className="start-writing-button"
            disabled={!sessionId || !outline || isStartingWriting}
          >
            {isStartingWriting ? '⏳ Avvio in corso...' : '✍️ Inizia Scrittura Romanzo'}
          </button>
          <button onClick={() => {
            setSubmitted(null);
            setFormData({});
            setValidationErrors({});
            setQuestions(null);
            setSessionId(null);
            setAnswersSubmitted(false);
            setFormPayload(null);
            setQuestionAnswers([]);
            setValidatedDraft(null);
            setOutline(null);
            setCurrentStep('form');
          }}>
            Nuova configurazione
          </button>
        </div>
      </div>
    );
  }

  // Mostra lo step di scrittura
  if (currentStep === 'writing' && sessionId) {
    return (
      <WritingStep
        sessionId={sessionId}
        onComplete={(progress) => {
          console.log('[DEBUG] Scrittura completata:', progress);
          // Opzionale: puoi navigare a una pagina di visualizzazione del libro completo
        }}
      />
    );
  }

  // Mostra loading durante generazione domande
  if (isGeneratingQuestions) {
    return (
      <div className="loading">
        <p>Generazione domande preliminari in corso...</p>
        <p style={{ fontSize: '0.9rem', color: '#666', marginTop: '0.5rem' }}>
          Questo potrebbe richiedere alcuni secondi
        </p>
      </div>
    );
  }

  return (
    <div className="dynamic-form-container">
      <h1>Agente di Scrittura Romanzi</h1>
      <p className="subtitle">Compila il form per configurare il tuo romanzo</p>
      
      {error && <div className="error-banner">{error}</div>}
      
      <form onSubmit={handleSubmit} className="dynamic-form">
        {config?.fields.map(renderField)}
        
        <div className="form-actions">
          <button type="submit" disabled={isSubmitting} className="submit-button">
            {isSubmitting ? 'Invio in corso...' : 'Invia'}
          </button>
        </div>
      </form>
    </div>
  );
}


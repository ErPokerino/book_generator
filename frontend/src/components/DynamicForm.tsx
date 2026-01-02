import { useState, useEffect, Suspense, lazy } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { fetchConfig, submitForm, generateQuestions, downloadPdf, getOutline, startBookGeneration, restoreSession, FieldConfig, SubmissionRequest, SubmissionResponse, Question, QuestionAnswer, SessionRestoreResponse } from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import QuestionsStep from './QuestionsStep';
import DraftStep from './DraftStep';
import WritingStep from './WritingStep';
import ErrorBoundary from './ErrorBoundary';
import StepIndicator from './StepIndicator';
import AlertModal from './AlertModal';
import './DynamicForm.css';

// Lazy load OutlineEditor per isolare potenziali problemi con @dnd-kit
const OutlineEditor = lazy(() => import('./OutlineEditor'));

const SESSION_STORAGE_KEY = 'current_book_session_id';

export default function DynamicForm() {
  const { user } = useAuth();
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
  const [validatedDraft, setValidatedDraft] = useState<{ title?: string; text: string; version?: number } | null>(null);
  const [outline, setOutline] = useState<string | null>(null);
  const [isStartingWriting, setIsStartingWriting] = useState(false);
  const [isEditingOutline, setIsEditingOutline] = useState(false);
  const [isGeneratingOutline, setIsGeneratingOutline] = useState(false);
  const [alertModal, setAlertModal] = useState<{ isOpen: boolean; title: string; message: string; variant?: 'error' | 'warning' | 'info' | 'success' }>({
    isOpen: false,
    title: '',
    message: '',
    variant: 'error',
  });

  useEffect(() => {
    loadConfig();
  }, []);

  // Hook per ripristinare lo stato della sessione al mount
  useEffect(() => {
    const restoreSessionState = async () => {
      const savedSessionId = localStorage.getItem(SESSION_STORAGE_KEY);
      if (!savedSessionId) {
        return; // Nessuna sessione salvata
      }

      try {
        console.log('[DynamicForm] Tentativo di ripristinare sessione:', savedSessionId);
        const restoreData = await restoreSession(savedSessionId);
        
        // Ripristina gli stati
        setSessionId(restoreData.session_id);
        setFormPayload(restoreData.form_data);
        
        // Ricostruisci formData da form_data
        const formDataObj: Record<string, string> = {};
        const formDataKeys: (keyof SubmissionRequest)[] = [
          'llm_model', 'plot', 'genre', 'subgenre', 'target_audience', 'theme',
          'protagonist', 'protagonist_archetype', 'character_arc', 'point_of_view',
          'narrative_voice', 'style', 'temporal_structure', 'pace', 'realism',
          'ambiguity', 'intentionality', 'author', 'user_name', 'cover_style'
        ];
        formDataKeys.forEach(key => {
          const value = restoreData.form_data[key];
          if (value !== undefined && value !== null) {
            formDataObj[key] = String(value);
          }
        });
        setFormData(formDataObj);
        
        // Ripristina questions se presenti
        if (restoreData.questions) {
          setQuestions(restoreData.questions);
        }
        
        // Ripristina question_answers se presenti
        if (restoreData.question_answers && restoreData.question_answers.length > 0) {
          setQuestionAnswers(restoreData.question_answers);
          setAnswersSubmitted(true);
        }
        
        // Ripristina draft se presente
        if (restoreData.draft) {
          setValidatedDraft({
            title: restoreData.draft.title,
            text: restoreData.draft.draft_text,
            version: restoreData.draft.version,
          });
        }
        
        // Ripristina outline se presente
        if (restoreData.outline) {
          setOutline(restoreData.outline);
        }
        
        // Se siamo in summary, imposta submitted PRIMA di cambiare step
        // Questo previene la rigenerazione dell'outline
        if (restoreData.current_step === 'summary') {
          setSubmitted({
            success: true,
            message: 'Struttura del libro generata! Rivedi e modifica la struttura prima di procedere con la scrittura.',
            data: restoreData.form_data,
          });
          // Assicurati che validatedDraft sia impostato se c'è il draft
          if (restoreData.draft && !restoreData.outline) {
            // Se siamo in summary ma non c'è outline, potrebbe essere ancora in generazione
            // Ma se c'è outline, siamo sicuramente in summary
            console.log('[DynamicForm] Ripristino in summary: outline presente, draft presente');
          }
        }
        
        // Ripristina lo step corrente DOPO aver impostato tutti gli stati
        setCurrentStep(restoreData.current_step);
        
        console.log('[DynamicForm] Sessione ripristinata con successo, step:', restoreData.current_step);
      } catch (err) {
        console.error('[DynamicForm] Errore nel ripristino sessione:', err);
        // Se la sessione non esiste o c'è un errore, rimuovi da localStorage
        localStorage.removeItem(SESSION_STORAGE_KEY);
        // Mostra form vuoto
      }
    };

    restoreSessionState();
  }, []); // Esegui solo al mount

  // Se siamo nel summary e non abbiamo l'outline, prova a recuperarlo.
  // Deve stare qui (top-level) per rispettare le Rules of Hooks (niente hook dentro if/return).
  useEffect(() => {
    if (currentStep !== 'summary') return;
    if (!sessionId) return;
    if (outline) return;

    console.log('[DEBUG DynamicForm] useEffect summary: tentativo recupero outline');
    console.log('[DEBUG DynamicForm] sessionId:', sessionId);
    console.log('[DEBUG DynamicForm] outline attuale:', outline);

    const fetchOutline = async () => {
      try {
        console.log('[DEBUG DynamicForm] Chiamata getOutline...');
        const retrievedOutline = await getOutline(sessionId);
        console.log('[DEBUG DynamicForm] Outline recuperato:', {
          success: retrievedOutline?.success,
          hasText: !!retrievedOutline?.outline_text,
          textLength: retrievedOutline?.outline_text?.length || 0,
        });
        
        if (retrievedOutline?.outline_text) {
          console.log('[DEBUG DynamicForm] Outline recuperato nel summary, length:', retrievedOutline.outline_text.length);
          setOutline(retrievedOutline.outline_text);
        } else {
          console.warn('[DEBUG DynamicForm] Outline recuperato ma senza outline_text');
        }
      } catch (err) {
        console.error('[DEBUG DynamicForm] Errore nel recupero outline:', err);
        if (err instanceof Error) {
          console.error('[DEBUG DynamicForm] Messaggio errore:', err.message);
          console.error('[DEBUG DynamicForm] Stack errore:', err.stack);
        }
      }
    };

    fetchOutline();
  }, [currentStep, sessionId, outline]);

  const loadConfig = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Timeout di 30 secondi per la chiamata API
      const timeoutPromise = new Promise<never>((_, reject) => 
        setTimeout(() => reject(new Error('Timeout: impossibile caricare la configurazione. Verifica che il backend sia in esecuzione.')), 30000)
      );
      
      const data = await Promise.race([
        fetchConfig(),
        timeoutPromise,
      ]);
      
      setConfig(data);
      
      // Inizializza formData con valori vuoti
      const initialData: Record<string, string> = {};
      data.fields.forEach(field => {
        initialData[field.id] = '';
      });
      
      // Imposta default per llm_model se esiste
      const llmModelField = data.fields.find(f => f.id === 'llm_model');
      if (llmModelField && llmModelField.type === 'select') {
        initialData['llm_model'] = 'gemini-3-flash';
      }
      
      // Imposta default per user_name con il nome dell'utente loggato se disponibile
      if (user?.name) {
        initialData['user_name'] = user.name;
      }
      
      setFormData(initialData);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Errore nel caricamento della configurazione';
      setError(errorMessage);
      console.error('Errore nel caricamento config:', err);
    } finally {
      // Sempre disabilita il loading, anche in caso di errore
      setLoading(false);
    }
  };

  const handleResetToForm = () => {
    // Reset di tutti gli stati per tornare al form iniziale
    setFormData({});
    setValidationErrors({});
    setSubmitted(null);
    setIsSubmitting(false);
    setQuestions(null);
    setSessionId(null);
    setFormPayload(null);
    setIsGeneratingQuestions(false);
    setAnswersSubmitted(false);
    setQuestionAnswers([]);
    setCurrentStep('form');
    setValidatedDraft(null);
    setOutline(null);
    setIsStartingWriting(false);
    setError(null);
    
    // Rimuovi sessionId da localStorage
    localStorage.removeItem(SESSION_STORAGE_KEY);
    
    // Reinizializza formData con valori vuoti se config è disponibile
    if (config) {
      const initialData: Record<string, string> = {};
      config.fields.forEach(field => {
        initialData[field.id] = '';
      });
      setFormData(initialData);
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
      console.log('[DynamicForm] Validazione form fallita');
      return;
    }

    console.log('[DynamicForm] Inizio submit form');
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

      console.log('[DynamicForm] Payload iniziale:', { llm_model: payload.llm_model });

      // Aggiunge solo i campi opzionali che sono stati compilati
      const optionalFields = [
        'genre', 'subgenre', 'theme', 'protagonist', 'character_arc',
        'point_of_view', 'narrative_voice', 'style', 'temporal_structure',
        'pace', 'realism', 'ambiguity', 'intentionality', 'author', 'user_name', 'cover_style'
      ];

      optionalFields.forEach(fieldId => {
        if (formData[fieldId]?.trim()) {
          (payload as any)[fieldId] = formData[fieldId].trim();
        }
      });
      
      // Aggiungi sempre user_name anche se vuoto, per mostrarlo nella struttura
      if (formData.user_name !== undefined) {
        (payload as any).user_name = formData.user_name || '';
      }

      console.log('[DynamicForm] Invio submitForm con payload:', payload);

      // Valida il form con timeout
      const submitPromise = submitForm(payload);
      const timeoutPromise = new Promise((_, reject) => 
        setTimeout(() => reject(new Error('Timeout: la richiesta ha impiegato troppo tempo')), 30000)
      );
      
      const response = await Promise.race([submitPromise, timeoutPromise]) as SubmissionResponse;
      console.log('[DynamicForm] submitForm completato:', response);
      setFormPayload(payload);

      // Genera le domande
      setIsGeneratingQuestions(true);
      try {
        console.log('[DynamicForm] Inizio generazione domande');
        const questionsPromise = generateQuestions(payload);
        const questionsTimeoutPromise = new Promise((_, reject) => 
          setTimeout(() => reject(new Error('Timeout: la generazione delle domande ha impiegato troppo tempo')), 60000)
        );
        
        const questionsResponse = await Promise.race([questionsPromise, questionsTimeoutPromise]) as QuestionsResponse;
        console.log('[DynamicForm] Domande generate:', questionsResponse);
        setQuestions(questionsResponse.questions);
        setSessionId(questionsResponse.session_id);
        // Salva sessionId in localStorage per permettere il ripristino
        localStorage.setItem(SESSION_STORAGE_KEY, questionsResponse.session_id);
        setIsGeneratingQuestions(false);
        setCurrentStep('questions'); // Passa allo step delle domande
      } catch (err) {
        console.error('[DynamicForm] Errore nella generazione delle domande:', err);
        setIsGeneratingQuestions(false);
        const errorMessage = err instanceof Error ? err.message : 'Errore nella generazione delle domande';
        setError(errorMessage);
        // Non rilanciare l'errore qui, così l'utente vede il messaggio
      }
    } catch (err) {
      console.error('[DynamicForm] Errore nell\'invio del form:', err);
      const errorMessage = err instanceof Error ? err.message : 'Errore nell\'invio del form';
      setError(errorMessage);
      setIsGeneratingQuestions(false);
    } finally {
      console.log('[DynamicForm] Submit completato, reset isSubmitting');
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
      version: draft.version,
    });
    
    // Reset isGeneratingOutline quando l'outline è completato
    setIsGeneratingOutline(false);
    
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
    
    // Dopo la validazione della bozza, mostra la struttura
    setSubmitted({
      success: true,
      message: 'Struttura del libro generata! Rivedi e modifica la struttura prima di procedere con la scrittura.',
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
            {field.id !== 'llm_model' && <option value="">-- Seleziona --</option>}
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

  // Mostra loading durante generazione outline (prima delle domande per priorità)
  if (isGeneratingOutline) {
    return (
      <div className="dynamic-form-layout">
        <div className="step-indicator-wrapper">
          <StepIndicator currentStep="summary" />
        </div>
        <div className="dynamic-form-main-content">
          <div className="loading">
            <h2>Generazione Struttura del Libro</h2>
            <p>Sto generando la struttura del libro...</p>
            <p style={{ fontSize: '0.9rem', color: '#666', marginTop: '0.5rem' }}>
              Questo potrebbe richiedere alcuni secondi
            </p>
          </div>
        </div>
      </div>
    );
  }

  // Mostra le domande se generate
  if (currentStep === 'questions' && questions && sessionId) {
    return (
      <div className="dynamic-form-layout">
        <div className="step-indicator-wrapper">
          <StepIndicator currentStep={currentStep} />
        </div>
        <div className="dynamic-form-main-content">
          <QuestionsStep
            questions={questions}
            sessionId={sessionId}
            onComplete={handleQuestionsComplete}
            onBack={handleBackToForm}
          />
        </div>
      </div>
    );
  }

  // Mostra lo step della bozza
  if (currentStep === 'draft' && sessionId && formPayload) {
    return (
      <div className="dynamic-form-layout">
        <div className="step-indicator-wrapper">
          <StepIndicator currentStep={currentStep} />
        </div>
        <div className="dynamic-form-main-content">
          <DraftStep
            sessionId={sessionId}
            formData={formPayload}
            questionAnswers={questionAnswers}
            onDraftValidated={handleDraftValidated}
            onBack={() => setCurrentStep('questions')}
            onOutlineGenerationStart={() => {
              setCurrentStep('summary');
              setIsGeneratingOutline(true);
            }}
            initialDraft={validatedDraft ? {
              success: true,
              session_id: sessionId || '',
              draft_text: validatedDraft.text,
              title: validatedDraft.title,
              version: validatedDraft.version || 1,
            } : null}
          />
        </div>
      </div>
    );
  }

  // Mostra struttura dopo la validazione della bozza
  if (currentStep === 'summary' && submitted && answersSubmitted) {
    // Logging dettagliato per diagnostica
    console.log('[DEBUG DynamicForm] Rendering summary step');
    console.log('[DEBUG DynamicForm] States:', {
      currentStep,
      hasSubmitted: !!submitted,
      hasAnswersSubmitted: answersSubmitted,
      hasValidatedDraft: !!validatedDraft,
      validatedDraftTitle: validatedDraft?.title,
      validatedDraftTextLength: validatedDraft?.text?.length || 0,
      hasOutline: !!outline,
      outlineLength: outline?.length || 0,
      outlineType: typeof outline,
      hasSessionId: !!sessionId,
      isEditingOutline,
    });

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
      <div className="dynamic-form-layout">
        <div className="step-indicator-wrapper">
          <StepIndicator currentStep={currentStep} />
        </div>
        <div className="dynamic-form-main-content">
          <div className="submission-success">
            <h2>Struttura del libro pronta!</h2>
            <p>{submitted.message}</p>
            
            {error && <div className="error-banner">{error}</div>}
            
            <div className="submission-summary">
          <div className="summary-section">
            <div className="summary-section-header">
              <h4>Struttura del Romanzo:</h4>
              {outline && !isEditingOutline && (
                <button
                  type="button"
                  onClick={() => setIsEditingOutline(true)}
                  className="btn-edit-outline"
                >
                  ✏️ Modifica struttura
                </button>
              )}
            </div>
            <ErrorBoundary>
              {outline ? (
                (typeof outline === 'string' && outline.trim()) ? (
                  isEditingOutline ? (
                    <Suspense fallback={
                      <div style={{ padding: '2rem', textAlign: 'center' }}>
                        <p>Caricamento editor struttura...</p>
                      </div>
                    }>
                      <OutlineEditor
                        sessionId={sessionId!}
                        outlineText={outline}
                        onOutlineUpdated={(updatedOutline) => {
                          console.log('[DEBUG DynamicForm] Outline aggiornato dall\'editor');
                          setOutline(updatedOutline);
                          setIsEditingOutline(false);
                        }}
                        onCancel={() => {
                          console.log('[DEBUG DynamicForm] Modifica outline annullata');
                          setIsEditingOutline(false);
                        }}
                      />
                    </Suspense>
                  ) : (
                    <div className="draft-markdown-container">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {outline}
                      </ReactMarkdown>
                    </div>
                  )
                ) : (
                  <p style={{ color: '#dc2626', fontStyle: 'italic', padding: '1rem' }}>
                    Errore: la struttura non è in un formato valido (tipo: {typeof outline}, valore: {String(outline).substring(0, 50)}...).
                  </p>
                )
              ) : (
                <p style={{ color: '#666', fontStyle: 'italic', padding: '1rem' }}>
                  La struttura non è ancora disponibile. Se hai appena validato la bozza, potrebbe essere in generazione.
                </p>
              )}
            </ErrorBoundary>
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
                  setAlertModal({
                    isOpen: true,
                    title: 'Errore',
                    message: `Errore: ${errorMessage}\n\nVerifica che:\n- La sessione sia ancora valida\n- Il backend sia in esecuzione\n- La bozza sia stata validata`,
                    variant: 'error',
                  });
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
                setAlertModal({
                  isOpen: true,
                  title: 'Errore',
                  message: 'Errore: SessionId non disponibile.',
                  variant: 'error',
                });
                return;
              }
              
              if (!outline) {
                setAlertModal({
                  isOpen: true,
                  title: 'Errore',
                  message: 'Errore: La struttura del romanzo non è ancora disponibile.',
                  variant: 'error',
                });
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
            // Rimuovi sessionId da localStorage
            localStorage.removeItem(SESSION_STORAGE_KEY);
          }}>
            Nuova configurazione
          </button>
        </div>
      </div>
        </div>
      </div>
    );
  }

  // Mostra lo step di scrittura
  if (currentStep === 'writing' && sessionId) {
    return (
      <div className="dynamic-form-layout">
        <div className="step-indicator-wrapper">
          <StepIndicator currentStep={currentStep} />
        </div>
        <div className="dynamic-form-main-content">
          <WritingStep
            sessionId={sessionId}
            onComplete={(progress) => {
              console.log('[DEBUG] Scrittura completata:', progress);
              // Rimuovi sessionId da localStorage quando il libro è completato
              localStorage.removeItem(SESSION_STORAGE_KEY);
              // Opzionale: puoi navigare a una pagina di visualizzazione del libro completo
            }}
            onNewBook={handleResetToForm}
          />
        </div>
      </div>
    );
  }

  // Mostra loading durante generazione domande
  if (isGeneratingQuestions) {
    return (
      <div className="dynamic-form-layout">
        <div className="step-indicator-wrapper">
          <StepIndicator currentStep="questions" />
        </div>
        <div className="dynamic-form-main-content">
          <div className="loading">
            <p>Generazione domande preliminari in corso...</p>
            <p style={{ fontSize: '0.9rem', color: '#666', marginTop: '0.5rem' }}>
              Questo potrebbe richiedere alcuni secondi
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="dynamic-form-layout">
      <div className="step-indicator-wrapper">
        <StepIndicator currentStep={currentStep} />
      </div>
      <div className="dynamic-form-main-content">
        <div className="dynamic-form-container">
          <h1>NarrAI</h1>
          <p className="subtitle">La tua storia, generata dall'AI</p>
          
          {error && <div className="error-banner">{error}</div>}
          
          {!config && !loading && !error && (
            <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
              <p>Caricamento configurazione in corso...</p>
            </div>
          )}
          
          {config && config.fields && config.fields.length > 0 ? (
            <form onSubmit={handleSubmit} className="dynamic-form">
              {config.fields.map((field) => renderField(field))}
              
              <div className="form-actions">
                <button type="submit" disabled={isSubmitting} className="submit-button">
                  {isSubmitting ? 'Invio in corso...' : 'Invia'}
                </button>
              </div>
            </form>
          ) : config && (!config.fields || config.fields.length === 0) ? (
            <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
              <p>Nessun campo disponibile nella configurazione.</p>
            </div>
          ) : null}
        </div>
      </div>

      <AlertModal
        isOpen={alertModal.isOpen}
        title={alertModal.title}
        message={alertModal.message}
        variant={alertModal.variant}
        onClose={() => setAlertModal({ isOpen: false, title: '', message: '' })}
      />
    </div>
  );
}


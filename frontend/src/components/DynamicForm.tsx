import { useState, useEffect, Suspense, lazy } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { fetchConfig, submitForm, generateQuestions, downloadPdf, getOutline, startBookGeneration, restoreSession, FieldConfig, SubmissionRequest, SubmissionResponse, Question, QuestionAnswer } from '../api/client';
import { useToast } from '../hooks/useToast';
import QuestionsStep from './QuestionsStep';
import DraftStep from './DraftStep';
import WritingStep from './WritingStep';
import ErrorBoundary from './ErrorBoundary';
import StepIndicator from './StepIndicator';
import PlotTextarea from './PlotTextarea';
import PageTransition from './ui/PageTransition';
import CreationJourneyPanel, { GenerationMode } from './CreationJourneyPanel';
import ModelSettingsPanel, {
  BOOK_STAGES,
  DEFAULT_TEXT_MODEL,
  ModelSettingsValue,
  buildModelOverrides,
} from './ModelSettingsPanel';
import './DynamicForm.css';

// Lazy load OutlineEditor per isolare potenziali problemi con @dnd-kit
const OutlineEditor = lazy(() => import('./OutlineEditor'));

const SESSION_STORAGE_KEY = 'current_book_session_id';
const FORM_DATA_STORAGE_KEY = 'dynamicForm.formData';
const MODEL_SETTINGS_STORAGE_KEY = 'dynamicForm.modelSettings';
const DEFAULT_AUTHOR = 'Autore';

function defaultBookModelSettings(): ModelSettingsValue {
  return {
    generationMode: 'standard',
    stageModels: Object.fromEntries(BOOK_STAGES.map((stage) => [stage.id, stage.defaultModel])),
  };
}

function hydrateBookModelSettings(raw?: Record<string, unknown> | null): ModelSettingsValue {
  const defaults = defaultBookModelSettings();
  if (!raw) return defaults;
  const incomingStages = raw.stageModels && typeof raw.stageModels === 'object'
    ? (raw.stageModels as Record<string, string>)
    : {};
  const stageModels = { ...defaults.stageModels, ...incomingStages };
  if (typeof raw.textModel === 'string') {
    for (const stage of BOOK_STAGES.filter((item) => item.purpose === 'text')) {
      if (!incomingStages[stage.id]) stageModels[stage.id] = raw.textModel;
    }
  }
  if (typeof raw.imageModel === 'string') {
    for (const stage of BOOK_STAGES.filter((item) => item.purpose === 'image')) {
      if (!incomingStages[stage.id]) stageModels[stage.id] = raw.imageModel;
    }
  }
  return {
    generationMode: raw.generationMode === 'ultra' ? 'ultra' : 'standard',
    stageModels,
  };
}

function modelSettingsFromRequest(data?: SubmissionRequest | null): ModelSettingsValue {
  const defaults = defaultBookModelSettings();
  if (!data) return defaults;
  const overrides = data.model_overrides || {};
  const stageModels = { ...defaults.stageModels };
  for (const stage of BOOK_STAGES) {
    if (overrides[stage.id]) {
      stageModels[stage.id] = overrides[stage.id];
    } else if (stage.purpose === 'text' && overrides.text) {
      stageModels[stage.id] = overrides.text;
    } else if (stage.purpose === 'image' && (overrides.cover || overrides.image)) {
      stageModels[stage.id] = overrides.cover || overrides.image;
    } else if (stage.id === 'chapters' && data.llm_model?.includes('lite')) {
      stageModels[stage.id] = 'gemini-3.5-flash-lite';
    }
  }
  return {
    generationMode: data.generation_mode === 'ultra' || (data.llm_model || '').includes('ultra') ? 'ultra' : 'standard',
    stageModels,
  };
}

function applyDefaultAuthor(data: Record<string, string>): Record<string, string> {
  if (data.author?.trim()) {
    return data;
  }
  return { ...data, author: DEFAULT_AUTHOR };
}

function getModeFromModel(modelName?: string | null, generationMode?: string | null): GenerationMode {
  if (generationMode === 'ultra' || (modelName || '').toLowerCase().includes('ultra')) return 'ultra';
  return 'standard';
}

export default function DynamicForm() {
  const toast = useToast();
  const [config, setConfig] = useState<{ llm_models: string[]; fields: FieldConfig[] } | null>(null);
  const [loading, setLoading] = useState(true);
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
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [restoreStatus, setRestoreStatus] = useState<'restored' | 'failed' | 'idle'>('idle');
  const [modelSettings, setModelSettings] = useState<ModelSettingsValue>(defaultBookModelSettings);
  const selectedMode = getModeFromModel(
    formData.llm_model || formPayload?.llm_model,
    modelSettings.generationMode || formPayload?.generation_mode,
  );

  useEffect(() => {
    loadConfig();
    
    // Ripristina preferenza showAdvanced da localStorage
    try {
      const saved = localStorage.getItem('dynamicForm.showAdvanced');
      if (saved === 'true') {
        setShowAdvanced(true);
      }
      
      // Ripristina formData da localStorage (solo se non c'è una sessione attiva)
      const savedFormData = localStorage.getItem(FORM_DATA_STORAGE_KEY);
      if (savedFormData) {
        try {
          const parsed = JSON.parse(savedFormData);
          if (parsed && typeof parsed === 'object') {
            setFormData(applyDefaultAuthor(parsed));
          }
        } catch (err) {
          console.warn('[DynamicForm] Errore nel parsing formData salvato:', err);
        }
      }
      const savedModelSettings = localStorage.getItem(MODEL_SETTINGS_STORAGE_KEY);
      if (savedModelSettings) {
        try {
          const parsed = JSON.parse(savedModelSettings);
          if (parsed && typeof parsed === 'object') {
            setModelSettings(hydrateBookModelSettings(parsed));
          }
        } catch (err) {
          console.warn('[DynamicForm] Errore nel parsing modelSettings salvato:', err);
        }
      }
    } catch (err) {
      // Ignora errori localStorage
    }
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
          'ambiguity', 'intentionality', 'author', 'user_name', 'cover_style', 'generation_mode'
        ];
        formDataKeys.forEach(key => {
          const value = restoreData.form_data[key];
          if (value !== undefined && value !== null) {
            formDataObj[key] = String(value);
          }
        });
        const restoredFormData = applyDefaultAuthor(formDataObj);
        setFormData(restoredFormData);
        setModelSettings(modelSettingsFromRequest(restoreData.form_data));
        // Salva anche in localStorage per persistenza
        try {
          localStorage.setItem(FORM_DATA_STORAGE_KEY, JSON.stringify(restoredFormData));
        } catch (err) {
          console.warn('[DynamicForm] Errore nel salvataggio formData dopo restore:', err);
        }
        
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

        if (restoreData.content_type === 'manga' || restoreData.current_step === 'manga') {
          console.warn('[DynamicForm] Sessione manga trovata nel restore del flusso libro, la ignoro');
          localStorage.removeItem(SESSION_STORAGE_KEY);
          setRestoreStatus('failed');
          return;
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
        setRestoreStatus('restored');
        
        console.log('[DynamicForm] Sessione ripristinata con successo, step:', restoreData.current_step);
      } catch (err) {
        console.error('[DynamicForm] Errore nel ripristino sessione:', err);
        // Se la sessione non esiste o c'è un errore, rimuovi da localStorage
        localStorage.removeItem(SESSION_STORAGE_KEY);
        setRestoreStatus('failed');
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
      
      // Timeout di 30 secondi per la chiamata API
      const timeoutPromise = new Promise<never>((_, reject) => 
        setTimeout(() => reject(new Error('Timeout: impossibile caricare la configurazione. Verifica che il backend sia in esecuzione.')), 30000)
      );
      
      const data = await Promise.race([
        fetchConfig(),
        timeoutPromise,
      ]);
      
      setConfig(data);
      
      // Inizializza formData con valori vuoti (solo se non c'è già formData salvato)
      const savedFormData = localStorage.getItem(FORM_DATA_STORAGE_KEY);
      if (!savedFormData) {
        const initialData: Record<string, string> = {};
        data.fields.forEach(field => {
          initialData[field.id] = '';
        });
        
        // Imposta default per llm_model se esiste
        const llmModelField = data.fields.find(f => f.id === 'llm_model');
        if (llmModelField && llmModelField.type === 'select') {
          initialData['llm_model'] = DEFAULT_TEXT_MODEL;
        }

        setFormData(applyDefaultAuthor(initialData));
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Errore nel caricamento della configurazione';
      toast.error(errorMessage);
      console.error('Errore nel caricamento config:', err);
    } finally {
      // Sempre disabilita il loading, anche in caso di errore
      setLoading(false);
    }
  };

  const handleResetToForm = () => {
    // Reset di tutti gli stati per tornare al form iniziale
    setFormData({});
    setModelSettings(defaultBookModelSettings());
    // Rimuovi formData salvato da localStorage
    try {
      localStorage.removeItem(FORM_DATA_STORAGE_KEY);
      localStorage.removeItem(MODEL_SETTINGS_STORAGE_KEY);
    } catch (err) {
      // Ignora errori
    }
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
    setRestoreStatus('idle');
    setValidatedDraft(null);
    setOutline(null);
    setIsStartingWriting(false);
    
    // Rimuovi sessionId da localStorage
    localStorage.removeItem(SESSION_STORAGE_KEY);
    
    // Reinizializza formData con valori vuoti se config è disponibile
    if (config) {
      const initialData: Record<string, string> = {};
      config.fields.forEach(field => {
        initialData[field.id] = '';
      });
      setFormData(applyDefaultAuthor(initialData));
    }
  };

  const handleChange = (fieldId: string, value: string) => {
    setFormData(prev => {
      const updated = { ...prev, [fieldId]: value };
      // Salva in localStorage con debounce
      try {
        localStorage.setItem(FORM_DATA_STORAGE_KEY, JSON.stringify(updated));
      } catch (err) {
        console.warn('[DynamicForm] Errore nel salvataggio formData:', err);
      }
      return updated;
    });
    // Rimuovi errore di validazione quando l'utente modifica il campo
    if (validationErrors[fieldId]) {
      setValidationErrors(prev => {
        const newErrors = { ...prev };
        delete newErrors[fieldId];
        return newErrors;
      });
    }
  };

  useEffect(() => {
    try {
      localStorage.setItem(MODEL_SETTINGS_STORAGE_KEY, JSON.stringify(modelSettings));
    } catch (err) {
      console.warn('[DynamicForm] Errore nel salvataggio modelSettings:', err);
    }
  }, [modelSettings]);

  // Migra alias legacy verso i modelli attuali.
  useEffect(() => {
    if (currentStep !== 'form') return;
    const current = formData.llm_model;
    if (!current) return;
    if (current === DEFAULT_TEXT_MODEL || current === 'gemini-3.5-flash-lite') return;
    setFormData(prev => ({ ...prev, llm_model: DEFAULT_TEXT_MODEL }));
  }, [currentStep, formData.llm_model]);

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
    setSubmitted(null);
    setQuestions(null);

    try {
      // Costruisce il payload secondo lo schema SubmissionRequest
      const payload: SubmissionRequest = {
        llm_model: modelSettings.stageModels.chapters || DEFAULT_TEXT_MODEL,
        generation_mode: modelSettings.generationMode || 'standard',
        model_overrides: buildModelOverrides(modelSettings, BOOK_STAGES),
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

      payload.author = formData.author?.trim() || DEFAULT_AUTHOR;
      
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

      // Genera le domande (sincrono - richiede pochi secondi)
      setIsGeneratingQuestions(true);
      try {
        console.log('[DynamicForm] Avvio generazione domande');
        const questionsResponse = await generateQuestions(payload);
        console.log('[DynamicForm] Generazione domande completata:', questionsResponse);

        setSessionId(questionsResponse.session_id);
        // Salva sessionId in localStorage per permettere il ripristino
        localStorage.setItem(SESSION_STORAGE_KEY, questionsResponse.session_id);

        setQuestions(questionsResponse.questions);
        toast.success('Domande generate con successo!');
        setCurrentStep('questions');
      } catch (err) {
        console.error('[DynamicForm] Errore nella generazione domande:', err);
        const errorMessage = err instanceof Error ? err.message : 'Errore nella generazione delle domande';
        toast.error(errorMessage);
      } finally {
        setIsGeneratingQuestions(false);
      }
    } catch (err) {
      console.error('[DynamicForm] Errore nell\'invio del form:', err);
      const errorMessage = err instanceof Error ? err.message : 'Errore nell\'invio del form';
      toast.error(errorMessage);
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

  const renderInfoIcon = () => {
    // Icone di informazione rimosse su richiesta
    return null;
  };

  // Lista campi Base (ordine desiderato)
  const baseFieldIds = ['plot', 'genre', 'cover_style', 'user_name', 'author'];
  const baseFieldIdsSet = new Set(baseFieldIds);

  // Raggruppa campi in Base e Avanzate
  const getGroupedFields = () => {
    if (!config || !config.fields) {
      return { baseFields: [], advancedFields: [] };
    }

    // Ordina baseFields secondo l'ordine desiderato
    const baseFields: FieldConfig[] = [];
    const fieldMap = new Map(config.fields.map(f => [f.id, f]));
    
    for (const fieldId of baseFieldIds) {
      const field = fieldMap.get(fieldId);
      if (field) {
        baseFields.push(field);
      }
    }
    
    const advancedFields = config.fields.filter(f => !baseFieldIdsSet.has(f.id));
    
    return { baseFields, advancedFields };
  };

  const renderField = (field: FieldConfig) => {
    const fieldError = validationErrors[field.id];
    const fieldValue = formData[field.id] || '';

    if (field.type === 'select') {
      // Stile Copertina: UI a card
      if (field.id === 'cover_style') {
        const coverStyleConfig: Record<string, { name: string; icon: string; description: string }> = {
          'illustrato': {
            name: 'Illustrato',
            icon: '🎨',
            description: 'Disegni artistici e pittorici'
          },
          'fotografico': {
            name: 'Fotografico',
            icon: '📷',
            description: 'Foto reali o rielaborate'
          },
          'tipografico': {
            name: 'Tipografico',
            icon: 'Aa',
            description: 'Focus su testo e composizione'
          },
          'simbolico': {
            name: 'Simbolico',
            icon: '🔷',
            description: 'Immagine metaforica e concettuale'
          },
          'cartoon': {
            name: 'Cartoon',
            icon: '✏️',
            description: 'Illustrazione stilizzata e vivace'
          }
        };

        const labelId = `${field.id}-label`;

        return (
          <div key={field.id} className="form-field">
            <label id={labelId}>
              {field.label}
              {field.required && <span className="required"> *</span>}
              {renderInfoIcon()}
            </label>

            <div
              className={`cover-style-cards ${fieldError ? 'error' : ''}`}
              role="radiogroup"
              aria-labelledby={labelId}
            >
              {field.options?.map((opt) => {
                const value = String(opt.value ?? '');
                const selected = value === fieldValue;
                const styleConfig = coverStyleConfig[value];

                if (!styleConfig) {
                  return null; // Skip unknown styles
                }

                return (
                  <button
                    key={value}
                    type="button"
                    className={`cover-style-card ${selected ? 'selected' : ''}`}
                    onClick={() => {
                      // Se già selezionata, deseleziona; altrimenti seleziona
                      if (selected) {
                        handleChange(field.id, '');
                      } else {
                        handleChange(field.id, value);
                      }
                    }}
                    aria-pressed={selected}
                    title={styleConfig.description}
                  >
                    <span className="cover-style-icon">{styleConfig.icon}</span>
                    <span className="cover-style-name">{styleConfig.name}</span>
                    <span className="cover-style-description">{styleConfig.description}</span>
                  </button>
                );
              })}
            </div>

            {fieldError && <span className="error-message">{fieldError}</span>}
          </div>
        );
      }

      if (field.id === 'llm_model') {
        return null;
      }

      return (
        <div key={field.id} className="form-field">
              <label htmlFor={field.id}>
                {field.label}
                {field.required && <span className="required"> *</span>}
                {renderInfoIcon()}
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
      // Usa PlotTextarea per "plot", input normale per altri campi
      const isPlot = field.id === 'plot';
      
      if (isPlot) {
        return (
          <div key={field.id} className="form-field">
            <PlotTextarea
              value={fieldValue}
              onChange={(value) => handleChange(field.id, value)}
              disabled={false}
              label={
                <>
                  {field.label}
                  {field.required && <span className="required"> *</span>}
                  {renderInfoIcon()}
                </>
              }
              placeholder={field.placeholder}
              minWordsHint={50}
              error={fieldError}
              id={field.id}
            />
          </div>
        );
      }
      
      return (
        <div key={field.id} className="form-field">
          <label htmlFor={field.id}>
            {field.label}
            {field.required && <span className="required"> *</span>}
            {renderInfoIcon()}
          </label>
          <input
            type="text"
            id={field.id}
            value={fieldValue}
            onChange={(e) => handleChange(field.id, e.target.value)}
            placeholder={field.placeholder}
            className={fieldError ? 'error' : ''}
          />
          {fieldError && <span className="error-message">{fieldError}</span>}
        </div>
      );
    }

    return null;
  };


  if (!config && !loading) {
    return (
      <div className="error-container">
        <p>Impossibile caricare la configurazione. Verifica che il backend sia in esecuzione.</p>
        <button onClick={loadConfig}>Riprova</button>
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

    return (
      <div className="dynamic-form-layout">
        <div className="step-indicator-wrapper">
          <StepIndicator currentStep={currentStep} />
        </div>
        <div className="dynamic-form-main-content">
          <div className="submission-success">
            <h2>Struttura del libro pronta!</h2>
            <p>{submitted.message}</p>
            
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
                  toast.error(`Errore nel download del PDF: ${errorMessage}`);
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
                toast.error('Errore: SessionId non disponibile.');
                return;
              }
              
              if (!outline) {
                toast.error('Errore: La struttura del romanzo non è ancora disponibile.');
                return;
              }
              
              try {
                setIsStartingWriting(true);
                console.log('[DEBUG] Chiamata startBookGeneration...');
                const response = await startBookGeneration({ session_id: sessionId });
                console.log('[DEBUG] Risposta:', response);
                setCurrentStep('writing');
                toast.success('Scrittura del libro avviata con successo!');
              } catch (err) {
                console.error('[DEBUG] Errore:', err);
                toast.error(err instanceof Error ? err.message : 'Errore nell\'avvio della scrittura del libro');
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
            // Rimuovi formData salvato da localStorage
            try {
              localStorage.removeItem(FORM_DATA_STORAGE_KEY);
            } catch (err) {
              // Ignora errori
            }
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


  return (
    <PageTransition>
      <div className="dynamic-form-layout">
        <div className="step-indicator-wrapper">
          <StepIndicator currentStep={currentStep} />
        </div>
        <div className="dynamic-form-main-content">
          <div className="dynamic-form-container">
            <h1>NarrAI</h1>
            <p className="subtitle">La tua storia, generata con l'AI</p>
            <CreationJourneyPanel
              currentStep={currentStep}
              selectedMode={selectedMode}
              sessionId={sessionId}
              restoreStatus={restoreStatus}
            />
          
          {loading ? (
            <div className="form-loading-skeleton" role="status" aria-label="Caricamento configurazione">
              <div className="skeleton-line" style={{ width: '60%', height: '1.5rem', marginBottom: '1rem' }} />
              <div className="skeleton-line" style={{ width: '80%', height: '1rem', marginBottom: '2rem' }} />
              <div className="skeleton-line" style={{ width: '100%', height: '3rem', marginBottom: '1.5rem' }} />
              <div className="skeleton-line" style={{ width: '100%', height: '3rem', marginBottom: '1.5rem' }} />
              <div className="skeleton-line" style={{ width: '90%', height: '3rem', marginBottom: '1.5rem' }} />
              <div className="skeleton-line" style={{ width: '70%', height: '8rem', marginBottom: '2rem' }} />
              <div className="skeleton-line" style={{ width: '50%', height: '3rem', marginBottom: '1.5rem' }} />
              <div className="skeleton-line" style={{ width: '40%', height: '3.5rem', marginBottom: '2rem' }} />
            </div>
          ) : config && config.fields && config.fields.length > 0 ? (() => {
            const { baseFields, advancedFields } = getGroupedFields();
            
            return (
              <form onSubmit={handleSubmit} className="dynamic-form">
                {/* Spinner semplice per generazione domande */}
                {isGeneratingQuestions && (
                  <div className="questions-loading-overlay">
                    <div className="questions-loading-spinner"></div>
                    <p>Generazione domande in corso...</p>
                  </div>
                )}
                
                {/* Campi Base */}
                <div className="form-fields-base">
                  <ModelSettingsPanel
                    value={modelSettings}
                    onChange={setModelSettings}
                    stages={BOOK_STAGES}
                    showGenerationMode
                    kind="book"
                  />
                  {baseFields.map((field) => renderField(field))}
                </div>
                
                {/* Sezione Avanzate (collassabile) */}
                {advancedFields.length > 0 && (
                  <div className="form-fields-advanced-section">
                    <button
                      type="button"
                      onClick={() => {
                        const newValue = !showAdvanced;
                        setShowAdvanced(newValue);
                        try {
                          localStorage.setItem('dynamicForm.showAdvanced', String(newValue));
                        } catch (err) {
                          // Ignora errori localStorage
                        }
                      }}
                      className="advanced-toggle"
                      aria-expanded={showAdvanced}
                    >
                      <span>{showAdvanced ? '▼' : '▶'}</span>
                      <span>Opzioni Avanzate</span>
                    </button>
                    
                    {showAdvanced && (
                      <div className="form-fields-advanced">
                        {advancedFields.map((field) => renderField(field))}
                      </div>
                    )}
                  </div>
                )}
                
                <div className="form-actions">
                  <button type="submit" disabled={isSubmitting} className="submit-button">
                    {isSubmitting ? 'Invio in corso...' : 'Invia'}
                  </button>
                </div>
              </form>
            );
          })() : config && (!config.fields || config.fields.length === 0) ? (
            <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
              <p>Nessun campo disponibile nella configurazione.</p>
            </div>
          ) : null}
          </div>
        </div>
      </div>
    </PageTransition>
  );
}


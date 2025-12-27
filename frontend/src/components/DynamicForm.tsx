import { useState, useEffect } from 'react';
import { fetchConfig, submitForm, generateQuestions, FieldConfig, SubmissionRequest, SubmissionResponse, Question, QuestionAnswer } from '../api/client';
import QuestionsStep from './QuestionsStep';
import DraftStep from './DraftStep';
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
  const [currentStep, setCurrentStep] = useState<'form' | 'questions' | 'draft' | 'summary'>('form');

  useEffect(() => {
    loadConfig();
  }, []);

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
        'pace', 'realism', 'ambiguity', 'intentionality', 'author'
      ];

      optionalFields.forEach(fieldId => {
        if (formData[fieldId]?.trim()) {
          (payload as any)[fieldId] = formData[fieldId].trim();
        }
      });

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

  const handleDraftValidated = () => {
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
    return (
      <div className="submission-success">
        <h2>✓ Configurazione completata con successo!</h2>
        <p>{submitted.message}</p>
        <div className="submission-summary">
          <h3>Riepilogo configurazione:</h3>
          <div style={{ marginBottom: '1.5rem' }}>
            <h4>Dati del form iniziale:</h4>
            <pre>{JSON.stringify(submitted.data, null, 2)}</pre>
          </div>
          {questionAnswers.length > 0 && (
            <div>
              <h4>Risposte alle domande preliminari:</h4>
              <pre>{JSON.stringify(questionAnswers, null, 2)}</pre>
            </div>
          )}
        </div>
        <button onClick={() => {
          setSubmitted(null);
          setFormData({});
          setValidationErrors({});
          setQuestions(null);
          setSessionId(null);
          setAnswersSubmitted(false);
          setFormPayload(null);
          setQuestionAnswers([]);
          setCurrentStep('form');
        }}>
          Nuova configurazione
        </button>
      </div>
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


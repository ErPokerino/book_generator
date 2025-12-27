import { useState, useEffect } from 'react';
import { fetchConfig, submitForm, FieldConfig, SubmissionRequest, SubmissionResponse } from '../api/client';
import './DynamicForm.css';

export default function DynamicForm() {
  const [config, setConfig] = useState<{ llm_models: string[]; fields: FieldConfig[] } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [formData, setFormData] = useState<Record<string, string>>({});
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({});
  const [submitted, setSubmitted] = useState<SubmissionResponse | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

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

      const response = await submitForm(payload);
      setSubmitted(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Errore nell\'invio del form');
    } finally {
      setIsSubmitting(false);
    }
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

  if (submitted) {
    return (
      <div className="submission-success">
        <h2>✓ Submission completata con successo!</h2>
        <p>{submitted.message}</p>
        <div className="submission-summary">
          <h3>Riepilogo dati inviati:</h3>
          <pre>{JSON.stringify(submitted.data, null, 2)}</pre>
        </div>
        <button onClick={() => {
          setSubmitted(null);
          setFormData({});
          setValidationErrors({});
        }}>
          Nuova submission
        </button>
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


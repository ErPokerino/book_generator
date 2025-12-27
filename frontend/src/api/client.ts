export interface FieldOption {
  value: string;
  label?: string;
}

export interface FieldConfig {
  id: string;
  label: string;
  type: 'select' | 'text';
  required: boolean;
  options?: FieldOption[];
  placeholder?: string;
  description?: string;
}

export interface ConfigResponse {
  llm_models: string[];
  fields: FieldConfig[];
}

export interface SubmissionRequest {
  llm_model: string;
  plot: string;
  genre?: string;
  subgenre?: string;
  theme?: string;
  protagonist?: string;
  character_arc?: string;
  point_of_view?: string;
  narrative_voice?: string;
  style?: string;
  temporal_structure?: string;
  pace?: string;
  realism?: string;
  ambiguity?: string;
  intentionality?: string;
  author?: string;
}

export interface SubmissionResponse {
  success: boolean;
  message: string;
  data?: SubmissionRequest;
}

export interface Question {
  id: string;
  text: string;
  type: 'text' | 'multiple_choice';
  options?: string[];
}

export interface QuestionsResponse {
  success: boolean;
  session_id: string;
  questions: Question[];
  message?: string;
}

export interface QuestionAnswer {
  question_id: string;
  answer?: string;
}

export interface AnswersRequest {
  session_id: string;
  answers: QuestionAnswer[];
}

export interface AnswersResponse {
  success: boolean;
  message: string;
  session_id: string;
}

export interface QuestionGenerationRequest {
  form_data: SubmissionRequest;
}

// Modelli per la bozza estesa
export interface DraftGenerationRequest {
  form_data: SubmissionRequest;
  question_answers: QuestionAnswer[];
  session_id: string;
}

export interface DraftResponse {
  success: boolean;
  session_id: string;
  draft_text: string;
  version: number;
  message?: string;
}

export interface DraftModificationRequest {
  session_id: string;
  user_feedback: string;
  current_version: number;
}

export interface DraftValidationRequest {
  session_id: string;
  validated: boolean;
}

export interface DraftValidationResponse {
  success: boolean;
  session_id: string;
  message: string;
}

const API_BASE = '/api';

export async function fetchConfig(): Promise<ConfigResponse> {
  const response = await fetch(`${API_BASE}/config`);
  if (!response.ok) {
    throw new Error(`Errore nel caricamento della configurazione: ${response.statusText}`);
  }
  return response.json();
}

export async function submitForm(data: SubmissionRequest): Promise<SubmissionResponse> {
  const response = await fetch(`${API_BASE}/submissions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Errore nell'invio: ${response.statusText}`);
  }
  
  return response.json();
}

export async function generateQuestions(data: SubmissionRequest): Promise<QuestionsResponse> {
  const response = await fetch(`${API_BASE}/questions/generate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ form_data: data }),
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Errore nella generazione delle domande: ${response.statusText}`);
  }
  
  return response.json();
}

export async function submitAnswers(data: AnswersRequest): Promise<AnswersResponse> {
  const response = await fetch(`${API_BASE}/questions/answers`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Errore nell'invio delle risposte: ${response.statusText}`);
  }
  
  return response.json();
}

export async function generateDraft(request: DraftGenerationRequest): Promise<DraftResponse> {
  const response = await fetch(`${API_BASE}/draft/generate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Errore nella generazione della bozza: ${response.statusText}`);
  }
  
  return response.json();
}

export async function modifyDraft(request: DraftModificationRequest): Promise<DraftResponse> {
  const response = await fetch(`${API_BASE}/draft/modify`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Errore nella modifica della bozza: ${response.statusText}`);
  }
  
  return response.json();
}

export async function validateDraft(request: DraftValidationRequest): Promise<DraftValidationResponse> {
  const response = await fetch(`${API_BASE}/draft/validate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Errore nella validazione della bozza: ${response.statusText}`);
  }
  
  return response.json();
}

export async function getDraft(sessionId: string): Promise<DraftResponse> {
  const response = await fetch(`${API_BASE}/draft/${sessionId}`);
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Errore nel recupero della bozza: ${response.statusText}`);
  }
  
  return response.json();
}


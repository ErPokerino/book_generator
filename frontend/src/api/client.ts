// ===== Auth Types =====
export interface User {
  id: string;
  email: string;
  name: string;
  role: 'user' | 'admin';
  is_active: boolean;
  is_verified?: boolean;
  created_at: string;
}

// Crediti per modalità generazione
export interface ModeCredits {
  flash: number;
  pro: number;
  ultra: number;
}

export interface UserCreditsResponse {
  credits: ModeCredits;
  credits_reset_at: string | null;
  next_reset_at: string;
}

export interface CreditsExhaustedResponse {
  success: false;
  error_type: 'credits_exhausted';
  message: string;
  mode: string;
  next_reset_at: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  name: string;
  ref_token?: string;  // Token referral opzionale per tracking inviti
}

export interface ForgotPasswordRequest {
  email: string;
}

export interface ResetPasswordRequest {
  token: string;
  new_password: string;
}

export interface AuthResponse {
  success: boolean;
  user: User;
  message?: string;
}

export interface RegisterResponse {
  success: boolean;
  message: string;
  email: string;
  requires_verification: boolean;
  verification_token?: string; // Solo in dev mode
}

export interface VerifyEmailResponse {
  success: boolean;
  message: string;
  email: string;
}

export interface CheckVerificationTokenResponse {
  success: boolean;
  valid: boolean;
  already_verified: boolean;
  message: string;
  email: string;
}

export interface ResendVerificationResponse {
  success: boolean;
  message: string;
  already_verified?: boolean;
}

export interface ForgotPasswordResponse {
  success: boolean;
  message: string;
}

export interface ResetPasswordResponse {
  success: boolean;
  message: string;
}

// ===== Existing Types =====
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
  mode_availability?: {
    flash?: number;
    pro?: number;
    ultra?: number;
  } | Record<string, number>;
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
  target_audience?: string;
  theme?: string;
  protagonist?: string;
  protagonist_archetype?: string;
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
  user_name?: string;
  cover_style?: string;
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
  title?: string;
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
  console.log('[API] submitForm chiamato con:', data);
  try {
    const response = await fetch(`${API_BASE}/submissions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });
    
    console.log('[API] submitForm response status:', response.status);
    
    if (!response.ok) {
      let errorDetail = `Errore nell'invio: ${response.statusText}`;
      try {
        const error = await response.json();
        errorDetail = error.detail || errorDetail;
      } catch {
        // Se non è JSON, usa il messaggio di default
      }
      console.error('[API] submitForm errore:', errorDetail);
      throw new Error(errorDetail);
    }
    
    const result = await response.json();
    console.log('[API] submitForm successo:', result);
    return result;
  } catch (err) {
    console.error('[API] submitForm eccezione:', err);
    throw err;
  }
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
  console.log('[API] submitAnswers chiamato con:', data);
  
  // Crea un AbortController per il timeout
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 30000); // 30 secondi di timeout
  
  try {
    const response = await fetch(`${API_BASE}/questions/answers`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
      signal: controller.signal,
    });
    
    clearTimeout(timeoutId);
    
    console.log('[API] submitAnswers response status:', response.status);
    
    if (!response.ok) {
      let errorDetail = `Errore nell'invio delle risposte: ${response.statusText}`;
      try {
        const error = await response.json();
        errorDetail = error.detail || errorDetail;
      } catch {
        // Se non è JSON, usa il messaggio di default
      }
      console.error('[API] submitAnswers errore:', errorDetail);
      throw new Error(errorDetail);
    }
    
    const result = await response.json();
    console.log('[API] submitAnswers successo:', result);
    return result;
  } catch (err) {
    clearTimeout(timeoutId);
    if (err instanceof Error && err.name === 'AbortError') {
      console.error('[API] submitAnswers timeout');
      throw new Error('Timeout: la richiesta ha impiegato troppo tempo. Riprova.');
    }
    console.error('[API] submitAnswers eccezione:', err);
    throw err;
  }
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

export interface OutlineResponse {
  success: boolean;
  session_id: string;
  outline_text: string;
  version: number;
  message?: string;
}

export interface OutlineGenerateRequest {
  session_id: string;
}

// ===== Process Progress Types =====
export interface ProcessProgress {
  status: 'pending' | 'running' | 'completed' | 'failed';
  current_step?: number;
  total_steps?: number;
  progress_percentage?: number;
  estimated_time_seconds?: number;
  error?: string;
  result?: QuestionsResponse | DraftResponse | OutlineResponse;
}

export interface ProcessStartResponse {
  success: boolean;
  session_id: string;
  message: string;
}

// ===== Async Process Start Functions =====
export async function startQuestionsGeneration(request: QuestionGenerationRequest): Promise<ProcessStartResponse> {
  const response = await fetch(`${API_BASE}/questions/generate/start`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Errore nell'avvio della generazione delle domande: ${response.statusText}`);
  }
  
  return response.json();
}

export async function getQuestionsProgress(sessionId: string): Promise<ProcessProgress> {
  const response = await fetch(`${API_BASE}/questions/progress/${sessionId}`);
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Errore nel recupero del progresso: ${response.statusText}`);
  }
  
  return response.json();
}

export async function startDraftGeneration(request: DraftGenerationRequest): Promise<ProcessStartResponse> {
  const response = await fetch(`${API_BASE}/draft/generate/start`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Errore nell'avvio della generazione della bozza: ${response.statusText}`);
  }
  
  return response.json();
}

export async function getDraftProgress(sessionId: string): Promise<ProcessProgress> {
  const response = await fetch(`${API_BASE}/draft/progress/${sessionId}`);
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Errore nel recupero del progresso: ${response.statusText}`);
  }
  
  return response.json();
}

export async function startOutlineGeneration(request: OutlineGenerateRequest): Promise<ProcessStartResponse> {
  const response = await fetch(`${API_BASE}/outline/generate/start`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Errore nell'avvio della generazione della struttura: ${response.statusText}`);
  }
  
  return response.json();
}

export async function getOutlineProgress(sessionId: string): Promise<ProcessProgress> {
  const response = await fetch(`${API_BASE}/outline/progress/${sessionId}`);
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Errore nel recupero del progresso: ${response.statusText}`);
  }
  
  return response.json();
}

export async function generateOutline(request: OutlineGenerateRequest): Promise<OutlineResponse> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 180000); // 3 minuti
  
  try {
    const response = await fetch(`${API_BASE}/outline/generate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
      signal: controller.signal,
    });
    
    clearTimeout(timeoutId);
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || `Errore nella generazione della struttura: ${response.statusText}`);
    }
    
    return response.json();
  } catch (error) {
    clearTimeout(timeoutId);
    if (error instanceof Error && error.name === 'AbortError') {
      throw new Error('Timeout: la generazione della struttura sta impiegando troppo tempo. Il backend potrebbe essere sovraccarico o la chiamata API esterna potrebbe essere lenta.');
    }
    throw error;
  }
}

export interface SessionRestoreResponse {
  session_id: string;
  form_data: SubmissionRequest;
  questions: Question[] | null;
  question_answers: QuestionAnswer[];
  draft: DraftResponse | null;
  outline: string | null;
  writing_progress: BookProgress | null;
  current_step: 'questions' | 'draft' | 'summary' | 'writing';
}

export async function restoreSession(sessionId: string): Promise<SessionRestoreResponse> {
  const response = await fetch(`${API_BASE}/session/${sessionId}/restore`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Errore nel ripristino sessione: ${response.statusText}`);
  }
  
  return response.json();
}

export async function getOutline(sessionId: string): Promise<OutlineResponse> {
  const response = await fetch(`${API_BASE}/outline/${sessionId}`);
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Errore nel recupero della struttura: ${response.statusText}`);
  }
  
  return response.json();
}

export interface OutlineSection {
  title: string;
  description: string;
  level: number;
  section_index: number;
}

export async function updateOutline(
  sessionId: string,
  sections: OutlineSection[]
): Promise<OutlineResponse> {
  const response = await fetch(`${API_BASE}/outline/update`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      session_id: sessionId,
      sections: sections,
    }),
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Errore nell'aggiornamento della struttura: ${response.statusText}`);
  }
  
  return response.json();
}

export async function downloadPdf(sessionId: string): Promise<Blob> {
  const response = await fetch(`${API_BASE}/pdf/${sessionId}`);
  
  if (!response.ok) {
    let errorMessage = `Errore nel download del PDF: ${response.statusText}`;
    try {
      const error = await response.json();
      errorMessage = error.detail || errorMessage;
    } catch {
      // Se non è JSON, usa il messaggio di default
    }
    throw new Error(errorMessage);
  }
  
  return response.blob();
}

// Modelli per la generazione del libro
export interface Chapter {
  title: string;
  content: string;
  section_index: number;
  page_count: number;
}

export interface LiteraryCritique {
  score: number;
  pros: string[];
  cons: string[];
  summary: string;
}

export interface BookProgress {
  session_id: string;
  current_step: number;
  total_steps: number;
  current_section_name?: string;
  completed_chapters: Chapter[];
  is_complete: boolean;
  is_paused?: boolean;
  error?: string;
  total_pages?: number;
  writing_time_minutes?: number;
  estimated_cost?: number;
  critique?: LiteraryCritique;
  critique_status?: 'pending' | 'running' | 'completed' | 'failed';
  critique_error?: string;
  estimated_time_minutes?: number;
  estimated_time_confidence?: 'high' | 'medium' | 'low';
}

export interface BookGenerationRequest {
  session_id: string;
}

export interface BookGenerationResponse {
  success: boolean;
  session_id: string;
  message: string;
}

export async function startBookGeneration(request: BookGenerationRequest): Promise<BookGenerationResponse> {
  const response = await fetch(`${API_BASE}/book/generate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });
  
  if (!response.ok) {
    const error = await response.json();
    // Gestisci errori di crediti esauriti (402 Payment Required)
    if (response.status === 402 && error.detail && typeof error.detail === 'object') {
      const creditsError = error.detail;
      const errorMessage = new Error(creditsError.message || `Hai esaurito i crediti per la modalità ${creditsError.mode || 'selezionata'}`);
      (errorMessage as any).error_type = 'credits_exhausted';
      (errorMessage as any).mode = creditsError.mode;
      (errorMessage as any).next_reset_at = creditsError.next_reset_at;
      throw errorMessage;
    }
    throw new Error(error.detail || `Errore nell'avvio della generazione: ${response.statusText}`);
  }
  
  return response.json();
}

export async function resumeBookGeneration(sessionId: string): Promise<BookGenerationResponse> {
  const response = await fetch(`${API_BASE}/book/resume/${sessionId}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Errore nella ripresa della generazione: ${response.statusText}`);
  }
  
  return response.json();
}

export async function getBookProgress(sessionId: string): Promise<BookProgress> {
  try {
    const response = await fetch(`${API_BASE}/book/progress/${sessionId}`);

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || `Errore nel recupero del progresso: ${response.statusText}`);
    }

    const data = await response.json();
    // DEBUG: Log per verificare la risposta raw del backend
    console.log('[API] getBookProgress response:', {
      estimated_time_minutes: data.estimated_time_minutes,
      estimated_time_confidence: data.estimated_time_confidence,
      current_step: data.current_step,
      total_steps: data.total_steps
    });
    return data;
  } catch (err) {
    // fetch() in browser lancia spesso TypeError su errori di rete (es. backend down / riavvio / proxy)
    if (err instanceof TypeError) {
      throw new Error('Connessione al backend non disponibile (riavvio in corso?). Riprovo tra poco.');
    }
    throw err;
  }
}

export interface BookResponse {
  title: string;
  author: string;
  chapters: Chapter[];
  total_pages?: number;
  writing_time_minutes?: number;
  critique?: LiteraryCritique;
  critique_status?: 'pending' | 'running' | 'completed' | 'failed';
  critique_error?: string;
}

export async function regenerateBookCritique(sessionId: string): Promise<LiteraryCritique> {
  const response = await fetch(`${API_BASE}/book/critique/${sessionId}`, { method: 'POST' });
  if (!response.ok) {
    let errorMessage = `Errore nella rigenerazione della critica: ${response.statusText}`;
    try {
      const error = await response.json();
      errorMessage = error.detail || errorMessage;
    } catch {
      // ignore
    }
    throw new Error(errorMessage);
  }
  return response.json();
}

export async function getCompleteBook(sessionId: string): Promise<BookResponse> {
  const response = await fetch(`${API_BASE}/book/${sessionId}`);
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Errore nel recupero del libro completo: ${response.statusText}`);
  }
  
  return response.json();
}

export async function getBookCritique(sessionId: string): Promise<LiteraryCritique | null> {
  try {
    const book = await getCompleteBook(sessionId);
    return book.critique || null;
  } catch (error) {
    throw new Error(`Errore nel recupero della critica: ${error instanceof Error ? error.message : 'Errore sconosciuto'}`);
  }
}

export async function getCritiqueAudio(sessionId: string): Promise<Blob> {
  const response = await fetch(`${API_BASE}/critique/audio/${sessionId}`, {
    method: 'POST',
    credentials: 'include',
  });
  
  if (!response.ok) {
    let errorMessage = `Errore nella generazione audio: ${response.statusText}`;
    try {
      const error = await response.json();
      errorMessage = error.detail || errorMessage;
    } catch {
      const text = await response.text().catch(() => '');
      if (text) {
        errorMessage = `Errore: ${text.substring(0, 100)}`;
      }
    }
    throw new Error(errorMessage);
  }
  
  return await response.blob();
}

export async function downloadBookPdf(sessionId: string): Promise<{ blob: Blob; filename: string }> {
  const response = await fetch(`${API_BASE}/book/pdf/${sessionId}`);
  
  if (!response.ok) {
    let errorMessage = `Errore nel download del PDF del libro: ${response.statusText}`;
    try {
      const error = await response.json();
      errorMessage = error.detail || errorMessage;
    } catch {
      // Ignora errori di parsing JSON
    }
    throw new Error(errorMessage);
  }
  
  // Estrai il nome file dall'header Content-Disposition
  const contentDisposition = response.headers.get('Content-Disposition');
  let filename = `Libro_${sessionId.substring(0, 8)}.pdf`;
  
  if (contentDisposition) {
    const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
    if (filenameMatch && filenameMatch[1]) {
      filename = filenameMatch[1].replace(/['"]/g, '');
    }
  }
  
  const blob = await response.blob();
  return { blob, filename };
}

export async function exportBook(sessionId: string, format: 'pdf' | 'epub' | 'docx'): Promise<{ blob: Blob; filename: string }> {
  const response = await fetch(`${API_BASE}/book/export/${sessionId}?format=${format}`, {
    credentials: 'include',
  });
  
  if (!response.ok) {
    let errorMessage = `Errore nell'export del libro in formato ${format}: ${response.statusText}`;
    try {
      const error = await response.json();
      errorMessage = error.detail || errorMessage;
    } catch {
      // Ignora errori di parsing JSON
    }
    throw new Error(errorMessage);
  }
  
  // Estrai il nome file dall'header Content-Disposition
  const contentDisposition = response.headers.get('Content-Disposition');
  let filename = `Libro_${sessionId.substring(0, 8)}.${format}`;
  
  if (contentDisposition) {
    const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
    if (filenameMatch && filenameMatch[1]) {
      filename = filenameMatch[1].replace(/['"]/g, '');
    }
  }
  
  const blob = await response.blob();
  return { blob, filename };
}

/**
 * Restituisce l'URL diretto per la copertina.
 * L'endpoint gestirà il redirect a GCS se necessario.
 */
export function getCoverImageUrl(sessionId: string): string {
  return `${API_BASE}/library/cover/${sessionId}`;
}

/**
 * @deprecated Usa getCoverImageUrl() invece. Mantenuto per compatibilità.
 */
export async function getCoverImage(sessionId: string): Promise<string | null> {
  // Usa direttamente l'URL invece di scaricare come blob
  // Questo evita problemi con redirect cross-origin
  return getCoverImageUrl(sessionId);
}

export interface MissingCoverBook {
  session_id: string;
  title: string;
  author: string;
  created_at: string;
}

export interface MissingCoversResponse {
  missing_covers: MissingCoverBook[];
  count: number;
}

export async function regenerateCover(sessionId: string): Promise<{ success: boolean; cover_path: string }> {
  const response = await fetch(`${API_BASE}/library/cover/regenerate/${sessionId}`, {
    method: 'POST',
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Errore nella rigenerazione della copertina: ${response.statusText}`);
  }
  
  return response.json();
}

export async function getBooksWithMissingCovers(): Promise<MissingCoversResponse> {
  const response = await fetch(`${API_BASE}/library/missing-covers`);
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Errore nel recupero dei libri senza copertina: ${response.statusText}`);
  }
  
  return response.json();
}

export interface AppConfig {
  api_timeouts: {
    submit_form?: number;
    generate_questions?: number;
    submit_answers?: number;
    generate_draft?: number;
    generate_outline?: number;
    download_pdf?: number;
  };
  frontend: {
    polling_interval?: number;
    polling_interval_critique?: number;
    mode_availability_defaults?: {
      flash?: number;
      pro?: number;
      ultra?: number;
    };
  };
}

export async function getAppConfig(): Promise<AppConfig> {
  const response = await fetch(`${API_BASE}/config/app`);
  if (!response.ok) {
    // Fallback a valori di default se l'endpoint fallisce
    console.warn('[API] Errore nel caricamento config app, uso valori di default');
    return {
      api_timeouts: {
        submit_form: 30000,
        generate_questions: 60000,
        submit_answers: 30000,
        generate_draft: 120000,
        generate_outline: 120000,
        download_pdf: 300000,
      },
      frontend: {
        polling_interval: 2000,
        polling_interval_critique: 5000,
        mode_availability_defaults: {
          flash: 10,
          pro: 5,
          ultra: 1,
        },
      },
    };
  }
  
  const data: AppConfig = await response.json();
  return data;
}

// Library interfaces and API functions
export interface LibraryEntry {
  session_id: string;
  title: string;
  author: string;
  llm_model: string;  // Ora contiene la modalità (Flash, Pro, Ultra) invece del nome del modello
  genre?: string;
  created_at: string;
  updated_at: string;
  status: 'draft' | 'outline' | 'writing' | 'paused' | 'complete';
  total_chapters: number;
  completed_chapters: number;
  total_pages?: number;
  critique_score?: number;
  critique_status?: string;
  pdf_path?: string;
  pdf_filename?: string;
  cover_image_path?: string;
  writing_time_minutes?: number;
  estimated_cost?: number;
  is_shared?: boolean;  // True se è un libro condiviso (per destinatario)
  shared_by_id?: string;  // ID utente che ha condiviso (per destinatario)
  shared_by_name?: string;  // Nome utente che ha condiviso (per destinatario)
}

export interface LibraryStats {
  total_books: number;
  completed_books: number;
  in_progress_books: number;
  average_score?: number;
  average_pages: number;
  average_writing_time_minutes: number;
  books_by_model: Record<string, number>;
  books_by_genre: Record<string, number>;
  score_distribution: Record<string, number>;
  average_score_by_model: Record<string, number>;
  average_writing_time_by_model?: Record<string, number>;
  average_time_per_page_by_model?: Record<string, number>;
  average_pages_by_model?: Record<string, number>;
  average_cost_by_model?: Record<string, number>;
  average_cost_per_page_by_model?: Record<string, number>;
}

export interface ModelComparisonEntry {
  model: string;
  total_books: number;
  completed_books: number;
  average_score?: number;
  average_pages: number;
  average_cost?: number;
  average_writing_time: number;
  average_time_per_page: number;
  score_range: Record<string, number>;
}

export interface AdvancedStats {
  books_over_time: Record<string, number>;
  score_trend_over_time: Record<string, number>;
  model_comparison: ModelComparisonEntry[];
}

export interface LibraryResponse {
  books: LibraryEntry[];
  total: number;
  has_more?: boolean;  // Indica se ci sono altri libri da caricare
  stats?: LibraryStats;
}

export interface LibraryFilters {
  status?: string;
  mode?: string;  // Modalità (Flash, Pro, Ultra) - preferito rispetto a llm_model
  llm_model?: string;  // Retrocompatibilità, deprecato
  genre?: string;
  search?: string;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
  skip?: number;  // Numero di libri da saltare (per paginazione)
  limit?: number;  // Numero massimo di libri da restituire (per paginazione)
}

export interface PdfEntry {
  filename: string;
  session_id?: string;
  title?: string;
  author?: string;
  created_date?: string;
  size_bytes?: number;
}

export async function getLibrary(filters?: LibraryFilters): Promise<LibraryResponse> {
  const params = new URLSearchParams();
  
  if (filters) {
    if (filters.status) params.append('status', filters.status);
    // Usa mode se disponibile, altrimenti llm_model per retrocompatibilità
    if (filters.mode) {
      params.append('mode', filters.mode);
    } else if (filters.llm_model) {
      params.append('llm_model', filters.llm_model);
    }
    if (filters.genre) params.append('genre', filters.genre);
    if (filters.search) params.append('search', filters.search);
    if (filters.sort_by) params.append('sort_by', filters.sort_by);
    if (filters.sort_order) params.append('sort_order', filters.sort_order);
    if (filters.skip !== undefined) params.append('skip', filters.skip.toString());
    if (filters.limit !== undefined) params.append('limit', filters.limit.toString());
  }
  
  const url = `${API_BASE}/library${params.toString() ? '?' + params.toString() : ''}`;
  const response = await fetch(url, {
    credentials: 'include',
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Errore nel recupero della libreria: ${response.statusText}`);
  }
  
  return response.json();
}

export async function getLibraryStats(): Promise<LibraryStats> {
  const response = await fetch(`${API_BASE}/library/stats`, {
    credentials: 'include',
  });
  
  if (!response.ok) {
    let errorMessage = `Errore nel recupero delle statistiche: ${response.statusText}`;
    try {
      const error = await response.json();
      errorMessage = error.detail || errorMessage;
    } catch {
      // Se la risposta non è JSON valido (es. connessione interrotta), usa il messaggio di default
      const text = await response.text().catch(() => '');
      if (text) {
        errorMessage = `Errore: ${text.substring(0, 100)}`;
      }
    }
    throw new Error(errorMessage);
  }
  
  try {
    return await response.json();
  } catch (e) {
    throw new Error(`Errore nel parsing della risposta: la connessione potrebbe essere stata interrotta. Riprova.`);
  }
}

export async function getAdvancedStats(): Promise<AdvancedStats> {
  const response = await fetch(`${API_BASE}/library/stats/advanced`, {
    credentials: 'include',
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Errore nel recupero delle statistiche avanzate: ${response.statusText}`);
  }
  
  return response.json();
}

export interface UsersStats {
  total_users: number;
  users_with_books: Array<{
    user_id: string;
    name: string;
    email: string;
    books_count: number;
  }>;
}

export async function getUsersStats(): Promise<UsersStats> {
  const response = await fetch(`${API_BASE}/admin/users/stats`, {
    credentials: 'include',
  });
  
  if (!response.ok) {
    let errorMessage = `Errore nel recupero delle statistiche utenti: ${response.statusText}`;
    try {
      const error = await response.json();
      errorMessage = error.detail || errorMessage;
    } catch {
      // Se la risposta non è JSON valido (es. connessione interrotta), usa il messaggio di default
      const text = await response.text().catch(() => '');
      if (text) {
        errorMessage = `Errore: ${text.substring(0, 100)}`;
      }
    }
    throw new Error(errorMessage);
  }
  
  try {
    return await response.json();
  } catch (e) {
    throw new Error(`Errore nel parsing della risposta: la connessione potrebbe essere stata interrotta. Riprova.`);
  }
}

export async function deleteUserAdmin(email: string): Promise<{ success: boolean; message: string }> {
  const response = await fetch(`${API_BASE}/admin/users/${encodeURIComponent(email)}`, {
    method: 'DELETE',
    credentials: 'include',
  });

  if (!response.ok) {
    let errorMessage = `Errore nell'eliminazione dell'utente: ${response.statusText}`;
    try {
      const error = await response.json();
      errorMessage = error.detail || errorMessage;
    } catch {
      // Ignora errori di parsing
    }
    throw new Error(errorMessage);
  }
  
  return await response.json();
}

export async function deleteBook(sessionId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/library/${sessionId}`, {
    method: 'DELETE',
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Errore nell'eliminazione del libro: ${response.statusText}`);
  }
}

export async function getAvailablePdfs(): Promise<PdfEntry[]> {
  const response = await fetch(`${API_BASE}/library/pdfs`);
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Errore nel recupero dei PDF: ${response.statusText}`);
  }
  
  return response.json();
}

export async function downloadPdfByFilename(filename: string): Promise<Blob> {
  const encodedFilename = encodeURIComponent(filename);
  const response = await fetch(`${API_BASE}/library/pdf/${encodedFilename}`);
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Errore nel download del PDF: ${response.statusText}`);
  }
  
  return response.blob();
}

export async function analyzeExternalPdf(
  file: File,
  title?: string,
  author?: string
): Promise<LiteraryCritique> {
  const formData = new FormData();
  formData.append('file', file);
  
  if (title) {
    formData.append('title', title);
  }
  
  if (author) {
    formData.append('author', author);
  }
  
  // Timeout molto lungo (10 minuti) perché l'analisi PDF può richiedere tempo
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 10 * 60 * 1000); // 10 minuti
  
  try {
    const response = await fetch(`${API_BASE}/critique/analyze-pdf`, {
      method: 'POST',
      body: formData,
      signal: controller.signal,
    });
    
    clearTimeout(timeoutId);
    
    if (!response.ok) {
      let errorMessage = `Errore nell'analisi del PDF: ${response.statusText}`;
      try {
        const error = await response.json();
        errorMessage = error.detail || errorMessage;
      } catch {
        // Se non riesce a parsare l'errore come JSON, usa il messaggio di default
      }
      throw new Error(errorMessage);
    }
    
    return response.json();
  } catch (error) {
    clearTimeout(timeoutId);
    if (error instanceof Error && error.name === 'AbortError') {
      throw new Error('Timeout: l\'analisi sta impiegando troppo tempo. Il PDF potrebbe essere troppo grande o complesso.');
    }
    throw error;
  }
}

// ===== Auth API Functions =====

export async function login(credentials: LoginRequest): Promise<AuthResponse> {
  try {
    const response = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include', // Include cookies for session management
      body: JSON.stringify(credentials),
    });

    if (!response.ok) {
      let errorDetail = 'Email o password non corretti';
      try {
        const error = await response.json();
        errorDetail = error.detail || errorDetail;
      } catch {
        // Se non è JSON, usa il messaggio di default
      }
      throw new Error(errorDetail);
    }

    return response.json();
  } catch (err) {
    if (err instanceof TypeError) {
      throw new Error('Connessione al backend non disponibile. Verifica che il backend sia avviato su porta 8000.');
    }
    throw err;
  }
}

export async function register(userData: RegisterRequest): Promise<RegisterResponse> {
  try {
    const response = await fetch(`${API_BASE}/auth/register`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
      body: JSON.stringify(userData),
    });

    if (!response.ok) {
      let errorDetail = 'Errore nella registrazione';
      try {
        const error = await response.json();
        errorDetail = error.detail || errorDetail;
      } catch {
        // Se non è JSON, usa il messaggio di default
      }
      throw new Error(errorDetail);
    }

    return response.json();
  } catch (err) {
    if (err instanceof TypeError) {
      throw new Error('Connessione al backend non disponibile. Verifica che il backend sia avviato su porta 8000.');
    }
    throw err;
  }
}

export async function checkVerificationToken(token: string): Promise<CheckVerificationTokenResponse> {
  const response = await fetch(`${API_BASE}/auth/verify/check?token=${encodeURIComponent(token)}`, {
    method: 'GET',
    credentials: 'include',
  });

  if (!response.ok) {
    let errorDetail = 'Token non valido o scaduto';
    try {
      const error = await response.json();
      errorDetail = error.detail || errorDetail;
    } catch {
      // Se non è JSON, usa il messaggio di default
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

export async function verifyEmail(token: string): Promise<VerifyEmailResponse> {
  const response = await fetch(`${API_BASE}/auth/verify`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify({ token }),
  });

  if (!response.ok) {
    let errorDetail = 'Token non valido o scaduto';
    try {
      const error = await response.json();
      errorDetail = error.detail || errorDetail;
    } catch {
      // Se non è JSON, usa il messaggio di default
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

export async function resendVerification(email: string): Promise<ResendVerificationResponse> {
  try {
    const response = await fetch(`${API_BASE}/auth/resend-verification`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
      body: JSON.stringify({ email }),
    });

    if (!response.ok) {
      let errorDetail = 'Errore nel reinvio email';
      try {
        const error = await response.json();
        errorDetail = error.detail || errorDetail;
      } catch {
        // Se non è JSON, usa il messaggio di default
      }
      throw new Error(errorDetail);
    }

    return response.json();
  } catch (err) {
    if (err instanceof TypeError) {
      throw new Error('Connessione al backend non disponibile. Verifica che il backend sia avviato su porta 8000.');
    }
    throw err;
  }
}

export async function logout(): Promise<{ success: boolean; message: string }> {
  const response = await fetch(`${API_BASE}/auth/logout`, {
    method: 'POST',
    credentials: 'include',
  });

  if (!response.ok) {
    throw new Error('Errore nel logout');
  }

  return response.json();
}

export async function getCurrentUser(): Promise<User | null> {
  try {
    const response = await fetch(`${API_BASE}/auth/me`, {
      method: 'GET',
      credentials: 'include',
    });

    if (response.status === 401 || response.status === 403) {
      return null; // Non autenticato
    }

    if (!response.ok) {
      throw new Error('Errore nel recupero utente');
    }

    return response.json();
  } catch (error) {
    console.error('[API] Errore nel recupero utente corrente:', error);
    return null;
  }
}

export async function getUserCredits(): Promise<UserCreditsResponse | null> {
  try {
    const response = await fetch(`${API_BASE}/auth/credits`, {
      method: 'GET',
      credentials: 'include',
    });

    if (response.status === 401 || response.status === 403) {
      return null; // Non autenticato
    }

    if (!response.ok) {
      console.warn('[API] Errore nel recupero crediti, uso default');
      return null;
    }

    return response.json();
  } catch (error) {
    console.error('[API] Errore nel recupero crediti utente:', error);
    return null;
  }
}

export async function forgotPassword(email: string): Promise<ForgotPasswordResponse> {
  console.log('[API] forgotPassword chiamato per email:', email);
  console.log('[API] URL:', `${API_BASE}/auth/password/forgot`);
  
  try {
    const response = await fetch(`${API_BASE}/auth/password/forgot`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
      body: JSON.stringify({ email }),
    });

    console.log('[API] forgotPassword response status:', response.status, response.statusText);

    if (!response.ok) {
      let errorDetail = 'Errore nella richiesta reset password';
      try {
        const error = await response.json();
        errorDetail = error.detail || errorDetail;
        console.error('[API] forgotPassword error response:', error);
      } catch (e) {
        console.error('[API] forgotPassword errore nel parsing JSON:', e);
        // Se non è JSON, usa il messaggio di default
      }
      throw new Error(errorDetail);
    }

    const result = await response.json();
    console.log('[API] forgotPassword success response:', result);
    return result;
  } catch (error) {
    console.error('[API] forgotPassword eccezione:', error);
    throw error;
  }
}

export async function resetPassword(token: string, newPassword: string): Promise<ResetPasswordResponse> {
  const response = await fetch(`${API_BASE}/auth/password/reset`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify({ token, new_password: newPassword }),
  });

  if (!response.ok) {
    let errorDetail = 'Errore nel reset password';
    try {
      const error = await response.json();
      errorDetail = error.detail || errorDetail;
    } catch {
      // Se non è JSON, usa il messaggio di default
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

// ===== Notifications API =====

export interface Notification {
  id: string;
  user_id: string;
  type: 'connection_request' | 'connection_accepted' | 'book_shared' | 'book_share_accepted' | 'system';
  title: string;
  message: string;
  data?: Record<string, any>;
  is_read: boolean;
  created_at: string;
}

export interface NotificationResponse {
  notifications: Notification[];
  unread_count: number;
  total: number;
  has_more: boolean;
}

export interface UnreadCountResponse {
  unread_count: number;
}

export interface NotificationMarkReadResponse {
  success: boolean;
  message: string;
}

export interface NotificationMarkAllReadResponse {
  success: boolean;
  message: string;
  updated_count: number;
}

export interface NotificationDeleteResponse {
  success: boolean;
  message: string;
}

export async function getNotifications(
  limit?: number,
  skip?: number,
  unreadOnly?: boolean
): Promise<NotificationResponse> {
  const params = new URLSearchParams();
  if (limit !== undefined) params.append('limit', limit.toString());
  if (skip !== undefined) params.append('skip', skip.toString());
  if (unreadOnly !== undefined) params.append('unread_only', unreadOnly.toString());

  const url = `${API_BASE}/notifications${params.toString() ? '?' + params.toString() : ''}`;
  const response = await fetch(url, {
    method: 'GET',
    credentials: 'include',
  });

  if (!response.ok) {
    let errorDetail = 'Errore nel recupero delle notifiche';
    try {
      const error = await response.json();
      errorDetail = error.detail || errorDetail;
    } catch {
      // Se non è JSON, usa il messaggio di default
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

export async function getUnreadCount(): Promise<UnreadCountResponse> {
  const response = await fetch(`${API_BASE}/notifications/unread-count`, {
    method: 'GET',
    credentials: 'include',
  });

  if (!response.ok) {
    let errorDetail = 'Errore nel recupero del conteggio notifiche';
    try {
      const error = await response.json();
      errorDetail = error.detail || errorDetail;
    } catch {
      // Se non è JSON, usa il messaggio di default
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

export async function markNotificationRead(notificationId: string): Promise<NotificationMarkReadResponse> {
  const response = await fetch(`${API_BASE}/notifications/${notificationId}/read`, {
    method: 'PATCH',
    credentials: 'include',
  });

  if (!response.ok) {
    let errorDetail = 'Errore nel marcare la notifica come letta';
    try {
      const error = await response.json();
      errorDetail = error.detail || errorDetail;
    } catch {
      // Se non è JSON, usa il messaggio di default
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

export async function markAllNotificationsRead(): Promise<NotificationMarkAllReadResponse> {
  const response = await fetch(`${API_BASE}/notifications/read-all`, {
    method: 'PATCH',
    credentials: 'include',
  });

  if (!response.ok) {
    let errorDetail = 'Errore nel marcare tutte le notifiche come lette';
    try {
      const error = await response.json();
      errorDetail = error.detail || errorDetail;
    } catch {
      // Se non è JSON, usa il messaggio di default
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

export async function deleteNotification(notificationId: string): Promise<NotificationDeleteResponse> {
  const response = await fetch(`${API_BASE}/notifications/${notificationId}`, {
    method: 'DELETE',
    credentials: 'include',
  });

  if (!response.ok) {
    let errorDetail = 'Errore nell\'eliminazione della notifica';
    try {
      const error = await response.json();
      errorDetail = error.detail || errorDetail;
    } catch {
      // Se non è JSON, usa il messaggio di default
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

// ===== Book Shares API =====

export interface BookShare {
  id: string;
  book_session_id: string;
  owner_id: string;
  recipient_id: string;
  status: 'pending' | 'accepted' | 'declined';
  created_at: string;
  updated_at: string;
  owner_name?: string;
  recipient_name?: string;
  book_title?: string;
}

export interface BookShareResponse {
  shares: BookShare[];
  total: number;
  has_more: boolean;
}

export interface BookShareActionResponse {
  success: boolean;
  message: string;
}

export async function shareBook(sessionId: string, recipientEmail: string): Promise<BookShare> {
  const response = await fetch(`${API_BASE}/books/${sessionId}/share`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify({ recipient_email: recipientEmail }),
  });

  if (!response.ok) {
    let errorDetail = 'Errore nella condivisione del libro';
    try {
      const error = await response.json();
      errorDetail = error.detail || errorDetail;
    } catch {
      // Se non è JSON, usa il messaggio di default
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

export async function getSharedBooks(
  status?: 'pending' | 'accepted' | 'declined',
  limit?: number,
  skip?: number
): Promise<BookShareResponse> {
  const params = new URLSearchParams();
  if (status) params.append('status', status);
  if (limit !== undefined) params.append('limit', limit.toString());
  if (skip !== undefined) params.append('skip', skip.toString());

  const url = `${API_BASE}/books/shares${params.toString() ? '?' + params.toString() : ''}`;
  const response = await fetch(url, {
    method: 'GET',
    credentials: 'include',
  });

  if (!response.ok) {
    let errorDetail = 'Errore nel recupero dei libri condivisi';
    try {
      const error = await response.json();
      errorDetail = error.detail || errorDetail;
    } catch {
      // Se non è JSON, usa il messaggio di default
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

export async function getSentShares(
  status?: 'pending' | 'accepted' | 'declined',
  limit?: number,
  skip?: number
): Promise<BookShareResponse> {
  const params = new URLSearchParams();
  if (status) params.append('status', status);
  if (limit !== undefined) params.append('limit', limit.toString());
  if (skip !== undefined) params.append('skip', skip.toString());

  const url = `${API_BASE}/books/shares/sent${params.toString() ? '?' + params.toString() : ''}`;
  const response = await fetch(url, {
    method: 'GET',
    credentials: 'include',
  });

  if (!response.ok) {
    let errorDetail = 'Errore nel recupero dei libri condivisi con altri';
    try {
      const error = await response.json();
      errorDetail = error.detail || errorDetail;
    } catch {
      // Se non è JSON, usa il messaggio di default
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

export async function acceptBookShare(shareId: string): Promise<BookShare> {
  const response = await fetch(`${API_BASE}/books/shares/${shareId}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify({ action: 'accept' }),
  });

  if (!response.ok) {
    let errorDetail = 'Errore nell\'accettazione della condivisione';
    try {
      const error = await response.json();
      errorDetail = error.detail || errorDetail;
    } catch {
      // Se non è JSON, usa il messaggio di default
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

export async function declineBookShare(shareId: string): Promise<BookShare> {
  const response = await fetch(`${API_BASE}/books/shares/${shareId}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify({ action: 'decline' }),
  });

  if (!response.ok) {
    let errorDetail = 'Errore nel rifiuto della condivisione';
    try {
      const error = await response.json();
      errorDetail = error.detail || errorDetail;
    } catch {
      // Se non è JSON, usa il messaggio di default
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

export async function revokeBookShare(shareId: string): Promise<BookShareActionResponse> {
  const response = await fetch(`${API_BASE}/books/shares/${shareId}`, {
    method: 'DELETE',
    credentials: 'include',
  });

  if (!response.ok) {
    let errorDetail = 'Errore nella revoca della condivisione';
    try {
      const error = await response.json();
      errorDetail = error.detail || errorDetail;
    } catch {
      // Se non è JSON, usa il messaggio di default
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

export async function getBookShares(sessionId: string): Promise<BookShareResponse> {
  const response = await fetch(`${API_BASE}/books/${sessionId}/shares`, {
    method: 'GET',
    credentials: 'include',
  });

  if (!response.ok) {
    let errorDetail = 'Errore nel recupero delle condivisioni del libro';
    try {
      const error = await response.json();
      errorDetail = error.detail || errorDetail;
    } catch {
      // Se non è JSON, usa il messaggio di default
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

// ===== Referral API Functions =====

export interface Referral {
  id: string;
  referrer_id: string;
  invited_email: string;
  status: 'pending' | 'registered' | 'expired';
  token: string;
  created_at: string;
  registered_at?: string;
  invited_user_id?: string;
  referrer_name?: string;
}

export interface ReferralStats {
  total_sent: number;
  total_registered: number;
  pending: number;
}

export async function sendReferral(email: string): Promise<Referral> {
  const response = await fetch(`${API_BASE}/referrals`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify({ email }),
  });

  if (!response.ok) {
    let errorDetail = 'Errore nell\'invio dell\'invito';
    try {
      const error = await response.json();
      errorDetail = error.detail || errorDetail;
    } catch {
      // Se non è JSON, usa il messaggio di default
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

export async function getReferrals(limit: number = 50, skip: number = 0): Promise<Referral[]> {
  const response = await fetch(`${API_BASE}/referrals?limit=${limit}&skip=${skip}`, {
    method: 'GET',
    credentials: 'include',
  });

  if (!response.ok) {
    let errorDetail = 'Errore nel recupero degli inviti';
    try {
      const error = await response.json();
      errorDetail = error.detail || errorDetail;
    } catch {
      // Se non è JSON, usa il messaggio di default
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

export async function getReferralStats(): Promise<ReferralStats> {
  const response = await fetch(`${API_BASE}/referrals/stats`, {
    method: 'GET',
    credentials: 'include',
  });

  if (!response.ok) {
    let errorDetail = 'Errore nel recupero delle statistiche referral';
    try {
      const error = await response.json();
      errorDetail = error.detail || errorDetail;
    } catch {
      // Se non è JSON, usa il messaggio di default
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

// ===== Connections API =====

export interface Connection {
  id: string;
  from_user_id: string;
  to_user_id: string;
  status: 'pending' | 'accepted';
  created_at: string;
  updated_at: string;
  from_user_name?: string;
  to_user_name?: string;
  from_user_email?: string;
  to_user_email?: string;
}

export interface ConnectionRequest {
  email: string;
}

export interface ConnectionResponse {
  connections: Connection[];
  total: number;
  has_more: boolean;
}

export interface UserSearchResponse {
  found: boolean;
  user?: User;
  is_connected: boolean;
  has_pending_request: boolean;
  pending_request_from_me: boolean;
  connection_id?: string;
}

export interface ConnectionActionResponse {
  success: boolean;
  message: string;
}

export async function searchUser(email: string): Promise<UserSearchResponse> {
  const params = new URLSearchParams({ email });
  const response = await fetch(`${API_BASE}/connections/search?${params.toString()}`, {
    method: 'GET',
    credentials: 'include',
  });

  if (!response.ok) {
    let errorDetail = 'Errore nella ricerca utente';
    try {
      const error = await response.json();
      errorDetail = error.detail || errorDetail;
    } catch {
      // Se non è JSON, usa il messaggio di default
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

export async function getConnections(
  status?: 'pending' | 'accepted',
  limit?: number,
  skip?: number
): Promise<ConnectionResponse> {
  const params = new URLSearchParams();
  if (status) params.append('status', status);
  if (limit !== undefined) params.append('limit', limit.toString());
  if (skip !== undefined) params.append('skip', skip.toString());

  const url = `${API_BASE}/connections${params.toString() ? '?' + params.toString() : ''}`;
  const response = await fetch(url, {
    method: 'GET',
    credentials: 'include',
  });

  if (!response.ok) {
    let errorDetail = 'Errore nel recupero delle connessioni';
    try {
      const error = await response.json();
      errorDetail = error.detail || errorDetail;
    } catch {
      // Se non è JSON, usa il messaggio di default
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

export async function getPendingRequests(incomingOnly?: boolean): Promise<ConnectionResponse> {
  const params = new URLSearchParams();
  if (incomingOnly !== undefined) params.append('incoming_only', incomingOnly.toString());

  const url = `${API_BASE}/connections/pending${params.toString() ? '?' + params.toString() : ''}`;
  const response = await fetch(url, {
    method: 'GET',
    credentials: 'include',
  });

  if (!response.ok) {
    let errorDetail = 'Errore nel recupero delle richieste pendenti';
    try {
      const error = await response.json();
      errorDetail = error.detail || errorDetail;
    } catch {
      // Se non è JSON, usa il messaggio di default
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

export async function sendConnectionRequest(email: string): Promise<Connection> {
  const response = await fetch(`${API_BASE}/connections`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify({ email }),
  });

  if (!response.ok) {
    let errorDetail = 'Errore nell\'invio della richiesta di connessione';
    try {
      const error = await response.json();
      errorDetail = error.detail || errorDetail;
    } catch {
      // Se non è JSON, usa il messaggio di default
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

export async function acceptConnection(connectionId: string): Promise<Connection> {
  const response = await fetch(`${API_BASE}/connections/${connectionId}/accept`, {
    method: 'PATCH',
    credentials: 'include',
  });

  if (!response.ok) {
    let errorDetail = 'Errore nell\'accettazione della connessione';
    try {
      const error = await response.json();
      errorDetail = error.detail || errorDetail;
    } catch {
      // Se non è JSON, usa il messaggio di default
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

export async function deleteConnection(connectionId: string): Promise<ConnectionActionResponse> {
  const response = await fetch(`${API_BASE}/connections/${connectionId}`, {
    method: 'DELETE',
    credentials: 'include',
  });

  if (!response.ok) {
    let errorDetail = 'Errore nell\'eliminazione della connessione';
    try {
      const error = await response.json();
      errorDetail = error.detail || errorDetail;
    } catch {
      // Se non è JSON, usa il messaggio di default
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

export async function getPendingConnectionsCount(): Promise<{ pending_count: number }> {
  const response = await fetch(`${API_BASE}/connections/pending-count`, {
    method: 'GET',
    credentials: 'include',
  });

  if (!response.ok) {
    let errorDetail = 'Errore nel recupero del conteggio richieste pendenti';
    try {
      const error = await response.json();
      errorDetail = error.detail || errorDetail;
    } catch {
      // Se non è JSON, usa il messaggio di default
    }
    throw new Error(errorDetail);
  }

  return response.json();
}
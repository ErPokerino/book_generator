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

export async function getCoverImage(sessionId: string): Promise<string | null> {
  try {
    const response = await fetch(`${API_BASE}/library/cover/${sessionId}`);
    
    if (!response.ok) {
      if (response.status === 404) {
        return null; // Nessuna copertina disponibile
      }
      throw new Error(`Errore nel recupero della copertina: ${response.statusText}`);
    }
    
    const blob = await response.blob();
    return URL.createObjectURL(blob);
  } catch (err) {
    console.warn('[getCoverImage] Errore:', err);
    return null;
  }
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
  };
}

let cachedAppConfig: AppConfig | null = null;

export async function getAppConfig(): Promise<AppConfig> {
  if (cachedAppConfig) {
    return cachedAppConfig;
  }
  
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
      },
    };
  }
  
  cachedAppConfig = await response.json();
  return cachedAppConfig;
}

// Library interfaces and API functions
export interface LibraryEntry {
  session_id: string;
  title: string;
  author: string;
  llm_model: string;
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
  stats?: LibraryStats;
}

export interface LibraryFilters {
  status?: string;
  llm_model?: string;
  genre?: string;
  search?: string;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
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
    if (filters.llm_model) params.append('llm_model', filters.llm_model);
    if (filters.genre) params.append('genre', filters.genre);
    if (filters.search) params.append('search', filters.search);
    if (filters.sort_by) params.append('sort_by', filters.sort_by);
    if (filters.sort_order) params.append('sort_order', filters.sort_order);
  }
  
  const url = `${API_BASE}/library${params.toString() ? '?' + params.toString() : ''}`;
  const response = await fetch(url);
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Errore nel recupero della libreria: ${response.statusText}`);
  }
  
  return response.json();
}

export async function getLibraryStats(): Promise<LibraryStats> {
  const response = await fetch(`${API_BASE}/library/stats`);
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Errore nel recupero delle statistiche: ${response.statusText}`);
  }
  
  return response.json();
}

export async function getAdvancedStats(): Promise<AdvancedStats> {
  const response = await fetch(`${API_BASE}/library/stats/advanced`);
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Errore nel recupero delle statistiche avanzate: ${response.statusText}`);
  }
  
  return response.json();
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


export interface StudioChapter { title: string; content: string; section_index: number; content_hash: string }
export interface NarrativeFact {
  id: string; subject: string; predicate: string; value: string; kind: string; certainty: 'explicit' | 'inferred';
  evidence: string; section_index: number; chapter_title: string; start: number; end: number;
}
export interface UsageEvent {
  id: string; phase: string; model: string; status: string; cost_usd: number | null;
  usage: { input_tokens: number; output_tokens: number; thinking_tokens: number; cached_tokens: number; image_tokens: number } | null;
}
export interface CostReport {
  cost_usd: number | null; converted_cost_eur: number | null; coverage_complete: boolean;
  unquantified_calls: number; historical_unverifiable: boolean; calls: number; events: UsageEvent[];
  pricing_source: string; pricing_verified_at: string; note: string;
}
export interface StudioData {
  session_id: string; title: string; author: string | null; status: string; updated_at: string;
  draft: string | null; validated: boolean; outline: string | null;
  chapters: StudioChapter[]; sections: { title: string; description: string; section_index: number }[];
  progress: { current_step: number; total_steps: number; error?: string; pause_requested?: boolean } | null;
  memory: { facts: NarrativeFact[]; chapters: Record<string, string>; checks: { section_index: number; status: string; contradictions: { fact_id: string; evidence: string; explanation: string }[] }[] };
  jobs: { id: string; kind: string; status: string; attempt: number; error?: string }[];
  costs: CostReport;
}
export interface ChapterRevision { revision: number; created_at: number; title: string; content: string; section_index: number }
const base = '/api/studio';
async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${base}/${path}`, options);
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(typeof body?.detail === 'string' ? body.detail : `Richiesta non riuscita (${response.status})`);
  }
  return response.json();
}
export const getStudio = (id: string, signal?: AbortSignal) => request<StudioData>(encodeURIComponent(id), { signal });
export const saveChapter = (id: string, index: number, content: string, expected_hash: string) => request<StudioData>(`${encodeURIComponent(id)}/chapters/${index}`, {
  method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ content, expected_hash }),
});
export const getRevisions = (id: string, index: number) => request<ChapterRevision[]>(`${encodeURIComponent(id)}/chapters/${index}/revisions`);
export const pauseWriting = (id: string) => request<{ message: string }>(`${encodeURIComponent(id)}/pause`, { method: 'POST' });

export const rebuildMemory = (id: string) => request<{ started: boolean }>(`${encodeURIComponent(id)}/memory/rebuild`, { method: 'POST' });

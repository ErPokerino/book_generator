export interface BookSizeEstimate {
  available: boolean;
  sample_count: number;
  mode_sample_count: number;
  scope: string;
  words_per_page: number;
  chapters?: number;
  pages?: number;
  pages_low?: number;
  pages_high?: number;
  words?: number;
  chapter_basis?: 'requested_length' | 'history';
  limited_history?: boolean;
}
export type BookSizeEstimates = Record<'standard' | 'ultra', BookSizeEstimate>;

export async function getBookEstimates(model: string, length?: string, signal?: AbortSignal): Promise<BookSizeEstimates> {
  const query = new URLSearchParams({ model });
  if (length) query.set('length', length);
  const response = await fetch(`/api/config/book-estimates?${query}`, { signal, cache: 'no-store' });
  if (!response.ok) throw new Error('Non è stato possibile leggere lo storico.');
  return response.json();
}

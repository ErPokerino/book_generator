import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { useState } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import ModelSettingsPanel, { BOOK_STAGES, type ModelSettingsValue } from './ModelSettingsPanel';
import { getBookEstimates, type BookSizeEstimates } from '../api/bookEstimates';

vi.mock('../api/client', () => ({ getAppConfig: vi.fn().mockResolvedValue({}) }));
vi.mock('../api/bookEstimates', () => ({ getBookEstimates: vi.fn() }));
const sample = { available: true, sample_count: 4, mode_sample_count: 4, scope: 'mode_model', words_per_page: 250, chapters: 8, pages: 40, pages_low: 30, pages_high: 60, words: 10000, chapter_basis: 'history' as const };
const history: BookSizeEstimates = { standard: sample, ultra: { ...sample, pages: 120, words: 30000 } };
function Panel({ length }: { length?: string }) {
  const [value, setValue] = useState<ModelSettingsValue>({ generationMode: 'standard', stageModels: Object.fromEntries(BOOK_STAGES.map(s => [s.id, s.defaultModel])) });
  return <ModelSettingsPanel value={value} onChange={setValue} stages={BOOK_STAGES} kind="book" bookLength={length} showGenerationMode />;
}
afterEach(cleanup);
beforeEach(() => { vi.clearAllMocks(); vi.mocked(getBookEstimates).mockResolvedValue(history); });

describe('creation settings', () => {
  it('keeps the forecast visible while models are collapsed, and updates it by mode', async () => {
    render(<Panel />);
    expect(await screen.findByText('~40')).toBeInTheDocument();
    expect(screen.queryByRole('combobox', { name: 'Modello per tutto il testo' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('radio', { name: /Ultra/ }));
    expect(screen.getByText('~120')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /^Modelli AI/ }));
    expect(screen.getByRole('combobox', { name: 'Modello per tutto il testo' })).toBeInTheDocument();
  });

  it('never substitutes the other mode when its own history is empty', async () => {
    vi.mocked(getBookEstimates).mockResolvedValue({ ...history, ultra: { available: false, sample_count: 0, mode_sample_count: 0, scope: 'mode', words_per_page: 250 } });
    render(<Panel />);
    await screen.findByText('~40');
    fireEvent.click(screen.getByRole('radio', { name: /Ultra/ }));
    expect(screen.getByText(/Nessun libro Ultra completato/)).toBeInTheDocument();
    expect(screen.queryByText('costo previsto')).not.toBeInTheDocument();
  });

  it('refreshes size estimates when the requested length changes', async () => {
    const view = render(<Panel length="breve" />);
    await screen.findByText('~40');
    view.rerender(<Panel length="lunga" />);
    await waitFor(() => expect(getBookEstimates).toHaveBeenLastCalledWith('gemini-3.8-flash', 'lunga', expect.any(AbortSignal)));
  });

  it('distinguishes a network failure from missing history and lets the user retry', async () => {
    vi.mocked(getBookEstimates).mockRejectedValueOnce(new Error('Storico non raggiungibile'));
    render(<Panel />);
    expect(await screen.findByText('Storico non raggiungibile')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Riprova' }));
    expect(await screen.findByText('~40')).toBeInTheDocument();
  });
});

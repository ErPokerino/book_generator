import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import ManuscriptStudio from './ManuscriptStudio';
import { getStudio, saveChapter } from '../api/studio';
vi.mock('../api/studio', () => ({ getStudio: vi.fn(), saveChapter: vi.fn(), getRevisions: vi.fn().mockResolvedValue([]), pauseWriting: vi.fn(), rebuildMemory: vi.fn() }));
vi.mock('./ExportDropdown', () => ({ default: () => <button>Esporta</button> }));
const project = {
  session_id: 'one', title: 'La casa sul fiume', author: 'Elena', status: 'paused', updated_at: '2026-09-20T10:00:00Z',
  draft: 'La trama', validated: true, outline: 'Indice', progress: { current_step: 1, total_steps: 2 }, jobs: [],
  sections: [{ title: 'Il ritorno', description: 'Anna torna.', section_index: 0 }, { title: 'La chiave', description: 'Un incontro.', section_index: 1 }],
  chapters: [{ title: 'Il ritorno', content: 'Anna osservava il fiume.', section_index: 0, content_hash: 'a'.repeat(64) }],
  memory: { facts: [], chapters: {}, checks: [] },
  costs: { cost_usd: null, converted_cost_eur: null, coverage_complete: false, unquantified_calls: 1, historical_unverifiable: false, calls: 1, events: [], pricing_source: 'https://ai.google.dev/gemini-api/docs/pricing', pricing_verified_at: '2026-09-20', note: 'Cambio indicativo.' },
};
function mount() {
  return render(<RouterProvider router={createMemoryRouter([{ path: '/studio/:sessionId', element: <ManuscriptStudio /> }], { initialEntries: ['/studio/one'] })} />);
}
afterEach(cleanup);
beforeEach(() => { vi.clearAllMocks(); vi.mocked(getStudio).mockResolvedValue(structuredClone(project)); });
describe('Manuscript studio', () => {
  it('keeps the edited text when a save fails and blocks chapter changes', async () => {
    vi.mocked(saveChapter).mockRejectedValue(new Error('Modifica concorrente'));
    mount();
    fireEvent.click(await screen.findByRole('button', { name: 'Modifica testo' }));
    fireEvent.change(screen.getByRole('textbox', { name: 'Testo del capitolo' }), { target: { value: 'Il mio testo da preservare.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Salva' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Modifica concorrente');
    expect(screen.getByRole('textbox')).toHaveValue('Il mio testo da preservare.');
    fireEvent.click(screen.getByRole('button', { name: /La chiave/ }));
    expect(screen.getByRole('textbox')).toHaveValue('Il mio testo da preservare.');
  });
  it('saves with the expected content hash', async () => {
    vi.mocked(saveChapter).mockResolvedValue({ ...project, chapters: [{ ...project.chapters[0], content: 'Testo corretto.', content_hash: 'b'.repeat(64) }] });
    mount();
    fireEvent.click(await screen.findByRole('button', { name: 'Modifica testo' }));
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Testo corretto.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Salva' }));
    await waitFor(() => expect(saveChapter).toHaveBeenCalledWith('one', 0, 'Testo corretto.', 'a'.repeat(64)));
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Salva' })).not.toBeInTheDocument());
  });
  it('labels missing consumption as partial instead of zero', async () => {
    mount();
    fireEvent.click(await screen.findByRole('button', { name: 'Costi' }));
    expect(screen.getByText(/Totale parziale/)).toBeInTheDocument();
    expect(screen.getByText(/1 richieste da verificare/)).toBeInTheDocument();
  });
});

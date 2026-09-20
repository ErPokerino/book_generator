import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import LibraryView from './LibraryView';

const { getLibrary, toast } = vi.hoisted(() => ({ getLibrary: vi.fn(), toast: { error: vi.fn() } }));
vi.mock('../api/client', () => ({ getLibrary, fetchConfig: () => Promise.resolve({ fields: [] }) }));
vi.mock('../hooks/useToast', () => ({ useToast: () => toast }));
vi.mock('./BookCard', () => ({ default: ({ book }: { book: { title: string } }) => <div>{book.title}</div> }));
vi.mock('./WritingStep', () => ({ default: () => null }));
vi.mock('./CritiqueModal', () => ({ default: () => null }));

const response = (title: string) => ({ books: [{ session_id: title, title }], total: 1, has_more: false });

describe('LibraryView', () => {
  beforeEach(() => {
    vi.stubGlobal('IntersectionObserver', class {
      observe() {} unobserve() {} disconnect() {}
    });
  });
  afterEach(() => { cleanup(); vi.clearAllMocks(); vi.unstubAllGlobals(); });

  it('ignores a stale search response when a newer filter has completed', async () => {
    let older!: (value: unknown) => void;
    let newer!: (value: unknown) => void;
    getLibrary.mockResolvedValueOnce(response('Iniziale'))
      .mockImplementationOnce(() => new Promise(resolve => { older = resolve; }))
      .mockImplementationOnce(() => new Promise(resolve => { newer = resolve; }));
    render(<MemoryRouter><LibraryView /></MemoryRouter>);
    await screen.findByText('Iniziale');
    fireEvent.change(screen.getByLabelText('Cerca'), { target: { value: 'vecchio' } });
    fireEvent.change(screen.getByLabelText('Cerca'), { target: { value: 'nuovo' } });
    await act(async () => newer(response('Nuovo risultato')));
    await act(async () => older(response('Risultato superato')));
    expect(screen.getByText('Nuovo risultato')).toBeInTheDocument();
    expect(screen.queryByText('Risultato superato')).not.toBeInTheDocument();
  });

  it('offers retry after a network error instead of claiming the library is empty', async () => {
    getLibrary.mockRejectedValueOnce(new Error('Offline')).mockResolvedValueOnce(response('Ritrovato'));
    render(<MemoryRouter><LibraryView /></MemoryRouter>);
    await screen.findByText('Libreria non disponibile');
    expect(screen.queryByText('Nessuna opera ancora')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Riprova' }));
    expect(await screen.findByText('Ritrovato')).toBeInTheDocument();
  });
});

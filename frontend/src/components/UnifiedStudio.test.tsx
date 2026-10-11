import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, useLocation } from 'react-router-dom';
import CreateShell from './CreateShell';
import LibraryView from './LibraryView';

const { getLibrary, toast } = vi.hoisted(() => ({ getLibrary: vi.fn(), toast: { error: vi.fn() } }));
vi.mock('../api/client', () => ({ getLibrary, fetchConfig: () => Promise.resolve({ fields: [] }) }));
vi.mock('../hooks/useToast', () => ({ useToast: () => toast }));
vi.mock('./BookCard', () => ({ default: ({ book }: { book: { title: string; content_type:string; session_id:string } }) => <article><a href={book.content_type==='essay'?`/read/essay/${book.session_id}`:`/book/${book.session_id}`}>{book.title}</a></article> }));
vi.mock('./CritiqueModal', () => ({ default: () => null }));

function Location() { return <output>{useLocation().pathname}</output>; }
afterEach(() => { cleanup(); vi.clearAllMocks(); vi.unstubAllGlobals(); });

describe('uno studio, tre modi di scrivere', () => {
  it('ordina Narrativa, Saggio e Fumetto e apre il percorso del saggio', () => {
    render(<MemoryRouter initialEntries={['/new']}><CreateShell medium="book"><p>Il tuo progetto</p></CreateShell><Location /></MemoryRouter>);
    expect(screen.getAllByRole('radio').map(item => item.textContent)).toEqual(['Narrativa', 'Saggio', 'Fumetto']);
    fireEvent.click(screen.getByRole('radio', { name: 'Saggio' }));
    expect(screen.getByRole('status')).toHaveTextContent('/new/essay');
  });

  it('mostra saggi e libri nello stesso scaffale e filtra tramite la stessa API', async () => {
    vi.stubGlobal('IntersectionObserver', class { observe() {} unobserve() {} disconnect() {} });
    const essay = { session_id: 'E1', content_type: 'essay', title: 'Le ragioni di una scelta', genre: 'Argomentativo', status: 'draft', word_count: 0 };
    getLibrary.mockResolvedValueOnce({ books: [{ session_id: 'B1', title: 'Un mondo nuovo', content_type: 'book' }, essay], total: 2, has_more: false })
      .mockResolvedValueOnce({ books: [essay], total: 1, has_more: false });
    render(<MemoryRouter><LibraryView /></MemoryRouter>);
    expect(await screen.findByText('Un mondo nuovo')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Le ragioni di una scelta' })).toHaveAttribute('href', '/read/essay/E1');
    fireEvent.click(screen.getByRole('radio', { name: 'Saggi' }));
    await waitFor(() => expect(getLibrary).toHaveBeenLastCalledWith(expect.objectContaining({ content_type: 'essay', skip: 0 }), expect.any(AbortSignal)));
    await waitFor(() => expect(screen.queryByText('Un mondo nuovo')).not.toBeInTheDocument());
  });
});

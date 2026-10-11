import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { ReactNode } from 'react';
import BookReader from './BookReader';

vi.mock('../api/client', () => ({
  getCompleteBook: () => Promise.resolve({ title: 'Prova', author: 'Autore', chapters: [
    { title: 'Capitolo sicuro', content: 'Testo **in evidenza**.\n\n<img src="x" onerror="alert(1)" />\n<script>alert(1)</script>' },
  ] }),
  getCoverImageUrl: () => '/cover.png',
}));
vi.mock('./AudioPlayer', () => ({ default: () => null }));
vi.mock('./ui/PageTransition', () => ({ default: ({ children }: { children: ReactNode }) => <>{children}</> }));

afterEach(cleanup);

it('renders Markdown without inserting model-generated HTML', async () => {
  const { container } = render(<MemoryRouter initialEntries={['/book/test']}>
    <Routes><Route path="/book/:sessionId" element={<BookReader />} /></Routes>
  </MemoryRouter>);
  vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
  const next = await screen.findByRole('button', { name: 'Pagina successiva' });
  fireEvent.click(next);
  expect(screen.getByText('in evidenza').tagName).toBe('STRONG');
  expect(container.querySelector('.reader-prose script')).toBeNull();
  expect(container.querySelector('.reader-prose img')).toBeNull();
});

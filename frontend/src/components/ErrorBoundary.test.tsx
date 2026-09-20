import { render, screen } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import ErrorBoundary from './ErrorBoundary';

it('explains a missing lazy chunk and offers a deliberate reload', () => {
  const log = vi.spyOn(console, 'error').mockImplementation(() => {});
  const Broken = (): never => { throw new TypeError('Failed to fetch dynamically imported module: /assets/old.js'); };
  try {
    render(<ErrorBoundary><Broken /></ErrorBoundary>);
    expect(screen.getByRole('heading', { name: 'Ricarica lo studio' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Ricarica la pagina' })).toBeInTheDocument();
    expect(screen.getByText(/capitoli già salvati/)).toBeInTheDocument();
  } finally { log.mockRestore(); }
});

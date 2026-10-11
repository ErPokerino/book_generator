import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { EssayForecast } from './EssayForecast';
import { BriefForm } from './BriefForm';
import { defaultBrief, type Config } from './api';

const forecast = { pages: 140, sections: 12, parts: 36, cost_eur: .44,
  cost_low_eur: .29, cost_high_eur: .7, minutes: 33, time_basis: 'configuration', time_samples: 0, cover_extra: false };
const config = { models: [{ id: 'gemini-3.8-flash', label: 'Gemini 3.8 Flash' }], stages: {},
  profiles: { argumentative: { label: 'Argomentativo', defaults: {} } },
  roles: { challenge: { label: 'Metti alla prova' } } } as unknown as Config;

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe('lunghezza e previsione del saggio', () => {
  it('edita le pagine e invia il budget compatibile con i progetti esistenti', () => {
    const save = vi.fn();
    render(<BriefForm initial={{ ...defaultBrief(), topic: 'Un tema valido' }} config={config} onSave={save} />);
    expect(screen.getByRole('spinbutton', { name: 'Numero di pagine' })).toHaveValue(140);
    expect(screen.getByRole('option', { name: 'Breve · 60 pagine' })).toBeInTheDocument();
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Numero di pagine' }), { target: { value: '80' } });
    fireEvent.click(screen.getByRole('button', { name: 'Crea progetto' }));
    expect(save).toHaveBeenCalledWith(expect.objectContaining({ target_words: 20000 }));
  });

  it('non arrotonda i budget storici quando si modifica un altro campo', () => {
    const save = vi.fn();
    render(<BriefForm initial={{ ...defaultBrief(), topic: 'Un tema valido', target_words: 15333 }} config={config} onSave={save} />);
    expect(screen.getByRole('spinbutton', { name: 'Numero di pagine' })).toHaveValue(62);
    fireEvent.click(screen.getByRole('button', { name: 'Crea progetto' }));
    expect(save).toHaveBeenCalledWith(expect.objectContaining({ target_words: 15333 }));
  });

  it('mostra costo, pagine e tempo già prima della prima opera', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(forecast))));
    render(<EssayForecast brief={defaultBrief()} />);
    expect(await screen.findByText('~€0.44')).toBeInTheDocument();
    expect(screen.getByText('~33 min')).toBeInTheDocument();
    expect(screen.getByText('~140')).toBeInTheDocument();
    expect(screen.getByText(/Ricerca, analisi delle fonti/)).toBeInTheDocument();
  });

  it('annulla la previsione precedente e ignora le risposte fuori ordine', async () => {
    let first!: (value: Response) => void;
    const fetch = vi.fn().mockImplementationOnce(() => new Promise<Response>(resolve => { first = resolve; }))
      .mockResolvedValue(new Response(JSON.stringify({ ...forecast, pages: 60, cost_eur: .2 })));
    vi.stubGlobal('fetch', fetch);
    const view = render(<EssayForecast brief={defaultBrief()} />);
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
    const signal = fetch.mock.calls[0][1].signal as AbortSignal;
    view.rerender(<EssayForecast brief={{ ...defaultBrief(), target_words: 15000 }} />);
    expect(signal.aborted).toBe(true);
    expect(await screen.findByText('~€0.20')).toBeInTheDocument();
    first(new Response(JSON.stringify(forecast)));
    await waitFor(() => expect(screen.queryByText('~€0.44')).not.toBeInTheDocument());
  });

  it('distingue un errore di rete e permette di riprovare', async () => {
    const fetch = vi.fn().mockRejectedValueOnce(new Error('Offline'))
      .mockResolvedValue(new Response(JSON.stringify(forecast)));
    vi.stubGlobal('fetch', fetch);
    render(<EssayForecast brief={defaultBrief()} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Riprova' }));
    expect(await screen.findByText('~€0.44')).toBeInTheDocument();
  });
});

import { useEffect, useState } from 'react';
import { Clock3, Coins } from 'lucide-react';
import { api, write, type Brief } from './api';
import { formatEstimateCost, formatEstimateTime } from '../utils/estimateGeneration';
import '../components/ModelSettingsPanel.css';

interface Forecast {
  pages: number; sections: number; parts: number; cost_eur: number | null;
  cost_low_eur: number | null; cost_high_eur: number | null; minutes: number;
  time_basis: string; time_samples: number; cover_extra: boolean;
}

export function EssayForecast({ brief }: { brief: Brief }) {
  const request = JSON.stringify({ topic: 'Previsione del saggio', target_words: brief.target_words,
    revision_mode: brief.revision_mode, llm_model: brief.llm_model,
    model_overrides: brief.model_overrides, cover_style: brief.cover_style });
  const [result, setResult] = useState<{ key: string; data: Forecast } | null>(null);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  const forecast = result?.key === request ? result.data : null;
  useEffect(() => {
    let disposed = false;
    const controller = new AbortController();
    setError('');
    const timer = setTimeout(() => {
      api<Forecast>('essay-estimates', { ...write(JSON.parse(request)), signal: controller.signal })
        .then(data => { if (!disposed) setResult({ key: request, data }); })
        .catch(() => { if (!disposed) setError('La previsione non è disponibile. Puoi comunque creare il saggio.'); });
    }, 180);
    return () => { disposed = true; clearTimeout(timer); controller.abort(); };
  }, [request, retry]);
  return <aside className="generation-forecast" aria-label="Previsione del saggio" aria-live="polite">
    <span className="forecast-eyebrow">PRIMA DI COMINCIARE</span>
    <h3>Quanto spazio alla tua idea?</h3>
    <div className="forecast-pages"><strong>~{Math.ceil(brief.target_words / 250)}</strong><span>pagine di testo obiettivo</span></div>
    <div className="forecast-metrics">
      <div><Coins size={17} /><strong>{forecast?.cost_eur != null ? `~${formatEstimateCost(forecast.cost_eur)}` : '—'}</strong><span>Costo indicativo</span></div>
      <div><Clock3 size={17} /><strong>{forecast ? formatEstimateTime(forecast.minutes) : '—'}</strong><span>Tempo AI indicativo</span></div>
    </div>
    {error ? <div className="forecast-empty"><p>{error}</p><button type="button" onClick={() => setRetry(value => value + 1)}>Riprova</button></div>
      : !forecast ? <p>Calcolo della previsione…</p> : <>
        <p className="forecast-source">{forecast.time_basis === 'history' ? `Tempo basato su ${forecast.time_samples} saggi comparabili.` : 'Previsione iniziale basata sulle ipotesi del percorso.'} {forecast.cover_extra && 'Copertina AI da aggiungere.'}</p>
        <details className="forecast-method"><summary>Come viene calcolata?</summary>
          <p>Circa {forecast.sections} capitoli, scritti in {forecast.parts} parti. Include domande, progetto editoriale e scrittura{brief.revision_mode === 'reviewed' ? ', con controllo dei capitoli' : ''}. Ricerca, analisi delle fonti, correzioni, revisione separata e copertina AI hanno consumi aggiuntivi.</p>
          <p>250 parole per pagina: l’ampiezza è un obiettivo, l’impaginazione PDF può variare. I tempi escludono le tue modifiche e le attese fra le fasi.</p>
          {forecast.cost_low_eur != null && forecast.cost_high_eur != null && <p>Fascia indicativa {formatEstimateCost(forecast.cost_low_eur)}–{formatEstimateCost(forecast.cost_high_eur)}: budget di token e listino configurato, senza garanzia sul totale. Il costo effettivo compare nello studio.</p>}
        </details>
      </>}
  </aside>;
}

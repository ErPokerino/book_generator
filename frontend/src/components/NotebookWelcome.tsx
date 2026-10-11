import { Link } from 'react-router-dom';
import { ArrowUpRight } from 'lucide-react';
import NotebookIllustration, { Medium } from './NotebookIllustration';

const modes: { medium: Medium; title: string; description: string; route: string; number: string }[] = [
  { medium: 'book', title: 'Narrativa', description: 'Inventa un mondo. Dagli una voce.', route: '/new', number: '01' },
  { medium: 'essay', title: 'Saggio', description: 'Segui una domanda. Costruisci le tue ragioni.', route: '/new/essay', number: '02' },
  { medium: 'manga', title: 'Fumetto', description: 'Una storia, un tratto, una tavola alla volta.', route: '/comics', number: '03' },
];

export default function NotebookWelcome() {
  return <section className="notebook-welcome" aria-labelledby="welcome-title">
    <div className="notebook-welcome-heading">
      <div><span className="notebook-eyebrow">Uno spazio per le tue idee</span><h1 id="welcome-title">Tutto comincia<br />da un <span className="ink-underline">foglio.</span></h1><p>Storie da inventare. Idee da approfondire.<br />Scegli una forma e comincia a scrivere.</p></div>
      <div className="notebook-margin-note" aria-hidden="true">la prossima idea<br />potrebbe essere qui.<svg viewBox="0 0 110 70" fill="none"><path d="M88 8 Q90 57 20 52 M20 52 L35 42 M20 52 L35 61" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" /></svg></div>
    </div>
    <div className="notebook-mode-grid">{modes.map(mode => <Link key={mode.medium} to={mode.route} className={`notebook-mode-card notebook-mode-${mode.medium}`}>
      <span className="notebook-mode-number">{mode.number}</span><NotebookIllustration medium={mode.medium} />
      <div className="notebook-mode-copy"><h2>{mode.title}{mode.medium === 'manga' && <span className="notebook-beta">beta</span>}</h2><p>{mode.description}</p></div><ArrowUpRight className="notebook-mode-arrow" size={21} strokeWidth={1.5} />
    </Link>)}</div>
  </section>;
}

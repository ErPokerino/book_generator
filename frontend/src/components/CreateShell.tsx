import { ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import SegmentedControl from './ui/SegmentedControl';
import './CreateShell.css';

interface CreateShellProps {
  medium: 'book' | 'essay' | 'manga';
  children: ReactNode;
}

export default function CreateShell({ medium, children }: CreateShellProps) {
  const navigate = useNavigate();

  return (
    <div className="page-shell create-shell">
      <header className="create-shell-header">
        <div><span className="notebook-eyebrow">Il tuo prossimo progetto</span><h1>{medium === 'book' ? 'Crea narrativa' : medium === 'essay' ? 'Crea un saggio' : 'Crea un fumetto'}</h1><p className="create-shell-subtitle">{medium === 'essay' ? 'Una domanda, le tue ragioni, un nuovo punto di vista.' : medium === 'manga' ? 'Dai una storia alle tue immagini.' : 'C’è una storia che solo tu puoi raccontare.'}</p></div>
        <SegmentedControl
          name="medium"
          ariaLabel="Tipo di opera"
          value={medium}
          options={[
            { value: 'book', label: 'Narrativa' },
            { value: 'essay', label: 'Saggio' },
            { value: 'manga', label: 'Fumetto' },
          ]}
          onChange={(next) => navigate(next === 'manga' ? '/comics' : next === 'essay' ? '/new/essay' : '/new')}
        />
      </header>
      {children}
    </div>
  );
}

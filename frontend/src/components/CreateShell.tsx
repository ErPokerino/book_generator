import { ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import SegmentedControl from './ui/SegmentedControl';
import './CreateShell.css';

interface CreateShellProps {
  medium: 'book' | 'manga';
  children: ReactNode;
}

export default function CreateShell({ medium, children }: CreateShellProps) {
  const navigate = useNavigate();

  return (
    <div className="page-shell create-shell">
      <header className="create-shell-header">
        <h1>Crea</h1>
        <SegmentedControl
          name="medium"
          ariaLabel="Tipo di opera"
          value={medium}
          options={[
            { value: 'book', label: 'Libro' },
            { value: 'manga', label: 'Manga' },
          ]}
          onChange={(next) => navigate(next === 'manga' ? '/manga' : '/new')}
        />
      </header>
      {children}
    </div>
  );
}

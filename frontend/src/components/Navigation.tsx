import './Navigation.css';

interface NavigationProps {
  currentView: 'library' | 'newBook' | 'benchmark';
  onNavigate: (view: 'library' | 'newBook' | 'benchmark') => void;
}

export default function Navigation({ currentView, onNavigate }: NavigationProps) {
  return (
    <nav className="main-navigation">
      <div className="nav-brand">
        <h1>📚 Scrittura Libro</h1>
      </div>
      <div className="nav-links">
        <button
          className={`nav-link ${currentView === 'library' ? 'active' : ''}`}
          onClick={() => onNavigate('library')}
        >
          Libreria
        </button>
        <button
          className={`nav-link ${currentView === 'newBook' ? 'active' : ''}`}
          onClick={() => onNavigate('newBook')}
        >
          Nuovo Libro
        </button>
        <button
          className={`nav-link ${currentView === 'benchmark' ? 'active' : ''}`}
          onClick={() => onNavigate('benchmark')}
        >
          Benchmark
        </button>
      </div>
    </nav>
  );
}


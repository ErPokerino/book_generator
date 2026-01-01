import { useState } from 'react'
import DynamicForm from './components/DynamicForm'
import Navigation from './components/Navigation'
import LibraryView from './components/LibraryView'
import BenchmarkView from './components/BenchmarkView'
import BookReader from './components/BookReader'
import ErrorBoundary from './components/ErrorBoundary'
import './App.css'

import AnalyticsView from './components/AnalyticsView'

function App() {
  const [currentView, setCurrentView] = useState<'library' | 'newBook' | 'benchmark' | 'analytics'>('newBook')
  const [readingBookId, setReadingBookId] = useState<string | null>(null)

  const handleReadBook = (sessionId: string) => {
    setReadingBookId(sessionId)
  }

  const handleCloseReader = () => {
    setReadingBookId(null)
  }

  // Se c'è un libro in lettura, mostra il reader
  if (readingBookId) {
    return (
      <ErrorBoundary>
        <BookReader sessionId={readingBookId} onClose={handleCloseReader} />
      </ErrorBoundary>
    )
  }

  return (
    <ErrorBoundary>
      <div className="App">
        <Navigation 
          currentView={currentView} 
          onNavigate={(view) => setCurrentView(view)} 
        />
        <main className="app-main">
          {currentView === 'library' ? (
            <LibraryView 
              onReadBook={handleReadBook}
              onNavigateToNewBook={() => setCurrentView('newBook')}
            />
          ) : currentView === 'benchmark' ? (
            <BenchmarkView />
          ) : currentView === 'analytics' ? (
            <AnalyticsView />
          ) : (
            <DynamicForm />
          )}
        </main>
      </div>
    </ErrorBoundary>
  )
}

export default App




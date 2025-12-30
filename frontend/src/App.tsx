import { useState } from 'react'
import DynamicForm from './components/DynamicForm'
import Navigation from './components/Navigation'
import LibraryView from './components/LibraryView'
import BenchmarkView from './components/BenchmarkView'
import BookReader from './components/BookReader'
import './App.css'

function App() {
  const [currentView, setCurrentView] = useState<'library' | 'newBook' | 'benchmark'>('newBook')
  const [readingBookId, setReadingBookId] = useState<string | null>(null)

  const handleReadBook = (sessionId: string) => {
    setReadingBookId(sessionId)
  }

  const handleCloseReader = () => {
    setReadingBookId(null)
  }

  // Se c'è un libro in lettura, mostra il reader
  if (readingBookId) {
    return <BookReader sessionId={readingBookId} onClose={handleCloseReader} />
  }

  return (
    <div className="App">
      <Navigation 
        currentView={currentView} 
        onNavigate={(view) => setCurrentView(view)} 
      />
      <main className="app-main">
        {currentView === 'library' ? (
          <LibraryView onReadBook={handleReadBook} />
        ) : currentView === 'benchmark' ? (
          <BenchmarkView />
        ) : (
          <DynamicForm />
        )}
      </main>
    </div>
  )
}

export default App




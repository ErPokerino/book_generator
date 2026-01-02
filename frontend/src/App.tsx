import { useState } from 'react'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import DynamicForm from './components/DynamicForm'
import Navigation from './components/Navigation'
import LibraryView from './components/LibraryView'
import BenchmarkView from './components/BenchmarkView'
import BookReader from './components/BookReader'
import ErrorBoundary from './components/ErrorBoundary'
import LoginPage from './components/LoginPage'
import RegisterPage from './components/RegisterPage'
import ForgotPasswordPage from './components/ForgotPasswordPage'
import ResetPasswordPage from './components/ResetPasswordPage'
import './App.css'

import AnalyticsView from './components/AnalyticsView'

type AuthView = 'login' | 'register' | 'forgot-password' | 'reset-password'

function AppContent() {
  const [currentView, setCurrentView] = useState<'library' | 'newBook' | 'benchmark' | 'analytics'>('newBook')
  const [readingBookId, setReadingBookId] = useState<string | null>(null)
  const [authView, setAuthView] = useState<AuthView | null>(null)
  const [resetToken, setResetToken] = useState<string | null>(null)
  const { isAuthenticated, isLoading } = useAuth()

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

  // Se non autenticato, mostra le pagine di autenticazione
  if (!isAuthenticated && !isLoading) {
    if (authView === 'register') {
      return (
        <ErrorBoundary>
          <RegisterPage onNavigateToLogin={() => setAuthView('login')} />
        </ErrorBoundary>
      )
    }
    if (authView === 'forgot-password') {
      return (
        <ErrorBoundary>
          <ForgotPasswordPage 
            onNavigateToLogin={() => setAuthView('login')} 
            onNavigateToReset={(token) => {
              setResetToken(token);
              setAuthView('reset-password');
            }}
          />
        </ErrorBoundary>
      )
    }
    if (authView === 'reset-password' && resetToken) {
      return (
        <ErrorBoundary>
          <ResetPasswordPage 
            token={resetToken}
            onNavigateToLogin={() => {
              setResetToken(null);
              setAuthView('login');
            }}
            onSuccess={() => {
              setResetToken(null);
              setAuthView('login');
            }}
          />
        </ErrorBoundary>
      )
    }
    return (
      <ErrorBoundary>
        <LoginPage 
          onNavigateToRegister={() => setAuthView('register')}
          onNavigateToForgotPassword={() => setAuthView('forgot-password')}
        />
      </ErrorBoundary>
    )
  }

  // Loading state
  if (isLoading) {
    return (
      <ErrorBoundary>
        <div className="App">
          <div style={{ 
            display: 'flex', 
            justifyContent: 'center', 
            alignItems: 'center', 
            minHeight: '100vh',
            fontSize: '1.125rem',
            color: 'var(--text-secondary)'
          }}>
            Caricamento...
          </div>
        </div>
      </ErrorBoundary>
    )
  }

  // App principale (autenticato)
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

function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  )
}

export default App




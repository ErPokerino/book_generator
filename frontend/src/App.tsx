import { useState, useEffect } from 'react'
import { Toaster } from 'react-hot-toast'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import { NotificationProvider } from './contexts/NotificationContext'
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
import VerifyEmailPage from './components/VerifyEmailPage'
import OnboardingCarousel from './components/Onboarding/OnboardingCarousel'
import { useOnboarding } from './hooks/useOnboarding'
import './App.css'

import AnalyticsView from './components/AnalyticsView'
import ConnectionsView from './components/ConnectionsView'

type AuthView = 'login' | 'register' | 'forgot-password' | 'reset-password' | 'verify-email'

function AppContent() {
  const [currentView, setCurrentView] = useState<'library' | 'newBook' | 'benchmark' | 'analytics' | 'connections'>('newBook')
  const [readingBookId, setReadingBookId] = useState<string | null>(null)
  const [authView, setAuthView] = useState<AuthView | null>(null)
  const [resetToken, setResetToken] = useState<string | null>(null)
  const [verifyToken, setVerifyToken] = useState<string | null>(null)
  const { isAuthenticated, isLoading } = useAuth()
  const { hasSeenCarousel, completeCarousel } = useOnboarding()

  // Controlla URL per token di verifica o reset all'avvio
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const path = window.location.pathname;
    
    // Gestisci /verify?token=xxx
    if (path === '/verify' || urlParams.has('token') && path.includes('verify')) {
      const token = urlParams.get('token');
      if (token) {
        setVerifyToken(token);
        setAuthView('verify-email');
        // Pulisci l'URL
        window.history.replaceState({}, document.title, '/');
      }
    }
    
    // Gestisci /reset-password?token=xxx
    if (path === '/reset-password' || path.includes('reset')) {
      const token = urlParams.get('token');
      if (token) {
        setResetToken(token);
        setAuthView('reset-password');
        // Pulisci l'URL
        window.history.replaceState({}, document.title, '/');
      }
    }
  }, []);

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
    if (authView === 'verify-email' && verifyToken) {
      return (
        <ErrorBoundary>
          <VerifyEmailPage 
            token={verifyToken}
            onNavigateToLogin={() => {
              setVerifyToken(null);
              setAuthView('login');
            }}
          />
        </ErrorBoundary>
      )
    }
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

  // Onboarding carousel (mostra al primo login)
  if (isAuthenticated && !hasSeenCarousel) {
    return (
      <ErrorBoundary>
        <OnboardingCarousel 
          onComplete={completeCarousel}
          onSkip={completeCarousel}
        />
      </ErrorBoundary>
    )
  }

  // App principale (autenticato)
  return (
    <ErrorBoundary>
      <div className="App">
        <Toaster 
          position="top-right"
          toastOptions={{
            duration: 4000,
            style: {
              background: 'var(--surface-elevated)',
              color: 'var(--text-primary)',
              boxShadow: 'var(--shadow-lg)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-md)',
              padding: '1rem',
              fontSize: '0.95rem',
            },
            success: {
              duration: 3000,
              iconTheme: {
                primary: 'var(--success)',
                secondary: 'white',
              },
            },
            error: {
              duration: 5000,
              iconTheme: {
                primary: 'var(--accent)',
                secondary: 'white',
              },
            },
            loading: {
              iconTheme: {
                primary: 'var(--accent)',
                secondary: 'white',
              },
            },
          }}
          containerStyle={{
            top: 20,
            right: 20,
          }}
        />
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
          ) : currentView === 'connections' ? (
            <ConnectionsView />
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
      <NotificationProvider>
        <AppContent />
      </NotificationProvider>
    </AuthProvider>
  )
}

export default App




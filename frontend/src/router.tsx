import { createBrowserRouter, Navigate } from 'react-router-dom';
import ErrorBoundary from './components/ErrorBoundary';
import RequireAuth from './components/routing/RequireAuth';
import RequireAdmin from './components/routing/RequireAdmin';
import DynamicForm from './components/DynamicForm';
import LibraryView from './components/LibraryView';
import BookReader from './components/BookReader';
import BenchmarkView from './components/BenchmarkView';
import AnalyticsView from './components/AnalyticsView';
import ConnectionsView from './components/ConnectionsView';
import LoginPage from './components/LoginPage';
import RegisterPage from './components/RegisterPage';
import ForgotPasswordPage from './components/ForgotPasswordPage';
import ResetPasswordPage from './components/ResetPasswordPage';
import VerifyEmailPage from './components/VerifyEmailPage';
import OnboardingCarousel from './components/Onboarding/OnboardingCarousel';
import Navigation from './components/Navigation';
import BottomNavigation from './components/BottomNavigation';
import Footer from './components/Footer';
import PrivacySettings from './components/PrivacySettings';
import PrivacyPolicy from './components/legal/PrivacyPolicy';
import CookiePolicy from './components/legal/CookiePolicy';
import TermsOfService from './components/legal/TermsOfService';
import { useAuth } from './contexts/AuthContext';
import { useOnboarding } from './hooks/useOnboarding';

/**
 * Layout per route protette (con Navigation e gestione onboarding)
 */
function ProtectedLayout({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth();
  const { hasSeenCarousel, completeCarousel } = useOnboarding();

  // Mostra onboarding se non visto
  if (isAuthenticated && !hasSeenCarousel) {
    return (
      <ErrorBoundary>
        <OnboardingCarousel 
          onComplete={completeCarousel}
          onSkip={completeCarousel}
        />
      </ErrorBoundary>
    );
  }

  return (
    <ErrorBoundary>
      <div className="App">
        <Navigation />
        <main className="app-main">
          {children}
          <Footer />
        </main>
        <BottomNavigation />
      </div>
    </ErrorBoundary>
  );
}

/**
 * Router principale dell'applicazione
 */
export const router = createBrowserRouter([
  {
    path: '/',
    element: (
      <RequireAuth>
        <Navigate to="/new" replace />
      </RequireAuth>
    ),
  },
  {
    path: '/login',
    element: (
      <ErrorBoundary>
        <LoginPage />
      </ErrorBoundary>
    ),
  },
  {
    path: '/register',
    element: (
      <ErrorBoundary>
        <RegisterPage />
      </ErrorBoundary>
    ),
  },
  {
    path: '/forgot-password',
    element: (
      <ErrorBoundary>
        <ForgotPasswordPage />
      </ErrorBoundary>
    ),
  },
  {
    path: '/reset-password',
    element: (
      <ErrorBoundary>
        <ResetPasswordPage />
      </ErrorBoundary>
    ),
  },
  {
    path: '/verify',
    element: (
      <ErrorBoundary>
        <VerifyEmailPage />
      </ErrorBoundary>
    ),
  },
  {
    path: '/new',
    element: (
      <RequireAuth>
        <ProtectedLayout>
          <DynamicForm />
        </ProtectedLayout>
      </RequireAuth>
    ),
  },
  {
    path: '/library',
    element: (
      <RequireAuth>
        <ProtectedLayout>
          <LibraryView />
        </ProtectedLayout>
      </RequireAuth>
    ),
  },
  {
    path: '/book/:sessionId',
    element: (
      <RequireAuth>
        <ErrorBoundary>
          <BookReader />
        </ErrorBoundary>
      </RequireAuth>
    ),
  },
  {
    path: '/benchmark',
    element: (
      <RequireAuth>
        <ProtectedLayout>
          <BenchmarkView />
        </ProtectedLayout>
      </RequireAuth>
    ),
  },
  {
    path: '/analytics',
    element: (
      <RequireAdmin>
        <ProtectedLayout>
          <AnalyticsView />
        </ProtectedLayout>
      </RequireAdmin>
    ),
  },
  {
    path: '/connections',
    element: (
      <RequireAuth>
        <ProtectedLayout>
          <ConnectionsView />
        </ProtectedLayout>
      </RequireAuth>
    ),
  },
  // Privacy Settings (autenticato)
  {
    path: '/settings/privacy',
    element: (
      <RequireAuth>
        <ProtectedLayout>
          <PrivacySettings />
        </ProtectedLayout>
      </RequireAuth>
    ),
  },
  // Pagine legali (pubbliche)
  {
    path: '/privacy',
    element: (
      <ErrorBoundary>
        <PrivacyPolicy />
      </ErrorBoundary>
    ),
  },
  {
    path: '/cookies',
    element: (
      <ErrorBoundary>
        <CookiePolicy />
      </ErrorBoundary>
    ),
  },
  {
    path: '/terms',
    element: (
      <ErrorBoundary>
        <TermsOfService />
      </ErrorBoundary>
    ),
  },
]);

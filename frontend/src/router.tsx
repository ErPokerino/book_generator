import { lazy, Suspense, type ReactNode } from 'react';
import { createBrowserRouter, Navigate } from 'react-router-dom';
import ErrorBoundary from './components/ErrorBoundary';
import RequireAuth from './components/routing/RequireAuth';
import RequireAdmin from './components/routing/RequireAdmin';
import Navigation from './components/Navigation';
import BottomNavigation from './components/BottomNavigation';
import Footer from './components/Footer';
import { useAuth } from './contexts/AuthContext';
import { useOnboarding } from './hooks/useOnboarding';

const DynamicForm = lazy(() => import('./components/DynamicForm'));
const LibraryView = lazy(() => import('./components/LibraryView'));
const BookReader = lazy(() => import('./components/BookReader'));
const BenchmarkView = lazy(() => import('./components/BenchmarkView'));
const AnalyticsView = lazy(() => import('./components/AnalyticsView'));
const ConnectionsView = lazy(() => import('./components/ConnectionsView'));
const NotificationsPage = lazy(() => import('./components/NotificationsPage'));
const LoginPage = lazy(() => import('./components/LoginPage'));
const RegisterPage = lazy(() => import('./components/RegisterPage'));
const ForgotPasswordPage = lazy(() => import('./components/ForgotPasswordPage'));
const ResetPasswordPage = lazy(() => import('./components/ResetPasswordPage'));
const VerifyEmailPage = lazy(() => import('./components/VerifyEmailPage'));
const OnboardingCarousel = lazy(() => import('./components/Onboarding/OnboardingCarousel'));
const PrivacySettings = lazy(() => import('./components/PrivacySettings'));
const WalletPage = lazy(() => import('./components/wallet/WalletPage'));
const PrivacyPolicy = lazy(() => import('./components/legal/PrivacyPolicy'));
const CookiePolicy = lazy(() => import('./components/legal/CookiePolicy'));
const TermsOfService = lazy(() => import('./components/legal/TermsOfService'));

function RouteFallback() {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '40vh',
        fontSize: '1rem',
        color: 'var(--text-secondary)',
      }}
    >
      Caricamento...
    </div>
  );
}

function LazyPage({ children }: { children: ReactNode }) {
  return <Suspense fallback={<RouteFallback />}>{children}</Suspense>;
}

/**
 * Layout per route protette (con Navigation e gestione onboarding)
 */
function ProtectedLayout({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth();
  const { hasSeenCarousel, completeCarousel } = useOnboarding();

  // Mostra onboarding se non visto
  if (isAuthenticated && !hasSeenCarousel) {
    return (
      <ErrorBoundary>
        <LazyPage>
          <OnboardingCarousel 
            onComplete={completeCarousel}
            onSkip={completeCarousel}
          />
        </LazyPage>
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
        <LazyPage>
          <LoginPage />
        </LazyPage>
      </ErrorBoundary>
    ),
  },
  {
    path: '/register',
    element: (
      <ErrorBoundary>
        <LazyPage>
          <RegisterPage />
        </LazyPage>
      </ErrorBoundary>
    ),
  },
  {
    path: '/forgot-password',
    element: (
      <ErrorBoundary>
        <LazyPage>
          <ForgotPasswordPage />
        </LazyPage>
      </ErrorBoundary>
    ),
  },
  {
    path: '/reset-password',
    element: (
      <ErrorBoundary>
        <LazyPage>
          <ResetPasswordPage />
        </LazyPage>
      </ErrorBoundary>
    ),
  },
  {
    path: '/verify',
    element: (
      <ErrorBoundary>
        <LazyPage>
          <VerifyEmailPage />
        </LazyPage>
      </ErrorBoundary>
    ),
  },
  {
    path: '/new',
    element: (
      <RequireAuth>
        <ProtectedLayout>
          <LazyPage>
            <DynamicForm />
          </LazyPage>
        </ProtectedLayout>
      </RequireAuth>
    ),
  },
  {
    path: '/library',
    element: (
      <RequireAuth>
        <ProtectedLayout>
          <LazyPage>
            <LibraryView />
          </LazyPage>
        </ProtectedLayout>
      </RequireAuth>
    ),
  },
  {
    path: '/book/:sessionId',
    element: (
      <RequireAuth>
        <ErrorBoundary>
          <LazyPage>
            <BookReader />
          </LazyPage>
        </ErrorBoundary>
      </RequireAuth>
    ),
  },
  {
    path: '/benchmark',
    element: (
      <RequireAuth>
        <ProtectedLayout>
          <LazyPage>
            <BenchmarkView />
          </LazyPage>
        </ProtectedLayout>
      </RequireAuth>
    ),
  },
  {
    path: '/analytics',
    element: (
      <RequireAdmin>
        <ProtectedLayout>
          <LazyPage>
            <AnalyticsView />
          </LazyPage>
        </ProtectedLayout>
      </RequireAdmin>
    ),
  },
  {
    path: '/notifications',
    element: (
      <RequireAuth>
        <ProtectedLayout>
          <LazyPage>
            <NotificationsPage />
          </LazyPage>
        </ProtectedLayout>
      </RequireAuth>
    ),
  },
  {
    path: '/connections',
    element: (
      <RequireAuth>
        <ProtectedLayout>
          <LazyPage>
            <ConnectionsView />
          </LazyPage>
        </ProtectedLayout>
      </RequireAuth>
    ),
  },
  // Wallet (Crediti)
  {
    path: '/wallet',
    element: (
      <RequireAuth>
        <ProtectedLayout>
          <LazyPage>
            <WalletPage />
          </LazyPage>
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
          <LazyPage>
            <PrivacySettings />
          </LazyPage>
        </ProtectedLayout>
      </RequireAuth>
    ),
  },
  // Pagine legali (pubbliche)
  {
    path: '/privacy',
    element: (
      <ErrorBoundary>
        <LazyPage>
          <PrivacyPolicy />
        </LazyPage>
      </ErrorBoundary>
    ),
  },
  {
    path: '/cookies',
    element: (
      <ErrorBoundary>
        <LazyPage>
          <CookiePolicy />
        </LazyPage>
      </ErrorBoundary>
    ),
  },
  {
    path: '/terms',
    element: (
      <ErrorBoundary>
        <LazyPage>
          <TermsOfService />
        </LazyPage>
      </ErrorBoundary>
    ),
  },
]);

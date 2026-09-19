import { lazy, Suspense, type ReactNode } from 'react';
import { createBrowserRouter, Navigate, useLocation } from 'react-router-dom';
import ErrorBoundary from './components/ErrorBoundary';
import Navigation from './components/Navigation';
import BottomNavigation from './components/BottomNavigation';
import Footer from './components/Footer';
import { useOnboarding } from './hooks/useOnboarding';

const DynamicForm = lazy(() => import('./components/DynamicForm'));
const MangaBetaView = lazy(() => import('./components/MangaBetaView'));
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

function LegacyMangaRedirect() {
  const location = useLocation();
  return <Navigate to={`/manga${location.search}`} replace />;
}

/**
 * Layout principale (con Navigation e gestione onboarding locale)
 */
function AppLayout({ children }: { children: ReactNode }) {
  const { hasSeenCarousel, completeCarousel } = useOnboarding();

  // Mostra onboarding se non visto (solo localStorage, niente login)
  if (!hasSeenCarousel) {
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
 * Router principale dell'applicazione (uso locale single-user, senza autenticazione)
 */
export const router = createBrowserRouter([
  {
    path: '/',
    element: (
      <Navigate to="/new" replace />
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
      <AppLayout>
        <LazyPage>
          <DynamicForm />
        </LazyPage>
      </AppLayout>
    ),
  },
  {
    path: '/manga',
    element: (
      <AppLayout>
        <LazyPage>
          <MangaBetaView />
        </LazyPage>
      </AppLayout>
    ),
  },
  {
    path: '/beta/manga',
    element: (
      <LegacyMangaRedirect />
    ),
  },
  {
    path: '/library',
    element: (
      <AppLayout>
        <LazyPage>
          <LibraryView />
        </LazyPage>
      </AppLayout>
    ),
  },
  {
    path: '/book/:sessionId',
    element: (
      <ErrorBoundary>
        <LazyPage>
          <BookReader />
        </LazyPage>
      </ErrorBoundary>
    ),
  },
  {
    path: '/benchmark',
    element: (
      <AppLayout>
        <LazyPage>
          <BenchmarkView />
        </LazyPage>
      </AppLayout>
    ),
  },
  {
    path: '/analytics',
    element: (
      <AppLayout>
        <LazyPage>
          <AnalyticsView />
        </LazyPage>
      </AppLayout>
    ),
  },
  {
    path: '/notifications',
    element: (
      <AppLayout>
        <LazyPage>
          <NotificationsPage />
        </LazyPage>
      </AppLayout>
    ),
  },
  {
    path: '/connections',
    element: (
      <AppLayout>
        <LazyPage>
          <ConnectionsView />
        </LazyPage>
      </AppLayout>
    ),
  },
  // Wallet (Crediti)
  {
    path: '/wallet',
    element: (
      <AppLayout>
        <LazyPage>
          <WalletPage />
        </LazyPage>
      </AppLayout>
    ),
  },
  // Privacy Settings (autenticato)
  {
    path: '/settings/privacy',
    element: (
      <AppLayout>
        <LazyPage>
          <PrivacySettings />
        </LazyPage>
      </AppLayout>
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

import { lazy, Suspense, type ReactNode } from 'react';
import { createBrowserRouter, Navigate, useLocation } from 'react-router-dom';
import ErrorBoundary from './components/ErrorBoundary';
import Navigation from './components/Navigation';
import BottomNavigation from './components/BottomNavigation';
import { useOnboarding } from './hooks/useOnboarding';

const DynamicForm = lazy(() => import('./components/DynamicForm'));
const MangaBetaView = lazy(() => import('./components/MangaBetaView'));
const EssayApp = lazy(() => import('./essay/EssayApp'));
const LibraryView = lazy(() => import('./components/LibraryView'));
const ManuscriptStudio = lazy(() => import('./components/ManuscriptStudio'));
const BookReader = lazy(() => import('./components/BookReader'));
const BenchmarkView = lazy(() => import('./components/BenchmarkView'));
const SettingsView = lazy(() => import('./components/SettingsView'));
const WorkReader = lazy(() => import('./components/WorkReader'));
const AnalyticsView = lazy(() => import('./components/AnalyticsView'));
const OnboardingCarousel = lazy(() => import('./components/Onboarding/OnboardingCarousel'));

function RouteFallback() {
  return (
    <div className="route-fallback" role="status">
      Caricamento
    </div>
  );
}

function LazyPage({ children }: { children: ReactNode }) {
  return <Suspense fallback={<RouteFallback />}>{children}</Suspense>;
}

function LegacyMangaRedirect() {
  const location = useLocation();
  return <Navigate to={`/comics${location.search}`} replace />;
}

function NarrativeCreation() {
  const location = useLocation();
  return <DynamicForm key={location.key} />;
}

function AppLayout({ children }: { children: ReactNode }) {
  const { hasSeenCarousel, completeCarousel } = useOnboarding();

  if (!hasSeenCarousel) {
    return (
      <ErrorBoundary>
        <LazyPage>
          <OnboardingCarousel onComplete={completeCarousel} onSkip={completeCarousel} />
        </LazyPage>
      </ErrorBoundary>
    );
  }

  return (
    <ErrorBoundary>
      <div className="App">
        <Navigation />
        <main className="app-main">{children}</main>
        <BottomNavigation />
      </div>
    </ErrorBoundary>
  );
}

export const router = createBrowserRouter([
  {
    path: '/',
    element: <Navigate to="/library" replace />,
  },
  {
    path: '/login',
    element: <Navigate to="/library" replace />,
  },
  {
    path: '/register',
    element: <Navigate to="/new" replace />,
  },
  {
    path: '/new',
    element: (
      <AppLayout>
        <LazyPage>
          <NarrativeCreation />
        </LazyPage>
      </AppLayout>
    ),
  },
  {
    path: '/comics',
    element: (
      <AppLayout>
        <LazyPage>
          <MangaBetaView />
        </LazyPage>
      </AppLayout>
    ),
  },
  { path: '/manga', element: <LegacyMangaRedirect /> },
  { path: '/read/:kind/:id', element: <ErrorBoundary><LazyPage><WorkReader /></LazyPage></ErrorBoundary> },
  { path: '/settings', element: <AppLayout><LazyPage><SettingsView /></LazyPage></AppLayout> },
  { path: '/new/essay', element: <AppLayout><LazyPage><EssayApp /></LazyPage></AppLayout> },
  { path: '/essay/:id', element: <AppLayout><LazyPage><EssayApp view="workspace" /></LazyPage></AppLayout> },
  {
    path: '/beta/manga',
    element: <LegacyMangaRedirect />,
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
  { path: '/studio/:sessionId', element: <ErrorBoundary><LazyPage><ManuscriptStudio /></LazyPage></ErrorBoundary> },
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
]);

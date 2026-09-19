import { FormEvent, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  downloadMangaPdf,
  getAppConfig,
  getManga,
  getMangaPageImageUrl,
  getMangaProgress,
  MangaCharacterInput,
  MangaCreateRequest,
  MangaProgress,
  MangaReaderResponse,
  MangaType,
  restoreSession,
  resumeMangaGeneration,
  startMangaGeneration,
  type AppConfig,
} from '../api/client';
import ProgressBar from './ui/ProgressBar';
import { useToast } from '../hooks/useToast';
import ModelSettingsPanel, {
  MANGA_STAGES,
  ModelSettingsValue,
  buildModelOverrides,
} from './ModelSettingsPanel';
import { elapsedMinutesBetween, formatElapsed, formatEstimateCost } from '../utils/estimateGeneration';
import './MangaBetaView.css';

const STORAGE_KEY = 'current_manga_session_id';
const DEFAULT_MANGA_PAGE_COUNT = 10;
const MIN_MANGA_PAGES = 10;
const MAX_MANGA_PAGES = 100;
const DEFAULT_PAGE_COLOR_MODE: MangaCreateRequest['page_color_mode'] = 'black_and_white';

const MANGA_TYPE_OPTIONS: Array<{ value: MangaType; label: string; description: string }> = [
  { value: 'shonen', label: 'Shonen', description: 'Azione / avventura' },
  { value: 'shojo', label: 'Shojo', description: 'Romantico / emotivo' },
  { value: 'seinen', label: 'Seinen', description: 'Maturo / realistico' },
  { value: 'josei', label: 'Josei', description: 'Quotidiano / relazioni' },
  { value: 'kodomo', label: 'Kodomo', description: 'Per bambini' },
];

const PAGE_COLOR_MODE_OPTIONS: Array<{
  value: MangaCreateRequest['page_color_mode'];
  label: string;
  description: string;
}> = [
  { value: 'black_and_white', label: 'Bianco e nero', description: 'Pagine interne in scala di grigi' },
  { value: 'color', label: 'A colori', description: 'Pagine interne interamente a colori' },
];

interface MangaBetaFormState {
  title: string;
  plot: string;
  manga_type: MangaType;
  page_color_mode: MangaCreateRequest['page_color_mode'];
  main_characters: MangaCharacterInput[];
  page_count: number;
}

function defaultMangaModelSettings(): ModelSettingsValue {
  return {
    stageModels: Object.fromEntries(MANGA_STAGES.map((stage) => [stage.id, stage.defaultModel])),
  };
}

const createEmptyCharacter = (): MangaCharacterInput => ({ name: '', description: '' });

const createDefaultFormState = (): MangaBetaFormState => ({
  title: '',
  plot: '',
  manga_type: 'shonen',
  page_color_mode: DEFAULT_PAGE_COLOR_MODE,
  main_characters: [createEmptyCharacter()],
  page_count: DEFAULT_MANGA_PAGE_COUNT,
});

function normalizeCharacters(characters: MangaCharacterInput[]): MangaCharacterInput[] {
  return characters
    .map((character) => ({
      name: character.name.trim(),
      description: character.description.trim(),
    }))
    .filter((character) => character.name && character.description);
}

function formatMangaType(type: MangaType): string {
  return MANGA_TYPE_OPTIONS.find((option) => option.value === type)?.label ?? type;
}

function formatPageRange(minPages?: number | null, maxPages?: number | null): string {
  const normalizedMin = minPages ?? DEFAULT_MANGA_PAGE_COUNT;
  const normalizedMax = maxPages ?? normalizedMin;
  return normalizedMin === normalizedMax
    ? `${normalizedMin} pagine`
    : `${normalizedMin}-${normalizedMax} pagine`;
}

function formatPageCount(pageCount?: number | null): string {
  return `${pageCount ?? DEFAULT_MANGA_PAGE_COUNT} pagine`;
}

function formatPageColorMode(mode?: MangaCreateRequest['page_color_mode'] | null): string {
  return PAGE_COLOR_MODE_OPTIONS.find((option) => option.value === mode)?.label ?? 'Bianco e nero';
}

function RequiredMark() {
  return (
    <span className="manga-required" aria-hidden="true">
      {' '}
      *
    </span>
  );
}

function formatPageStatus(status: MangaReaderResponse['pages'][number]['status']): string {
  const labels: Record<MangaReaderResponse['pages'][number]['status'], string> = {
    pending: 'In attesa',
    completed: 'Completata',
    failed: 'Errore',
  };
  return labels[status] ?? status;
}

function ReaderPages({
  sessionId,
  pages,
}: {
  sessionId: string;
  pages: MangaReaderResponse['pages'];
}) {
  if (pages.length === 0) {
    return (
      <div className="manga-empty-pages">
        Le pagine compariranno qui appena saranno pronte.
      </div>
    );
  }

  return (
    <div className="manga-pages-grid">
      {pages.map((page) => {
        const imageUrl = page.image_url || getMangaPageImageUrl(sessionId, page.page_number);
        return (
          <article key={page.page_number} className="manga-page-card">
            <div className="manga-page-card-header">
              <span className="manga-page-number">Pagina {page.page_number}</span>
              <span className={`manga-page-status ${page.status}`}>{formatPageStatus(page.status)}</span>
            </div>
            <h4>{page.title}</h4>
            {imageUrl ? (
              <img
                src={imageUrl}
                alt={`Pagina ${page.page_number} del manga`}
                className="manga-page-image"
                loading="lazy"
              />
            ) : (
              <div className="manga-page-placeholder">Immagine in preparazione...</div>
            )}
            <p className="manga-page-summary">{page.summary}</p>
          </article>
        );
      })}
    </div>
  );
}

function MangaSessionPanel({
  sessionId,
  initialProgress,
  initialReader,
  onStartOver,
}: {
  sessionId: string;
  initialProgress: MangaProgress | null;
  initialReader: MangaReaderResponse | null;
  onStartOver: () => void;
}) {
  const toast = useToast();
  const [progress, setProgress] = useState<MangaProgress | null>(initialProgress);
  const [reader, setReader] = useState<MangaReaderResponse | null>(initialReader);
  const [isPolling, setIsPolling] = useState(true);
  const [isResuming, setIsResuming] = useState(false);
  const [isDownloadingPdf, setIsDownloadingPdf] = useState(false);
  const [fatalError, setFatalError] = useState<string | null>(null);
  const [appConfig, setAppConfig] = useState<AppConfig | null>(null);
  const [nowMs, setNowMs] = useState(() => Date.now());
  const progressRef = useRef<MangaProgress | null>(initialProgress);
  const failuresRef = useRef(0);

  useEffect(() => {
    getAppConfig()
      .then(setAppConfig)
      .catch((error) => {
        console.warn('[MangaBetaView] Errore nel caricamento config app:', error);
      });
  }, []);

  useEffect(() => {
    if (!sessionId || !isPolling) return;

    let cancelled = false;
    let timeoutId: number | null = null;

    const pollOnce = async () => {
      try {
        const nextProgress = await getMangaProgress(sessionId);
        const nextReader = await getManga(sessionId);
        if (cancelled) return;

        setProgress(nextProgress);
        setReader(nextReader);
        progressRef.current = nextProgress;
        failuresRef.current = 0;
        setFatalError(null);

        if (nextProgress.is_complete || nextProgress.is_paused || nextProgress.status === 'failed') {
          setIsPolling(false);
          return;
        }
      } catch (error) {
        if (cancelled) return;
        const nextFailures = failuresRef.current + 1;
        failuresRef.current = nextFailures;
        if (nextFailures % 3 === 1) {
          toast.error(`Connessione instabile (tentativo ${nextFailures}/10). Riprovo...`);
        }
        if (nextFailures >= 10) {
          setFatalError(error instanceof Error ? error.message : 'Errore nel recupero del manga');
          setIsPolling(false);
          return;
        }
      }

      const basePolling = appConfig?.frontend?.polling_interval ?? 2000;
      const failures = failuresRef.current;
      const nextDelay = failures > 0
        ? Math.min(15000, basePolling * Math.pow(2, Math.min(failures, 3)))
        : basePolling;
      timeoutId = window.setTimeout(pollOnce, nextDelay);
    };

    pollOnce();

    return () => {
      cancelled = true;
      if (timeoutId != null) {
        window.clearTimeout(timeoutId);
      }
    };
  }, [sessionId, isPolling, appConfig, toast]);

  const generationActive = Boolean(
    progress && !progress.is_complete && !progress.is_paused && progress.status !== 'failed',
  );

  useEffect(() => {
    if (!generationActive) {
      return;
    }
    const timer = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [generationActive]);

  const visiblePages = reader?.pages ?? progress?.completed_pages ?? [];
  const requestedMinPages =
    progress?.requested_min_pages
    ?? reader?.requested_min_pages
    ?? appConfig?.manga_generation?.page_count
    ?? DEFAULT_MANGA_PAGE_COUNT;
  const requestedMaxPages =
    progress?.requested_max_pages
    ?? reader?.requested_max_pages
    ?? appConfig?.manga_generation?.page_count
    ?? DEFAULT_MANGA_PAGE_COUNT;
  const plannedTotalPages =
    progress?.planned_total_pages
    ?? reader?.planned_total_pages
    ?? (reader?.total_pages && reader.total_pages > 0 ? reader.total_pages : null);
  const requestedPageCount =
    plannedTotalPages
    ?? (requestedMinPages === requestedMaxPages ? requestedMinPages : null);
  const pageColorMode = reader?.page_color_mode ?? DEFAULT_PAGE_COLOR_MODE;
  const totalSteps = plannedTotalPages ?? progress?.total_steps ?? appConfig?.manga_generation?.page_count ?? DEFAULT_MANGA_PAGE_COUNT;
  const currentStep = Math.min(progress?.current_step ?? visiblePages.length, totalSteps);
  const progressPercentage = totalSteps > 0 ? Math.round((currentStep / totalSteps) * 100) : 0;
  const showPageProgress =
    (progress?.current_phase ?? 'planning') === 'generating_pages' || Boolean(progress?.is_complete);
  const costBreakdown = (progress?.cost_breakdown ?? {}) as Record<string, number>;
  const currentCostEur =
    typeof progress?.current_cost_eur === 'number'
      ? progress.current_cost_eur
      : typeof costBreakdown.current_cost_eur === 'number'
        ? costBreakdown.current_cost_eur
        : null;
  const estimatedCostEur =
    typeof progress?.estimated_cost === 'number'
      ? progress.estimated_cost
      : typeof costBreakdown.estimated_total_eur === 'number'
        ? costBreakdown.estimated_total_eur
        : null;
  const elapsedMinutes = elapsedMinutesBetween(
    progress?.started_at,
    nowMs,
    progress?.is_complete || progress?.is_paused || progress?.status === 'failed'
      ? progress?.completed_at ?? progress?.updated_at
      : null,
  );

  if (fatalError) {
    return (
      <div className="manga-beta-shell">
        <div className="manga-status-card error">
          <h2>Errore nel lettore manga</h2>
          <p>{fatalError}</p>
          <button type="button" className="manga-secondary-button" onClick={onStartOver}>
            Torna al form
          </button>
        </div>
      </div>
    );
  }

  if (!progress) {
    return (
      <div className="manga-beta-shell">
        <div className="manga-status-card">
          <h2>Sto recuperando la sessione manga...</h2>
          <p>Attendi qualche istante.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="manga-beta-shell">
      <section className="manga-hero-card">
        <div>
          <span className="manga-beta-badge">Manga</span>
          <h1>{reader?.title || 'Manga in generazione'}</h1>
          <p className="manga-subtitle">
            {reader && plannedTotalPages
              ? `${formatMangaType(reader.manga_type)} da ${plannedTotalPages} pagine, interni ${formatPageColorMode(pageColorMode).toLowerCase()} e doppia copertina.`
              : requestedPageCount
              ? `Pagine richieste: ${formatPageCount(requestedPageCount)}. Sto preparando il lettore dedicato del manga.`
              : `Range richiesto: ${formatPageRange(requestedMinPages, requestedMaxPages)}. Sto preparando il lettore dedicato del manga.`}
          </p>
        </div>
        <button type="button" className="manga-secondary-button" onClick={onStartOver}>
          Nuovo manga
        </button>
      </section>

      {reader?.synopsis && (
        <section className="manga-meta-grid">
          <article className="manga-meta-card">
            <h3>Sinossi</h3>
            <p>{reader.synopsis}</p>
          </article>
          <article className="manga-meta-card">
            <h3>Personaggi</h3>
            <div className="manga-character-list">
              {reader.characters.length > 0 ? (
                reader.characters.map((character) => (
                  <div key={character.name} className="manga-character-item">
                    <strong>{character.name}</strong>
                    <span>{character.role || character.personality}</span>
                  </div>
                ))
              ) : (
                <span className="manga-muted">Le schede appariranno al termine del planning.</span>
              )}
            </div>
          </article>
        </section>
      )}

      <section className="manga-status-card">
        <div className="manga-status-header">
          <div>
            <h2>
              {progress.current_phase === 'planning'
                ? 'Sto preparando trama e storyboard'
                : progress.current_phase === 'generating_cover'
                ? 'Sto creando la copertina'
                : progress.current_phase === 'generating_back_cover'
                ? 'Sto creando la retro-copertina'
                : progress.is_complete
                ? 'Manga completato'
                : 'Generazione pagina per pagina'}
            </h2>
            <p>
              {progress.current_phase === 'planning'
                ? requestedPageCount
                  ? `Definisco titolo, sinossi, bible personaggi e storyboard per un manga di ${formatPageCount(requestedPageCount)}.`
                  : `Definisco titolo, sinossi, bible personaggi e lunghezza finale nel range ${formatPageRange(requestedMinPages, requestedMaxPages)}.`
                : progress.current_phase === 'generating_cover'
                ? 'Genero una copertina coerente con trama, stile e personaggi prima di passare alle pagine.'
                : progress.current_phase === 'generating_back_cover'
                ? 'Sto creando la retro-copertina finale, coerente con il finale del manga e con la copertina iniziale.'
                : progress.current_page_title
                ? `Pagina corrente: ${progress.current_page_title}`
                : 'Sto aggiornando il lettore dedicato.'}
            </p>
          </div>
          {showPageProgress && (
            <div className="manga-progress-counter">
              {currentStep} / {totalSteps}
            </div>
          )}
        </div>

        {showPageProgress ? (
          <ProgressBar percentage={progressPercentage} />
        ) : (
          <div className="manga-planning-loader">
            <div className="manga-spinner" />
            <span>
              {progress.current_phase === 'generating_cover'
                ? 'Copertina in preparazione...'
                : progress.current_phase === 'generating_back_cover'
                ? 'Retro-copertina in preparazione...'
                : 'Planning in corso...'}
            </span>
          </div>
        )}

        <div className="manga-generation-metrics">
          {elapsedMinutes != null && (
            <div className="manga-metric-chip">
              <span>Tempo trascorso</span>
              <strong>{formatElapsed(elapsedMinutes)}</strong>
            </div>
          )}
          {currentCostEur != null && (
            <div className="manga-metric-chip">
              <span>Costo attuale</span>
              <strong>{formatEstimateCost(currentCostEur)}</strong>
            </div>
          )}
          {estimatedCostEur != null && !progress.is_complete && (
            <div className="manga-metric-chip">
              <span>Costo stimato finale</span>
              <strong>{formatEstimateCost(estimatedCostEur)}</strong>
            </div>
          )}
        </div>

        {progress.is_paused && (
          <div className="manga-paused-box">
            <div>
              <strong>Generazione in pausa</strong>
              <p>{progress.error || 'Il processo si e fermato e puo essere ripreso.'}</p>
            </div>
            <button
              type="button"
              className="manga-primary-button"
              disabled={isResuming}
              onClick={async () => {
                try {
                  setIsResuming(true);
                  await resumeMangaGeneration(sessionId);
                  toast.success('Generazione manga ripresa');
                  setIsPolling(true);
                } catch (error) {
                  toast.error(error instanceof Error ? error.message : 'Errore nella ripresa del manga');
                } finally {
                  setIsResuming(false);
                }
              }}
            >
              {isResuming ? 'Riprendo...' : 'Riprendi generazione'}
            </button>
          </div>
        )}

        {!progress.is_paused && progress.error && (
          <div className="manga-inline-error">{progress.error}</div>
        )}
      </section>

      <section className="manga-reader-section">
        <div className="manga-reader-header">
          <h2>Lettore manga</h2>
          <div className="manga-reader-actions">
            <span>
              {plannedTotalPages
                ? `${visiblePages.length} / ${plannedTotalPages} pagine disponibili`
                : `${visiblePages.length} pagine disponibili`}
            </span>
            {progress.is_complete && (
              <button
                type="button"
                className="manga-secondary-button"
                disabled={isDownloadingPdf}
                onClick={async () => {
                  try {
                    setIsDownloadingPdf(true);
                    const { blob, filename } = await downloadMangaPdf(sessionId);
                    const url = window.URL.createObjectURL(blob);
                    const anchor = document.createElement('a');
                    anchor.href = url;
                    anchor.download = filename;
                    document.body.appendChild(anchor);
                    anchor.click();
                    window.setTimeout(() => {
                      window.URL.revokeObjectURL(url);
                      document.body.removeChild(anchor);
                    }, 100);
                    toast.success('PDF del manga scaricato');
                  } catch (error) {
                    toast.error(error instanceof Error ? error.message : 'Errore nel download del PDF manga');
                  } finally {
                    setIsDownloadingPdf(false);
                  }
                }}
              >
                {isDownloadingPdf ? 'Download in corso...' : 'Scarica PDF'}
              </button>
            )}
          </div>
        </div>
        {reader?.cover_image_url && (
          <article className="manga-cover-card">
            <span className="manga-page-number">Copertina frontale</span>
            <img
              src={reader.cover_image_url}
              alt={`Copertina di ${reader.title}`}
              className="manga-cover-image"
              loading="lazy"
            />
          </article>
        )}
        <ReaderPages sessionId={sessionId} pages={visiblePages} />
        {reader?.back_cover_image_url && (
          <article className="manga-cover-card">
            <span className="manga-page-number">Retro copertina</span>
            <img
              src={reader.back_cover_image_url}
              alt={`Retro copertina di ${reader.title}`}
              className="manga-cover-image"
              loading="lazy"
            />
          </article>
        )}
      </section>
    </div>
  );
}

export default function MangaBetaView() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const toast = useToast();
  const [formState, setFormState] = useState<MangaBetaFormState>(createDefaultFormState);
  const [modelSettings, setModelSettings] = useState<ModelSettingsValue>(defaultMangaModelSettings);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [appConfig, setAppConfig] = useState<AppConfig | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [initialProgress, setInitialProgress] = useState<MangaProgress | null>(null);
  const [initialReader, setInitialReader] = useState<MangaReaderResponse | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isRestoring, setIsRestoring] = useState(true);
  const sessionFromQuery = searchParams.get('session');
  const minPageLimit = appConfig?.manga_generation?.min_page_count ?? MIN_MANGA_PAGES;
  const maxPageLimit = appConfig?.manga_generation?.max_page_count ?? MAX_MANGA_PAGES;
  const defaultPageCount = appConfig?.manga_generation?.page_count ?? DEFAULT_MANGA_PAGE_COUNT;

  useEffect(() => {
    getAppConfig()
      .then(setAppConfig)
      .catch((error) => {
        console.warn('[MangaBetaView] Errore nel caricamento config app:', error);
      });
  }, []);

  useEffect(() => {
    if (sessionId) return;
    setFormState((current) => {
      if (current.page_count !== DEFAULT_MANGA_PAGE_COUNT) {
        return current;
      }
      return {
        ...current,
        page_count: defaultPageCount,
      };
    });
  }, [defaultPageCount, sessionId]);

  useEffect(() => {
    const restoreStoredSession = async () => {
      if (sessionFromQuery) {
        window.localStorage.setItem(STORAGE_KEY, sessionFromQuery);
        setSessionId(sessionFromQuery);
        setInitialProgress(null);
        setInitialReader(null);
        setIsRestoring(false);
        return;
      }

      const storedSessionId = window.localStorage.getItem(STORAGE_KEY);
      if (!storedSessionId) {
        setIsRestoring(false);
        return;
      }

      try {
        const restored = await restoreSession(storedSessionId);
        if (restored.content_type !== 'manga') {
          window.localStorage.removeItem(STORAGE_KEY);
          setIsRestoring(false);
          return;
        }

        if (restored.manga_form_data) {
          const restoredPageCount =
            restored.manga_form_data.page_count
            ?? restored.manga?.planned_total_pages
            ?? restored.manga_progress?.planned_total_pages
            ?? restored.manga_form_data.min_pages
            ?? restored.manga_form_data.max_pages
            ?? defaultPageCount;
          setFormState({
            title: restored.manga_form_data.title || '',
            plot: restored.manga_form_data.plot,
            manga_type: restored.manga_form_data.manga_type,
            page_color_mode: restored.manga_form_data.page_color_mode,
            page_count: restoredPageCount,
            main_characters:
              restored.manga_form_data.main_characters.length > 0
                ? restored.manga_form_data.main_characters
                : [createEmptyCharacter()],
          });
        }

        setSessionId(restored.session_id);
        setInitialProgress(restored.manga_progress ?? null);
        setInitialReader(restored.manga ?? null);
      } catch (error) {
        console.warn('[MangaBetaView] Ripristino sessione manga fallito:', error);
        window.localStorage.removeItem(STORAGE_KEY);
      } finally {
        setIsRestoring(false);
      }
    };

    restoreStoredSession();
  }, [defaultPageCount, sessionFromQuery]);

  const cleanedCharacters = useMemo(
    () => normalizeCharacters(formState.main_characters),
    [formState.main_characters],
  );

  const handleStartOver = () => {
    window.localStorage.removeItem(STORAGE_KEY);
    setSessionId(null);
    setInitialProgress(null);
    setInitialReader(null);
    setFormState(createDefaultFormState());
    setModelSettings(defaultMangaModelSettings());
    navigate('/manga', { replace: true });
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nextErrors: Record<string, string> = {};
    if (!formState.plot.trim()) {
      nextErrors.plot = 'Inserisci la trama di partenza.';
    }
    if (cleanedCharacters.length === 0) {
      nextErrors.characters = 'Aggiungi almeno un personaggio con nome e descrizione.';
    }
    if (formState.page_count < minPageLimit || formState.page_count > maxPageLimit) {
      nextErrors.page_count = `Seleziona un numero di pagine tra ${minPageLimit} e ${maxPageLimit}.`;
    }
    setFieldErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) {
      toast.error(Object.values(nextErrors)[0]);
      return;
    }

    const payload: MangaCreateRequest = {
      title: formState.title.trim() || undefined,
      plot: formState.plot.trim(),
      manga_type: formState.manga_type,
      page_color_mode: formState.page_color_mode,
      main_characters: cleanedCharacters,
      page_count: formState.page_count,
      min_pages: formState.page_count,
      max_pages: formState.page_count,
      model_overrides: buildModelOverrides(modelSettings, MANGA_STAGES),
    };

    try {
      setIsSubmitting(true);
      const response = await startMangaGeneration(payload);
      window.localStorage.setItem(STORAGE_KEY, response.session_id);
      navigate(`/manga?session=${response.session_id}`, { replace: true });
      setSessionId(response.session_id);
      setInitialProgress(null);
      setInitialReader(null);
      toast.success('Generazione manga avviata');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Errore nell\'avvio del manga');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isRestoring) {
    return (
      <div className="manga-beta-shell">
        <div className="manga-status-card">
          <h2>Sto controllando se esiste una sessione manga da riprendere...</h2>
          <p>Attendi qualche istante.</p>
        </div>
      </div>
    );
  }

  if (sessionId) {
    return (
      <MangaSessionPanel
        sessionId={sessionId}
        initialProgress={initialProgress}
        initialReader={initialReader}
        onStartOver={handleStartOver}
      />
    );
  }

  return (
    <div className="manga-beta-shell">
      <section className="manga-hero-card">
        <div>
          <span className="manga-beta-badge">Manga</span>
          <h1>Genera un manga</h1>
          <p className="manga-subtitle">
            Inserisci trama, tipo di manga, personaggi principali, modalita colore e il numero di pagine desiderato da {minPageLimit} a {maxPageLimit}. Poi il sistema genera copertina frontale, pagine e retro-copertina finale.
          </p>
        </div>
      </section>

      <form className="manga-form-card" onSubmit={handleSubmit}>
        <ModelSettingsPanel
          value={modelSettings}
          onChange={setModelSettings}
          stages={MANGA_STAGES}
          kind="manga"
          mangaPageCount={formState.page_count}
        />
        <div className="manga-form-grid">
          <label className="manga-field">
            <span>Titolo opzionale</span>
            <input
              type="text"
              value={formState.title}
              onChange={(event) => setFormState((current) => ({ ...current, title: event.target.value }))}
              placeholder="Lascia vuoto per farlo scegliere al planner"
            />
          </label>

          <label className="manga-field">
            <span>Tipo di manga</span>
            <select
              value={formState.manga_type}
              onChange={(event) =>
                setFormState((current) => ({ ...current, manga_type: event.target.value as MangaType }))
              }
            >
              {MANGA_TYPE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label} - {option.description}
                </option>
              ))}
            </select>
          </label>

          <label className="manga-field">
            <span>Stile colore pagine interne</span>
            <select
              value={formState.page_color_mode}
              onChange={(event) =>
                setFormState((current) => ({
                  ...current,
                  page_color_mode: event.target.value as MangaCreateRequest['page_color_mode'],
                }))
              }
            >
              {PAGE_COLOR_MODE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label} - {option.description}
                </option>
              ))}
            </select>
          </label>

          <label className={`manga-field${fieldErrors.page_count ? ' has-error' : ''}`}>
            <span>
              Numero pagine
              <RequiredMark />
            </span>
            <input
              type="number"
              min={minPageLimit}
              max={maxPageLimit}
              step={1}
              required
              aria-required="true"
              value={formState.page_count}
              onChange={(event) => {
                setFieldErrors((current) => ({ ...current, page_count: '' }));
                setFormState((current) => ({
                  ...current,
                  page_count: Number(event.target.value),
                }));
              }}
            />
            {fieldErrors.page_count ? <em className="manga-field-error">{fieldErrors.page_count}</em> : null}
          </label>
        </div>

        <label className={`manga-field${fieldErrors.plot ? ' has-error' : ''}`}>
          <span>
            Trama di partenza
            <RequiredMark />
          </span>
          <textarea
            value={formState.plot}
            onChange={(event) => {
              setFieldErrors((current) => ({ ...current, plot: '' }));
              setFormState((current) => ({ ...current, plot: event.target.value }));
            }}
            rows={8}
            required
            aria-required="true"
            placeholder="Descrivi il conflitto, i protagonisti e il finale che vorresti ottenere."
          />
          {fieldErrors.plot ? <em className="manga-field-error">{fieldErrors.plot}</em> : null}
        </label>

        <div className="manga-characters-card">
          <div className="manga-characters-header">
            <div>
              <h3>
                Personaggi principali
                <RequiredMark />
              </h3>
              <p>Almeno un personaggio con nome e descrizione è obbligatorio, così il planner resta coerente tra le pagine.</p>
            </div>
            <button
              type="button"
              className="manga-secondary-button"
              onClick={() =>
                setFormState((current) => ({
                  ...current,
                  main_characters: [...current.main_characters, createEmptyCharacter()],
                }))
              }
            >
              Aggiungi personaggio
            </button>
          </div>

          <div className="manga-character-editor-list">
            {formState.main_characters.map((character, index) => (
              <div key={`character-${index}`} className="manga-character-editor">
                <label className="manga-field">
                  <span>
                    Nome
                    <RequiredMark />
                  </span>
                  <input
                    type="text"
                    value={character.name}
                    required
                    aria-required="true"
                    onChange={(event) => {
                      setFieldErrors((current) => ({ ...current, characters: '' }));
                      setFormState((current) => ({
                        ...current,
                        main_characters: current.main_characters.map((item, itemIndex) =>
                          itemIndex === index ? { ...item, name: event.target.value } : item,
                        ),
                      }));
                    }}
                    placeholder="Es. Akira"
                  />
                </label>
                <label className="manga-field">
                  <span>
                    Descrizione
                    <RequiredMark />
                  </span>
                  <textarea
                    value={character.description}
                    required
                    aria-required="true"
                    onChange={(event) => {
                      setFieldErrors((current) => ({ ...current, characters: '' }));
                      setFormState((current) => ({
                        ...current,
                        main_characters: current.main_characters.map((item, itemIndex) =>
                          itemIndex === index ? { ...item, description: event.target.value } : item,
                        ),
                      }));
                    }}
                    rows={4}
                    placeholder="Aspetto, carattere, ruolo nella storia, dettagli visivi importanti."
                  />
                </label>
                {formState.main_characters.length > 1 && (
                  <button
                    type="button"
                    className="manga-link-button"
                    onClick={() =>
                      setFormState((current) => ({
                        ...current,
                        main_characters: current.main_characters.filter((_, itemIndex) => itemIndex !== index),
                      }))
                    }
                  >
                    Rimuovi
                  </button>
                )}
              </div>
            ))}
          </div>
          {fieldErrors.characters ? <em className="manga-field-error">{fieldErrors.characters}</em> : null}
        </div>

        <div className="manga-submit-row">
          <div className="manga-submit-copy">
            <strong>Generazione semplificata</strong>
            <span>
              Planning invisibile, copertine automatiche sempre a colori, generazione autoregressiva e lettore dedicato con ripresa sessione. Le pagine interne saranno in {formatPageColorMode(formState.page_color_mode).toLowerCase()} e il manga avra {formatPageCount(formState.page_count)}. Un numero di pagine piu alto puo aumentare tempo di attesa e costo stimato.
            </span>
          </div>
          <button type="submit" className="manga-primary-button" disabled={isSubmitting}>
            {isSubmitting ? 'Avvio in corso...' : 'Genera manga'}
          </button>
        </div>
      </form>
    </div>
  );
}

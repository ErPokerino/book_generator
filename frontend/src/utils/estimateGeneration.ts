import type { AppConfig } from '../api/client';

export type GenerationMode = 'standard' | 'ultra';

export interface EstimateStage {
  id: string;
  defaultModel: string;
}

export interface GenerationEstimateInput {
  kind: 'book' | 'manga';
  generationMode?: GenerationMode;
  stageModels: Record<string, string>;
  stages: EstimateStage[];
  mangaPageCount?: number;
  config?: AppConfig | null;
}

export interface GenerationEstimate {
  minutes: number;
  costEur: number;
  assumptions: string;
}

const FALLBACK_TEXT_PRICING: Record<string, { input: number; output: number }> = {
  'gemini-3.8-flash': { input: 0.5, output: 3.0 },
  'gemini-3.5-flash-lite': { input: 0.1, output: 0.4 },
};

const FALLBACK_CHAPTER_SECONDS: Record<string, number> = {
  'gemini-3.8-flash': 40,
  'gemini-3.5-flash-lite': 28,
};

const DEFAULT_BOOK_CHAPTERS = 10;
const DEFAULT_BOOK_PAGES = 100;
const DEFAULT_MANGA_PAGES = 10;
const DEFAULT_EXCHANGE = 0.92;
const DEFAULT_IMAGE_USD = 0.02;
const TOKENS_PER_PAGE = 350;

function stageModel(stageModels: Record<string, string>, stages: EstimateStage[], stageId: string): string {
  const stage = stages.find((item) => item.id === stageId);
  return stageModels[stageId] || stage?.defaultModel || 'gemini-3.8-flash';
}

function textPricing(modelId: string, config?: AppConfig | null): { input: number; output: number } {
  const costs = config?.cost_estimation?.model_costs?.[modelId];
  if (costs) {
    return {
      input: costs.input_cost_per_million ?? FALLBACK_TEXT_PRICING['gemini-3.8-flash'].input,
      output: costs.output_cost_per_million ?? FALLBACK_TEXT_PRICING['gemini-3.8-flash'].output,
    };
  }
  return FALLBACK_TEXT_PRICING[modelId] || FALLBACK_TEXT_PRICING['gemini-3.8-flash'];
}

function tokenCostUsd(modelId: string, inputTokens: number, outputTokens: number, config?: AppConfig | null): number {
  const pricing = textPricing(modelId, config);
  return (inputTokens * pricing.input + outputTokens * pricing.output) / 1_000_000;
}

function imageCostUsd(count: number, config?: AppConfig | null): number {
  const unit = config?.cost_estimation?.image_generation_cost
    ?? config?.cost_estimation?.manga_image_generation_cost
    ?? DEFAULT_IMAGE_USD;
  return count * unit;
}

function linearChapterSeconds(mode: GenerationMode, chapters: number, config?: AppConfig | null): number {
  const params = config?.time_estimation?.linear_model_params?.[mode]
    ?? config?.time_estimation?.linear_model_params?.[mode === 'ultra' ? 'ultra' : 'standard']
    ?? (mode === 'ultra' ? { a: 0.5682, b: 90.43 } : { a: 0.1584, b: 25.85 });
  const a = params.a ?? 0.16;
  const b = params.b ?? 26;
  const sumIndices = chapters * (1 + chapters) / 2;
  return a * sumIndices + b * chapters;
}

function chapterTimeScale(modelId: string, config?: AppConfig | null): number {
  const byModel = config?.time_estimation?.fallback_by_model || FALLBACK_CHAPTER_SECONDS;
  const base = byModel['gemini-3.8-flash'] ?? 40;
  const current = byModel[modelId] ?? FALLBACK_CHAPTER_SECONDS[modelId] ?? base;
  return current / base;
}

export function estimateGeneration({
  kind,
  generationMode = 'standard',
  stageModels,
  stages,
  mangaPageCount,
  config,
}: GenerationEstimateInput): GenerationEstimate {
  const exchange = config?.cost_estimation?.exchange_rate_usd_to_eur ?? DEFAULT_EXCHANGE;
  const preview = config?.cost_estimation?.preview;
  const bookChapters = preview?.book_chapters ?? DEFAULT_BOOK_CHAPTERS;
  const bookPages = preview?.book_pages ?? DEFAULT_BOOK_PAGES;
  const tokensPerPage = config?.cost_estimation?.tokens_per_page ?? TOKENS_PER_PAGE;

  if (kind === 'manga') {
    const pages = Math.max(1, mangaPageCount || preview?.manga_pages || DEFAULT_MANGA_PAGES);
    const planningModel = stageModel(stageModels, stages, 'manga_planning');
    const pageModel = stageModel(stageModels, stages, 'manga_pages');
    const coverModel = stageModel(stageModels, stages, 'manga_cover');
    const backCoverModel = stageModel(stageModels, stages, 'manga_back_cover');

    const planningUsd = tokenCostUsd(planningModel, 2500, 1800, config);
    const imagesUsd = imageCostUsd(pages + 2, config);
    const costEur = (planningUsd + imagesUsd) * exchange;

    const planningSeconds = preview?.manga_planning_seconds ?? 20;
    const pageSecondsBase = preview?.manga_page_seconds ?? 12;
    const coverSeconds = preview?.manga_cover_seconds ?? 20;
    const pageScale = pageModel.includes('lite') ? 0.75 : 1;
    const coverScale = (model: string) => (model.includes('lite') ? 0.75 : 1);
    const seconds = planningSeconds
      + pages * pageSecondsBase * pageScale
      + coverSeconds * coverScale(coverModel)
      + coverSeconds * coverScale(backCoverModel);

    return {
      minutes: Math.max(1, Math.round(seconds / 60)),
      costEur,
      assumptions: `Stima per ${pages} pagine, più copertina e retro.`,
    };
  }

  const questionsModel = stageModel(stageModels, stages, 'questions');
  const draftModel = stageModel(stageModels, stages, 'draft');
  const outlineModel = stageModel(stageModels, stages, 'outline');
  const chaptersModel = stageModel(stageModels, stages, 'chapters');
  const critiqueModel = stageModel(stageModels, stages, 'critique');

  const splitCalls = generationMode === 'ultra' ? 2 : 1;
  const writerPrompt = 2800;
  const storyBible = 3400;
  const avgPagesPerChapter = bookPages / bookChapters;
  const avgChapterTokens = avgPagesPerChapter * tokensPerPage;
  let chaptersInput = 0;
  for (let index = 0; index < bookChapters; index += 1) {
    const fullPrev = Math.min(index, 1);
    chaptersInput += (writerPrompt + storyBible + fullPrev * avgChapterTokens) * splitCalls;
  }
  const chaptersOutput = bookPages * tokensPerPage;

  const usd = tokenCostUsd(questionsModel, 1200, 800, config)
    + tokenCostUsd(draftModel, 800, Math.max(1200, bookPages * 12), config)
    + tokenCostUsd(outlineModel, 3000, 2000, config)
    + tokenCostUsd(chaptersModel, chaptersInput, chaptersOutput, config)
    + tokenCostUsd(critiqueModel, bookPages * tokensPerPage * 1.2, 1200, config)
    + imageCostUsd(1, config);

  const questionsSeconds = preview?.questions_seconds ?? 8;
  const draftSeconds = preview?.draft_seconds ?? 20;
  const outlineSeconds = preview?.outline_seconds ?? 18;
  const critiqueSeconds = preview?.critique_seconds ?? 40;
  const coverSeconds = preview?.cover_seconds ?? 25;
  const chapterSeconds = linearChapterSeconds(generationMode, bookChapters, config)
    * chapterTimeScale(chaptersModel, config);
  const seconds = questionsSeconds + draftSeconds + outlineSeconds + chapterSeconds + critiqueSeconds + coverSeconds;

  return {
    minutes: Math.max(1, Math.round(seconds / 60)),
    costEur: usd * exchange,
    assumptions: `Stima per ~${bookChapters} capitoli / ${bookPages} pagine.`,
  };
}

export function formatEstimateCost(costEur: number): string {
  if (costEur >= 0.01) {
    return `€${costEur.toFixed(2)}`;
  }
  return `€${costEur.toFixed(3)}`;
}

export function formatEstimateTime(minutes: number): string {
  if (minutes < 1) return '< 1 min';
  return `~${minutes} min`;
}

export function formatElapsed(minutes: number): string {
  const totalSeconds = Math.max(0, Math.floor(minutes * 60));
  const hours = Math.floor(totalSeconds / 3600);
  const mins = Math.floor((totalSeconds % 3600) / 60);
  const secs = totalSeconds % 60;
  if (hours > 0) {
    return `${hours} h ${mins.toString().padStart(2, '0')} min`;
  }
  if (mins < 1) {
    return `${secs} s`;
  }
  return `${mins} min ${secs.toString().padStart(2, '0')} s`;
}

export function elapsedMinutesBetween(
  startedAt?: string | null,
  nowMs: number = Date.now(),
  endedAt?: string | null,
): number | null {
  if (!startedAt) return null;
  const started = Date.parse(startedAt);
  if (Number.isNaN(started)) return null;
  const parsedEnd = endedAt ? Date.parse(endedAt) : Number.NaN;
  const endMs = Number.isNaN(parsedEnd) ? nowMs : parsedEnd;
  return Math.max(0, (endMs - started) / 60000);
}

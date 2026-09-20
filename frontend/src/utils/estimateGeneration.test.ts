import { describe, expect, it } from 'vitest';
import { BOOK_STAGES, MANGA_STAGES } from '../components/ModelSettingsPanel';
import { estimateGeneration, elapsedMinutesBetween, formatElapsed } from './estimateGeneration';

const standardSize = { available: true, sample_count: 4, mode_sample_count: 4, scope: 'mode', words_per_page: 250, chapters: 8, pages: 40, pages_low: 30, pages_high: 60 };
const ultraSize = { ...standardSize, pages: 120, pages_low: 90, pages_high: 150 };

describe('estimateGeneration', () => {
  it('increases book time and cost when switching to Ultra', () => {
    const standard = estimateGeneration({
      kind: 'book',
      generationMode: 'standard',
      bookSize: standardSize,
      stageModels: Object.fromEntries(BOOK_STAGES.map((stage) => [stage.id, stage.defaultModel])),
      stages: BOOK_STAGES,
    });
    const ultra = estimateGeneration({
      kind: 'book',
      generationMode: 'ultra',
      bookSize: ultraSize,
      stageModels: Object.fromEntries(BOOK_STAGES.map((stage) => [stage.id, stage.defaultModel])),
      stages: BOOK_STAGES,
    });

    expect(ultra.minutes).toBeGreaterThan(standard.minutes!);
    expect(ultra.costEur).toBeGreaterThan(standard.costEur!);
  });

  it('lowers book cost when chapter model is lite', () => {
    const defaults = Object.fromEntries(BOOK_STAGES.map((stage) => [stage.id, stage.defaultModel]));
    const flash = estimateGeneration({
      kind: 'book',
      generationMode: 'standard',
      bookSize: standardSize,
      stageModels: defaults,
      stages: BOOK_STAGES,
    });
    const lite = estimateGeneration({
      kind: 'book',
      generationMode: 'standard',
      bookSize: standardSize,
      stageModels: { ...defaults, chapters: 'gemini-3.5-flash-lite' },
      stages: BOOK_STAGES,
    });

    expect(lite.costEur).toBeLessThan(flash.costEur!);
  });

  it('scales manga estimate with page count', () => {
    const stageModels = Object.fromEntries(MANGA_STAGES.map((stage) => [stage.id, stage.defaultModel]));
    const shortRun = estimateGeneration({
      kind: 'manga',
      stageModels,
      stages: MANGA_STAGES,
      mangaPageCount: 10,
    });
    const longRun = estimateGeneration({
      kind: 'manga',
      stageModels,
      stages: MANGA_STAGES,
      mangaPageCount: 40,
    });

    expect(longRun.minutes).toBeGreaterThan(shortRun.minutes!);
    expect(longRun.costEur).toBeGreaterThan(shortRun.costEur!);
  });

  it('does not invent a book estimate without history', () => {
    const result = estimateGeneration({ kind: 'book', stages: BOOK_STAGES, stageModels: {} });
    expect(result.costEur).toBeNull();
    expect(result.minutes).toBeNull();
    expect(result.assumptions).not.toContain('100');
  });

  it('uses observed pages for output costs and returns a size-based range', () => {
    const common = { kind: 'book' as const, stages: BOOK_STAGES, stageModels: {}, generationMode: 'standard' as const };
    const short = estimateGeneration({ ...common, bookSize: standardSize });
    const long = estimateGeneration({ ...common, bookSize: ultraSize });
    expect(long.costEur).toBeGreaterThan(short.costEur!);
    expect(short.costLowEur).toBeLessThan(short.costEur!);
    expect(short.costHighEur).toBeGreaterThan(short.costEur!);
    expect(long.assumptions).toContain('120 pagine');
  });

  it('formats elapsed time and computes minutes from timestamps', () => {
    expect(formatElapsed(0.2)).toBe('12 s');
    expect(formatElapsed(3.5)).toBe('3 min 30 s');
    expect(formatElapsed(61)).toBe('1 h 01 min');

    const startedAt = '2026-09-19T12:00:00.000Z';
    const nowMs = Date.parse('2026-09-19T12:02:30.000Z');
    expect(elapsedMinutesBetween(startedAt, nowMs)).toBe(2.5);
    expect(elapsedMinutesBetween(startedAt, nowMs, '2026-09-19T12:01:00.000Z')).toBe(1);
    expect(elapsedMinutesBetween(null, nowMs)).toBeNull();
  });
});

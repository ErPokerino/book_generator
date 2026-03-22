import { renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { ProcessProgress } from '../api/client';
import { useProcessPolling } from './useProcessPolling';

const { mockGetAppConfig, mockToastError } = vi.hoisted(() => ({
  mockGetAppConfig: vi.fn(),
  mockToastError: vi.fn(),
}));

vi.mock('../api/client', () => ({
  getAppConfig: mockGetAppConfig,
}));

vi.mock('./useToast', () => ({
  useToast: () => ({
    error: mockToastError,
  }),
}));

function buildProgress(overrides: Partial<ProcessProgress>): ProcessProgress {
  return {
    status: 'running',
    current_step: 0,
    total_steps: 1,
    progress_percentage: 0,
    ...overrides,
  };
}

describe('useProcessPolling', () => {
  beforeEach(() => {
    mockGetAppConfig.mockReturnValue(new Promise(() => {}));
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it('stops polling and surfaces paused jobs as recoverable errors', async () => {
    const progressEndpoint = vi
      .fn<() => Promise<ProcessProgress>>()
      .mockResolvedValue(buildProgress({ status: 'paused', error: 'Processo sospeso' }));
    const onError = vi.fn();

    const { result } = renderHook(() =>
      useProcessPolling({
        sessionId: 'session-1',
        progressEndpoint,
        pollingInterval: 5,
        onError,
      }),
    );

    await waitFor(() => expect(result.current.isPolling).toBe(false));

    expect(progressEndpoint).toHaveBeenCalledTimes(1);
    expect(result.current.progress).toEqual(
      expect.objectContaining({
        status: 'paused',
        error: 'Processo sospeso',
      }),
    );
    expect(onError).toHaveBeenCalledWith('Processo sospeso');
  });

  it('calls onComplete only once when the process is already completed', async () => {
    const progressEndpoint = vi
      .fn<() => Promise<ProcessProgress>>()
      .mockResolvedValue(buildProgress({ status: 'completed', current_step: 1, total_steps: 1 }));
    const onComplete = vi.fn();

    const { result, rerender } = renderHook(
      ({ sessionId }) =>
        useProcessPolling({
          sessionId,
          progressEndpoint,
          pollingInterval: 10,
          onComplete,
        }),
      {
        initialProps: {
          sessionId: 'session-2',
        },
      },
    );

    await waitFor(() => expect(result.current.isPolling).toBe(false));

    rerender({ sessionId: 'session-2' });

    expect(progressEndpoint).toHaveBeenCalledTimes(1);
    expect(onComplete).toHaveBeenCalledTimes(1);
    expect(onComplete).toHaveBeenCalledWith(
      expect.objectContaining({
        status: 'completed',
      }),
    );
  });
});

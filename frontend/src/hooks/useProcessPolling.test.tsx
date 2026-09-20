import { act, renderHook, waitFor } from '@testing-library/react';
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

  it('ignores an old session response after switching sessions', async () => {
    let finishOld!: (progress: ProcessProgress) => void;
    const endpoint = vi.fn((id: string) => id === 'old'
      ? new Promise<ProcessProgress>(resolve => { finishOld = resolve; })
      : Promise.resolve(buildProgress({ current_step: 2 })));
    const onComplete = vi.fn();
    const { result, rerender } = renderHook(({ sessionId }) => useProcessPolling({
      sessionId, progressEndpoint: endpoint, onComplete,
    }), { initialProps: { sessionId: 'old' } });
    rerender({ sessionId: 'new' });
    await waitFor(() => expect(result.current.progress?.current_step).toBe(2));
    await act(async () => finishOld(buildProgress({ status: 'completed' })));
    expect(result.current.progress?.status).toBe('running');
    expect(onComplete).not.toHaveBeenCalled();
  });

  it('restarts polling when a failed process is enabled again', async () => {
    const endpoint = vi.fn().mockResolvedValueOnce(buildProgress({ status: 'failed' }))
      .mockResolvedValueOnce(buildProgress({ status: 'completed' }));
    const onComplete = vi.fn();
    const { result, rerender } = renderHook(({ enabled }) => useProcessPolling({
      sessionId: 'book', progressEndpoint: endpoint, enabled, onComplete,
    }), { initialProps: { enabled: true } });
    await waitFor(() => expect(result.current.isPolling).toBe(false));
    rerender({ enabled: false });
    rerender({ enabled: true });
    await waitFor(() => expect(onComplete).toHaveBeenCalledTimes(1));
    expect(endpoint).toHaveBeenCalledTimes(2);
  });

  it('keeps the polling cadence with inline callbacks and config arriving late', async () => {
    vi.useFakeTimers();
    let finishConfig!: (value: unknown) => void;
    mockGetAppConfig.mockReturnValue(new Promise(resolve => { finishConfig = resolve; }));
    const endpoint = vi.fn().mockResolvedValue(buildProgress({}));
    const { rerender } = renderHook(() => useProcessPolling({
      sessionId: 'book', progressEndpoint: endpoint, pollingInterval: 100,
      onComplete: () => {}, onError: () => {},
    }));
    await act(async () => {});
    rerender();
    await act(async () => finishConfig({ frontend: { polling_interval: 5 } }));
    expect(endpoint).toHaveBeenCalledTimes(1);
    await act(async () => vi.advanceTimersByTimeAsync(99));
    expect(endpoint).toHaveBeenCalledTimes(1);
    await act(async () => vi.advanceTimersByTimeAsync(1));
    expect(endpoint).toHaveBeenCalledTimes(2);
  });

  it('stops after ten network failures and can be retried explicitly', async () => {
    vi.useFakeTimers();
    const endpoint = vi.fn().mockRejectedValue(new Error('Offline'));
    const onError = vi.fn();
    const { result } = renderHook(() => useProcessPolling({
      sessionId: 'book', progressEndpoint: endpoint, pollingInterval: 1, onError,
    }));
    await act(async () => vi.advanceTimersByTimeAsync(200));
    expect(endpoint).toHaveBeenCalledTimes(10);
    expect(result.current.fatalError).toBe('Offline');
    expect(onError).toHaveBeenCalledTimes(1);
    endpoint.mockResolvedValue(buildProgress({ status: 'completed' }));
    await act(async () => result.current.setIsPolling(true));
    expect(endpoint).toHaveBeenCalledTimes(11);
    expect(result.current.fatalError).toBeNull();
  });

  it('does not deliver completion callbacks after unmount', async () => {
    let finish!: (value: ProcessProgress) => void;
    const endpoint = vi.fn(() => new Promise<ProcessProgress>(resolve => { finish = resolve; }));
    const onComplete = vi.fn();
    const { unmount } = renderHook(() => useProcessPolling({ sessionId: 'book', progressEndpoint: endpoint, onComplete }));
    unmount();
    await act(async () => finish(buildProgress({ status: 'completed' })));
    expect(onComplete).not.toHaveBeenCalled();
  });
});

import { renderHook, act } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';

import { useSubmissionProcessingStatus } from '../useSubmissionProcessingStatus';
import { ProcessingStatusApiResult, ProcessingStatusResponse } from '../types';

const getSubmissionProcessingStatusMock = vi.fn();

vi.mock('../api', () => ({
  getSubmissionProcessingStatus: (...args: unknown[]) => getSubmissionProcessingStatusMock(...args),
}));

function buildStatusData(overallStatus: ProcessingStatusResponse['overall_status']): ProcessingStatusResponse {
  return {
    exam_submission_id: 12001,
    overall_status: overallStatus,
    is_terminal: ['COMPLETED', 'CAPTURE_FAILED', 'GRADING_FAILED', 'NEEDS_REVIEW', 'NOT_FOUND'].includes(overallStatus),
    can_retry: ['CAPTURE_FAILED', 'GRADING_FAILED'].includes(overallStatus),
    pending_reason: null,
    failure_reason: null,
    seal: {
      submission_seal_id: 91001,
      seal_status: 'SEALED',
      sealed_at: '2026-05-13T08:00:00Z',
      sealed_answer_count: 3,
      has_sealed_answer: true,
    },
    capture: {
      required: false,
      status: null,
      capture_job_id: null,
      capture_profile_id: null,
      artifact_count: 0,
      dataset_count: 0,
      latest_event_type: null,
      latest_error_code: null,
      latest_error_message_sanitized: null,
    },
    grading: {
      grading_job_id: null,
      grading_job_status: null,
      grading_run_id: null,
      grading_run_status: null,
      worker_id: null,
      claimed_at: null,
      finished_at: null,
      latest_event_type: null,
    },
    tasks: {
      total: 3,
      queued: 0,
      running: 0,
      waiting_capture: 0,
      completed: 0,
      failed: 0,
      needs_review: 0,
      by_input_source: { SEALED_TEXT_ANSWER: 3 },
      by_answer_language: { SQL: 3 },
    },
    results: {
      actual_result_count: 0,
      comparison_count: 0,
      question_score_count: 0,
    },
    score: {
      submission_score_id: null,
      total_score: null,
      max_score: null,
      score_status: null,
      finalized_at: null,
    },
    timestamps: {
      created_at: '2026-05-13T08:00:00Z',
      updated_at: '2026-05-13T08:00:00Z',
      latest_activity_at: '2026-05-13T08:00:00Z',
    },
  };
}

function okResult(status: ProcessingStatusResponse['overall_status']): ProcessingStatusApiResult {
  return {
    ok: true,
    data: buildStatusData(status),
  };
}

function errorResult(status: number, code: string): ProcessingStatusApiResult {
  return {
    ok: false,
    status,
    error: {
      code,
      message: `Error: ${code}`,
      details: {},
      request_id: null,
    },
  };
}

describe('useSubmissionProcessingStatus', () => {
  async function flushMicrotasks() {
    await Promise.resolve();
    await Promise.resolve();
  }

  beforeEach(() => {
    vi.useFakeTimers();
    getSubmissionProcessingStatusMock.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  test('starts polling when enabled', async () => {
    getSubmissionProcessingStatusMock.mockResolvedValue(okResult('WAITING_GRADING'));

    renderHook(() =>
      useSubmissionProcessingStatus({
        examSubmissionId: 12001,
        enabled: true,
        initialIntervalMs: 1000,
        maxIntervalMs: 4000,
      })
    );

    await act(async () => {
      await flushMicrotasks();
    });
    expect(getSubmissionProcessingStatusMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
      await flushMicrotasks();
    });
    expect(getSubmissionProcessingStatusMock).toHaveBeenCalledTimes(2);
  });

  test('does not poll when disabled', async () => {
    renderHook(() =>
      useSubmissionProcessingStatus({
        examSubmissionId: 12001,
        enabled: false,
      })
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });

    expect(getSubmissionProcessingStatusMock).not.toHaveBeenCalled();
  });

  test.each(['COMPLETED', 'CAPTURE_FAILED', 'GRADING_FAILED', 'NEEDS_REVIEW'] as const)(
    'stops polling on %s',
    async (terminalStatus) => {
      getSubmissionProcessingStatusMock.mockResolvedValue(okResult(terminalStatus));

      const { result } = renderHook(() =>
        useSubmissionProcessingStatus({
          examSubmissionId: 12001,
          enabled: true,
          initialIntervalMs: 1000,
          maxIntervalMs: 4000,
        })
      );

      await act(async () => {
        await flushMicrotasks();
      });
      expect(getSubmissionProcessingStatusMock).toHaveBeenCalledTimes(1);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(5000);
        await flushMicrotasks();
      });

      expect(getSubmissionProcessingStatusMock).toHaveBeenCalledTimes(1);
      expect(result.current.status).toBe(terminalStatus);
      expect(result.current.isTerminal).toBe(true);
      expect(result.current.isPolling).toBe(false);
    }
  );

  test.each([
    [403, 'permission_denied'],
    [404, 'submission_not_found'],
  ])('stops polling on HTTP %s', async (httpStatus, code) => {
    getSubmissionProcessingStatusMock.mockResolvedValue(errorResult(httpStatus, code));

    const { result } = renderHook(() =>
      useSubmissionProcessingStatus({
        examSubmissionId: 12001,
        enabled: true,
        initialIntervalMs: 1000,
        maxIntervalMs: 4000,
      })
    );

    await act(async () => {
      await flushMicrotasks();
    });
    expect(getSubmissionProcessingStatusMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
      await flushMicrotasks();
    });

    expect(getSubmissionProcessingStatusMock).toHaveBeenCalledTimes(1);
    expect(result.current.isTerminal).toBe(true);
    expect(result.current.isPolling).toBe(false);
  });

  test('backs off on 503', async () => {
    getSubmissionProcessingStatusMock
      .mockResolvedValueOnce(errorResult(503, 'database_unavailable'))
      .mockResolvedValueOnce(okResult('WAITING_GRADING'))
      .mockResolvedValue(okResult('WAITING_GRADING'));

    renderHook(() =>
      useSubmissionProcessingStatus({
        examSubmissionId: 12001,
        enabled: true,
        initialIntervalMs: 1000,
        maxIntervalMs: 8000,
      })
    );

    await act(async () => {
      await flushMicrotasks();
    });
    expect(getSubmissionProcessingStatusMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
      await flushMicrotasks();
    });
    expect(getSubmissionProcessingStatusMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
      await flushMicrotasks();
    });
    expect(getSubmissionProcessingStatusMock).toHaveBeenCalledTimes(2);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
      await flushMicrotasks();
    });
    expect(getSubmissionProcessingStatusMock).toHaveBeenCalledTimes(3);
  });

  test('aborts in-flight request on unmount cleanup', async () => {
    let capturedSignal: AbortSignal | undefined;

    getSubmissionProcessingStatusMock.mockImplementation(
      async (_submissionId: number, options?: { signal?: AbortSignal }): Promise<ProcessingStatusApiResult> => {
        capturedSignal = options?.signal;
        return new Promise((resolve) => {
          options?.signal?.addEventListener('abort', () => {
            resolve(errorResult(0, 'request_aborted'));
          });
        });
      }
    );

    const { unmount } = renderHook(() =>
      useSubmissionProcessingStatus({
        examSubmissionId: 12001,
        enabled: true,
        initialIntervalMs: 1000,
      })
    );

    await act(async () => {
      await flushMicrotasks();
    });
    expect(getSubmissionProcessingStatusMock).toHaveBeenCalledTimes(1);

    expect(capturedSignal).toBeDefined();
    expect(capturedSignal?.aborted).toBe(false);

    unmount();

    expect(capturedSignal?.aborted).toBe(true);
  });

  test('manual retry triggers immediate fetch', async () => {
    getSubmissionProcessingStatusMock.mockResolvedValue(okResult('WAITING_GRADING'));

    const { result } = renderHook(() =>
      useSubmissionProcessingStatus({
        examSubmissionId: 12001,
        enabled: true,
        initialIntervalMs: 10000,
        maxIntervalMs: 20000,
      })
    );

    await act(async () => {
      await flushMicrotasks();
    });
    expect(getSubmissionProcessingStatusMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      result.current.retryNow();
      await flushMicrotasks();
    });
    expect(getSubmissionProcessingStatusMock).toHaveBeenCalledTimes(2);
  });

  test('unknown future status uses safe fallback behavior', async () => {
    getSubmissionProcessingStatusMock.mockResolvedValue({
      ok: true,
      data: {
        ...buildStatusData('WAITING_GRADING'),
        overall_status: 'FUTURE_STATUS',
        is_terminal: false,
      },
    } as unknown as ProcessingStatusApiResult);

    const { result } = renderHook(() =>
      useSubmissionProcessingStatus({
        examSubmissionId: 12001,
        enabled: true,
        initialIntervalMs: 1000,
      })
    );

    await act(async () => {
      await flushMicrotasks();
    });
    expect(getSubmissionProcessingStatusMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
      await flushMicrotasks();
    });

    expect(getSubmissionProcessingStatusMock).toHaveBeenCalledTimes(1);
    expect(result.current.status).toBe('UNKNOWN');
    expect(result.current.isTerminal).toBe(true);
    expect(result.current.isPolling).toBe(false);
    expect(result.current.error?.code).toBe('unknown_status');
  });
});

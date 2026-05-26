import { useCallback, useEffect, useRef, useState } from 'react';

import { getSubmissionProcessingStatus } from './api';
import { ACTIVE_PROCESSING_STATUSES, TERMINAL_PROCESSING_STATUSES, isProcessingOverallStatus } from './statusContract';
import { ProcessingOverallStatus, ProcessingStatusApiError, ProcessingStatusResponse } from './types';

const DEFAULT_INTERVAL_MS = 2500;
const DEFAULT_MAX_INTERVAL_MS = 20000;

const ACTIVE_STATUS_SET = new Set<ProcessingOverallStatus>(ACTIVE_PROCESSING_STATUSES);
const TERMINAL_STATUS_SET = new Set<ProcessingOverallStatus>(TERMINAL_PROCESSING_STATUSES);

const STOP_ON_HTTP_STATUS = new Set([403, 404, 422]);
const BACKOFF_HTTP_STATUS = new Set([0, 503]);

export interface UseSubmissionProcessingStatusOptions {
  examSubmissionId: number;
  enabled?: boolean;
  initialIntervalMs?: number;
  maxIntervalMs?: number;
}

export interface UseSubmissionProcessingStatusState {
  data: ProcessingStatusResponse | null;
  status: ProcessingOverallStatus | 'UNKNOWN' | null;
  isLoading: boolean;
  isPolling: boolean;
  isTerminal: boolean;
  error: ProcessingStatusApiError | null;
  lastUpdatedAt: string | null;
  retryNow: () => void;
  stop: () => void;
}

function ensurePositiveInterval(input: number | undefined, fallback: number): number {
  if (typeof input !== 'number' || !Number.isFinite(input) || input <= 0) {
    return fallback;
  }
  return Math.floor(input);
}

export function useSubmissionProcessingStatus(
  options: UseSubmissionProcessingStatusOptions
): UseSubmissionProcessingStatusState {
  const enabled = options.enabled ?? true;
  const initialIntervalMs = ensurePositiveInterval(options.initialIntervalMs, DEFAULT_INTERVAL_MS);
  const maxIntervalMs = Math.max(initialIntervalMs, ensurePositiveInterval(options.maxIntervalMs, DEFAULT_MAX_INTERVAL_MS));

  const [data, setData] = useState<ProcessingStatusResponse | null>(null);
  const [status, setStatus] = useState<ProcessingOverallStatus | 'UNKNOWN' | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(enabled);
  const [isPolling, setIsPolling] = useState<boolean>(enabled);
  const [isTerminal, setIsTerminal] = useState<boolean>(false);
  const [error, setError] = useState<ProcessingStatusApiError | null>(null);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<string | null>(null);

  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const controllerRef = useRef<AbortController | null>(null);
  const runningRef = useRef<boolean>(false);
  const hasLoadedRef = useRef<boolean>(false);
  const currentIntervalRef = useRef<number>(initialIntervalMs);

  const clearTimer = useCallback(() => {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const stopLoop = useCallback(() => {
    runningRef.current = false;
    clearTimer();
    if (controllerRef.current !== null) {
      controllerRef.current.abort();
      controllerRef.current = null;
    }
    setIsPolling(false);
  }, [clearTimer]);

  const scheduleNext = useCallback(
    (delayMs: number, fetchNow: () => Promise<void>) => {
      if (!runningRef.current) {
        return;
      }

      clearTimer();
      timerRef.current = setTimeout(() => {
        void fetchNow();
      }, delayMs);
    },
    [clearTimer]
  );

  const fetchOnce = useCallback(async () => {
    if (!runningRef.current) {
      return;
    }

    if (controllerRef.current !== null) {
      controllerRef.current.abort();
      controllerRef.current = null;
    }

    const controller = new AbortController();
    controllerRef.current = controller;

    if (!hasLoadedRef.current) {
      setIsLoading(true);
    }

    const result = await getSubmissionProcessingStatus(options.examSubmissionId, { signal: controller.signal });

    if (!runningRef.current) {
      return;
    }

    if (controllerRef.current === controller) {
      controllerRef.current = null;
    }

    setIsLoading(false);

    if (result.ok) {
      hasLoadedRef.current = true;
      currentIntervalRef.current = initialIntervalMs;
      setError(null);
      setData(result.data);
      setLastUpdatedAt(new Date().toISOString());

      const rawStatus = result.data.overall_status as unknown;
      if (!isProcessingOverallStatus(rawStatus)) {
        setStatus('UNKNOWN');
        setIsTerminal(true);
        setIsPolling(false);
        setError({
          code: 'unknown_status',
          message: 'Unknown processing status received',
          details: {},
          request_id: null,
        });
        stopLoop();
        return;
      }

      setStatus(rawStatus);
      const terminal = Boolean(result.data.is_terminal || TERMINAL_STATUS_SET.has(rawStatus));
      setIsTerminal(terminal);

      if (terminal) {
        stopLoop();
        return;
      }

      if (!ACTIVE_STATUS_SET.has(rawStatus)) {
        setStatus('UNKNOWN');
        setIsTerminal(true);
        setIsPolling(false);
        setError({
          code: 'unknown_status',
          message: 'Unsupported processing status behavior',
          details: {},
          request_id: null,
        });
        stopLoop();
        return;
      }

      setIsPolling(true);
      scheduleNext(initialIntervalMs, fetchOnce);
      return;
    }

    setError(result.error);

    if (result.status === 404) {
      setStatus('NOT_FOUND');
      setIsTerminal(true);
      stopLoop();
      return;
    }

    if (STOP_ON_HTTP_STATUS.has(result.status)) {
      setIsTerminal(true);
      stopLoop();
      return;
    }

    if (BACKOFF_HTTP_STATUS.has(result.status)) {
      const nextInterval = Math.min(maxIntervalMs, currentIntervalRef.current * 2);
      currentIntervalRef.current = nextInterval;
      setIsPolling(true);
      scheduleNext(nextInterval, fetchOnce);
      return;
    }

    setIsTerminal(true);
    stopLoop();
  }, [
    initialIntervalMs,
    maxIntervalMs,
    options.examSubmissionId,
    scheduleNext,
    stopLoop,
  ]);

  const stop = useCallback(() => {
    stopLoop();
  }, [stopLoop]);

  const retryNow = useCallback(() => {
    if (!enabled) {
      return;
    }

    runningRef.current = true;
    setIsPolling(true);
    setIsTerminal(false);
    clearTimer();
    currentIntervalRef.current = initialIntervalMs;
    void fetchOnce();
  }, [clearTimer, enabled, fetchOnce, initialIntervalMs]);

  useEffect(() => {
    hasLoadedRef.current = false;
    currentIntervalRef.current = initialIntervalMs;

    if (!enabled) {
      runningRef.current = false;
      clearTimer();
      if (controllerRef.current !== null) {
        controllerRef.current.abort();
        controllerRef.current = null;
      }
      setIsLoading(false);
      setIsPolling(false);
      return;
    }

    runningRef.current = true;
    setIsLoading(true);
    setIsPolling(true);
    setIsTerminal(false);

    void fetchOnce();

    return () => {
      runningRef.current = false;
      clearTimer();
      if (controllerRef.current !== null) {
        controllerRef.current.abort();
        controllerRef.current = null;
      }
      setIsPolling(false);
    };
  }, [clearTimer, enabled, fetchOnce, initialIntervalMs]);

  return {
    data,
    status,
    isLoading,
    isPolling,
    isTerminal,
    error,
    lastUpdatedAt,
    retryNow,
    stop,
  };
}

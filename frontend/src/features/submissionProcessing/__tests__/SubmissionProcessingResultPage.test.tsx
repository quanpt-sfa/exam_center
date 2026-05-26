import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { render, screen, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, test, vi } from 'vitest';

import { SubmissionProcessingResultPage } from '../SubmissionProcessingResultPage';
import type { ProcessingStatusApiError, ProcessingStatusResponse } from '../types';
import type { UseSubmissionProcessingStatusState } from '../useSubmissionProcessingStatus';

const useSubmissionProcessingStatusMock = vi.fn();

vi.mock('../useSubmissionProcessingStatus', () => ({
  useSubmissionProcessingStatus: (...args: unknown[]) => useSubmissionProcessingStatusMock(...args),
}));

const CURRENT_DIR = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(CURRENT_DIR, '..', '..', '..', '..', '..', '..');
const FIXTURE_DIR = resolve(REPO_ROOT, 'apps', 'api', 'tests', 'fixtures', 'processing_status');

function loadFixture(name: string): ProcessingStatusResponse {
  return JSON.parse(readFileSync(resolve(FIXTURE_DIR, name), 'utf-8')) as ProcessingStatusResponse;
}

function makeHookState(overrides: Partial<UseSubmissionProcessingStatusState>): UseSubmissionProcessingStatusState {
  return {
    data: null,
    status: null,
    isLoading: false,
    isPolling: false,
    isTerminal: false,
    error: null,
    lastUpdatedAt: null,
    retryNow: vi.fn(),
    stop: vi.fn(),
    ...overrides,
  };
}

function renderRoute(path: string) {
  return render(
    <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }} initialEntries={[path]}>
      <Routes>
        <Route path="/submissions/:examSubmissionId/result" element={<SubmissionProcessingResultPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('SubmissionProcessingResultPage', () => {
  beforeEach(() => {
    useSubmissionProcessingStatusMock.mockReset();
  });

  test('valid examSubmissionId renders loading then active status', () => {
    const waiting = loadFixture('waiting_grading.json');
    let state = makeHookState({ isLoading: true, isPolling: true, isTerminal: false });

    useSubmissionProcessingStatusMock.mockImplementation(() => state);

    const rendered = renderRoute('/submissions/12001/result');
    screen.getByText('Loading processing status');

    state = makeHookState({
      data: waiting,
      status: 'WAITING_GRADING',
      isLoading: false,
      isPolling: true,
      isTerminal: false,
    });

    rendered.rerender(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }} initialEntries={['/submissions/12001/result']}>
        <Routes>
          <Route path="/submissions/:examSubmissionId/result" element={<SubmissionProcessingResultPage />} />
        </Routes>
      </MemoryRouter>
    );

    screen.getByText('Your submission is queued for grading.');
    screen.getByText('Automatic checking is running.');
  });

  test('completed status renders score and stops polling', () => {
    const completed = loadFixture('completed.json');
    useSubmissionProcessingStatusMock.mockReturnValue(
      makeHookState({
        data: completed,
        status: 'COMPLETED',
        isLoading: false,
        isPolling: false,
        isTerminal: true,
      })
    );

    renderRoute('/submissions/12005/result');

    screen.getByText('Score Summary');
    screen.getByText('Automatic checking has stopped.');
  });

  test('capture failed renders sanitized failure', () => {
    const failed = loadFixture('capture_failed.json');
    useSubmissionProcessingStatusMock.mockReturnValue(
      makeHookState({
        data: failed,
        status: 'CAPTURE_FAILED',
        isLoading: false,
        isPolling: false,
        isTerminal: true,
      })
    );

    renderRoute('/submissions/12006/result');

    screen.getByText('Processing failed');
    const alert = screen.getByRole('alert');
    within(alert).getByText('Capture step failed.');
    screen.getByText('Reason code:');
    expect(screen.queryByText(/dsn|password|traceback|select \*/i)).toBeNull();
  });

  test('grading failed renders sanitized failure', () => {
    const failed = loadFixture('grading_failed.json');
    useSubmissionProcessingStatusMock.mockReturnValue(
      makeHookState({
        data: failed,
        status: 'GRADING_FAILED',
        isLoading: false,
        isPolling: false,
        isTerminal: true,
      })
    );

    renderRoute('/submissions/12007/result');

    screen.getByText('Processing failed');
    screen.getByText('Grading step failed.');
    expect(screen.queryByRole('button', { name: 'Retry now' })).toBeNull();
  });

  test('needs review renders manual review message', () => {
    const review = loadFixture('needs_review.json');
    useSubmissionProcessingStatusMock.mockReturnValue(
      makeHookState({
        data: review,
        status: 'NEEDS_REVIEW',
        isLoading: false,
        isPolling: false,
        isTerminal: true,
      })
    );

    renderRoute('/submissions/12008/result');

    screen.getByText('Manual review required');
    expect(screen.queryByText('Processing failed')).toBeNull();
  });

  test('403 renders access denied and stops polling', () => {
    const error: ProcessingStatusApiError = {
      code: 'permission_denied',
      message: 'Insufficient permissions',
      details: {},
      request_id: null,
    };

    useSubmissionProcessingStatusMock.mockReturnValue(
      makeHookState({
        error,
        isLoading: false,
        isPolling: false,
        isTerminal: true,
      })
    );

    renderRoute('/submissions/12009/result');

    screen.getByText('Access denied');
    expect(screen.queryByRole('button', { name: 'Retry now' })).toBeNull();
  });

  test('404 renders not found and stops polling', () => {
    const error: ProcessingStatusApiError = {
      code: 'submission_not_found',
      message: 'Submission not found',
      details: {},
      request_id: null,
    };

    useSubmissionProcessingStatusMock.mockReturnValue(
      makeHookState({
        error,
        isLoading: false,
        isPolling: false,
        isTerminal: true,
      })
    );

    renderRoute('/submissions/999999/result');

    screen.getByText('Submission not found');
    expect(screen.queryByRole('button', { name: 'Retry now' })).toBeNull();
  });

  test('503 temporary unavailable shows retry button', () => {
    const retryNow = vi.fn();
    const error: ProcessingStatusApiError = {
      code: 'database_unavailable',
      message: 'Database temporarily unavailable',
      details: {},
      request_id: null,
    };

    useSubmissionProcessingStatusMock.mockReturnValue(
      makeHookState({
        error,
        isLoading: false,
        isPolling: true,
        isTerminal: false,
        retryNow,
      })
    );

    renderRoute('/submissions/12010/result');

    screen.getByText('Service temporarily unavailable');
    screen.getByRole('button', { name: 'Retry now' }).click();
    expect(retryNow).toHaveBeenCalledTimes(1);
  });

  test('invalid route id renders validation error and does not call API hook as enabled', () => {
    useSubmissionProcessingStatusMock.mockReturnValue(
      makeHookState({
        isLoading: false,
      })
    );

    renderRoute('/submissions/abc/result');

    screen.getByText('Invalid submission identifier');
    expect(useSubmissionProcessingStatusMock).toHaveBeenCalledWith(
      expect.objectContaining({ examSubmissionId: 0, enabled: false })
    );
  });

  test('terminal status does not continue polling', () => {
    const completed = loadFixture('completed.json');
    useSubmissionProcessingStatusMock.mockReturnValue(
      makeHookState({
        data: completed,
        status: 'COMPLETED',
        isLoading: false,
        isPolling: false,
        isTerminal: true,
      })
    );

    renderRoute('/submissions/12005/result');

    screen.getByText('Automatic checking has stopped.');
  });
});

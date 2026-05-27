import { render, screen, within } from '@testing-library/react';
import { describe, expect, test, vi } from 'vitest';

import { SubmissionProcessingResultPanel } from '../components/SubmissionProcessingResultPanel';
import { ProcessingStatusApiError, ProcessingStatusResponse } from '../types';
import { loadProcessingStatusFixture } from './testPaths';

const FORBIDDEN_TOKENS = [
  'answer_state',
  'answer_text',
  'sealed_answer_text',
  'raw_answer',
  'row_payload_json',
  'capture_dataset_row',
  'password',
  'dsn',
  'traceback',
  'select *',
];

function loadFixture(name: string): ProcessingStatusResponse {
  return loadProcessingStatusFixture<ProcessingStatusResponse>(name);
}

function renderFromFixture(name: string) {
  const data = loadFixture(name);
  return render(
    <SubmissionProcessingResultPanel
      data={data}
      status={data.overall_status}
      error={null}
      isLoading={false}
      isPolling={!data.is_terminal}
      isTerminal={data.is_terminal}
      onRetryFailure={vi.fn()}
    />
  );
}

describe('SubmissionProcessingResultPanel', () => {
  test('renders WAITING_CAPTURE state', () => {
    renderFromFixture('waiting_capture.json');
    screen.getByText("Preparing and capturing the student's database state.");
    screen.getByText('Polling is active.');
  });

  test('renders CAPTURING state', () => {
    renderFromFixture('capturing.json');
    screen.getByText('Capture is in progress.');
  });

  test('renders WAITING_GRADING state', () => {
    renderFromFixture('waiting_grading.json');
    screen.getByText('Your submission is queued for grading.');
  });

  test('renders GRADING state', () => {
    renderFromFixture('grading.json');
    screen.getByText('Your submission is being graded.');
  });

  test('renders COMPLETED state with score summary only when appropriate', () => {
    renderFromFixture('completed.json');
    screen.getByText('Processing completed.');
    screen.getByText('Score Summary');
    screen.getByText('Total score:');

    const waiting = loadFixture('waiting_grading.json');
    render(
      <SubmissionProcessingResultPanel
        data={waiting}
        status={waiting.overall_status}
        error={null}
        isLoading={false}
        isPolling={true}
        isTerminal={false}
      />
    );
    expect(screen.queryAllByText('Score Summary').length).toBe(1);
  });

  test('renders CAPTURE_FAILED failure notice and retry action', () => {
    const retrySpy = vi.fn();
    const data = loadFixture('capture_failed.json');
    render(
      <SubmissionProcessingResultPanel
        data={data}
        status={data.overall_status}
        error={null}
        isLoading={false}
        isPolling={false}
        isTerminal={true}
        onRetryFailure={retrySpy}
      />
    );

    screen.getByText('Processing failed');
    const alert = screen.getByRole('alert');
    within(alert).getByText('Capture step failed.');
    screen.getByText('Reason code:');
    screen.getByRole('button', { name: 'Retry now' }).click();
    expect(retrySpy).toHaveBeenCalledTimes(1);
  });

  test('renders GRADING_FAILED failure notice', () => {
    renderFromFixture('grading_failed.json');
    screen.getByText('Processing failed');
    screen.getByText('Grading step failed.');
  });

  test('renders NEEDS_REVIEW as manual review, not failure', () => {
    renderFromFixture('needs_review.json');
    screen.getByText('Manual review is required before final release.');
    screen.getByText('Manual review required');
    expect(screen.queryByText('Processing failed')).toBeNull();
  });

  test('renders 403 access denied state', () => {
    const error: ProcessingStatusApiError = {
      code: 'permission_denied',
      message: 'Insufficient permissions',
      details: {},
      request_id: null,
    };

    render(
      <SubmissionProcessingResultPanel
        data={null}
        status={null}
        error={error}
        isLoading={false}
        isPolling={false}
        isTerminal={true}
      />
    );

    screen.getByText('Access denied');
    expect(screen.queryByRole('button', { name: 'Retry now' })).toBeNull();
  });

  test('renders 404 not found state', () => {
    const error: ProcessingStatusApiError = {
      code: 'submission_not_found',
      message: 'Submission not found',
      details: {},
      request_id: null,
    };

    render(
      <SubmissionProcessingResultPanel
        data={null}
        status={null}
        error={error}
        isLoading={false}
        isPolling={false}
        isTerminal={true}
      />
    );

    screen.getByText('Submission not found');
    expect(screen.queryByRole('button', { name: 'Retry now' })).toBeNull();
  });

  test('renders temporary error retry button when callback is provided', () => {
    const retrySpy = vi.fn();
    const error: ProcessingStatusApiError = {
      code: 'database_unavailable',
      message: 'Database temporarily unavailable',
      details: {},
      request_id: null,
    };

    render(
      <SubmissionProcessingResultPanel
        data={null}
        status={null}
        error={error}
        isLoading={false}
        isPolling={true}
        isTerminal={false}
        onRetryTemporary={retrySpy}
      />
    );

    screen.getByText('Service temporarily unavailable');
    screen.getByRole('button', { name: 'Retry now' }).click();
    expect(retrySpy).toHaveBeenCalledTimes(1);
  });

  test('renders unknown status fallback', () => {
    const data = loadFixture('waiting_grading.json');
    render(
      <SubmissionProcessingResultPanel
        data={data}
        status={'UNKNOWN'}
        error={null}
        isLoading={false}
        isPolling={false}
        isTerminal={true}
      />
    );

    screen.getByText('Processing status unavailable');
  });

  test('does not render forbidden tokens in UI output', () => {
    const rendered = renderFromFixture('capture_failed.json');
    const text = (rendered.container.textContent ?? '').toLowerCase();

    for (const token of FORBIDDEN_TOKENS) {
      expect(text.includes(token)).toBe(false);
    }
  });
});

import { readdirSync } from 'node:fs';

import { render, screen } from '@testing-library/react';
import { describe, expect, test, vi } from 'vitest';

import { SubmissionProcessingResultPanel } from '../components/SubmissionProcessingResultPanel';
import { ProcessingStatusApiError, ProcessingStatusResponse } from '../types';
import { loadProcessingStatusFixture, PROCESSING_STATUS_FIXTURE_DIR } from './testPaths';

const FORBIDDEN_TOKENS = [
  'answer_state',
  'answer_text',
  'sealed_answer_text',
  'raw_answer',
  'row_payload_json',
  'capture_dataset_row',
  'student_capture_source_dsn',
  'password',
  'dsn',
  'traceback',
  'select *',
];

function loadFixture(name: string): ProcessingStatusResponse {
  return loadProcessingStatusFixture<ProcessingStatusResponse>(name);
}

function expectNoForbiddenTokens(text: string, context: string): void {
  const normalized = text.toLowerCase();
  for (const token of FORBIDDEN_TOKENS) {
    expect(normalized.includes(token), `${context} leaked token: ${token}`).toBe(false);
  }
}

describe('processing status redaction guards', () => {
  test('rendering all status fixtures does not leak forbidden content', () => {
    const fixtureFiles = readdirSync(PROCESSING_STATUS_FIXTURE_DIR).filter((name) => name.endsWith('.json'));
    expect(fixtureFiles.length).toBeGreaterThan(0);

    for (const fixtureFile of fixtureFiles) {
      const data = loadFixture(fixtureFile);
      const rendered = render(
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

      expectNoForbiddenTokens(rendered.container.textContent ?? '', fixtureFile);
      rendered.unmount();
    }
  });

  test.each([
    {
      code: 'permission_denied',
      expectedHeadline: 'Access denied',
      expectedStatus: 403,
    },
    {
      code: 'submission_not_found',
      expectedHeadline: 'Submission not found',
      expectedStatus: 404,
    },
    {
      code: 'validation_error',
      expectedHeadline: 'Invalid request',
      expectedStatus: 422,
    },
    {
      code: 'database_unavailable',
      expectedHeadline: 'Service temporarily unavailable',
      expectedStatus: 503,
    },
  ])(
    'error view for HTTP $expectedStatus is redacted',
    ({ code, expectedHeadline }) => {
      const error: ProcessingStatusApiError = {
        code,
        message: 'traceback password=secret dsn=postgres://u:p@host/db SELECT * FROM submission.answer_state',
        details: {
          db: 'STUDENT_CAPTURE_SOURCE_DSN=postgres://u:p@host/db',
          trace: 'Traceback (most recent call last): ...',
          sql: 'SELECT * FROM capture.capture_dataset_row',
        },
        request_id: 'req-sensitive-123',
      };

      const rendered = render(
        <SubmissionProcessingResultPanel
          data={null}
          status={null}
          error={error}
          isLoading={false}
          isPolling={code === 'database_unavailable'}
          isTerminal={code !== 'database_unavailable'}
          onRetryTemporary={vi.fn()}
        />
      );

      screen.getByText(expectedHeadline);
      expectNoForbiddenTokens(rendered.container.textContent ?? '', `error:${code}`);
      rendered.unmount();
    }
  );
});

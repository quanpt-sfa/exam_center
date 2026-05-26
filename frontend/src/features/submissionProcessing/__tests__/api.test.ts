import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { afterEach, describe, expect, test, vi } from 'vitest';

import { buildApiUrl } from '../../../shared/api/httpClient';
import { getSubmissionProcessingStatus } from '../api';

const CURRENT_DIR = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(CURRENT_DIR, '..', '..', '..', '..', '..', '..');
const PROCESSING_FIXTURE_DIR = resolve(REPO_ROOT, 'apps', 'api', 'tests', 'fixtures', 'processing_status');

function loadProcessingFixture(name: string): unknown {
  const fixturePath = resolve(PROCESSING_FIXTURE_DIR, name);
  const raw = readFileSync(fixturePath, 'utf-8');
  return JSON.parse(raw);
}

describe('submissionProcessing api client', () => {
  afterEach(() => {
    window.localStorage.clear();
  });

  test('builds correct URL', async () => {
    const completed = loadProcessingFixture('completed.json');
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ ok: true, data: completed, error: null }),
    });
    vi.stubGlobal('fetch', fetchMock);

    const result = await getSubmissionProcessingStatus(12005);

    expect(result.ok).toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith(
      buildApiUrl('/submissions/12005/processing-status'),
      expect.objectContaining({ method: 'GET', credentials: 'include' })
    );
  });

  test('rejects invalid examSubmissionId', async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);

    const result = await getSubmissionProcessingStatus(0);

    expect(result.ok).toBe(false);
    if (result.ok) {
      return;
    }
    expect(result.status).toBe(422);
    expect(result.error.code).toBe('invalid_exam_submission_id');
    expect(fetchMock).not.toHaveBeenCalled();
  });

  test('parses successful COMPLETED response fixture', async () => {
    const completed = loadProcessingFixture('completed.json');
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ ok: true, data: completed, error: null }),
      })
    );

    const result = await getSubmissionProcessingStatus(12005);

    expect(result.ok).toBe(true);
    if (!result.ok) {
      return;
    }
    expect(result.data.overall_status).toBe('COMPLETED');
    expect(result.data.score.total_score).toBe(8.5);
  });

  test('parses WAITING_CAPTURE response fixture', async () => {
    const waitingCapture = loadProcessingFixture('waiting_capture.json');
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ ok: true, data: waitingCapture, error: null }),
      })
    );

    const result = await getSubmissionProcessingStatus(12002);

    expect(result.ok).toBe(true);
    if (!result.ok) {
      return;
    }
    expect(result.data.overall_status).toBe('WAITING_CAPTURE');
    expect(result.data.capture.required).toBe(true);
  });

  test('handles 403 forbidden', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 403,
        json: async () => ({
          error: {
            code: 'permission_denied',
            message: 'Insufficient permissions',
            details: { exam_submission_id: 12009 },
            request_id: 'req-demo-403',
          },
        }),
      })
    );

    const result = await getSubmissionProcessingStatus(12009);

    expect(result.ok).toBe(false);
    if (result.ok) {
      return;
    }
    expect(result.status).toBe(403);
    expect(result.error.code).toBe('permission_denied');
  });

  test('handles 404 not found', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        json: async () => ({
          error: {
            code: 'submission_not_found',
            message: 'Submission not found',
            details: { exam_submission_id: 999999 },
            request_id: 'req-demo-404',
          },
        }),
      })
    );

    const result = await getSubmissionProcessingStatus(999999);

    expect(result.ok).toBe(false);
    if (result.ok) {
      return;
    }
    expect(result.status).toBe(404);
    expect(result.error.code).toBe('submission_not_found');
  });

  test('handles 503 database unavailable', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 503,
        json: async () => ({
          error: {
            code: 'database_unavailable',
            message: 'Database temporarily unavailable',
            details: { exam_submission_id: 12010 },
            request_id: 'req-demo-503',
          },
        }),
      })
    );

    const result = await getSubmissionProcessingStatus(12010);

    expect(result.ok).toBe(false);
    if (result.ok) {
      return;
    }
    expect(result.status).toBe(503);
    expect(result.error.code).toBe('database_unavailable');
  });

  test('treats malformed response as client error', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ ok: true, data: { unexpected: true }, error: null }),
      })
    );

    const result = await getSubmissionProcessingStatus(12011);

    expect(result.ok).toBe(false);
    if (result.ok) {
      return;
    }
    expect(result.status).toBe(502);
    expect(result.error.code).toBe('malformed_response');
  });

  test('supports AbortSignal', async () => {
    const abortError = new DOMException('Aborted', 'AbortError');
    const fetchMock = vi.fn().mockRejectedValue(abortError);
    vi.stubGlobal('fetch', fetchMock);

    const controller = new AbortController();
    controller.abort();

    const result = await getSubmissionProcessingStatus(12005, { signal: controller.signal });

    expect(result.ok).toBe(false);
    if (result.ok) {
      return;
    }
    expect(result.status).toBe(0);
    expect(result.error.code).toBe('request_aborted');
    expect(fetchMock).toHaveBeenCalledWith(
      buildApiUrl('/submissions/12005/processing-status'),
      expect.objectContaining({ signal: controller.signal })
    );
  });

  test('includes bearer Authorization header when access token exists', async () => {
    window.localStorage.setItem('exam_sys_next_access_token', 'submission-token');
    const completed = loadProcessingFixture('completed.json');
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ ok: true, data: completed, error: null }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await getSubmissionProcessingStatus(12012);

    const [, options] = fetchMock.mock.calls[0];
    const headers = new Headers(options.headers as HeadersInit);
    expect(headers.get('Authorization')).toBe('Bearer submission-token');
  });

  test('does not include bearer Authorization header when access token is absent', async () => {
    const completed = loadProcessingFixture('completed.json');
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ ok: true, data: completed, error: null }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await getSubmissionProcessingStatus(12013);

    const [, options] = fetchMock.mock.calls[0];
    const headers = new Headers(options.headers as HeadersInit);
    expect(headers.get('Authorization')).toBeNull();
  });
});

import { buildApiUrl } from '../../shared/api/httpClient';
import { getAccessToken } from '../../shared/auth/tokenStorage';
import { isProcessingOverallStatus } from './statusContract';
import { ProcessingStatusApiError, ProcessingStatusApiResult, ProcessingStatusResponse } from './types';

export const PROCESSING_PUBLIC_RESPONSE_FIELDS = [
  'exam_submission_id',
  'overall_status',
  'is_terminal',
  'can_retry',
  'pending_reason',
  'failure_reason',
  'seal',
  'capture',
  'grading',
  'tasks',
  'results',
  'score',
  'timestamps',
] as const;

const FORBIDDEN_FIELD_KEYS = new Set([
  'answer_state',
  'answer_text',
  'sealed_answer_text',
  'raw_answer',
  'row_payload_json',
  'capture_dataset_row',
]);

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function hasForbiddenKey(value: unknown): boolean {
  if (!isObject(value)) {
    return false;
  }

  for (const [key, nestedValue] of Object.entries(value)) {
    if (FORBIDDEN_FIELD_KEYS.has(key)) {
      return true;
    }
    if (hasForbiddenKey(nestedValue)) {
      return true;
    }
  }
  return false;
}

function fallbackCodeForStatus(status: number): string {
  if (status === 403) return 'permission_denied';
  if (status === 404) return 'submission_not_found';
  if (status === 422) return 'validation_error';
  if (status === 503) return 'database_unavailable';
  return 'request_failed';
}

function typedError(
  status: number,
  code: string,
  message: string,
  details: Record<string, unknown> = {}
): ProcessingStatusApiResult {
  return {
    ok: false,
    status,
    error: {
      code,
      message,
      details,
      request_id: null,
    },
  };
}

function parseErrorEnvelope(payload: unknown, status: number): ProcessingStatusApiError {
  if (isObject(payload) && isObject(payload.error)) {
    const details = isObject(payload.error.details) ? payload.error.details : {};
    return {
      code: typeof payload.error.code === 'string' ? payload.error.code : fallbackCodeForStatus(status),
      message: typeof payload.error.message === 'string' ? payload.error.message : `Request failed with status ${status}`,
      details,
      request_id: typeof payload.error.request_id === 'string' ? payload.error.request_id : null,
    };
  }

  return {
    code: fallbackCodeForStatus(status),
    message: `Request failed with status ${status}`,
    details: {},
    request_id: null,
  };
}

function isProcessingStatusResponse(payload: unknown): payload is ProcessingStatusResponse {
  if (!isObject(payload)) {
    return false;
  }

  for (const key of PROCESSING_PUBLIC_RESPONSE_FIELDS) {
    if (!(key in payload)) {
      return false;
    }
  }

  if (!Number.isInteger(payload.exam_submission_id) || payload.exam_submission_id <= 0) {
    return false;
  }

  if (!isProcessingOverallStatus(payload.overall_status)) {
    return false;
  }

  if (typeof payload.is_terminal !== 'boolean' || typeof payload.can_retry !== 'boolean') {
    return false;
  }

  if (payload.pending_reason !== null && typeof payload.pending_reason !== 'string') {
    return false;
  }

  if (payload.failure_reason !== null && typeof payload.failure_reason !== 'string') {
    return false;
  }

  if (!isObject(payload.seal) || !isObject(payload.capture) || !isObject(payload.grading)) {
    return false;
  }

  if (!isObject(payload.tasks) || !isObject(payload.results) || !isObject(payload.score) || !isObject(payload.timestamps)) {
    return false;
  }

  if (hasForbiddenKey(payload)) {
    return false;
  }

  return true;
}

function parseSuccessEnvelope(payload: unknown): ProcessingStatusResponse | null {
  if (!isObject(payload) || payload.ok !== true || !('data' in payload)) {
    return null;
  }

  const responseData = payload.data;
  if (!isProcessingStatusResponse(responseData)) {
    return null;
  }

  return responseData;
}

export async function getSubmissionProcessingStatus(
  examSubmissionId: number,
  options?: { signal?: AbortSignal }
): Promise<ProcessingStatusApiResult> {
  if (!Number.isInteger(examSubmissionId) || examSubmissionId <= 0) {
    return typedError(422, 'invalid_exam_submission_id', 'examSubmissionId must be a positive integer');
  }

  const path = `/submissions/${examSubmissionId}/processing-status`;
  const requestUrl = buildApiUrl(path);
  const accessToken = getAccessToken();
  const headers = new Headers({
    Accept: 'application/json',
  });
  if (accessToken) {
    headers.set('Authorization', `Bearer ${accessToken}`);
  }

  let response: Response;
  try {
    response = await fetch(requestUrl, {
      method: 'GET',
      credentials: 'include',
      headers,
      signal: options?.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      return typedError(0, 'request_aborted', 'Request was aborted');
    }

    return typedError(0, 'network_error', 'Network request failed');
  }

  const payload = await response.json().catch(() => null);

  if (response.ok) {
    const data = parseSuccessEnvelope(payload);
    if (data !== null) {
      return { ok: true, data };
    }

    return typedError(502, 'malformed_response', 'Processing status response shape is invalid');
  }

  return {
    ok: false,
    status: response.status,
    error: parseErrorEnvelope(payload, response.status),
  };
}

export interface ApiErrorDetail {
  code: string;
  message: string;
  details?: unknown;
  request_id?: string;
}

export interface ApiSuccessEnvelope<T> {
  ok: true;
  success: true;
  data: T;
  error: null;
  message: null;
}

export interface ApiErrorEnvelope {
  ok: false;
  success: false;
  data: null;
  error: ApiErrorDetail;
  message: null;
}

export type ApiEnvelope<T> = ApiSuccessEnvelope<T> | ApiErrorEnvelope;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

export function parseApiSuccess<T>(payload: unknown): ApiSuccessEnvelope<T> {
  if (!isRecord(payload) || payload.ok !== true || !('data' in payload)) {
    throw new Error('Invalid success envelope');
  }

  return {
    ok: true,
    success: true,
    data: payload.data as T,
    error: null,
    message: null,
  };
}

export function parseApiError(payload: unknown): ApiErrorEnvelope {
  const fallback: ApiErrorEnvelope = {
    ok: false,
    success: false,
    data: null,
    error: {
      code: 'unknown_error',
      message: 'Unknown error',
    },
    message: null,
  };

  if (!isRecord(payload) || !isRecord(payload.error)) {
    return fallback;
  }

  const errorObject = payload.error;
  const code =
    typeof errorObject.code === 'string' && errorObject.code.trim()
      ? errorObject.code
      : 'unknown_error';
  const message =
    typeof errorObject.message === 'string' && errorObject.message.trim()
      ? errorObject.message
      : 'Unknown error';

  return {
    ok: false,
    success: false,
    data: null,
    error: {
      code,
      message,
      details: errorObject.details,
      request_id: typeof errorObject.request_id === 'string' ? errorObject.request_id : undefined,
    },
    message: null,
  };
}

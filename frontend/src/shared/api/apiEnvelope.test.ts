import { describe, expect, test } from 'vitest';
import { parseApiError, parseApiSuccess } from './apiEnvelope';

describe('apiEnvelope', () => {
  test('apiEnvelope parses success response', () => {
    const payload = {
      ok: true,
      data: [{ id: 1 }],
      error: null,
    };

    const parsed = parseApiSuccess<Array<{ id: number }>>(payload);
    expect(parsed.ok).toBe(true);
    expect(parsed.success).toBe(true);
    expect(parsed.data[0].id).toBe(1);
  });

  test('apiEnvelope parses error response', () => {
    const payload = {
      error: {
        code: 'validation_error',
        message: 'Invalid request',
        details: { field: 'identifier' },
        request_id: 'req-1',
      },
    };

    const parsed = parseApiError(payload);
    expect(parsed.ok).toBe(false);
    expect(parsed.success).toBe(false);
    expect(parsed.error.code).toBe('validation_error');
    expect(parsed.error.request_id).toBe('req-1');
  });
});

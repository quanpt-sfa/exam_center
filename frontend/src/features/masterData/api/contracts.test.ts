import { describe, expect, test } from 'vitest';
import { normalizePaginatedListEnvelope, normalizePagination } from './contracts';

describe('master data contracts', () => {
  test('normalizePagination keeps canonical backend pagination fields', () => {
    expect(
      normalizePagination({
        page: 2,
        page_size: 50,
        total: 120,
        total_pages: 3,
        has_next: true,
        has_previous: true,
      })
    ).toEqual({
      page: 2,
      page_size: 50,
      total: 120,
      total_pages: 3,
      has_next: true,
      has_previous: true,
    });
  });

  test('normalizePagination backfills legacy total_items only at the API boundary', () => {
    expect(
      normalizePagination({
        page: 1,
        page_size: 20,
        total_items: 41,
      })
    ).toEqual({
      page: 1,
      page_size: 20,
      total: 41,
      total_pages: 3,
      has_next: true,
      has_previous: false,
    });
  });

  test('normalizePaginatedListEnvelope preserves error envelopes and normalizes success payloads', () => {
    expect(
      normalizePaginatedListEnvelope({
        ok: true,
        success: true,
        data: {
          items: [{ department_id: 1 }],
          pagination: { page: 1, page_size: 20, total: 1, has_next: false, has_previous: false },
        },
        error: null,
        message: null,
      })
    ).toEqual({
      ok: true,
      success: true,
      data: {
        items: [{ department_id: 1 }],
        pagination: { page: 1, page_size: 20, total: 1, total_pages: 1, has_next: false, has_previous: false },
      },
      error: null,
      message: null,
    });

    const errorEnvelope = {
      ok: false as const,
      success: false as const,
      data: null,
      error: { code: 'request_failed', message: 'Boom' },
      message: null,
    };
    expect(normalizePaginatedListEnvelope(errorEnvelope)).toBe(errorEnvelope);
  });
});

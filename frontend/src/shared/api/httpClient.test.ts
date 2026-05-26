import { afterEach, describe, expect, test, vi } from 'vitest';
import { httpRequest } from './httpClient';

afterEach(() => {
  window.localStorage.clear();
  vi.unstubAllGlobals();
});

describe('httpClient', () => {
  test('httpClient includes credentials for session cookies', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      json: async () => ({ ok: true, data: [], error: null }),
    });

    vi.stubGlobal('fetch', fetchMock);

    await httpRequest('/health');

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, options] = fetchMock.mock.calls[0];
    expect(options.credentials).toBe('include');
  });

  test('httpClient sends bearer Authorization header when token is present', async () => {
    window.localStorage.setItem('exam_sys_next_access_token', 'demo-token');

    const fetchMock = vi.fn().mockResolvedValue({
      json: async () => ({ ok: true, data: [], error: null }),
    });

    vi.stubGlobal('fetch', fetchMock);

    await httpRequest('/health');

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, options] = fetchMock.mock.calls[0];
    const headers = new Headers(options.headers as HeadersInit);
    expect(headers.get('Authorization')).toBe('Bearer demo-token');
  });

  test('httpClient refreshes access token and retries once after 401', async () => {
    window.localStorage.setItem('exam_sys_next_access_token', 'expired-access-token');
    window.localStorage.setItem('exam_sys_next_refresh_token', 'valid-refresh-token');

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        status: 401,
        ok: false,
        json: async () => ({
          ok: false,
          error: { code: 'unauthorized', message: 'Expired' },
        }),
      })
      .mockResolvedValueOnce({
        status: 200,
        ok: true,
        json: async () => ({
          ok: true,
          data: {
            access_token: 'new-access-token',
            refresh_token: 'new-refresh-token',
          },
          error: null,
        }),
      })
      .mockResolvedValueOnce({
        status: 200,
        ok: true,
        json: async () => ({
          ok: true,
          data: [{ id: 1 }],
          error: null,
        }),
      });

    vi.stubGlobal('fetch', fetchMock);

    const response = await httpRequest('/auth/me');

    expect(response.ok).toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock.mock.calls[1][0]).toContain('/api/v1/auth/refresh');
    expect(window.localStorage.getItem('exam_sys_next_access_token')).toBe('new-access-token');
    expect(window.localStorage.getItem('exam_sys_next_refresh_token')).toBe('new-refresh-token');

    const [, retryOptions] = fetchMock.mock.calls[2];
    const retryHeaders = new Headers(retryOptions.headers as HeadersInit);
    expect(retryHeaders.get('Authorization')).toBe('Bearer new-access-token');
  });
});

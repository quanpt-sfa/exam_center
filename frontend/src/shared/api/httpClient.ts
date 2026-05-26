import { ApiEnvelope, ApiErrorEnvelope, parseApiError, parseApiSuccess } from './apiEnvelope';
import { clearAuthTokens, getAccessToken, getRefreshToken, setAccessToken, setRefreshToken } from '../auth/tokenStorage';

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');
const apiPrefix = '/api/v1';

function normalizePath(path: string): string {
  return path.startsWith('/') ? path : `/${path}`;
}

function fallbackError(status: number): ApiErrorEnvelope {
  return parseApiError({
    error: {
      code: status === 401 ? 'unauthenticated' : 'request_failed',
      message: `Request failed with status ${status}`,
    },
  });
}

export function buildApiUrl(path: string): string {
  return `${apiBaseUrl}${apiPrefix}${normalizePath(path)}`;
}

type RefreshTokenResult = {
  access_token: string;
  refresh_token: string;
};

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    return null;
  }

  let response: Response;
  try {
    response = await fetch(buildApiUrl('/auth/refresh'), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
  } catch {
    return null;
  }

  const payload = await response.json().catch(() => null);
  if (!response.ok || !payload || typeof payload !== 'object') {
    clearAuthTokens();
    return null;
  }

  try {
    const envelope = parseApiSuccess<RefreshTokenResult>(payload);
    setAccessToken(envelope.data.access_token);
    setRefreshToken(envelope.data.refresh_token);
    return envelope.data.access_token;
  } catch {
    clearAuthTokens();
    return null;
  }
}

async function fetchWithAuth(path: string, init?: RequestInit, overrideAccessToken?: string | null): Promise<Response> {
  const headers = new Headers(init?.headers ?? {});
  const hasMultipartBody = typeof FormData !== 'undefined' && init?.body instanceof FormData;
  if (!headers.has('Content-Type') && init?.body && !hasMultipartBody) {
    headers.set('Content-Type', 'application/json');
  }

  const accessToken = overrideAccessToken ?? getAccessToken();
  if (accessToken && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${accessToken}`);
  }

  return fetch(buildApiUrl(path), {
    ...init,
    headers,
    credentials: 'include',
  });
}

export async function httpRequest<T>(path: string, init?: RequestInit): Promise<ApiEnvelope<T>> {
  let response: Response;
  try {
    response = await fetchWithAuth(path, init);
  } catch {
    return parseApiError({
      error: {
        code: 'network_error',
        message: 'Network request failed',
      },
    });
  }

  if (response.status === 401 && normalizePath(path) !== '/auth/refresh') {
    const newAccessToken = await refreshAccessToken();
    if (newAccessToken) {
      try {
        response = await fetchWithAuth(path, init, newAccessToken);
      } catch {
        return parseApiError({
          error: {
            code: 'network_error',
            message: 'Network request failed',
          },
        });
      }
    }
  }

  const payload = await response.json().catch(() => null);
  if (payload && typeof payload === 'object') {
    const typed = payload as Record<string, unknown>;
    if (typed.ok === true) {
      return parseApiSuccess<T>(typed);
    }

    if ('error' in typed) {
      return parseApiError(typed);
    }
  }

  if (!response.ok) {
    return fallbackError(response.status);
  }

  return parseApiError({
    error: {
      code: 'invalid_response',
      message: 'Invalid API response envelope',
    },
  });
}

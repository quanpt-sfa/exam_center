const ACCESS_TOKEN_STORAGE_KEY = 'exam_sys_next_access_token';
const REFRESH_TOKEN_STORAGE_KEY = 'exam_sys_next_refresh_token';

function canUseStorage(): boolean {
  return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined';
}

export function getAccessToken(): string | null {
  if (!canUseStorage()) {
    return null;
  }

  try {
    const token = window.localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY);
    if (!token) {
      return null;
    }
    return token.trim() || null;
  } catch {
    return null;
  }
}

export function setAccessToken(token: string): void {
  if (!canUseStorage()) {
    return;
  }

  const value = String(token || '').trim();
  if (!value) {
    window.localStorage.removeItem(ACCESS_TOKEN_STORAGE_KEY);
    return;
  }

  window.localStorage.setItem(ACCESS_TOKEN_STORAGE_KEY, value);
}

export function getRefreshToken(): string | null {
  if (!canUseStorage()) {
    return null;
  }

  try {
    const token = window.localStorage.getItem(REFRESH_TOKEN_STORAGE_KEY);
    if (!token) {
      return null;
    }
    return token.trim() || null;
  } catch {
    return null;
  }
}

export function setRefreshToken(token: string): void {
  if (!canUseStorage()) {
    return;
  }

  const value = String(token || '').trim();
  if (!value) {
    window.localStorage.removeItem(REFRESH_TOKEN_STORAGE_KEY);
    return;
  }

  window.localStorage.setItem(REFRESH_TOKEN_STORAGE_KEY, value);
}

export function clearAccessToken(): void {
  if (!canUseStorage()) {
    return;
  }
  window.localStorage.removeItem(ACCESS_TOKEN_STORAGE_KEY);
}

export function clearAuthTokens(): void {
  if (!canUseStorage()) {
    return;
  }
  window.localStorage.removeItem(ACCESS_TOKEN_STORAGE_KEY);
  window.localStorage.removeItem(REFRESH_TOKEN_STORAGE_KEY);
}

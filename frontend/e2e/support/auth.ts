import type { BrowserContext, Page } from '@playwright/test';
import { authMode, envText, frontendBaseUrl, type Ue2ePersona } from './env';
import { seedAuthPrincipals, type AuthPrincipalSeedResult } from './seed';

export type AuthResult = {
  ok: boolean;
  reason?: string;
};

const ACCESS_TOKEN_STORAGE_KEY = 'exam_sys_next_access_token';

let cachedAuthSeed: AuthPrincipalSeedResult | null = null;

function getAuthSeed(): AuthPrincipalSeedResult {
  if (cachedAuthSeed) {
    return cachedAuthSeed;
  }
  cachedAuthSeed = seedAuthPrincipals();
  return cachedAuthSeed;
}

function parseCookiePair(raw: string): { name: string; value: string } | null {
  const trimmed = raw.trim();
  if (!trimmed || !trimmed.includes('=')) {
    return null;
  }
  const firstPart = trimmed.split(';', 1)[0] || '';
  const index = firstPart.indexOf('=');
  if (index <= 0) {
    return null;
  }
  const name = firstPart.slice(0, index).trim();
  const value = firstPart.slice(index + 1).trim();
  if (!name || !value) {
    return null;
  }
  return { name, value };
}

async function applyCookieAuth(context: BrowserContext, rawCookie: string): Promise<AuthResult> {
  const pair = parseCookiePair(rawCookie);
  if (!pair) {
    return {
      ok: false,
      reason: 'Cookie auth mode requires UE2E_STUDENT_X_COOKIE in name=value format.',
    };
  }

  const targetUrl = new URL(frontendBaseUrl());
  await context.addCookies([
    {
      name: pair.name,
      value: pair.value,
      domain: targetUrl.hostname,
      path: '/',
      httpOnly: false,
      secure: targetUrl.protocol === 'https:',
    },
  ]);

  return { ok: true };
}

async function applyUiLogin(page: Page, login: string, password: string): Promise<AuthResult> {
  if (!login || !password) {
    return {
      ok: false,
      reason: 'UI login mode requires UE2E_STUDENT_X_LOGIN and UE2E_STUDENT_X_PASSWORD.',
    };
  }

  await page.goto('/login');
  await page.locator('#identifier').fill(login);
  await page.locator('#password').fill(password);
  await page.getByRole('button', { name: /đăng nhập|dang nhap|sign in/i }).click();
  await page.waitForLoadState('networkidle');
  return { ok: true };
}

async function applyBearerAuth(page: Page, persona: Ue2ePersona): Promise<AuthResult> {
  const seeded = getAuthSeed();
  if (seeded.token_output !== 'raw_machine_mode') {
    return {
      ok: false,
      reason: 'Bearer auth mode requires machine-mode seed tokens (token_output=raw_machine_mode).',
    };
  }

  const token =
    persona === 'studentA' ? seeded.tokens.owner_access_token : seeded.tokens.non_owner_access_token;
  if (!token) {
    return {
      ok: false,
      reason: 'Bearer auth mode requires seed-auth-principals to return owner/non-owner access tokens.',
    };
  }

  await page.addInitScript(
    ({ storageKey, accessToken }) => {
      window.localStorage.setItem(storageKey, accessToken);
    },
    {
      storageKey: ACCESS_TOKEN_STORAGE_KEY,
      accessToken: token,
    }
  );

  return { ok: true };
}

export async function authenticateAs(page: Page, persona: Ue2ePersona): Promise<AuthResult> {
  const mode = authMode();
  const isA = persona === 'studentA';

  if (mode === 'bearer') {
    return applyBearerAuth(page, persona);
  }

  if (mode === 'cookie') {
    const cookieRaw = envText(isA ? 'UE2E_STUDENT_A_COOKIE' : 'UE2E_STUDENT_B_COOKIE');
    if (!cookieRaw) {
      return {
        ok: false,
        reason: 'Cookie auth mode is selected but student cookie env vars are missing.',
      };
    }
    return applyCookieAuth(page.context(), cookieRaw);
  }

  if (mode === 'ui-login') {
    const login = envText(isA ? 'UE2E_STUDENT_A_LOGIN' : 'UE2E_STUDENT_B_LOGIN');
    const password = envText(isA ? 'UE2E_STUDENT_A_PASSWORD' : 'UE2E_STUDENT_B_PASSWORD');
    return applyUiLogin(page, login, password);
  }

  return {
    ok: false,
    reason: 'Unsupported UE2E_AUTH_MODE. Use bearer, cookie, or ui-login.',
  };
}

const TRUE_VALUES = new Set(['1', 'true', 'yes', 'on']);

export type Ue2ePersona = 'studentA' | 'studentB';
export type Ue2eAuthMode = 'bearer' | 'cookie' | 'ui-login';

export function envFlag(name: string, fallback = false): boolean {
  const raw = process.env[name];
  if (typeof raw !== 'string') {
    return fallback;
  }
  return TRUE_VALUES.has(raw.trim().toLowerCase());
}

export function envText(name: string, fallback = ''): string {
  const raw = process.env[name];
  if (typeof raw !== 'string') {
    return fallback;
  }
  return raw.trim();
}

export function requireEnv(name: string): string {
  const value = envText(name);
  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}

export function integrationEnabled(): boolean {
  return envFlag('UE2E_RUN_INTEGRATION', false);
}

export function integrationSkipReason(): string {
  return 'Set UE2E_RUN_INTEGRATION=1 and required test env vars to run browser integration scenarios.';
}

export function authMode(): Ue2eAuthMode {
  const raw = envText('UE2E_AUTH_MODE', 'bearer').toLowerCase();
  if (raw === 'cookie' || raw === 'ui-login' || raw === 'bearer') {
    return raw;
  }
  return 'bearer';
}

export function apiBaseUrl(): string {
  return envText('API_BASE_URL', 'http://127.0.0.1:8001').replace(/\/$/, '');
}

export function frontendBaseUrl(): string {
  return envText('FRONTEND_BASE_URL', 'http://127.0.0.1:4173').replace(/\/$/, '');
}

export function ownerPersona(): Ue2ePersona {
  const raw = envText('UE2E_OWNER_PERSONA', 'studentA').toLowerCase();
  return raw === 'studentb' ? 'studentB' : 'studentA';
}

export function nonOwnerPersona(): Ue2ePersona {
  return ownerPersona() === 'studentA' ? 'studentB' : 'studentA';
}

export function sanitizeValue(value: string): string {
  if (!value) {
    return '<empty>';
  }
  if (value.length <= 4) {
    return '<redacted>';
  }
  return `${value.slice(0, 2)}***${value.slice(-2)}`;
}

export function sanitizedRuntimeSnapshot(): Record<string, string | boolean> {
  return {
    UE2E_RUN_INTEGRATION: integrationEnabled(),
    FRONTEND_BASE_URL: frontendBaseUrl(),
    API_BASE_URL: apiBaseUrl(),
    UE2E_AUTH_MODE: authMode(),
    UE2E_OWNER_PERSONA: ownerPersona(),
    UE2E_STUDENT_A_LOGIN: sanitizeValue(envText('UE2E_STUDENT_A_LOGIN')),
    UE2E_STUDENT_B_LOGIN: sanitizeValue(envText('UE2E_STUDENT_B_LOGIN')),
  };
}

import { existsSync } from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import type { SpawnSyncReturns } from 'node:child_process';

export type SeedResult = {
  scenario: string;
  prefix: string;
  exam_session_id?: number;
  exam_submission_id: number;
  owner_user_id: number | null;
  non_owner_user_id: number | null;
};

export type SubmitSealFlowSeedResult = SeedResult & {
  exam_session_id: number;
  exam_assignment_id: number;
  owner_student_id: number;
  non_owner_student_id: number;
  submission_status: string;
  seeded_answer_text: string;
};

export type EnqueueGradingResult = {
  scenario: 'enqueue_grading_for_submission';
  prefix: string;
  exam_submission_id: number;
  grading_job_id: number;
};

export type CleanupResult = {
  scenario: 'cleanup';
  prefix: string;
  deleted: Record<string, number>;
};

export type AuthPrincipalSeedResult = {
  scenario: 'seed_auth_principals';
  token_type: 'bearer';
  token_output: 'redacted' | 'raw_machine_mode';
  principals: {
    admin: {
      username: string;
      user_id: number;
      person_id: number;
      student_id: null;
      roles: string[];
    };
    owner: {
      username: string;
      user_id: number;
      person_id: number;
      student_id: number;
      roles: string[];
    };
    non_owner: {
      username: string;
      user_id: number;
      person_id: number;
      student_id: number;
      roles: string[];
    };
  };
  tokens: {
    admin_access_token: string;
    owner_access_token: string;
    non_owner_access_token: string;
  };
};

export type AuthJunkAuditResult = {
  scenario: 'audit_auth_junk';
  known_test_prefix_counts: Record<string, number>;
  canonical_accounts: Record<
    string,
    {
      exists: boolean;
      user_id: number | null;
      person_id: number | null;
      student_id: number | null;
      student_code: string | null;
      roles: string[];
      user_status: string | null;
    }
  >;
  junk_candidate_count: number;
  junk_candidate_usernames: string[];
  total_app_users: number;
};

export type AuthJunkCleanupResult = {
  scenario: 'cleanup_auth_junk';
  dry_run: boolean;
  apply: boolean;
  candidate_count: number;
  already_disabled_count: number;
  changed_count: number;
  counts_by_table: Record<string, number>;
  candidate_usernames: string[];
};

type SeedRunner = (
  command: string,
  args: readonly string[],
  options: {
    cwd: string;
    env: NodeJS.ProcessEnv;
    encoding: BufferEncoding;
  }
) => Pick<SpawnSyncReturns<string>, 'status' | 'stdout' | 'stderr'>;

function repoRootPath(): string {
  const currentDir = path.dirname(fileURLToPath(import.meta.url));
  return path.resolve(currentDir, '../../../../');
}

const JWT_LIKE_REGEX = /eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g;

function envEnabled(name: string): boolean {
  const raw = process.env[name];
  if (typeof raw !== 'string') {
    return false;
  }
  return new Set(['1', 'true', 'yes', 'on']).has(raw.trim().toLowerCase());
}

function envAuthMode(): string {
  const raw = process.env.UE2E_AUTH_MODE;
  if (typeof raw !== 'string' || !raw.trim()) {
    return 'bearer';
  }
  return raw.trim().toLowerCase();
}

export function shouldUseMachineTokenSeedMode(): boolean {
  return envEnabled('UE2E_RUN_INTEGRATION') && envAuthMode() === 'bearer';
}

export function sanitizeSeedHelperFailure(output: string): string {
  return String(output || '')
    .replace(/(password\s*[:=]\s*)([^,\s;]+)/gi, '$1<redacted>')
    .replace(/(dsn\s*[:=]\s*)([^,\s;]+)/gi, '$1<redacted>')
    .replace(/("(?:admin|owner|non_owner)_access_token"\s*:\s*")([^"]+)(")/gi, '$1<redacted>$3')
    .replace(/("tokens"\s*:\s*\{[^}]*\})/gis, (fullMatch) =>
      fullMatch.replace(/(:\s*")([^"]+)(")/g, '$1<redacted>$3')
    )
    .replace(/postgres(?:ql)?:\/\/[^\s]+/gi, 'postgresql://<redacted>')
    .replace(JWT_LIKE_REGEX, '<redacted-jwt>');
}

export function buildSeedAuthPrincipalsArgs(): string[] {
  if (!shouldUseMachineTokenSeedMode()) {
    throw new Error(
      'seed-auth-principals machine mode requires UE2E_RUN_INTEGRATION=1 and UE2E_AUTH_MODE=bearer.'
    );
  }
  return ['seed-auth-principals', '--emit-tokens'];
}

function resolvePythonExecutable(repoRoot: string): string {
  const envPython = process.env.UE2E_PYTHON?.trim();
  if (envPython) {
    return envPython;
  }

  const winCandidate = path.join(repoRoot, 'venv', 'Scripts', 'python.exe');
  if (existsSync(winCandidate)) {
    return winCandidate;
  }

  const unixCandidate = path.join(repoRoot, 'venv', 'bin', 'python');
  if (existsSync(unixCandidate)) {
    return unixCandidate;
  }

  return 'python';
}

function parseJsonFromOutput(output: string): unknown {
  const lines = output
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  for (let index = lines.length - 1; index >= 0; index -= 1) {
    const line = lines[index];
    try {
      return JSON.parse(line);
    } catch {
      continue;
    }
  }

  throw new Error('Seed helper did not emit JSON output.');
}

export function runSeedHelperWithRunner(args: string[], runner: SeedRunner): unknown {
  const repoRoot = repoRootPath();
  const python = resolvePythonExecutable(repoRoot);
  const scriptPath = path.join(repoRoot, 'apps', 'frontend', 'scripts', 'ue2e_seed_helper.py');

  const completed = runner(python, [scriptPath, ...args], {
    cwd: repoRoot,
    env: {
      ...process.env,
      EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION: process.env.EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION || '1',
    },
    encoding: 'utf-8',
  });

  if ((completed.status ?? 1) !== 0) {
    const sanitized = sanitizeSeedHelperFailure(`${completed.stdout || ''}\n${completed.stderr || ''}`);
    throw new Error(`Seed helper failed: ${sanitized}`);
  }

  return parseJsonFromOutput(completed.stdout || '');
}

function runSeedHelper(args: string[]): unknown {
  return runSeedHelperWithRunner(args, (command, cmdArgs, options) =>
    spawnSync(command, cmdArgs, options)
  );
}

export function seedTextboxSubmission(suffix: string): SeedResult {
  return runSeedHelper(['seed-textbox', '--suffix', suffix]) as SeedResult;
}

export function seedCaptureFailureSubmission(suffix: string): SeedResult {
  return runSeedHelper(['seed-capture-failure', '--suffix', suffix]) as SeedResult;
}

export function seedSubmitSealFlow(suffix: string): SubmitSealFlowSeedResult {
  return runSeedHelper(['seed-submit-seal-flow', '--suffix', suffix]) as SubmitSealFlowSeedResult;
}

export function enqueueGradingForSubmission(examSubmissionId: number, prefix: string): EnqueueGradingResult {
  return runSeedHelper([
    'enqueue-grading-for-submission',
    '--submission-id',
    String(examSubmissionId),
    '--prefix',
    prefix,
  ]) as EnqueueGradingResult;
}

export function cleanupByPrefix(prefix = 'ue2e-'): CleanupResult {
  return runSeedHelper(['cleanup', '--prefix', prefix]) as CleanupResult;
}

export function seedAuthPrincipals(): AuthPrincipalSeedResult {
  return runSeedHelper(buildSeedAuthPrincipalsArgs()) as AuthPrincipalSeedResult;
}

export function seedAuthPrincipalsWithRunner(runner: SeedRunner): AuthPrincipalSeedResult {
  return runSeedHelperWithRunner(buildSeedAuthPrincipalsArgs(), runner) as AuthPrincipalSeedResult;
}

export function auditAuthJunk(): AuthJunkAuditResult {
  return runSeedHelper(['audit-auth-junk']) as AuthJunkAuditResult;
}

export function cleanupAuthJunk(options?: { apply?: boolean }): AuthJunkCleanupResult {
  const args = ['cleanup-auth-junk'];
  if (options?.apply) {
    args.push('--apply');
  }
  return runSeedHelper(args) as AuthJunkCleanupResult;
}

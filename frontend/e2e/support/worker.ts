import { existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

type WorkerRunOptions = {
  submissionId: number;
  actorUserId?: number | null;
  includeCaptureRole?: boolean;
  boundedIdleCycles?: number;
};

type WorkerRunResult = {
  exitCode: number;
  stdout: string;
  stderr: string;
  command: string;
};

const currentFilePath = fileURLToPath(import.meta.url);
const currentDirPath = path.dirname(currentFilePath);

function repoRootPath(): string {
  return path.resolve(currentDirPath, '../../../../');
}

function sanitizeConsole(text: string): string {
  return text
    .replace(/(password\s*[:=]\s*)([^,\s;]+)/gi, '$1<redacted>')
    .replace(/(dsn\s*[:=]\s*)([^,\s;]+)/gi, '$1<redacted>')
    .replace(/postgres(?:ql)?:\/\/[^\s]+/gi, 'postgresql://<redacted>');
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

function resolveTextboxExecutorDsn(): string | null {
  const explicit = process.env.TEXTBOX_SQL_EXECUTOR_DSN?.trim();
  if (explicit) {
    return explicit;
  }

  const host = (process.env.POSTGRES_HOST || '127.0.0.1').trim();
  const port = (process.env.POSTGRES_PORT || '5432').trim();
  const database = (process.env.POSTGRES_DB || '').trim();
  const user = (process.env.POSTGRES_USER || 'exam_sys_app').trim();
  const password = (process.env.POSTGRES_PASSWORD || process.env.PGPASSWORD || '').trim();
  const sslMode = (process.env.POSTGRES_SSLMODE || 'prefer').trim();
  const connectTimeout = (process.env.POSTGRES_CONNECT_TIMEOUT || '3').trim();

  if (!database) {
    return null;
  }

  if (!password) {
    return null;
  }

  const auth = `${encodeURIComponent(user)}:${encodeURIComponent(password)}`;
  const location = `${host}:${port}/${encodeURIComponent(database)}`;
  const query = `sslmode=${encodeURIComponent(sslMode)}&connect_timeout=${encodeURIComponent(connectTimeout)}`;
  return `postgresql://${auth}@${location}?${query}`;
}

export function runWorkerOnce(options: WorkerRunOptions): WorkerRunResult {
  const repoRoot = repoRootPath();
  const workerRoot = path.join(repoRoot, 'apps', 'worker');
  const python = resolvePythonExecutable(repoRoot);

  const roles = options.includeCaptureRole ? 'dispatcher,capture,grading' : 'dispatcher,grading';
  const args = [
    '-m',
    'worker_runtime.cli',
    'run-all',
    '--once',
    '--roles',
    roles,
    '--dispatcher-submission-id',
    String(options.submissionId),
  ];

  if (typeof options.actorUserId === 'number' && Number.isInteger(options.actorUserId)) {
    args.push('--dispatcher-actor-user-id', String(options.actorUserId));
  }

  if (options.includeCaptureRole) {
    args.push('--allow-app-db-dsn-for-tests', '--use-deterministic-test-adapter');
  }

  if (typeof options.boundedIdleCycles === 'number' && options.boundedIdleCycles > 0) {
    args.push('--stop-after-idle-cycles', String(options.boundedIdleCycles));
  }

  const textboxExecutorDsn = resolveTextboxExecutorDsn();
  const workerEnv: NodeJS.ProcessEnv = {
    ...process.env,
    EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION: process.env.EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION || '1',
  };
  if (textboxExecutorDsn) {
    workerEnv.TEXTBOX_SQL_EXECUTOR_DSN = textboxExecutorDsn;
    workerEnv.ALLOW_TEXTBOX_SQL_APP_DB_DSN_FOR_TESTS =
      process.env.ALLOW_TEXTBOX_SQL_APP_DB_DSN_FOR_TESTS || '1';
  }

  const completed = spawnSync(python, args, {
    cwd: workerRoot,
    env: workerEnv,
    encoding: 'utf-8',
  });

  const stdout = sanitizeConsole(completed.stdout || '');
  const stderr = sanitizeConsole(completed.stderr || '');

  return {
    exitCode: completed.status ?? 1,
    stdout,
    stderr,
    command: [python, ...args].join(' '),
  };
}

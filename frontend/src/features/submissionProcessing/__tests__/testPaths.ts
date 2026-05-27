import { existsSync, readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const CURRENT_TEST_DIR = dirname(fileURLToPath(import.meta.url));
const FRONTEND_ROOT = resolve(CURRENT_TEST_DIR, '..', '..', '..', '..');
const PROJECT_ROOT = resolve(FRONTEND_ROOT, '..');

function expectPathExists(path: string, label: string): string {
  if (!existsSync(path)) {
    throw new Error(`Missing ${label}: ${path}`);
  }
  return path;
}

expectPathExists(resolve(FRONTEND_ROOT, 'package.json'), 'frontend package root');
expectPathExists(resolve(PROJECT_ROOT, 'manifest.yaml'), 'standalone project root');

export const PROCESSING_STATUS_FIXTURE_DIR = expectPathExists(
  resolve(PROJECT_ROOT, 'backend', 'tests', 'fixtures', 'processing_status'),
  'processing status fixture directory'
);

export function loadProcessingStatusFixture<T>(name: string): T {
  const fixturePath = expectPathExists(resolve(PROCESSING_STATUS_FIXTURE_DIR, name), `processing status fixture ${name}`);
  return JSON.parse(readFileSync(fixturePath, 'utf-8')) as T;
}

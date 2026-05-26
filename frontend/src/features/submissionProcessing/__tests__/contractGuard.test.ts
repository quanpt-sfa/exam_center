import { readFileSync, readdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, test } from 'vitest';

import { PROCESSING_PUBLIC_RESPONSE_FIELDS } from '../api';
import {
  ACTIVE_PROCESSING_STATUSES,
  PROCESSING_OVERALL_STATUSES,
  TERMINAL_PROCESSING_STATUSES,
} from '../statusContract';

const CURRENT_DIR = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(CURRENT_DIR, '..', '..', '..', '..', '..', '..');
const FIXTURE_DIR = resolve(REPO_ROOT, 'apps', 'api', 'tests', 'fixtures', 'processing_status');

const EXPECTED_ALL_STATUSES = [
  'NOT_FOUND',
  'DRAFT_OR_UNSEALED',
  'SEALED',
  'WAITING_CAPTURE',
  'CAPTURING',
  'CAPTURE_FAILED',
  'WAITING_GRADING',
  'GRADING',
  'GRADING_FAILED',
  'COMPLETED',
  'NEEDS_REVIEW',
] as const;

const EXPECTED_PUBLIC_RESPONSE_FIELDS = [
  'exam_submission_id',
  'overall_status',
  'is_terminal',
  'can_retry',
  'pending_reason',
  'failure_reason',
  'seal',
  'capture',
  'grading',
  'tasks',
  'results',
  'score',
  'timestamps',
] as const;

const EXPECTED_ACTIVE_STATUSES = [
  'DRAFT_OR_UNSEALED',
  'SEALED',
  'WAITING_CAPTURE',
  'CAPTURING',
  'WAITING_GRADING',
  'GRADING',
] as const;

const EXPECTED_TERMINAL_STATUSES = [
  'COMPLETED',
  'CAPTURE_FAILED',
  'GRADING_FAILED',
  'NEEDS_REVIEW',
  'NOT_FOUND',
] as const;

describe('processing status contract guards', () => {
  test('status enum parity matches frozen backend contract', () => {
    expect(PROCESSING_OVERALL_STATUSES).toEqual(EXPECTED_ALL_STATUSES);
    expect(new Set(PROCESSING_OVERALL_STATUSES).size).toBe(PROCESSING_OVERALL_STATUSES.length);
  });

  test('public response field parity matches frozen backend contract', () => {
    expect(PROCESSING_PUBLIC_RESPONSE_FIELDS).toEqual(EXPECTED_PUBLIC_RESPONSE_FIELDS);
  });

  test('fixture payloads include all required public response fields', () => {
    const fixtureFiles = readdirSync(FIXTURE_DIR).filter((name) => name.endsWith('.json'));
    expect(fixtureFiles.length).toBeGreaterThan(0);

    for (const fixtureFile of fixtureFiles) {
      const payload = JSON.parse(readFileSync(resolve(FIXTURE_DIR, fixtureFile), 'utf-8')) as Record<string, unknown>;
      for (const key of PROCESSING_PUBLIC_RESPONSE_FIELDS) {
        expect(key in payload, `${fixtureFile} is missing ${key}`).toBe(true);
      }
    }
  });

  test('polling matrix parity is unchanged', () => {
    expect(ACTIVE_PROCESSING_STATUSES).toEqual(EXPECTED_ACTIVE_STATUSES);
    expect(TERMINAL_PROCESSING_STATUSES).toEqual([
      'NOT_FOUND',
      'CAPTURE_FAILED',
      'GRADING_FAILED',
      'COMPLETED',
      'NEEDS_REVIEW',
    ]);

    const activeSet = new Set(ACTIVE_PROCESSING_STATUSES);
    const terminalSet = new Set(TERMINAL_PROCESSING_STATUSES);

    for (const status of EXPECTED_ACTIVE_STATUSES) {
      expect(activeSet.has(status)).toBe(true);
      expect(terminalSet.has(status)).toBe(false);
    }

    for (const status of EXPECTED_TERMINAL_STATUSES) {
      expect(terminalSet.has(status)).toBe(true);
      expect(activeSet.has(status)).toBe(false);
    }

    const union = new Set([...ACTIVE_PROCESSING_STATUSES, ...TERMINAL_PROCESSING_STATUSES]);
    for (const status of EXPECTED_ALL_STATUSES) {
      expect(union.has(status)).toBe(true);
    }
  });
});

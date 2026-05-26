import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, test } from 'vitest';

describe('student frontend boundary guards', () => {
  test('examTaking API client does not call grading score endpoints directly', () => {
    const apiPath = resolve(process.cwd(), 'src/features/examTaking/api.ts');
    const content = readFileSync(apiPath, 'utf8').toLowerCase();

    expect(content.includes('/grading/')).toBe(false);
    expect(content.includes('question_score')).toBe(false);
    expect(content.includes('submission_score')).toBe(false);
  });

  test('examTaking page does not embed expected-answer fields', () => {
    const pagePath = resolve(process.cwd(), 'src/features/examTaking/ExamTakingPage.tsx');
    const content = readFileSync(pagePath, 'utf8').toLowerCase();

    expect(content.includes('expected_answer')).toBe(false);
    expect(content.includes('reference_solution')).toBe(false);
    expect(content.includes('generated_expected_answer')).toBe(false);
  });
});

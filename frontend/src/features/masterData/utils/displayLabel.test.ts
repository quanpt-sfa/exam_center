import { describe, expect, test } from 'vitest';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { resolveDisplayLabel } from './displayLabel';

const thisDir = dirname(fileURLToPath(import.meta.url));

describe('resolveDisplayLabel', () => {
  test('renders only Vietnamese by default when vi/en labels both exist', () => {
    const label = resolveDisplayLabel({ labelVi: 'Tên khoa', labelEn: 'Department name' });

    expect(label).toBe('Tên khoa');
    expect(label).not.toBe('Department name');
  });

  test('supports labels object shape with locale override', () => {
    const label = resolveDisplayLabel({ labels: { vi: 'Mã sinh viên', en: 'Student code' } }, 'en');

    expect(label).toBe('Student code');
  });

  test('falls back safely when localized key is missing', () => {
    const label = resolveDisplayLabel({ labelEn: 'Room name' }, 'vi');

    expect(label).toBe('Room name');
  });

  test('returns plain string labels as-is', () => {
    expect(resolveDisplayLabel('Tên môn học')).toBe('Tên môn học');
  });

  test('does not read localStorage directly in feature resolver', () => {
    const source = readFileSync(resolve(thisDir, 'displayLabel.ts'), 'utf8');

    expect(source).not.toContain('localStorage');
  });
});

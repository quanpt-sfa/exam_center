import { describe, expect, test } from 'vitest';
import { buildCsvSample, containsEncodingReplacementCharInRows } from './MasterDataPage';
import type { ImportTemplate } from './masterDataApi';

describe('Master data import encoding guard', () => {
  test('CSV sample starts with UTF-8 BOM and preserves Vietnamese text', () => {
    const template: ImportTemplate = {
      import_type: 'INSTRUCTORS',
      label: 'Giảng viên',
      columns: [
        { name: 'instructor_code', required: true, default: null, description: '' },
        { name: 'full_name', required: true, default: null, description: '' },
      ],
      sample_row: {
        instructor_code: 'GV001',
        full_name: 'Nông Ngọc Duy',
      },
    };

    const csv = buildCsvSample(template);
    expect(csv.startsWith('\uFEFF')).toBe(true);
    expect(csv).toContain('Nông Ngọc Duy');
  });

  test('detects replacement character in parsed rows', () => {
    expect(containsEncodingReplacementCharInRows([{ full_name: 'N�ng Ng?c D?' }])).toBe(true);
    expect(containsEncodingReplacementCharInRows([{ full_name: 'Nông Ngọc Duy' }])).toBe(false);
  });
});


import { describe, expect, test } from 'vitest';
import type { EntityFieldConfig } from '../types';
import { resolveMasterDataFieldLayout } from './fieldLayout';

function makeField(partial: Partial<EntityFieldConfig> & Pick<EntityFieldConfig, 'name' | 'label'>): EntityFieldConfig {
  return {
    ...partial,
  };
}

describe('resolveMasterDataFieldLayout', () => {
  test('uses explicit gridSpan first, then fieldSize metadata', () => {
    const field = makeField({
      name: 'department_code',
      label: 'Mã đơn vị',
      fieldSize: 'sm',
      gridSpan: 8,
    });

    const layout = resolveMasterDataFieldLayout(field);

    expect(layout.fieldSize).toBe('sm');
    expect(layout.gridSpan).toBe(8);
    expect(layout.dataAttributes['data-grid-span']).toBe(8);
  });

  test('uses fieldKind metadata when fieldSize is omitted', () => {
    const field = makeField({
      name: 'department_name',
      label: 'Tên đơn vị',
      fieldKind: 'longName',
    });

    const layout = resolveMasterDataFieldLayout(field);

    expect(layout.fieldKind).toBe('longName');
    expect(layout.fieldSize).toBe('lg');
    expect(layout.className).toContain('field-span-lg');
  });

  test('falls back to name/type heuristic and numeric input mode', () => {
    const field = makeField({
      name: 'entry_year',
      label: 'Năm nhập học',
      type: 'number',
    });

    const layout = resolveMasterDataFieldLayout(field);

    expect(layout.fieldKind).toBe('year');
    expect(layout.fieldSize).toBe('xs');
    expect(layout.inputMode).toBe('numeric');
  });

  test('enables multiline layout for description-like fields', () => {
    const field = makeField({
      name: 'room_description',
      label: 'Mô tả',
      type: 'text',
    });

    const layout = resolveMasterDataFieldLayout(field);

    expect(layout.fieldKind).toBe('description');
    expect(layout.fieldSize).toBe('full');
    expect(layout.multiline).toBe(true);
  });
});

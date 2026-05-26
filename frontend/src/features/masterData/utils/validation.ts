export function parseNumericId(value: string): number | null {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function hasValidBulkRange(start: string, end: string): boolean {
  const startValue = Number(start);
  const endValue = Number(end);
  return Number.isFinite(startValue) && Number.isFinite(endValue) && endValue >= startValue;
}

import { parseFiniteNumber } from '../api/formCoercion';
import type { EntityFieldConfig, EntityFormErrors } from '../types';

export function validateEntityForm(
  fields: EntityFieldConfig[],
  form: Record<string, string>,
  getOptionsForField: (field: EntityFieldConfig) => Array<{ label: string; value: string }>
): EntityFormErrors {
  const errors: EntityFormErrors = {};

  for (const field of fields) {
    const rawValue = String(form[field.name] ?? '');
    const trimmedValue = rawValue.trim();
    const options = field.type === 'select' ? getOptionsForField(field) : [];

    if (field.required && trimmedValue === '') {
      errors[field.name] = field.validationMessage ?? `${field.label} không được để trống.`;
      continue;
    }

    if (trimmedValue === '') {
      continue;
    }

    const parsedNumericValue = field.type === 'number' || field.valueType === 'number' ? parseFiniteNumber(rawValue) : undefined;
    const allowManualNumericValue =
      field.type === 'select' &&
      field.allowManualLookupFallback === true &&
      field.valueType === 'number' &&
      parsedNumericValue !== undefined &&
      (!field.integer || Number.isInteger(parsedNumericValue));

    if (field.type === 'select' && options.length > 0 && !options.some((option) => option.value === rawValue) && !allowManualNumericValue) {
      errors[field.name] = `${field.label} không hợp lệ.`;
      continue;
    }

    if (field.type === 'number' || field.valueType === 'number') {
      const parsed = parsedNumericValue;
      if (parsed === undefined) {
        errors[field.name] = `${field.label} phải là số hợp lệ.`;
        continue;
      }
      if (field.integer && !Number.isInteger(parsed)) {
        errors[field.name] = `${field.label} phải là số nguyên.`;
        continue;
      }
      if (field.min != null && parsed < field.min) {
        errors[field.name] = `${field.label} phải lớn hơn hoặc bằng ${field.min}.`;
        continue;
      }
      if (field.max != null && parsed > field.max) {
        errors[field.name] = `${field.label} phải nhỏ hơn hoặc bằng ${field.max}.`;
      }
    }
  }

  return errors;
}
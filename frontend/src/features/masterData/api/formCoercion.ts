type FormValues = Record<string, string>;

function getRawValue(form: FormValues, fieldName: string): string {
  return String(form[fieldName] ?? '');
}

export function readRequiredTrimmedString(form: FormValues, fieldName: string): string | undefined {
  const value = getRawValue(form, fieldName).trim();
  return value || undefined;
}

export function readOptionalTrimmedString(form: FormValues, fieldName: string): string | undefined {
  const value = getRawValue(form, fieldName).trim();
  return value || undefined;
}

export function readOptionalInteger(form: FormValues, fieldName: string): number | undefined {
  const value = getRawValue(form, fieldName).trim();
  if (!value) {
    return undefined;
  }
  if (!/^-?\d+$/.test(value)) {
    return undefined;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

export function readOptionalNumber(form: FormValues, fieldName: string): number | undefined {
  const value = getRawValue(form, fieldName).trim();
  if (!value) {
    return undefined;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

export function isBlankValue(value: string | undefined | null): boolean {
  return String(value ?? '').trim() === '';
}

export function parseFiniteNumber(value: string): number | undefined {
  const trimmed = value.trim();
  if (!trimmed) {
    return undefined;
  }
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : undefined;
}

export function readCsvTokens(value: string): string[] {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}
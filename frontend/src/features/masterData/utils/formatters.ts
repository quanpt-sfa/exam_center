import type { ImportTemplate } from '../masterDataApi';
import type { MasterDataRow } from '../masterDataApi';

export function getCellValue(row: MasterDataRow, key: string): unknown {
  return key.split('.').reduce<unknown>((value, segment) => {
    if (value && typeof value === 'object') {
      return (value as Record<string, unknown>)[segment];
    }
    return undefined;
  }, row);
}

export function displayCell(value: unknown): string {
  if (value == null || value === '') {
    return '-';
  }
  if (typeof value === 'boolean') {
    return value ? 'Có' : 'Không';
  }
  if (typeof value === 'number') {
    return String(value);
  }
  if (typeof value === 'object') {
    return JSON.stringify(value);
  }
  return String(value);
}

export function departmentOptionLabel(row: MasterDataRow): string {
  const code = String(row.department_code ?? '').trim();
  const name = String(row.department_name ?? '').trim();
  if (code && name) {
    return `${code} - ${name}`;
  }
  return code || name || `Đơn vị #${String(row.department_id ?? '')}`;
}

export function programOptionLabel(row: MasterDataRow): string {
  const code = String(row.program_code ?? '').trim();
  const name = String(row.program_name ?? '').trim();
  const department = String(row.department_code ?? '').trim();
  const label = code && name ? `${code} - ${name}` : code || name || `Chương trình #${String(row.program_id ?? '')}`;
  return department ? `${label} (${department})` : label;
}

export function courseOptionLabel(row: MasterDataRow): string {
  const code = String(row.course_code ?? '').trim();
  const name = String(row.course_name ?? '').trim();
  if (code && name) {
    return `${code} - ${name}`;
  }
  return code || name || `Môn học #${String(row.course_id ?? '')}`;
}

function sanitizeImportRow(row: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(row)
      .filter(([key]) => key && !key.startsWith('__EMPTY'))
      .map(([key, value]) => [key.trim(), typeof value === 'string' ? value.trim() : value])
  );
}

export function tableRowsToObjects(rows: unknown[][]): Array<Record<string, unknown>> {
  const [headerRow, ...dataRows] = rows;
  const headers = (headerRow ?? []).map((value) => String(value ?? '').trim());
  return dataRows
    .map((row) =>
      sanitizeImportRow(
        Object.fromEntries(headers.map((header, index) => [header, row[index] ?? '']).filter(([header]) => header))
      )
    )
    .filter((row) => Object.values(row).some((value) => value != null && String(value).trim() !== ''));
}

export function parseCsv(text: string): unknown[][] {
  const rows: string[][] = [];
  let current = '';
  let row: string[] = [];
  let inQuotes = false;

  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    const next = text[index + 1];

    if (char === '"' && inQuotes && next === '"') {
      current += '"';
      index += 1;
      continue;
    }
    if (char === '"') {
      inQuotes = !inQuotes;
      continue;
    }
    if (char === ',' && !inQuotes) {
      row.push(current);
      current = '';
      continue;
    }
    if ((char === '\n' || char === '\r') && !inQuotes) {
      if (char === '\r' && next === '\n') {
        index += 1;
      }
      row.push(current);
      rows.push(row);
      row = [];
      current = '';
      continue;
    }
    current += char;
  }

  row.push(current);
  rows.push(row);
  return rows.filter((item) => item.some((value) => value.trim() !== ''));
}

export function formatCounts(counts: Record<string, number> | undefined): string {
  const entries = Object.entries(counts ?? {});
  if (entries.length === 0) {
    return '0 dòng';
  }
  return entries.map(([key, value]) => `${key}: ${value}`).join(' · ');
}

function escapeCsvCell(value: unknown): string {
  const text = String(value ?? '');
  if (text.includes('"') || text.includes(',') || text.includes('\n') || text.includes('\r')) {
    return `"${text.replaceAll('"', '""')}"`;
  }
  return text;
}

export function buildCsvSample(template: ImportTemplate): string {
  const header = template.columns.map((column) => escapeCsvCell(column.name)).join(',');
  const sample = template.columns.map((column) => escapeCsvCell(template.sample_row[column.name] ?? '')).join(',');
  return `\uFEFF${header}\r\n${sample}\r\n`;
}

export function containsEncodingReplacementCharInRows(rows: Array<Record<string, unknown>>): boolean {
  return rows.some((row) =>
    Object.values(row).some((value) => typeof value === 'string' && value.includes('\uFFFD'))
  );
}

export function importStatusLabel(status?: string | null): string {
  const normalized = String(status || '').toUpperCase();
  if (normalized === 'QUEUED') return 'Đang chờ worker';
  if (normalized === 'RUNNING') return 'Worker đang xử lý';
  if (normalized === 'VALIDATED') return 'Đã kiểm tra, đang chờ ghi dữ liệu';
  if (normalized === 'COMMITTED' || normalized === 'SUCCEEDED') return 'Import hoàn tất';
  if (normalized === 'FAILED' || normalized === 'DEAD_LETTERED') return 'Import lỗi';
  if (normalized === 'CANCELLED') return 'Đã hủy';
  return normalized || 'Chưa import';
}

export function isTerminalImportStatus(status?: string | null): boolean {
  return ['COMMITTED', 'SUCCEEDED', 'FAILED', 'DEAD_LETTERED', 'CANCELLED', 'VALIDATION_FAILED', 'COMMIT_FAILED'].includes(
    String(status || '').toUpperCase()
  );
}
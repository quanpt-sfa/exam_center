import { beforeEach, describe, expect, test, vi } from 'vitest';
import { httpRequest } from '../../shared/api/httpClient';
import {
  commitImportJob,
  createImportJob,
  getImportJob,
  getImportJobStatus,
  listImportErrors,
  listImportRows,
  loadImportTemplates,
  validateImportJob,
} from './importCenterApi';

vi.mock('../../shared/api/httpClient', () => ({
  httpRequest: vi.fn(),
}));

const mockedHttpRequest = vi.mocked(httpRequest);

describe('importCenterApi', () => {
  beforeEach(() => {
    mockedHttpRequest.mockReset();
    mockedHttpRequest.mockResolvedValue({ ok: true, success: true, data: { items: [] }, error: null, message: null });
  });

  test('loadImportTemplates uses the canonical templates endpoint', async () => {
    await loadImportTemplates();
    expect(mockedHttpRequest).toHaveBeenCalledWith('/master-data/import-templates');
  });

  test('createImportJob posts to the canonical import endpoint', async () => {
    await createImportJob({
      import_type: 'STUDENTS',
      source_filename: 'students.csv',
      rows: [{ student_code: 'SV001', full_name: 'Nguyễn Văn A' }],
      metadata_json: { source: 'frontend_excel_import' },
    });

    expect(mockedHttpRequest).toHaveBeenCalledWith('/master-data/imports', {
      method: 'POST',
      body: JSON.stringify({
        import_type: 'STUDENTS',
        source_filename: 'students.csv',
        rows: [{ student_code: 'SV001', full_name: 'Nguyễn Văn A' }],
        metadata_json: { source: 'frontend_excel_import' },
      }),
    });
  });

  test('getImportJobStatus uses the canonical status endpoint', async () => {
    await getImportJobStatus(101);
    expect(mockedHttpRequest).toHaveBeenCalledWith('/master-data/imports/101/status');
  });

  test('getImportJob uses the canonical detail endpoint', async () => {
    await getImportJob(101);
    expect(mockedHttpRequest).toHaveBeenCalledWith('/master-data/imports/101');
  });

  test('listImportRows uses the canonical rows endpoint with pagination query params', async () => {
    await listImportRows(101, { page: 2, page_size: 50 });
    expect(mockedHttpRequest).toHaveBeenCalledWith('/master-data/imports/101/rows?page=2&page_size=50');
  });

  test('listImportErrors uses the canonical errors endpoint with pagination query params', async () => {
    await listImportErrors(101, { page: 3, page_size: 100 });
    expect(mockedHttpRequest).toHaveBeenCalledWith('/master-data/imports/101/errors?page=3&page_size=100');
  });

  test('validateImportJob posts to the canonical validate endpoint', async () => {
    await validateImportJob(101);
    expect(mockedHttpRequest).toHaveBeenCalledWith('/master-data/imports/101/validate', {
      method: 'POST',
    });
  });

  test('commitImportJob posts to the canonical commit endpoint with the provided payload', async () => {
    await commitImportJob(101, { idempotency_key: 'job-101' });
    expect(mockedHttpRequest).toHaveBeenCalledWith('/master-data/imports/101/commit', {
      method: 'POST',
      body: JSON.stringify({ idempotency_key: 'job-101' }),
    });
  });

  test('extended import API helpers propagate backend failures without converting them into success', async () => {
    mockedHttpRequest.mockResolvedValueOnce({
      ok: false,
      success: false,
      data: null,
      error: { code: 'import_failed', message: 'Không thể validate job import' },
      message: null,
    });

    const response = await validateImportJob(101);
    expect(response.ok).toBe(false);
    expect(response.error?.message).toBe('Không thể validate job import');
  });
});
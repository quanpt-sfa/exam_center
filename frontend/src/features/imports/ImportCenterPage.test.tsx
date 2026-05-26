import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import { httpRequest } from '../../shared/api/httpClient';
import { ImportCenterPage } from './ImportCenterPage';

vi.mock('../../shared/api/httpClient', () => ({
  httpRequest: vi.fn(),
}));

const mockedHttpRequest = vi.mocked(httpRequest);

const templates = [
  {
    import_type: 'STUDENTS',
    label: 'Sinh viên',
    columns: [
      { name: 'student_code', required: true, default: null, description: 'Mã sinh viên' },
      { name: 'full_name', required: true, default: null, description: 'Họ tên' },
    ],
    sample_row: { student_code: 'SV001', full_name: 'Nguyễn Văn A' },
  },
  {
    import_type: 'ROOMS',
    label: 'Phòng học',
    columns: [
      { name: 'room_code', required: true, default: null, description: 'Mã phòng' },
      { name: 'room_name', required: true, default: null, description: 'Tên phòng' },
    ],
    sample_row: { room_code: 'A101', room_name: 'Phòng A101' },
  },
] as const;

function ok(data: unknown) {
  return { ok: true, success: true, data, error: null, message: null };
}

function createImportFile(content = 'student_code,full_name\nSV001,Nguyễn Văn A\n') {
  const file = new File([content], 'students.csv', { type: 'text/csv' });
  Object.defineProperty(file, 'text', {
    value: vi.fn().mockResolvedValue(content),
  });
  return file;
}

function renderPage() {
  render(
    <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <ImportCenterPage />
    </MemoryRouter>
  );
}

async function uploadAndStartImport(file = createImportFile()) {
  fireEvent.change(screen.getByLabelText('File Excel'), { target: { files: [file] } });
  await screen.findByText(/Đã đọc 1 dòng từ students.csv/i);
  fireEvent.click(screen.getByRole('button', { name: 'Import dữ liệu' }));
  await waitFor(() =>
    expect(mockedHttpRequest).toHaveBeenCalledWith('/master-data/imports', expect.objectContaining({ method: 'POST' }))
  );
}

function buildBackendMock(options?: {
  terminalStatus?: 'QUEUED' | 'VALIDATED' | 'COMMITTED';
  validationOutcome?: 'PENDING' | 'PASSED' | 'FAILED';
  commitStatus?: 'NOT_COMMITTED' | 'COMMITTED';
  includeValidationErrors?: boolean;
}) {
  const state = {
    detail: {
      import_job_id: 101,
      import_type: 'STUDENTS',
      status: options?.terminalStatus === 'VALIDATED' ? 'VALIDATED' : options?.terminalStatus === 'COMMITTED' ? 'COMMITTED' : 'QUEUED',
      validation_status: options?.validationOutcome ?? 'PENDING',
      commit_status: options?.commitStatus ?? 'NOT_COMMITTED',
      counts: {
        total_rows: 1,
        valid_rows: options?.validationOutcome === 'PASSED' ? 1 : 0,
        invalid_rows: options?.includeValidationErrors ? 1 : 0,
        committed_rows: options?.commitStatus === 'COMMITTED' ? 1 : 0,
        failed_rows: 0,
      },
    },
    status: {
      import_job_id: 101,
      import_type: 'STUDENTS',
      status: options?.terminalStatus ?? 'QUEUED',
      worker_status: options?.terminalStatus ?? 'QUEUED',
      total_rows: 1,
      valid_rows: options?.validationOutcome === 'PASSED' ? 1 : 0,
      invalid_rows: options?.includeValidationErrors ? 1 : 0,
      committed_rows: options?.commitStatus === 'COMMITTED' ? 1 : 0,
      failed_rows: 0,
      skipped_rows: 0,
      created_at: '2024-01-01T10:00:00Z',
      updated_at: '2024-01-01T10:01:00Z',
      started_at: '2024-01-01T10:00:30Z',
      finished_at: options?.terminalStatus === 'QUEUED' ? null : '2024-01-01T10:02:00Z',
      last_error_message: null,
    },
    rowsByPage: {
      '1-20': {
        items: [
          {
            import_row_id: 1,
            row_number: 1,
            validation_status: options?.validationOutcome === 'PASSED' ? 'VALID' : options?.includeValidationErrors ? 'INVALID' : 'PENDING',
            commit_status: options?.commitStatus === 'COMMITTED' ? 'COMMITTED' : 'NOT_COMMITTED',
            raw_row: { student_code: 'SV001', full_name: 'Nguyễn Văn A' },
            normalized_row: options?.validationOutcome === 'PASSED' ? { student_code: 'SV001', full_name: 'Nguyễn Văn A' } : null,
            errors: options?.includeValidationErrors
              ? [{ row_number: 1, field: 'student_code', code: 'required', message: 'Mã sinh viên bị thiếu', details: { row_number: 1 } }]
              : [],
            error_count: options?.includeValidationErrors ? 1 : 0,
            has_errors: Boolean(options?.includeValidationErrors),
          },
        ],
        pagination: { page: 1, page_size: 20, total: 2, total_pages: 2, has_previous: false, has_next: true },
      },
      '2-20': {
        items: [
          {
            import_row_id: 2,
            row_number: 2,
            validation_status: 'INVALID',
            commit_status: 'NOT_COMMITTED',
            raw_row: { student_code: '', full_name: 'Sinh viên lỗi' },
            normalized_row: null,
            errors: [{ row_number: 2, field: 'student_code', code: 'required', message: 'Thiếu mã sinh viên', details: { row_number: 2 } }],
            error_count: 1,
            has_errors: true,
          },
        ],
        pagination: { page: 2, page_size: 20, total: 2, total_pages: 2, has_previous: true, has_next: false },
      },
    } as Record<string, unknown>,
    errorsByPage: {
      '1-20': {
        items: options?.includeValidationErrors
          ? [
              {
                row_number: 1,
                field_name: 'student_code',
                error_code: 'required',
                error_message: 'Mã sinh viên bị thiếu',
                severity: 'ERROR',
                details: { row_number: 1, field: 'student_code' },
              },
            ]
          : [],
        pagination: { page: 1, page_size: 20, total: 2, total_pages: 2, has_previous: false, has_next: true },
      },
      '2-20': {
        items: [
          {
            row_number: 2,
            field_name: 'student_code',
            error_code: 'required',
            error_message: 'Thiếu mã sinh viên',
            severity: 'ERROR',
            details: { row_number: 2, field: 'student_code' },
          },
        ],
        pagination: { page: 2, page_size: 20, total: 2, total_pages: 2, has_previous: true, has_next: false },
      },
    } as Record<string, unknown>,
  };

  mockedHttpRequest.mockImplementation((path, init) => {
    if (path === '/master-data/import-templates') {
      return Promise.resolve(ok({ items: templates }));
    }
    if (path === '/master-data/imports' && init?.method === 'POST') {
      return Promise.resolve(
        ok({
          import_job_id: 101,
          import_type: 'STUDENTS',
          status: 'QUEUED',
          validation_status: 'PENDING',
          commit_status: 'NOT_COMMITTED',
          counts: { total_rows: 1, valid_rows: 0, invalid_rows: 0, committed_rows: 0, failed_rows: 0 },
        })
      );
    }
    if (path === '/master-data/imports/101') {
      return Promise.resolve(ok(state.detail));
    }
    if (path === '/master-data/imports/101/status') {
      return Promise.resolve(ok(state.status));
    }
    if (path.startsWith('/master-data/imports/101/rows?')) {
      const query = path.split('?')[1] ?? '';
      const params = new URLSearchParams(query);
      const key = `${params.get('page') ?? '1'}-${params.get('page_size') ?? '20'}`;
      return Promise.resolve(ok(state.rowsByPage[key] ?? { items: [], pagination: { page: 1, page_size: 20, total: 0, total_pages: 0 } }));
    }
    if (path.startsWith('/master-data/imports/101/errors?')) {
      const query = path.split('?')[1] ?? '';
      const params = new URLSearchParams(query);
      const key = `${params.get('page') ?? '1'}-${params.get('page_size') ?? '20'}`;
      return Promise.resolve(ok(state.errorsByPage[key] ?? { items: [], pagination: { page: 1, page_size: 20, total: 0, total_pages: 0 } }));
    }
    if (path === '/master-data/imports/101/validate' && init?.method === 'POST') {
      state.detail = {
        ...state.detail,
        status: options?.includeValidationErrors ? 'VALIDATION_FAILED' : 'VALIDATED',
        validation_status: options?.includeValidationErrors ? 'FAILED' : 'PASSED',
        counts: {
          total_rows: 1,
          valid_rows: options?.includeValidationErrors ? 0 : 1,
          invalid_rows: options?.includeValidationErrors ? 1 : 0,
          committed_rows: 0,
          failed_rows: 0,
        },
      };
      state.status = {
        ...state.status,
        status: options?.includeValidationErrors ? 'VALIDATION_FAILED' : 'VALIDATED',
        worker_status: options?.includeValidationErrors ? 'VALIDATION_FAILED' : 'VALIDATED',
        valid_rows: options?.includeValidationErrors ? 0 : 1,
        invalid_rows: options?.includeValidationErrors ? 1 : 0,
      };
      return Promise.resolve(ok(state.detail));
    }
    if (path === '/master-data/imports/101/commit' && init?.method === 'POST') {
      state.detail = {
        ...state.detail,
        status: 'COMMITTED',
        validation_status: 'PASSED',
        commit_status: 'COMMITTED',
        counts: {
          total_rows: 1,
          valid_rows: 1,
          invalid_rows: 0,
          committed_rows: 1,
          failed_rows: 0,
        },
      };
      state.status = {
        ...state.status,
        status: 'COMMITTED',
        worker_status: 'COMMITTED',
        valid_rows: 1,
        invalid_rows: 0,
        committed_rows: 1,
        finished_at: '2024-01-01T10:03:00Z',
      };
      return Promise.resolve(ok({ import_job_id: 101, status: 'COMMITTED', committed_rows: 1, failed_rows: 0, total_rows: 1 }));
    }
    return Promise.resolve(ok({ items: [] }));
  });
}

describe('ImportCenterPage', () => {
  beforeEach(() => {
    mockedHttpRequest.mockReset();
    vi.spyOn(window, 'setInterval').mockImplementation(((callback: TimerHandler) => {
      if (typeof callback === 'function') {
        void Promise.resolve().then(() => callback());
      }
      return 1 as unknown as number;
    }) as typeof window.setInterval);
    vi.spyOn(window, 'clearInterval').mockImplementation(() => undefined);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  test('renders import workflow, loads job detail rows/errors, and polls terminal status after create', async () => {
    buildBackendMock({ terminalStatus: 'COMMITTED', validationOutcome: 'PASSED', commitStatus: 'COMMITTED' });
    renderPage();

    expect(await screen.findByRole('heading', { name: 'Import dữ liệu nền' })).toBeInTheDocument();
    await uploadAndStartImport();

    await waitFor(() => expect(mockedHttpRequest).toHaveBeenCalledWith('/master-data/imports/101'));
    await waitFor(() => expect(mockedHttpRequest).toHaveBeenCalledWith('/master-data/imports/101/rows?page=1&page_size=20'));
    await waitFor(() => expect(mockedHttpRequest).toHaveBeenCalledWith('/master-data/imports/101/errors?page=1&page_size=20'));

    expect(await screen.findByText(/Import hoàn tất 1\/1 dòng/i)).toBeInTheDocument();
    expect(screen.getByText('Tóm tắt job import')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Mở surface liên quan' })).toHaveAttribute('href', '/admin/master-data/people');
    expect(screen.getByText('Dòng dữ liệu đã nạp')).toBeInTheDocument();
    expect(screen.getByText('Lỗi import')).toBeInTheDocument();

    const summarySection = screen.getByRole('heading', { name: 'Tóm tắt job import' }).closest('section');
    expect(summarySection).not.toBeNull();
    const summaryIconGroup = within(summarySection as HTMLElement).getByRole('button', { name: 'Tải lại trạng thái' }).closest('[data-action-group="true"]');
    expect(summaryIconGroup).toHaveAttribute('data-action-mode', 'icon');
    expect(within(summaryIconGroup as HTMLElement).queryByRole('button', { name: 'Kiểm tra dữ liệu' })).not.toBeInTheDocument();
    expect(within(summaryIconGroup as HTMLElement).queryByRole('button', { name: 'Ghi dữ liệu vào hệ thống' })).not.toBeInTheDocument();
  });

  test('validates import jobs, renders diagnostics, and paginates backend rows and errors', async () => {
    buildBackendMock({ includeValidationErrors: true });
    renderPage();

    await screen.findByRole('heading', { name: 'Import dữ liệu nền' });
    await uploadAndStartImport();

    fireEvent.click(await screen.findByRole('button', { name: 'Kiểm tra dữ liệu' }));

    await waitFor(() => expect(mockedHttpRequest).toHaveBeenCalledWith('/master-data/imports/101/validate', { method: 'POST' }));
    expect(await screen.findByText('Đã kiểm tra dữ liệu import.')).toBeInTheDocument();
    expect(screen.getAllByText('FAILED').length).toBeGreaterThan(0);
    expect(screen.getByText('Mã sinh viên bị thiếu')).toBeInTheDocument();

    const errorsSection = screen.getByRole('heading', { name: 'Lỗi import' }).closest('section');
    expect(errorsSection).not.toBeNull();
    const errorsPagerGroup = within(errorsSection as HTMLElement).getByRole('button', { name: 'Sau' }).closest('[data-action-group="true"]');
    expect(errorsPagerGroup).toHaveAttribute('data-action-mode', 'icon');
    fireEvent.click(within(errorsSection as HTMLElement).getByRole('button', { name: 'Sau' }));

    await waitFor(() => expect(mockedHttpRequest).toHaveBeenCalledWith('/master-data/imports/101/errors?page=2&page_size=20'));
    expect(await screen.findByText('Thiếu mã sinh viên')).toBeInTheDocument();

    const rowsSection = screen.getByRole('heading', { name: 'Dòng dữ liệu đã nạp' }).closest('section');
    expect(rowsSection).not.toBeNull();
    const rowsPagerGroup = within(rowsSection as HTMLElement).getByRole('button', { name: 'Sau' }).closest('[data-action-group="true"]');
    expect(rowsPagerGroup).toHaveAttribute('data-action-mode', 'icon');
    fireEvent.click(within(rowsSection as HTMLElement).getByRole('button', { name: 'Sau' }));

    await waitFor(() => expect(mockedHttpRequest).toHaveBeenCalledWith('/master-data/imports/101/rows?page=2&page_size=20'));
    expect(await within(rowsSection as HTMLElement).findByText((content) => content.includes('Sinh viên lỗi'))).toBeInTheDocument();
  });

  test('commits validated import jobs through confirmation dialog and resets workflow on import-type change', async () => {
    buildBackendMock({ terminalStatus: 'VALIDATED', validationOutcome: 'PASSED' });
    renderPage();

    await screen.findByRole('heading', { name: 'Import dữ liệu nền' });
    await uploadAndStartImport();

    const openCommitButton = await screen.findByRole('button', { name: 'Ghi dữ liệu vào hệ thống' });
    expect(openCommitButton).toBeEnabled();
    fireEvent.click(openCommitButton);

    const dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Ghi dữ liệu' }));

    await waitFor(() =>
      expect(mockedHttpRequest).toHaveBeenCalledWith('/master-data/imports/101/commit', {
        method: 'POST',
        body: JSON.stringify({}),
      })
    );

    expect(await screen.findByText('Đã ghi 1/1 dòng vào hệ thống.')).toBeInTheDocument();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Loại dữ liệu'), { target: { value: 'ROOMS' } });

    await waitFor(() => expect(screen.queryByText('Tóm tắt job import')).not.toBeInTheDocument());
    expect(screen.queryByText(/Đã ghi 1\/1 dòng vào hệ thống./i)).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Mở surface liên quan' })).toHaveAttribute('href', '/admin/facility');
  });
});

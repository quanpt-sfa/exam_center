import { type ChangeEvent, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { CompactPage } from '../../shared/components/compact/CompactPage';
import { CompactStatBar } from '../../shared/components/compact/CompactStatBar';
import { CompactSurface } from '../../shared/components/compact/CompactSurface';
import { IconActionButton, PrimaryActionSlot, RowActionGroup, ToolbarActionGroup } from '../../shared/components/compact/IconActionButton';
import { AdminSurfaceHeader } from '../masterData/components/AdminSurfaceHeader';
import { ConfirmationDialog } from '../masterData/components/ConfirmationDialog';
import { ImportPanel } from '../masterData/components/ImportPanel';
import { importEntityKeyByType } from '../masterData/registry/masterDataEntities';
import {
  containsEncodingReplacementCharInRows,
  displayCell,
  importStatusLabel,
  isTerminalImportStatus,
  parseCsv,
  tableRowsToObjects,
} from '../masterData/utils/formatters';
import {
  commitImportJob,
  createImportJob,
  getImportJob,
  getImportJobStatus,
  listImportErrors,
  listImportRows,
  loadImportTemplates,
  type ImportCommitPayload,
  type ImportErrorDetail,
  type ImportErrorsResponse,
  type ImportJob,
  type ImportJobDetail,
  type ImportJobStatus,
  type ImportPagination,
  type ImportRow,
  type ImportRowDetail,
  type ImportRowsResponse,
  type ImportTemplate,
  type ImportType,
  validateImportJob,
} from './importCenterApi';

type PagingState = {
  page: number;
  page_size: number;
};

const defaultPagingState: PagingState = {
  page: 1,
  page_size: 20,
};

function deriveCounts(importJob: ImportJob | null, importJobDetail: ImportJobDetail | null, importStatus: ImportJobStatus | null) {
  const counts = importJobDetail?.counts ?? importJob?.counts ?? {};
  return {
    total_rows: importStatus?.total_rows ?? counts.total_rows ?? 0,
    valid_rows: importStatus?.valid_rows ?? counts.valid_rows ?? 0,
    invalid_rows: importStatus?.invalid_rows ?? counts.invalid_rows ?? 0,
    committed_rows: importStatus?.committed_rows ?? counts.committed_rows ?? 0,
    failed_rows: importStatus?.failed_rows ?? counts.failed_rows ?? 0,
    skipped_rows: importStatus?.skipped_rows ?? counts.skipped_rows ?? 0,
  };
}

function deriveValidationStatus(importJob: ImportJob | null, importJobDetail: ImportJobDetail | null) {
  return importJobDetail?.validation_status ?? importJob?.validation_status ?? 'PENDING';
}

function deriveCommitStatus(importJob: ImportJob | null, importJobDetail: ImportJobDetail | null) {
  return importJobDetail?.commit_status ?? importJob?.commit_status ?? 'NOT_COMMITTED';
}

function formatTimestamp(value?: string | null) {
  if (!value) {
    return '-';
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString('vi-VN');
}

function renderObjectPreview(payload: Record<string, unknown> | null | undefined, fallback = 'Không có dữ liệu chi tiết.') {
  if (!payload || Object.keys(payload).length === 0) {
    return <span className="muted">{fallback}</span>;
  }

  return (
    <details>
      <summary>Xem dữ liệu</summary>
      <pre>{JSON.stringify(payload, null, 2)}</pre>
    </details>
  );
}

function canValidateJob(importJob: ImportJob | null, importJobDetail: ImportJobDetail | null, importStatus: ImportJobStatus | null) {
  if (!importJob) {
    return false;
  }
  const status = String(importStatus?.status ?? importJobDetail?.status ?? importJob.status).toUpperCase();
  const commitStatus = deriveCommitStatus(importJob, importJobDetail).toUpperCase();
  return !['COMMITTED', 'SUCCEEDED', 'CANCELLED'].includes(status) && commitStatus !== 'COMMITTED';
}

function canCommitJob(importJob: ImportJob | null, importJobDetail: ImportJobDetail | null, importStatus: ImportJobStatus | null) {
  if (!importJob) {
    return false;
  }
  const status = String(importStatus?.status ?? importJobDetail?.status ?? importJob.status).toUpperCase();
  const validationStatus = deriveValidationStatus(importJob, importJobDetail).toUpperCase();
  const commitStatus = deriveCommitStatus(importJob, importJobDetail).toUpperCase();
  const counts = deriveCounts(importJob, importJobDetail, importStatus);
  return validationStatus === 'PASSED' && commitStatus !== 'COMMITTED' && counts.invalid_rows === 0 && !['COMMITTED', 'SUCCEEDED'].includes(status);
}

const entityRouteByKey: Record<string, string> = {
  students: '/admin/master-data/people',
  instructors: '/admin/master-data/people',
  courses: '/admin/master-data/academic',
  classSections: '/admin/master-data/academic',
  enrollments: '/admin/master-data/academic',
  rooms: '/admin/facility',
  stations: '/admin/facility',
  devices: '/admin/facility',
};

export function ImportCenterPage() {
  const [importType, setImportType] = useState<ImportType>('STUDENTS');
  const [importRows, setImportRows] = useState<ImportRow[]>([]);
  const [importFileName, setImportFileName] = useState('');
  const [importJob, setImportJob] = useState<ImportJob | null>(null);
  const [importJobDetail, setImportJobDetail] = useState<ImportJobDetail | null>(null);
  const [importStatus, setImportStatus] = useState<ImportJobStatus | null>(null);
  const [rowsPaging, setRowsPaging] = useState<PagingState>(defaultPagingState);
  const [rowsResponse, setRowsResponse] = useState<ImportRowsResponse | null>(null);
  const [rowsLoading, setRowsLoading] = useState(false);
  const [rowsError, setRowsError] = useState<string | null>(null);
  const [errorsPaging, setErrorsPaging] = useState<PagingState>(defaultPagingState);
  const [errorsResponse, setErrorsResponse] = useState<ImportErrorsResponse | null>(null);
  const [errorsLoading, setErrorsLoading] = useState(false);
  const [errorsError, setErrorsError] = useState<string | null>(null);
  const [importTemplates, setImportTemplates] = useState<ImportTemplate[]>([]);
  const [importTemplatesLoading, setImportTemplatesLoading] = useState(true);
  const [importTemplatesError, setImportTemplatesError] = useState<string | null>(null);
  const [importBusy, setImportBusy] = useState(false);
  const [validateBusy, setValidateBusy] = useState(false);
  const [commitBusy, setCommitBusy] = useState(false);
  const [commitDialogOpen, setCommitDialogOpen] = useState(false);
  const [commitDialogError, setCommitDialogError] = useState<string | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const [importMessage, setImportMessage] = useState<string | null>(null);
  const validateInFlightRef = useRef(false);
  const commitInFlightRef = useRef(false);

  const selectedTemplate = importTemplates.find((template) => template.import_type === importType) ?? null;
  const linkedEntityKey = importStatus ? importEntityKeyByType[importStatus.import_type] : importEntityKeyByType[importType];
  const linkedEntityRoute = linkedEntityKey ? entityRouteByKey[linkedEntityKey] : null;
  const counts = deriveCounts(importJob, importJobDetail, importStatus);
  const validationStatus = deriveValidationStatus(importJob, importJobDetail);
  const commitStatus = deriveCommitStatus(importJob, importJobDetail);
  const currentJobId = importJob?.import_job_id ?? null;
  const isCommitSuccessful = String(importStatus?.status ?? importJobDetail?.status ?? importJob?.status ?? '').toUpperCase() === 'COMMITTED';

  function resetImportWorkflowState() {
    setImportRows([]);
    setImportFileName('');
    setImportJob(null);
    setImportJobDetail(null);
    setImportStatus(null);
    setRowsPaging(defaultPagingState);
    setRowsResponse(null);
    setRowsError(null);
    setErrorsPaging(defaultPagingState);
    setErrorsResponse(null);
    setErrorsError(null);
    setImportError(null);
    setImportMessage(null);
    setValidateBusy(false);
    setCommitBusy(false);
    setCommitDialogOpen(false);
    setCommitDialogError(null);
    validateInFlightRef.current = false;
    commitInFlightRef.current = false;
  }

  async function refreshImportJob(importJobId: number) {
    const [jobResponse, statusResponse] = await Promise.all([getImportJob(importJobId), getImportJobStatus(importJobId)]);

    if (!jobResponse.ok) {
      setImportError(jobResponse.error.message);
    } else {
      setImportJobDetail(jobResponse.data);
    }

    if (!statusResponse.ok) {
      setImportError(statusResponse.error.message);
    } else {
      setImportStatus(statusResponse.data);
    }
  }

  async function refreshImportRows(importJobId: number, paging = rowsPaging) {
    setRowsLoading(true);
    setRowsError(null);
    const response = await listImportRows(importJobId, paging);
    setRowsLoading(false);
    if (!response.ok) {
      setRowsResponse(null);
      setRowsError(response.error.message);
      return;
    }
    setRowsResponse(response.data);
  }

  async function refreshImportErrors(importJobId: number, paging = errorsPaging) {
    setErrorsLoading(true);
    setErrorsError(null);
    const response = await listImportErrors(importJobId, paging);
    setErrorsLoading(false);
    if (!response.ok) {
      setErrorsResponse(null);
      setErrorsError(response.error.message);
      return;
    }
    setErrorsResponse(response.data);
  }

  async function refreshAllImportData(importJobId: number, nextRowsPaging = rowsPaging, nextErrorsPaging = errorsPaging) {
    await refreshImportJob(importJobId);
    await Promise.all([refreshImportRows(importJobId, nextRowsPaging), refreshImportErrors(importJobId, nextErrorsPaging)]);
  }

  useEffect(() => {
    let cancelled = false;

    async function loadTemplates() {
      setImportTemplatesLoading(true);
      setImportTemplatesError(null);
      const response = await loadImportTemplates();
      if (cancelled) {
        return;
      }
      if (!response.ok) {
        setImportTemplates([]);
        setImportTemplatesLoading(false);
        setImportTemplatesError(response.error.message || 'Không tải được cấu trúc file import.');
        return;
      }

      setImportTemplates(response.data.items);
      setImportTemplatesLoading(false);
      if (response.data.items.length > 0 && !response.data.items.some((template) => template.import_type === importType)) {
        setImportType(response.data.items[0].import_type);
      }
    }

    void loadTemplates();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!importJob || isTerminalImportStatus(importStatus?.status)) {
      return;
    }

    let cancelled = false;
    const timer = window.setInterval(() => {
      void (async () => {
        const response = await getImportJobStatus(importJob.import_job_id);
        if (cancelled) {
          return;
        }
        if (!response.ok) {
          setImportError(response.error.message);
          return;
        }

        setImportStatus(response.data);
        if (isTerminalImportStatus(response.data.status)) {
          window.clearInterval(timer);
          void refreshImportJob(importJob.import_job_id);
          if (String(response.data.status).toUpperCase() === 'COMMITTED') {
            setImportMessage(`Import hoàn tất ${response.data.committed_rows}/${response.data.total_rows} dòng.`);
          } else if (response.data.last_error_message) {
            setImportError(response.data.last_error_message);
          }
        }
      })();
    }, 2000);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [importJob, importStatus?.status]);

  useEffect(() => {
    if (!currentJobId) {
      return;
    }
    void refreshImportRows(currentJobId, rowsPaging);
  }, [currentJobId, rowsPaging.page, rowsPaging.page_size]);

  useEffect(() => {
    if (!currentJobId) {
      return;
    }
    void refreshImportErrors(currentJobId, errorsPaging);
  }, [currentJobId, errorsPaging.page, errorsPaging.page_size]);

  async function handleImportFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    try {
      setImportBusy(true);
      resetImportWorkflowState();

      const lowerName = file.name.toLowerCase();
      const rows = lowerName.endsWith('.csv')
        ? tableRowsToObjects(parseCsv(await file.text()))
        : tableRowsToObjects((await (await import('read-excel-file/browser')).default(file)) as unknown[][]);

      if (containsEncodingReplacementCharInRows(rows)) {
        throw new Error('File CSV có lỗi mã hóa tiếng Việt. Vui lòng tải lại file mẫu .xlsx hoặc lưu CSV dưới dạng CSV UTF-8.');
      }

      setImportFileName(file.name);
      setImportRows(rows);
      setImportMessage(`Đã đọc ${rows.length} dòng từ ${file.name}.`);
    } catch (error) {
      setImportRows([]);
      setImportFileName('');
      setImportError(error instanceof Error ? error.message : 'Không đọc được file Excel.');
    } finally {
      setImportBusy(false);
    }
  }

  async function handleStartImport() {
    if (!selectedTemplate) {
      setImportError('Chưa tải được cấu trúc import từ Backend API.');
      return;
    }
    if (importRows.length === 0) {
      setImportError('File chưa có dữ liệu để import.');
      return;
    }

    setImportBusy(true);
    setImportError(null);
    setImportMessage(null);
    setImportStatus(null);
    setImportJobDetail(null);
    setRowsPaging(defaultPagingState);
    setErrorsPaging(defaultPagingState);

    const response = await createImportJob({
      import_type: importType,
      source_filename: importFileName,
      rows: importRows,
      metadata_json: { source: 'frontend_excel_import' },
    });

    setImportBusy(false);
    if (!response.ok) {
      setImportError(response.error.message);
      return;
    }

    setImportJob(response.data);
    setImportJobDetail(response.data);
    setImportStatus({
      import_job_id: response.data.import_job_id,
      import_type: response.data.import_type,
      status: response.data.status,
      worker_status: response.data.status,
      total_rows: response.data.counts.total_rows ?? importRows.length,
      valid_rows: response.data.counts.valid_rows ?? 0,
      invalid_rows: response.data.counts.invalid_rows ?? 0,
      committed_rows: response.data.counts.committed_rows ?? 0,
      failed_rows: response.data.counts.failed_rows ?? 0,
      skipped_rows: 0,
    });
    setImportMessage(`Đã gửi file import. Mã xử lý #${response.data.import_job_id}.`);
    void refreshAllImportData(response.data.import_job_id, defaultPagingState, defaultPagingState);
  }

  async function handleValidate() {
    if (!currentJobId || validateInFlightRef.current) {
      return;
    }
    validateInFlightRef.current = true;
    setValidateBusy(true);
    setImportError(null);
    setImportMessage(null);
    try {
      const response = await validateImportJob(currentJobId);
      if (!response.ok) {
        setImportError(response.error.message);
        return;
      }
      await refreshAllImportData(currentJobId);
      setImportMessage('Đã kiểm tra dữ liệu import.');
    } finally {
      validateInFlightRef.current = false;
      setValidateBusy(false);
    }
  }

  async function handleCommit() {
    if (!currentJobId || commitInFlightRef.current) {
      return;
    }
    const payload: ImportCommitPayload = {};
    commitInFlightRef.current = true;
    setCommitBusy(true);
    setCommitDialogError(null);
    setImportError(null);
    setImportMessage(null);
    try {
      const response = await commitImportJob(currentJobId, payload);
      if (!response.ok) {
        setCommitDialogError(response.error.message);
        setImportError(response.error.message);
        return;
      }
      setCommitDialogOpen(false);
      await refreshAllImportData(currentJobId);
      setImportMessage(`Đã ghi ${response.data.committed_rows}/${response.data.total_rows} dòng vào hệ thống.`);
    } finally {
      commitInFlightRef.current = false;
      setCommitBusy(false);
    }
  }

  function renderPaginationControls(prefix: 'rows' | 'errors', pagination?: ImportPagination, paging?: PagingState) {
    if (!paging) {
      return null;
    }

    const canGoPrevious = pagination?.has_previous ?? paging.page > 1;
    const canGoNext = pagination?.has_next ?? (pagination?.total_pages != null ? paging.page < pagination.total_pages : false);

    return (
      <div className="master-data-pagination">
        <span className="muted">
          Trang {paging.page}
          {pagination?.total_pages != null ? ` / ${pagination.total_pages}` : ''}
          {pagination?.total != null ? ` - ${pagination.total} mục` : ''}
        </span>
        <div>
          <label>
            Số dòng/trang
            <select
              aria-label={prefix === 'rows' ? 'Số dòng/trang dữ liệu import' : 'Số dòng/trang lỗi import'}
              value={String(paging.page_size)}
              onChange={(event) => {
                const nextPageSize = Number(event.target.value);
                if (prefix === 'rows') {
                  setRowsPaging({ page: 1, page_size: nextPageSize });
                } else {
                  setErrorsPaging({ page: 1, page_size: nextPageSize });
                }
              }}
            >
              {[20, 50, 100].map((size) => (
                <option key={size} value={size}>
                  {size}
                </option>
              ))}
            </select>
          </label>
        </div>
        <RowActionGroup className="master-data-row-actions master-data-row-actions--compact">
          <IconActionButton
            icon="chevron-left"
            label="Trước"
            disabled={!canGoPrevious}
            onClick={() => {
              if (prefix === 'rows') {
                setRowsPaging((current) => ({ ...current, page: current.page - 1 }));
              } else {
                setErrorsPaging((current) => ({ ...current, page: current.page - 1 }));
              }
            }}
          />
          <IconActionButton
            icon="chevron-right"
            label="Sau"
            disabled={!canGoNext}
            onClick={() => {
              if (prefix === 'rows') {
                setRowsPaging((current) => ({ ...current, page: current.page + 1 }));
              } else {
                setErrorsPaging((current) => ({ ...current, page: current.page + 1 }));
              }
            }}
          />
        </RowActionGroup>
      </div>
    );
  }

  return (
    <CompactPage className="master-data-page">
      <AdminSurfaceHeader
        eyebrow="Import center"
        title="Import dữ liệu nền"
        description="Tải template import, upload file dữ liệu và theo dõi trạng thái xử lý job từ backend worker."
      />

      <ImportPanel
        importType={importType}
        importRowsCount={importRows.length}
        importFileName={importFileName}
        importJob={importJob}
        importStatus={importStatus}
        importTemplates={importTemplates}
        importTemplatesLoading={importTemplatesLoading}
        importTemplatesError={importTemplatesError}
        importBusy={importBusy}
        importError={importError}
        importMessage={importMessage}
        selectedTemplate={selectedTemplate}
        onImportTypeChange={(nextImportType) => {
          resetImportWorkflowState();
          setImportType(nextImportType);
        }}
        onFileChange={handleImportFile}
        onStartImport={() => void handleStartImport()}
      />

      <ConfirmationDialog
        open={commitDialogOpen}
        title="Xác nhận ghi dữ liệu"
        body="Thao tác này sẽ ghi các dòng hợp lệ vào dữ liệu nền của hệ thống. Vui lòng kiểm tra lỗi trước khi tiếp tục."
        targetLabel={currentJobId ? `Job #${currentJobId}` : null}
        error={commitDialogError}
        confirmLabel="Ghi dữ liệu"
        cancelLabel="Hủy"
        confirming={commitBusy}
        onConfirm={() => void handleCommit()}
        onCancel={() => {
          if (commitBusy) {
            return;
          }
          setCommitDialogError(null);
          setCommitDialogOpen(false);
        }}
      />

      {currentJobId ? (
        <CompactSurface
          className="import-center-summary"
          title="Tóm tắt job import"
          description="Theo dõi trạng thái, kiểm tra dữ liệu, và ghi dữ liệu hợp lệ vào hệ thống."
          actions={
            <div className="compact-action-cluster">
              <PrimaryActionSlot>
                <button
                  type="button"
                  className="primary-button compact-button"
                  disabled={!canValidateJob(importJob, importJobDetail, importStatus) || validateBusy}
                  aria-busy={validateBusy}
                  onClick={() => void handleValidate()}
                >
                  {validateBusy ? 'Đang kiểm tra...' : 'Kiểm tra dữ liệu'}
                </button>
                <button
                  type="button"
                  className="primary-button compact-button"
                  disabled={!canCommitJob(importJob, importJobDetail, importStatus) || commitBusy}
                  aria-busy={commitBusy}
                  onClick={() => setCommitDialogOpen(true)}
                >
                  {commitBusy ? 'Đang ghi dữ liệu...' : 'Ghi dữ liệu vào hệ thống'}
                </button>
              </PrimaryActionSlot>
              <ToolbarActionGroup>
                <IconActionButton icon="refresh" label="Tải lại trạng thái" onClick={() => void refreshAllImportData(currentJobId)} />
              </ToolbarActionGroup>
            </div>
          }
        >
          <CompactStatBar
            items={[
              { label: 'Job ID', value: currentJobId },
              { label: 'Loại import', value: importStatus?.import_type ?? importJobDetail?.import_type ?? importJob?.import_type ?? importType },
              { label: 'Trạng thái', value: importStatusLabel(importStatus?.status ?? importJobDetail?.status ?? importJob?.status) },
              { label: 'Kiểm tra', value: validationStatus },
              { label: 'Commit', value: commitStatus },
              { label: 'Tổng dòng', value: counts.total_rows },
              { label: 'Hợp lệ', value: counts.valid_rows },
              { label: 'Không hợp lệ', value: counts.invalid_rows },
              { label: 'Đã ghi', value: counts.committed_rows },
              { label: 'Ghi lỗi', value: counts.failed_rows },
            ]}
          />

          <div className="import-summary-grid">
            <p><strong>Job ID:</strong> {currentJobId}</p>
            <p><strong>Loại import:</strong> {importStatus?.import_type ?? importJobDetail?.import_type ?? importJob?.import_type ?? importType}</p>
            <p><strong>Trạng thái:</strong> {importStatusLabel(importStatus?.status ?? importJobDetail?.status ?? importJob?.status)}</p>
            <p><strong>Trạng thái kiểm tra:</strong> {validationStatus}</p>
            <p><strong>Trạng thái ghi dữ liệu:</strong> {commitStatus}</p>
            <p><strong>Tổng dòng:</strong> {counts.total_rows}</p>
            <p><strong>Dòng hợp lệ:</strong> {counts.valid_rows}</p>
            <p><strong>Dòng không hợp lệ:</strong> {counts.invalid_rows}</p>
            <p><strong>Dòng đã ghi:</strong> {counts.committed_rows}</p>
            <p><strong>Dòng ghi lỗi:</strong> {counts.failed_rows}</p>
            <p><strong>Lỗi gần nhất:</strong> {importStatus?.last_error_message ?? '-'}</p>
            <p><strong>Tạo lúc:</strong> {formatTimestamp(importStatus?.created_at)}</p>
            <p><strong>Cập nhật lúc:</strong> {formatTimestamp(importStatus?.updated_at)}</p>
            <p><strong>Bắt đầu lúc:</strong> {formatTimestamp(importStatus?.started_at)}</p>
            <p><strong>Kết thúc lúc:</strong> {formatTimestamp(importStatus?.finished_at)}</p>
          </div>
        </CompactSurface>
      ) : null}

      {currentJobId ? (
        <CompactSurface
          className="import-center-rows compact-data-table"
          title="Dòng dữ liệu đã nạp"
          description="Dữ liệu backend đã staging cho job hiện tại."
          actions={
            <IconActionButton icon="refresh" label="Tải lại dòng dữ liệu" onClick={() => void refreshImportRows(currentJobId)} />
          }
        >
          {rowsLoading ? <p className="muted">Đang tải dòng dữ liệu...</p> : null}
          {rowsError ? <p className="form-error">{rowsError}</p> : null}
          {!rowsLoading && !rowsError && (rowsResponse?.items.length ?? 0) === 0 ? <p className="muted">Chưa có dòng dữ liệu nào.</p> : null}
          {!rowsLoading && !rowsError && (rowsResponse?.items.length ?? 0) > 0 ? (
            <div className="master-data-table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Dòng</th>
                    <th>Kiểm tra</th>
                    <th>Ghi dữ liệu</th>
                    <th>Dữ liệu gốc</th>
                    <th>Dữ liệu chuẩn hóa</th>
                    <th>Lỗi</th>
                  </tr>
                </thead>
                <tbody>
                  {rowsResponse?.items.map((row: ImportRowDetail) => (
                    <tr key={row.import_row_id}>
                      <td>{displayCell(row.row_number)}</td>
                      <td>{displayCell(row.validation_status)}</td>
                      <td>{displayCell(row.commit_status)}</td>
                      <td>{renderObjectPreview(row.raw_row)}</td>
                      <td>{renderObjectPreview(row.normalized_row ?? null, 'Chưa có dữ liệu chuẩn hóa.')}</td>
                      <td>{row.error_count ?? row.errors?.length ?? 0}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
          {renderPaginationControls('rows', rowsResponse?.pagination, rowsPaging)}
        </CompactSurface>
      ) : null}

      {currentJobId ? (
        <CompactSurface
          className="import-center-errors compact-data-table"
          title="Lỗi import"
          description="Danh sách lỗi kiểm tra hoặc ghi dữ liệu từ backend."
          actions={
            <IconActionButton icon="refresh" label="Tải lại lỗi import" onClick={() => void refreshImportErrors(currentJobId)} />
          }
        >
          {errorsLoading ? <p className="muted">Đang tải lỗi import...</p> : null}
          {errorsError ? <p className="form-error">{errorsError}</p> : null}
          {!errorsLoading && !errorsError && (errorsResponse?.items.length ?? 0) === 0 ? <p className="muted">Không có lỗi import.</p> : null}
          {!errorsLoading && !errorsError && (errorsResponse?.items.length ?? 0) > 0 ? (
            <div className="master-data-table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Dòng</th>
                    <th>Trường</th>
                    <th>Mã lỗi</th>
                    <th>Mức độ</th>
                    <th>Thông điệp</th>
                    <th>Chi tiết</th>
                  </tr>
                </thead>
                <tbody>
                  {errorsResponse?.items.map((error: ImportErrorDetail, index) => (
                    <tr key={`${error.error_code ?? 'error'}-${error.row_number ?? index}-${index}`}>
                      <td>{displayCell(error.row_number)}</td>
                      <td>{displayCell(error.field_name)}</td>
                      <td>{displayCell(error.error_code)}</td>
                      <td>{displayCell(error.severity)}</td>
                      <td>{error.error_message}</td>
                      <td>{renderObjectPreview(error.details ?? null)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
          {renderPaginationControls('errors', errorsResponse?.pagination, errorsPaging)}
        </CompactSurface>
      ) : null}

      <CompactSurface className="import-center-note" title="Điều hướng sau import" tight>
        <p className="muted">
          Trạng thái hiện tại: <strong>{importStatusLabel(importStatus?.status ?? importJob?.status)}</strong>
        </p>
        {linkedEntityRoute ? (
          <Link className={isCommitSuccessful ? 'primary-button compact-button' : 'secondary-button compact-button'} to={linkedEntityRoute}>
            Mở surface liên quan
          </Link>
        ) : (
          <p className="muted">Loại import này chưa được ánh xạ sang một surface chuyên biệt.</p>
        )}
      </CompactSurface>
    </CompactPage>
  );
}

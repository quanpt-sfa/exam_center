import type { ChangeEvent } from 'react';
import { CompactSurface } from '../../../shared/components/compact/CompactSurface';
import { CompactToolbar } from '../../../shared/components/compact/CompactToolbar';
import type { ImportJobResponse, ImportStatusResponse, ImportTemplate, ImportType } from '../masterDataApi';
import { buildCsvSample, formatCounts, importStatusLabel } from '../utils/formatters';

function downloadCsvSample(template: ImportTemplate) {
  const blob = new Blob([buildCsvSample(template)], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `${template.import_type.toLowerCase()}_template_utf8.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export function ImportPanel({
  importType,
  importRowsCount,
  importFileName,
  importJob,
  importStatus,
  importTemplates,
  importTemplatesLoading,
  importTemplatesError,
  importBusy,
  importError,
  importMessage,
  selectedTemplate,
  onImportTypeChange,
  onFileChange,
  onStartImport,
}: {
  importType: ImportType;
  importRowsCount: number;
  importFileName: string;
  importJob: ImportJobResponse | null;
  importStatus: ImportStatusResponse | null;
  importTemplates: ImportTemplate[];
  importTemplatesLoading: boolean;
  importTemplatesError: string | null;
  importBusy: boolean;
  importError: string | null;
  importMessage: string | null;
  selectedTemplate: ImportTemplate | null;
  onImportTypeChange: (importType: ImportType) => void;
  onFileChange: (event: ChangeEvent<HTMLInputElement>) => void;
  onStartImport: () => void;
}) {
  const selectedTemplateColumns = selectedTemplate?.columns ?? [];

  return (
    <CompactSurface
      className="import-panel"
      title="Import Excel"
      description="Chọn loại dữ liệu, tải file mẫu nếu cần, sau đó import. Hệ thống sẽ tạo job phía backend và worker xử lý validate/commit."
    >
      <div className="import-panel-copy">
        <p className="muted">Khuyến nghị dùng file .xlsx hoặc CSV UTF-8 để tránh lỗi tiếng Việt.</p>
        <p className="muted">Không dùng CSV ANSI/Windows mặc định từ Excel.</p>
      </div>

      <CompactToolbar className="import-controls">
        <label htmlFor="master-import-type">
          Loại dữ liệu
          <select
            id="master-import-type"
            value={importType}
            onChange={(event) => onImportTypeChange(event.target.value as ImportType)}
            disabled={importTemplates.length === 0}
          >
            {importTemplates.length === 0 ? <option value={importType}>Không có cấu trúc import</option> : null}
            {importTemplates.map((template) => (
              <option key={template.import_type} value={template.import_type}>
                {template.label}
              </option>
            ))}
          </select>
        </label>

        <label htmlFor="master-import-file">
          File Excel
          <input id="master-import-file" type="file" accept=".xlsx,.csv" onChange={onFileChange} />
        </label>

        <button type="button" className="secondary-button compact-button" disabled={!selectedTemplate} onClick={() => selectedTemplate && downloadCsvSample(selectedTemplate)}>
          Tải CSV mẫu UTF-8
        </button>
        <button className="primary-button compact-button" type="button" disabled={importBusy || importRowsCount === 0 || !selectedTemplate} onClick={onStartImport}>
          {importBusy ? 'Đang đọc file...' : 'Import dữ liệu'}
        </button>
      </CompactToolbar>

      <div className="import-template-panel compact-data-table">
        <h4>Cấu trúc file import</h4>
        {importTemplatesLoading ? <p className="muted">Đang tải cấu trúc file import...</p> : null}
        {importTemplatesError ? (
          <p className="form-error">Không tải được cấu trúc file import từ Backend API. Vui lòng thử lại trước khi tải mẫu hoặc import.</p>
        ) : null}
        {!importTemplatesLoading && !importTemplatesError && selectedTemplate ? (
          <table>
            <thead>
              <tr>
                <th>Cột</th>
                <th>Bắt buộc</th>
                <th>Default</th>
                <th>Ghi chú</th>
              </tr>
            </thead>
            <tbody>
              {selectedTemplateColumns.map((column) => (
                <tr key={column.name}>
                  <td>{column.name}</td>
                  <td>{column.required ? 'Có' : 'Không'}</td>
                  <td>{column.default || '-'}</td>
                  <td>{column.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
      </div>

      <div className="import-summary">
        <span>{importFileName ? importFileName : 'Chưa chọn file'}</span>
        <span>{importRowsCount} dòng</span>
        {importJob ? (
          <span>
            Mã xử lý #{importJob.import_job_id} · {importStatusLabel(importStatus?.status ?? importJob.status)} · {formatCounts(importJob.counts)}
          </span>
        ) : null}
        {importStatus ? (
          <span>
            Đã ghi {importStatus.committed_rows}/{importStatus.total_rows} · lỗi {importStatus.invalid_rows + importStatus.failed_rows}
          </span>
        ) : null}
      </div>

      {importError ? <p className="form-error">{importError}</p> : null}
      {importMessage ? <p className="success-message">{importMessage}</p> : null}
    </CompactSurface>
  );
}

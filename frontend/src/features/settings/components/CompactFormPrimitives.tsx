import type { HTMLAttributes, ReactNode } from 'react';

export function CompactFormGrid({
  children,
  columns = 2,
  className = '',
  ...rest
}: {
  children: ReactNode;
  columns?: 1 | 2;
  className?: string;
} & HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={`settings-form-grid settings-form-grid--${columns}${className ? ` ${className}` : ''}`.trim()}
      {...rest}
    >
      {children}
    </div>
  );
}

export function CompactFormSection({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <section className="compact-surface settings-form-section" aria-label={title}>
      <header className="settings-form-section__header">
        <h3>{title}</h3>
        {description ? <p className="muted">{description}</p> : null}
      </header>
      <div className="settings-form-section__body">{children}</div>
    </section>
  );
}

export function CompactFieldLabel({
  htmlFor,
  label,
  required = false,
}: {
  htmlFor: string;
  label: string;
  required?: boolean;
}) {
  return (
    <label htmlFor={htmlFor} className="settings-field-label">
      {label}
      {required ? (
        <span aria-hidden="true" className="settings-field-required-mark">
          *
        </span>
      ) : null}
    </label>
  );
}

export function CompactHelpText({ children }: { children: ReactNode }) {
  return <span className="settings-help-text">{children}</span>;
}

export function CompactValidationMessage({ message }: { message: string }) {
  return (
    <span className="settings-validation-message" role="alert">
      {message}
    </span>
  );
}

export function CompactField({
  label,
  htmlFor,
  description,
  error,
  required = false,
  children,
}: {
  label: string;
  htmlFor: string;
  description?: string;
  error?: string;
  required?: boolean;
  children: ReactNode;
}) {
  return (
    <div className="settings-field-row">
      <CompactFieldLabel htmlFor={htmlFor} label={label} required={required} />
      {description ? <CompactHelpText>{description}</CompactHelpText> : null}
      {children}
      {error ? <CompactValidationMessage message={error} /> : null}
    </div>
  );
}

export function CompactFormActions({
  isDirty,
  saving,
  onReset,
}: {
  isDirty: boolean;
  saving: boolean;
  onReset: () => void;
}) {
  return (
    <div className="save-settings-bar" role="status" aria-live="polite">
      <div>
        {isDirty ? (
          <span className="save-settings-bar__dirty">Bạn có thay đổi chưa lưu</span>
        ) : (
          <span className="muted save-settings-bar__saved">Đã lưu tất cả thay đổi</span>
        )}
      </div>

      <div className="save-settings-bar__actions">
        <button type="button" className="secondary-button" onClick={onReset} disabled={saving || !isDirty}>
          Hủy thay đổi
        </button>
        <button type="submit" className="primary-button" disabled={saving || !isDirty}>
          {saving ? 'Đang lưu cấu hình...' : 'Lưu cấu hình'}
        </button>
      </div>
    </div>
  );
}

export function CompactAuditMetadata({
  updatedAt,
  updatedBy,
  version,
}: {
  updatedAt?: string;
  updatedBy?: number | string | null;
  version?: number;
}) {
  if (!updatedAt && updatedBy === undefined && version === undefined) {
    return null;
  }

  const formattedDate = updatedAt ? new Date(updatedAt).toLocaleString() : 'N/A';

  return (
    <section className="compact-surface compact-surface--tight settings-audit-meta" aria-label="Audit metadata">
      <span>
        <strong>Phiên bản cấu hình:</strong> {version ?? 'N/A'}
      </span>
      <span>
        <strong>Cập nhật cuối:</strong> {formattedDate}
      </span>
      <span>
        <strong>Thực hiện bởi:</strong> {updatedBy !== undefined && updatedBy !== null ? `ID ${updatedBy}` : 'N/A'}
      </span>
    </section>
  );
}
type ConfirmationDialogProps = {
  open: boolean;
  title: string;
  body: string;
  targetLabel?: string | null;
  error?: string | null;
  confirmLabel: string;
  cancelLabel: string;
  confirming: boolean;
  onConfirm: () => void;
  onCancel: () => void;
};

export function ConfirmationDialog({
  open,
  title,
  body,
  targetLabel,
  error,
  confirmLabel,
  cancelLabel,
  confirming,
  onConfirm,
  onCancel,
}: ConfirmationDialogProps) {
  if (!open) {
    return null;
  }

  return (
    <div className="master-data-confirmation" role="dialog" aria-modal="true" aria-labelledby="master-data-confirmation-title">
      <div className="master-data-confirmation-card">
        <h4 id="master-data-confirmation-title">{title}</h4>
        <p>{body}</p>
        {targetLabel ? <p className="muted">Bản ghi: {targetLabel}</p> : null}
        {error ? <p className="form-error">{error}</p> : null}
        <div className="master-data-form-actions">
          <button type="button" onClick={onCancel} disabled={confirming}>
            {cancelLabel}
          </button>
          <button type="button" className="primary-button" onClick={onConfirm} disabled={confirming} aria-busy={confirming}>
            {confirming ? 'Đang xử lý...' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
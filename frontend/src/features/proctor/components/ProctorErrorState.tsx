type ProctorErrorStateProps = {
  title?: string;
  message: string;
  retryLabel?: string;
  onRetry?: () => void;
};

export function ProctorErrorState({
  title = 'Không tải được dữ liệu',
  message,
  retryLabel = 'Thử lại',
  onRetry,
}: ProctorErrorStateProps) {
  return (
    <div className="card" style={{ borderColor: 'var(--clr-danger-light)' }}>
      <h3>{title}</h3>
      <p className="error">{message}</p>
      {onRetry ? (
        <button type="button" className="primary-button" onClick={onRetry}>
          {retryLabel}
        </button>
      ) : null}
    </div>
  );
}

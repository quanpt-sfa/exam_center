import { ProcessingOverallStatus, ProcessingStatusApiError } from '../types';

type SubmissionFailureNoticeProps = {
  status: ProcessingOverallStatus;
  failureReason: string | null;
  error: ProcessingStatusApiError | null;
  canRetry: boolean;
  onRetry?: () => void;
};

function sanitizeFailureReason(input: string | null): string | null {
  if (input === null) {
    return null;
  }

  const normalized = input.trim().toUpperCase();
  if (!/^[A-Z0-9_ -]+$/.test(normalized)) {
    return 'UNAVAILABLE';
  }

  return normalized;
}

function failureHeadline(status: ProcessingOverallStatus): string {
  if (status === 'CAPTURE_FAILED') {
    return 'Capture step failed.';
  }
  if (status === 'GRADING_FAILED') {
    return 'Grading step failed.';
  }
  return 'Processing failed.';
}

export function SubmissionFailureNotice({
  status,
  failureReason,
  error,
  canRetry,
  onRetry,
}: SubmissionFailureNoticeProps) {
  const safeReason = sanitizeFailureReason(failureReason);

  return (
    <section className="card" role="alert" aria-live="polite">
      <h3>Processing failed</h3>
      <p>{failureHeadline(status)}</p>
      {safeReason ? <p><strong>Reason code:</strong> {safeReason}</p> : null}
      {error?.code ? <p><strong>Error code:</strong> {error.code}</p> : null}
      <p className="muted">Please retry later or contact support if the issue persists.</p>
      {canRetry && onRetry ? (
        <button type="button" onClick={onRetry}>Retry now</button>
      ) : null}
    </section>
  );
}

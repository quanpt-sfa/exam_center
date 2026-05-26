import { ProcessingStatusBadge } from './ProcessingStatusBadge';
import { ProcessingStatusMessage } from './ProcessingStatusMessage';
import { ProcessingProgressPanel } from './ProcessingProgressPanel';
import { SubmissionFailureNotice } from './SubmissionFailureNotice';
import { SubmissionScoreSummary } from './SubmissionScoreSummary';
import { ProcessingOverallStatus, ProcessingStatusApiError, ProcessingStatusResponse } from '../types';

type SubmissionProcessingResultPanelProps = {
  data: ProcessingStatusResponse | null;
  status: ProcessingOverallStatus | 'UNKNOWN' | null;
  error: ProcessingStatusApiError | null;
  isLoading: boolean;
  isPolling: boolean;
  isTerminal: boolean;
  onRetryTemporary?: () => void;
  onRetryFailure?: () => void;
};

function renderErrorState(error: ProcessingStatusApiError, onRetryTemporary?: () => void): JSX.Element {
  if (error.code === 'permission_denied') {
    return (
      <section className="card" role="alert" aria-live="polite">
        <h3>Access denied</h3>
        <p>You are not allowed to view this submission status.</p>
      </section>
    );
  }

  if (error.code === 'submission_not_found') {
    return (
      <section className="card" role="alert" aria-live="polite">
        <h3>Submission not found</h3>
        <p>The requested submission could not be found.</p>
      </section>
    );
  }

  if (error.code === 'validation_error' || error.code === 'invalid_exam_submission_id') {
    return (
      <section className="card" role="alert" aria-live="polite">
        <h3>Invalid request</h3>
        <p>The request parameters are invalid. Please verify the submission identifier.</p>
      </section>
    );
  }

  if (error.code === 'database_unavailable' || error.code === 'network_error' || error.code === 'request_failed') {
    return (
      <section className="card" role="alert" aria-live="polite">
        <h3>Service temporarily unavailable</h3>
        <p>Please try again in a few moments.</p>
        {onRetryTemporary ? (
          <button type="button" onClick={onRetryTemporary}>Retry now</button>
        ) : null}
      </section>
    );
  }

  return (
    <section className="card" role="alert" aria-live="polite">
      <h3>Processing status unavailable</h3>
      <p>An unexpected error occurred while loading status.</p>
    </section>
  );
}

export function SubmissionProcessingResultPanel({
  data,
  status,
  error,
  isLoading,
  isPolling,
  isTerminal,
  onRetryTemporary,
  onRetryFailure,
}: SubmissionProcessingResultPanelProps) {
  const resolvedStatus = status ?? data?.overall_status ?? null;

  if (isLoading && data === null && error === null) {
    return (
      <section className="card" aria-live="polite">
        <h3>Loading processing status</h3>
        <p className="muted">Please wait while we load your submission status.</p>
      </section>
    );
  }

  if (error !== null) {
    return renderErrorState(error, onRetryTemporary);
  }

  if (resolvedStatus === 'NOT_FOUND') {
    return (
      <section className="card" role="alert" aria-live="polite">
        <h3>Submission not found</h3>
        <p>The requested submission could not be found.</p>
      </section>
    );
  }

  if (resolvedStatus === 'UNKNOWN') {
    return (
      <section className="card" role="alert" aria-live="polite">
        <h3>Processing status unavailable</h3>
        <p>The system returned an unsupported status value.</p>
      </section>
    );
  }

  if (data === null) {
    return (
      <section className="card" aria-live="polite">
        <h3>Processing status unavailable</h3>
        <p>No status data is currently available.</p>
      </section>
    );
  }

  const showFailure = resolvedStatus === 'CAPTURE_FAILED' || resolvedStatus === 'GRADING_FAILED';
  const showScore = resolvedStatus === 'COMPLETED';

  return (
    <section className="card" aria-live="polite">
      <h2>Submission Processing Status</h2>
      <ProcessingStatusBadge status={resolvedStatus} />
      <ProcessingStatusMessage status={resolvedStatus} isPolling={isPolling} />

      <ProcessingProgressPanel data={data} />

      {showScore ? <SubmissionScoreSummary data={data} /> : null}

      {showFailure ? (
        <SubmissionFailureNotice
          status={resolvedStatus}
          failureReason={data.failure_reason}
          error={error}
          canRetry={data.can_retry}
          onRetry={onRetryFailure}
        />
      ) : null}

      {resolvedStatus === 'NEEDS_REVIEW' ? (
        <section className="card" aria-live="polite">
          <h3>Manual review required</h3>
          <p>This submission requires manual review before final release.</p>
        </section>
      ) : null}

      <p className="muted">{isTerminal ? 'Automatic checking has stopped.' : 'Automatic checking is running.'}</p>
    </section>
  );
}

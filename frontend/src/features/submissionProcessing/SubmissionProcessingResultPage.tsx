import { useMemo } from 'react';
import { useParams } from 'react-router-dom';

import { SubmissionProcessingResultPanel } from './components/SubmissionProcessingResultPanel';
import { useSubmissionProcessingStatus } from './useSubmissionProcessingStatus';

const TEMPORARY_RETRY_CODES = new Set([
  'database_unavailable',
  'network_error',
  'request_failed',
  'request_aborted',
]);

function parseSubmissionId(raw: string | undefined): number | null {
  if (typeof raw !== 'string') {
    return null;
  }

  const numeric = Number(raw);
  if (!Number.isInteger(numeric) || numeric <= 0) {
    return null;
  }

  return numeric;
}

export function SubmissionProcessingResultPage() {
  const { examSubmissionId: examSubmissionIdRaw } = useParams<{ examSubmissionId: string }>();
  const examSubmissionId = parseSubmissionId(examSubmissionIdRaw);
  const isValidRouteId = examSubmissionId !== null;

  const pollingState = useSubmissionProcessingStatus({
    examSubmissionId: examSubmissionId ?? 0,
    enabled: isValidRouteId,
    initialIntervalMs: 2500,
    maxIntervalMs: 20000,
  });

  const allowTemporaryRetry = useMemo(() => {
    if (pollingState.error === null) {
      return false;
    }
    return TEMPORARY_RETRY_CODES.has(pollingState.error.code);
  }, [pollingState.error]);

  if (!isValidRouteId) {
    return (
      <section className="card" role="alert" aria-live="polite">
        <h2>Invalid submission identifier</h2>
        <p>Please provide a valid positive exam submission ID.</p>
      </section>
    );
  }

  const isTerminalFailureState = pollingState.status === 'CAPTURE_FAILED' || pollingState.status === 'GRADING_FAILED';

  return (
    <section>
      <h2>Submission Result</h2>
      <p className="muted">
        <strong>Submission ID:</strong> {examSubmissionId}
      </p>

      <SubmissionProcessingResultPanel
        data={pollingState.data}
        status={pollingState.status}
        error={pollingState.error}
        isLoading={pollingState.isLoading}
        isPolling={pollingState.isPolling}
        isTerminal={pollingState.isTerminal}
        onRetryTemporary={allowTemporaryRetry ? pollingState.retryNow : undefined}
        onRetryFailure={undefined}
      />

      {isTerminalFailureState && pollingState.data?.can_retry ? (
        <section className="card" aria-live="polite">
          <h3>Retry request</h3>
          <p>
            This submission is retry-eligible, but no student-facing retry endpoint is currently available.
            Please contact support or an instructor for assistance.
          </p>
        </section>
      ) : null}

      {pollingState.lastUpdatedAt ? (
        <p className="muted">
          <strong>Last updated:</strong> {pollingState.lastUpdatedAt}
        </p>
      ) : null}
    </section>
  );
}

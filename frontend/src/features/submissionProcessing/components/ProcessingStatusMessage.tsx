import { ProcessingOverallStatus } from '../types';

type ProcessingStatusMessageProps = {
  status: ProcessingOverallStatus | 'UNKNOWN' | null;
  isPolling: boolean;
};

function statusMessage(status: ProcessingOverallStatus | 'UNKNOWN' | null): string {
  if (status === 'WAITING_CAPTURE') {
    return "Preparing and capturing the student's database state.";
  }
  if (status === 'CAPTURING') {
    return 'Capture is in progress.';
  }
  if (status === 'WAITING_GRADING') {
    return 'Your submission is queued for grading.';
  }
  if (status === 'GRADING') {
    return 'Your submission is being graded.';
  }
  if (status === 'COMPLETED') {
    return 'Processing completed.';
  }
  if (status === 'CAPTURE_FAILED') {
    return 'Capture step failed.';
  }
  if (status === 'GRADING_FAILED') {
    return 'Grading failed.';
  }
  if (status === 'NEEDS_REVIEW') {
    return 'Manual review is required before final release.';
  }
  if (status === 'DRAFT_OR_UNSEALED') {
    return 'Submission has not been fully sealed for processing yet.';
  }
  if (status === 'SEALED') {
    return 'Submission is sealed and waiting for processing pipeline progress.';
  }
  if (status === 'NOT_FOUND') {
    return 'Submission not found.';
  }
  return 'Processing status unavailable.';
}

export function ProcessingStatusMessage({ status, isPolling }: ProcessingStatusMessageProps) {
  return (
    <div aria-live="polite">
      <p>{statusMessage(status)}</p>
      <p className="muted">{isPolling ? 'Polling is active.' : 'Polling has stopped.'}</p>
    </div>
  );
}

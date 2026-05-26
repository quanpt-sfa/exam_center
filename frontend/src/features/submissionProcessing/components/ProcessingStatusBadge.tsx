import { ProcessingOverallStatus } from '../types';

type ProcessingStatusBadgeProps = {
  status: ProcessingOverallStatus | 'UNKNOWN' | null;
};

const STATUS_LABELS: Record<ProcessingOverallStatus | 'UNKNOWN', string> = {
  NOT_FOUND: 'Not Found',
  DRAFT_OR_UNSEALED: 'Draft or Unsealed',
  SEALED: 'Sealed',
  WAITING_CAPTURE: 'Waiting Capture',
  CAPTURING: 'Capturing',
  CAPTURE_FAILED: 'Capture Failed',
  WAITING_GRADING: 'Waiting Grading',
  GRADING: 'Grading',
  GRADING_FAILED: 'Grading Failed',
  COMPLETED: 'Completed',
  NEEDS_REVIEW: 'Needs Review',
  UNKNOWN: 'Unavailable',
};

export function ProcessingStatusBadge({ status }: ProcessingStatusBadgeProps) {
  if (status === null) {
    return <p><strong>Status:</strong> Unknown</p>;
  }

  return (
    <p>
      <strong>Status:</strong> {STATUS_LABELS[status]}
    </p>
  );
}

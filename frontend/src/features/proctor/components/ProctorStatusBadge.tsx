import { StatusBadge } from '../../../shared/components/StatusBadge';
import {
  assignmentStatusLabel,
  incidentStatusLabel,
  incidentTypeLabel,
  readinessStatusLabel,
  sessionStatusLabel,
  stationAssignmentStatusLabel,
  submissionStatusLabel,
} from '../proctorDisplay';

type ProctorStatusBadgeProps = {
  kind: 'session' | 'submission' | 'readiness' | 'assignment' | 'station-assignment' | 'incident-type' | 'incident-status' | 'raw';
  value?: string | null;
};

export function ProctorStatusBadge({ kind, value }: ProctorStatusBadgeProps) {
  let label = value ?? 'UNKNOWN';
  switch (kind) {
    case 'session':
      label = sessionStatusLabel(value);
      break;
    case 'submission':
      label = submissionStatusLabel(value);
      break;
    case 'readiness':
      label = readinessStatusLabel(value);
      break;
    case 'assignment':
      label = assignmentStatusLabel(value);
      break;
    case 'station-assignment':
      label = stationAssignmentStatusLabel(value);
      break;
    case 'incident-type':
      label = incidentTypeLabel(value);
      break;
    case 'incident-status':
      label = incidentStatusLabel(value);
      break;
    case 'raw':
      break;
  }

  return <StatusBadge status={value ?? 'UNKNOWN'} customLabel={label} />;
}

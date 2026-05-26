import React from 'react';

type StatusType =
  | 'DRAFT'
  | 'PUBLISHED'
  | 'CONFIGURED'
  | 'ARCHIVED'
  | 'SCHEDULED'
  | 'CHECK_IN_OPEN'
  | 'IN_PROGRESS'
  | 'CLOSED'
  | 'LOCKED'
  | 'PRESENT'
  | 'ABSENT'
  | 'LATE'
  | 'FLAGGED'
  | 'SUBMITTED'
  | 'SEALED'
  | 'GRADED'
  | string;

type StatusBadgeProps = {
  status: StatusType;
  customLabel?: string;
};

export function StatusBadge({ status, customLabel }: StatusBadgeProps) {
  const norm = String(status || '').toUpperCase().trim();

  let label = customLabel || status;
  let bg = 'var(--clr-gray-100)';
  let color = 'var(--clr-gray-700)';
  let borderColor = 'var(--clr-gray-200)';

  switch (norm) {
    case 'PUBLISHED':
    case 'PRESENT':
    case 'SUBMITTED':
    case 'GRADED':
      bg = 'var(--clr-success-light)';
      color = 'var(--clr-success)';
      borderColor = 'rgba(22, 163, 74, 0.2)';
      break;

    case 'IN_PROGRESS':
    case 'CHECK_IN_OPEN':
    case 'CONFIGURED':
      bg = 'var(--clr-primary-50)';
      color = 'var(--clr-primary-600)';
      borderColor = 'var(--clr-primary-200)';
      break;

    case 'DRAFT':
    case 'SCHEDULED':
      bg = 'var(--clr-gray-100)';
      color = 'var(--clr-gray-600)';
      borderColor = 'var(--clr-gray-250, #e2e8f0)';
      break;

    case 'LATE':
    case 'WARNING':
      bg = 'var(--clr-warning-light)';
      color = 'var(--clr-warning)';
      borderColor = 'rgba(217, 119, 6, 0.2)';
      break;

    case 'ABSENT':
    case 'FLAGGED':
    case 'DANGER':
    case 'ERROR':
      bg = 'var(--clr-danger-light)';
      color = 'var(--clr-danger)';
      borderColor = 'rgba(220, 38, 38, 0.2)';
      break;

    case 'SEALED':
    case 'LOCKED':
    case 'ARCHIVED':
      bg = 'var(--clr-gray-800)';
      color = '#ffffff';
      borderColor = 'var(--clr-gray-900)';
      break;

    default:
      // Neutral
      break;
  }

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        padding: 'var(--sp-1) var(--sp-3)',
        borderRadius: 'var(--radius-full)',
        fontSize: 'var(--text-xs)',
        fontWeight: 'var(--fw-semibold)',
        textTransform: 'uppercase',
        backgroundColor: bg,
        color: color,
        border: `1px solid ${borderColor}`,
        whiteSpace: 'nowrap',
        letterSpacing: '0.025em',
      }}
    >
      {label}
    </span>
  );
}

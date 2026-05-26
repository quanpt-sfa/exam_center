import { render, screen } from '@testing-library/react';
import { describe, expect, test } from 'vitest';
import { ProctorStatusBadge } from './components/ProctorStatusBadge';

describe('ProctorStatusBadge', () => {
  test('renders safe fallback for unknown session status', () => {
    render(<ProctorStatusBadge kind="session" value="WAITING_ROOM" />);
    expect(screen.getByText('Không xác định: WAITING_ROOM')).toBeInTheDocument();
  });

  test('renders safe fallback for unknown submission status', () => {
    render(<ProctorStatusBadge kind="submission" value="QUEUED_REVIEW" />);
    expect(screen.getByText('Không xác định: QUEUED_REVIEW')).toBeInTheDocument();
  });

  test('renders safe fallback for unknown readiness severity', () => {
    render(<ProctorStatusBadge kind="readiness" value="DEGRADED" />);
    expect(screen.getByText('Không xác định: DEGRADED')).toBeInTheDocument();
  });

  test('renders safe fallback for unknown incident type and status', () => {
    const { rerender } = render(<ProctorStatusBadge kind="incident-type" value="STRANGE_CASE" />);
    expect(screen.getByText('Không xác định: STRANGE_CASE')).toBeInTheDocument();

    rerender(<ProctorStatusBadge kind="incident-status" value="ESCALATED_EXTERNALLY" />);
    expect(screen.getByText('Không xác định: ESCALATED_EXTERNALLY')).toBeInTheDocument();
  });
});

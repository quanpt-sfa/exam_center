import { EmptyState } from '../../../shared/components/EmptyState';

type ProctorEmptyStateProps = {
  message: string;
  icon?: string;
  actionLabel?: string;
  onAction?: () => void;
};

export function ProctorEmptyState({ message, icon, actionLabel, onAction }: ProctorEmptyStateProps) {
  return <EmptyState message={message} icon={icon} actionLabel={actionLabel} onAction={onAction} />;
}

type ApiStatus = 'connected' | 'partial' | 'missing';

function getDefaultLabel(status: ApiStatus): string {
  if (status === 'connected') {
    return 'Đã nối API';
  }
  if (status === 'partial') {
    return 'Nối một phần';
  }
  return 'Chưa có API';
}

export function ApiStatusChip({
  status,
  label,
}: {
  status: ApiStatus;
  label?: string;
}) {
  return (
    <span className={`compact-status-chip compact-status-chip--${status}`}>
      {label ?? getDefaultLabel(status)}
    </span>
  );
}
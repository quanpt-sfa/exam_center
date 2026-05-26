import { Link } from 'react-router-dom';
import { StatusBadge } from '../../shared/components/StatusBadge';
import { CompactSurface } from '../../shared/components/compact/CompactSurface';
import type { AdminDashboardAlert, DashboardSeverity } from './adminDashboardContracts';

type AdminDashboardAlertPanelProps = {
  alerts: AdminDashboardAlert[];
};

function normalizeSeverity(severity: DashboardSeverity): string {
  const normalized = String(severity || '').trim().toLowerCase();
  if (!normalized) {
    return 'info';
  }
  return normalized;
}

function severityBadgeStatus(severity: DashboardSeverity): string {
  switch (normalizeSeverity(severity)) {
    case 'critical':
      return 'ERROR';
    case 'warning':
      return 'WARNING';
    default:
      return 'CONFIGURED';
  }
}

function severityLabel(severity: DashboardSeverity): string {
  switch (normalizeSeverity(severity)) {
    case 'critical':
      return 'Critical';
    case 'warning':
      return 'Warning';
    case 'info':
      return 'Info';
    default:
      return String(severity || 'Unknown');
  }
}

function formatTimestamp(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat('vi-VN', {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(parsed);
}

function alertTypeLabel(type: string): string {
  switch (String(type).toUpperCase()) {
    case 'INCIDENT':
      return 'Incident';
    case 'CLOSE_ROOM_BLOCKED':
      return 'Close room blocked';
    case 'SETUP_BLOCKER_NO_PUBLISHED_EXAM':
      return 'Setup blocker: no published exam';
    case 'SETUP_BLOCKER_NOT_PREPARED':
      return 'Setup blocker: runtime not prepared';
    case 'SESSION_STALE':
      return 'Session stale';
    case 'SESSION_INTERRUPTED':
      return 'Session interrupted';
    default:
      return type;
  }
}

export function AdminDashboardAlertPanel({ alerts }: AdminDashboardAlertPanelProps) {
  return (
    <CompactSurface
      className="dashboard-alert-surface compact-data-table"
      aria-label="Operational alerts"
      title="Operational alerts"
      description="Danh sách cảnh báo vận hành từ backend, không có thao tác resolve cục bộ."
    >
      {alerts.length === 0 ? (
        <div className="empty-state">Không có cảnh báo vận hành hiện tại.</div>
      ) : (
        <div className="dashboard-alert-table-wrap">
          <table>
            <thead>
              <tr>
                <th>Mức độ</th>
                <th>Cảnh báo</th>
                <th>Ngữ cảnh</th>
                <th>Thời điểm</th>
                <th>Thao tác</th>
              </tr>
            </thead>
            <tbody>
              {alerts.map((alert) => (
                <tr key={alert.alert_id}>
                  <td>
                    <div className="dashboard-alert-cell-stack">
                      <StatusBadge status={severityBadgeStatus(alert.severity)} customLabel={severityLabel(alert.severity)} />
                      <span>{alertTypeLabel(alert.type)}</span>
                    </div>
                  </td>
                  <td>
                    <div className="dashboard-alert-cell-stack">
                      <strong>{alert.title}</strong>
                      <span>{alert.description}</span>
                    </div>
                  </td>
                  <td>
                    <div className="dashboard-alert-cell-stack">
                      <span>Entity: {alert.entity_type} #{alert.entity_id}</span>
                      {alert.exam_sitting_id != null ? <span>Ca thi: {alert.exam_sitting_id}</span> : null}
                      {alert.exam_sitting_room_id != null ? <span>Phòng: {alert.exam_sitting_room_id}</span> : null}
                      <span>Status: {alert.status}</span>
                    </div>
                  </td>
                  <td>{formatTimestamp(alert.created_at)}</td>
                  <td>
                    {alert.action_route ? (
                      <Link className="secondary-button compact-button" to={alert.action_route}>
                        Mở workflow
                      </Link>
                    ) : (
                      <span className="muted">Chỉ đọc</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </CompactSurface>
  );
}

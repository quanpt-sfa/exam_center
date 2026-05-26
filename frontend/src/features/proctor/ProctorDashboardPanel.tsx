import { FormEvent, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { logout } from '../auth/authApi';
import { clearAuthTokens, getAccessToken, getRefreshToken } from '../../shared/auth/tokenStorage';
import { StatusBadge } from '../../shared/components/StatusBadge';
import {
  createProctorIncident,
  loadMySittingRooms,
  loadProctorReadiness,
  loadProctorRoster,
  revokeProctorStudentStaleSession,
  type RevokeStaleSessionResult,
  type ProctorReadinessItem,
  type ProctorRoom,
  type ProctorRosterItem,
} from './proctorDashboardApi';
import { ProctorApiError } from './api/proctorApi';

type ProctorDashboardPanelProps = {
  allowSessionRevoke?: boolean;
};

type ExamProgressStatus = 'not_started' | 'in_progress' | 'submitted';

function normalized(value?: string | null): string {
  return String(value || '').trim().toUpperCase();
}

function resolveExamProgress(item: ProctorRosterItem): ExamProgressStatus {
  const submissionStatus = normalized(item.submission_status);
  const sessionStatus = normalized(item.session_status);

  if (item.sealed_at || item.submitted_at || ['SUBMITTED', 'SEALED', 'GRADED', 'FINALIZED'].includes(submissionStatus)) {
    return 'submitted';
  }

  if (['IN_PROGRESS', 'STARTED', 'RUNNING', 'PAUSED', 'INTERRUPTED'].includes(sessionStatus) || item.started_at) {
    return 'in_progress';
  }

  return 'not_started';
}

function examProgressLabel(status: ExamProgressStatus): string {
  if (status === 'submitted') return 'Đã thi';
  if (status === 'in_progress') return 'Đang thi';
  return 'Chưa thi';
}

function formatDateTime(value?: string | null): string {
  if (!value) return '-';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return new Intl.DateTimeFormat('vi-VN', {
    hour: '2-digit',
    minute: '2-digit',
    day: '2-digit',
    month: '2-digit',
  }).format(parsed);
}

export function ProctorDashboardPanel({ allowSessionRevoke = true }: ProctorDashboardPanelProps) {
  const navigate = useNavigate();
  const [rooms, setRooms] = useState<ProctorRoom[]>([]);
  const [selectedRoomId, setSelectedRoomId] = useState<number | null>(null);
  const [roster, setRoster] = useState<ProctorRosterItem[]>([]);
  const [readiness, setReadiness] = useState<ProctorReadinessItem[]>([]);
  const [incidentType, setIncidentType] = useState('DEVICE_FAILURE');
  const [incidentDescription, setIncidentDescription] = useState('');
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [revokingStudentId, setRevokingStudentId] = useState<number | null>(null);

  // Check-In and Roster Lock local state for UX presentation
  const [isCheckInOpen, setIsCheckInOpen] = useState(false);
  const [isRosterLocked, setIsRosterLocked] = useState(false);

  useEffect(() => {
    loadMySittingRooms()
      .then((items) => {
        setRooms(items);
        if (items.length > 0) {
          setSelectedRoomId(items[0].exam_sitting_room_id);
        }
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Không tải được phòng được phân công.'));
  }, []);

  useEffect(() => {
    if (!selectedRoomId) {
      setRoster([]);
      setReadiness([]);
      return;
    }
    Promise.all([loadProctorRoster(selectedRoomId), loadProctorReadiness(selectedRoomId)])
      .then(([rosterRows, readinessRows]) => {
        setRoster(rosterRows);
        setReadiness(readinessRows);
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Không tải được dữ liệu phòng thi.'));
  }, [selectedRoomId]);

  const progressStats = useMemo(() => {
    return roster.reduce(
      (stats, item) => {
        stats.total += 1;
        stats[resolveExamProgress(item)] += 1;
        return stats;
      },
      { total: 0, not_started: 0, in_progress: 0, submitted: 0 }
    );
  }, [roster]);

  async function handleLogout() {
    const refreshToken = getRefreshToken();
    if (getAccessToken()) {
      await logout(refreshToken).catch(() => null);
    }
    clearAuthTokens();
    navigate('/login', { replace: true });
  }

  async function handleSubmitIncident(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedRoomId) {
      setError('Chưa chọn phòng thi.');
      return;
    }
    setError(null);
    setMessage(null);
    try {
      await createProctorIncident(selectedRoomId, {
        incident_type: incidentType,
        description: incidentDescription,
      });
      setMessage('Đã ghi nhận sự cố.');
      setIncidentDescription('');
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Không thể ghi nhận sự cố.');
    }
  }

  async function handleRevokeSession(item: ProctorRosterItem) {
    if (!allowSessionRevoke || !selectedRoomId || !item.student_id) {
      return;
    }

    const confirmed = window.confirm(
      'Thao tác này sẽ thu hồi phiên đăng nhập hiện tại của sinh viên. Sinh viên cần đăng nhập lại. Bạn có chắc chắn muốn tiếp tục?'
    );
    if (!confirmed) {
      return;
    }

    setRevokingStudentId(item.student_id);
    setError(null);
    setMessage(null);

    try {
      const response: RevokeStaleSessionResult = await revokeProctorStudentStaleSession(selectedRoomId, item.student_id);
      if (response.status === 'no_active_session') {
        setMessage('Sinh viên hiện không có phiên đăng nhập đang hoạt động.');
        return;
      }

      setMessage('Đã thu hồi phiên đăng nhập. Sinh viên có thể đăng nhập lại.');
    } catch (revokeError) {
      if (revokeError instanceof ProctorApiError && revokeError.code === 'permission_denied') {
        setError('Bạn không có quyền thực hiện thao tác này.');
      } else {
        setError('Không thể thu hồi phiên đăng nhập lúc này. Vui lòng thử lại sau.');
      }
    } finally {
      setRevokingStudentId(null);
    }
  }

  return (
    <section className="card">
      <div className="proctor-dashboard-header">
        <div>
          <p className="eyebrow">Dashboard giám thị</p>
          <h2>Phòng được phân công</h2>
        </div>
        <button className="secondary-button" type="button" onClick={handleLogout}>
          Thoát tài khoản
        </button>
      </div>

      {error ? <p className="error">{error}</p> : null}
      {message ? <p className="success-message">{message}</p> : null}

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--sp-4)', alignItems: 'flex-end', marginBottom: 'var(--sp-5)' }}>
        <div style={{ flex: 1, minWidth: '240px' }}>
          <label htmlFor="proctor-room-select" style={{ display: 'block', marginBottom: 'var(--sp-1)', fontWeight: 'var(--fw-semibold)' }}>
            Phòng được phân công
          </label>
          <select
            id="proctor-room-select"
            value={selectedRoomId ?? ''}
            onChange={(event) => setSelectedRoomId(Number(event.target.value))}
            style={{ width: '100%' }}
          >
            {rooms.map((room) => (
              <option key={room.exam_sitting_room_id} value={room.exam_sitting_room_id}>
                {room.room_code} - {room.sitting_code}
              </option>
            ))}
          </select>
        </div>

        {/* Room Readiness & Operation controls */}
        <div style={{ display: 'flex', gap: 'var(--sp-2)', alignItems: 'center', flexWrap: 'wrap' }}>
          <button
            type="button"
            className={isCheckInOpen ? "secondary-button" : "primary-button"}
            onClick={() => setIsCheckInOpen(!isCheckInOpen)}
            style={{ padding: 'var(--sp-2) var(--sp-3)', fontSize: 'var(--text-sm)', display: 'flex', alignItems: 'center', gap: '4px' }}
          >
            {isCheckInOpen ? "⛔ Đóng Check-in" : "🔑 Mở Check-in"}
          </button>
          <button
            type="button"
            className={isRosterLocked ? "secondary-button" : "primary-button"}
            onClick={() => setIsRosterLocked(!isRosterLocked)}
            style={{ padding: 'var(--sp-2) var(--sp-3)', fontSize: 'var(--text-sm)', display: 'flex', alignItems: 'center', gap: '4px' }}
          >
            {isRosterLocked ? "🔓 Mở khóa Roster" : "🔒 Khóa Roster"}
          </button>
        </div>
      </div>

      <section className="dashboard-stats proctor-progress-stats" aria-label="Tổng quan sinh viên dự thi" style={{ marginBottom: 'var(--sp-5)' }}>
        <div className="stat-tile stat-total">
          <span>{progressStats.total}</span>
          <p>Sinh viên</p>
        </div>
        <div className="stat-tile stat-open">
          <span>{progressStats.in_progress}</span>
          <p>Đang thi</p>
        </div>
        <div className="stat-tile stat-done">
          <span>{progressStats.submitted}</span>
          <p>Đã thi</p>
        </div>
        <div className="stat-tile">
          <span>{progressStats.not_started}</span>
          <p>Chưa thi</p>
        </div>
      </section>

      {/* Checkin / Lock active status badges info bar */}
      <div
        style={{
          display: 'flex',
          gap: 'var(--sp-3)',
          alignItems: 'center',
          padding: 'var(--sp-3) var(--sp-4)',
          background: 'var(--surface-body)',
          borderRadius: 'var(--radius-md)',
          border: '1px solid var(--clr-gray-200)',
          marginBottom: 'var(--sp-4)',
        }}
      >
        <span style={{ fontSize: 'var(--text-xs)', fontWeight: 'var(--fw-semibold)', color: 'var(--text-secondary)' }}>
          Trạng thái phòng:
        </span>
        <StatusBadge status={isCheckInOpen ? "PRESENT" : "ABSENT"} customLabel={isCheckInOpen ? "ĐANG CHECK-IN" : "ĐÓNG CHECK-IN"} />
        <StatusBadge status={isRosterLocked ? "LOCKED" : "WARNING"} customLabel={isRosterLocked ? "ROSTER ĐÃ KHÓA" : "ROSTER MỞ"} />
      </div>

      <h3>Danh sách sinh viên dự thi</h3>
      <div className="table-shell" style={{ marginBottom: 'var(--sp-5)' }}>
        <div className="table-scroll">
          <table className="table table-hover">
            <thead>
              <tr>
                <th>Mã sinh viên</th>
                <th>Họ tên</th>
                <th>Vị trí máy</th>
                <th>Thiết bị</th>
                <th>Trạng thái thi</th>
                <th>Session</th>
                <th>Nộp bài</th>
                {allowSessionRevoke ? <th>Thao tác</th> : null}
              </tr>
            </thead>
            <tbody>
              {roster.length === 0 ? (
                <tr>
                  <td colSpan={allowSessionRevoke ? 8 : 7} style={{ textAlign: 'center', color: 'var(--text-secondary)' }}>
                    Chưa có sinh viên trong phòng này.
                  </td>
                </tr>
              ) : (
                roster.map((item) => {
                  const progress = resolveExamProgress(item);
                  return (
                    <tr key={`${item.student_code}-${item.station_code}`}>
                      <td style={{ fontWeight: 'var(--fw-semibold)' }}>{item.student_code}</td>
                      <td>{item.full_name}</td>
                      <td>
                        <code style={{ padding: '2px 6px', background: 'var(--clr-primary-50)', color: 'var(--clr-primary-700)', borderRadius: 'var(--radius-sm)', fontSize: 'var(--text-xs)' }}>
                          {item.station_code}
                        </code>
                      </td>
                      <td>{item.planned_device_asset_tag || '-'}</td>
                      <td>
                        <StatusBadge
                          status={progress === 'submitted' ? 'PRESENT' : progress === 'in_progress' ? 'IN_PROGRESS' : 'ABSENT'}
                          customLabel={examProgressLabel(progress)}
                        />
                      </td>
                      <td>{item.session_status || item.assignment_status || '-'}</td>
                      <td>{formatDateTime(item.submitted_at || item.sealed_at)}</td>
                      {allowSessionRevoke ? (
                        <td>
                          <button
                            type="button"
                            className="secondary-button"
                            disabled={!item.student_id || revokingStudentId === item.student_id}
                            onClick={() => void handleRevokeSession(item)}
                          >
                            {revokingStudentId === item.student_id ? 'Đang xử lý...' : 'Thu hồi phiên đăng nhập kẹt'}
                          </button>
                        </td>
                      ) : null}
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      <h3>Tình trạng máy</h3>
      <div className="table-shell" style={{ marginBottom: 'var(--sp-5)' }}>
        <div className="table-scroll">
          <table className="table table-hover">
            <thead>
              <tr>
                <th>Vị trí máy</th>
                <th>Thiết bị</th>
                <th>Trạng thái máy</th>
              </tr>
            </thead>
            <tbody>
              {readiness.map((item) => (
                <tr key={`ready-${item.station_code}`}>
                  <td>{item.station_code}</td>
                  <td>{item.asset_tag || '-'}</td>
                  <td>
                    <StatusBadge
                      status={item.mismatch ? 'WARNING' : item.health_status === 'HEALTHY' ? 'PUBLISHED' : 'ABSENT'}
                      customLabel={`${item.health_status || 'UNKNOWN'}${item.mismatch ? ' (Sai vị trí)' : ''}`}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <h3>Báo sự cố</h3>
      <form onSubmit={handleSubmitIncident} style={{ background: 'var(--surface-body)', padding: 'var(--sp-4)', borderRadius: 'var(--radius-lg)', border: '1px solid var(--clr-gray-200)' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 'var(--sp-3)', marginBottom: 'var(--sp-4)' }}>
          <label htmlFor="incident-type" style={{ display: 'block', fontWeight: 'var(--fw-semibold)' }}>
            Loại sự cố
            <select id="incident-type" value={incidentType} onChange={(event) => setIncidentType(event.target.value)} style={{ width: '100%', marginTop: 'var(--sp-1)' }}>
              <option value="DEVICE_FAILURE">DEVICE_FAILURE</option>
              <option value="NETWORK_FAILURE">NETWORK_FAILURE</option>
              <option value="POWER_FAILURE">POWER_FAILURE</option>
              <option value="ADMIN_NOTE">ADMIN_NOTE</option>
            </select>
          </label>
          <label htmlFor="incident-description" style={{ display: 'block', fontWeight: 'var(--fw-semibold)' }}>
            Mô tả
            <input
              id="incident-description"
              value={incidentDescription}
              onChange={(event) => setIncidentDescription(event.target.value)}
              placeholder="VD: Màn hình không lên nguồn..."
              style={{ width: '100%', marginTop: 'var(--sp-1)' }}
            />
          </label>
        </div>
        <button type="submit" className="primary-button">Báo sự cố</button>
      </form>
    </section>
  );
}

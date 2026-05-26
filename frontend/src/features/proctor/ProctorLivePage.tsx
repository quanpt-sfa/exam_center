import { useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import { CompactPage } from '../../shared/components/compact/CompactPage';
import { CompactPageHeader } from '../../shared/components/compact/CompactPageHeader';
import { CompactSurface } from '../../shared/components/compact/CompactSurface';
import { CompactToolbar } from '../../shared/components/compact/CompactToolbar';
import { getProctorRoomRoster } from './api/proctorApi';
import type { ProctorRoomRosterItem, ProctorRoomRosterResponse } from './api/contracts';
import { ProctorEmptyState } from './components/ProctorEmptyState';
import { ProctorErrorState } from './components/ProctorErrorState';
import { ProctorInvalidRoomState } from './components/ProctorInvalidRoomState';
import { ProctorLoadingState } from './components/ProctorLoadingState';
import { ProctorStatusBadge } from './components/ProctorStatusBadge';
import { RevokeStaleSessionDialog } from './components/RevokeStaleSessionDialog';
import { formatDateTime, hasTerminalSubmissionState } from './proctorDisplay';
import { resolveExamSittingRoomId } from './proctorRoute';

const POLL_INTERVAL_MS = 15000;

function shouldKeepPolling(items: ProctorRoomRosterItem[]): boolean {
  if (items.length === 0) {
    return true;
  }
  return !items.every((item) => hasTerminalSubmissionState(item));
}

export function ProctorLivePage() {
  const params = useParams<{ examSittingRoomId: string }>();
  const routeExamSittingRoomId = params.examSittingRoomId;
  const roomIdResolution = resolveExamSittingRoomId(routeExamSittingRoomId);
  const examSittingRoomId = roomIdResolution.isValid ? roomIdResolution.examSittingRoomId : null;
  const [roster, setRoster] = useState<ProctorRoomRosterResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<string | null>(null);
  const [selectedCandidate, setSelectedCandidate] = useState<ProctorRoomRosterItem | null>(null);
  const [pollingEnabled, setPollingEnabled] = useState(true);
  const pollingRef = useRef<number | null>(null);

  async function loadRoster(mode: 'initial' | 'refresh' = 'initial') {
    if (!roomIdResolution.isValid || examSittingRoomId === null) {
      setLoading(false);
      setRefreshing(false);
      setError(roomIdResolution.errorMessage);
      return;
    }
    if (mode === 'refresh') {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError(null);
    try {
      const nextRoster = await getProctorRoomRoster(examSittingRoomId);
      setRoster(nextRoster);
      setLastUpdatedAt(new Date().toISOString());
      const nextPollingEnabled = shouldKeepPolling(nextRoster.items);
      setPollingEnabled(nextPollingEnabled);
      if (!nextPollingEnabled && pollingRef.current !== null) {
        window.clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Không tải được dữ liệu theo dõi phòng thi.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => {
    if (!roomIdResolution.isValid || examSittingRoomId === null) {
      setLoading(false);
      setError(roomIdResolution.errorMessage);
      return;
    }
    void loadRoster();
    pollingRef.current = window.setInterval(() => {
      void loadRoster('refresh');
    }, POLL_INTERVAL_MS);

    return () => {
      if (pollingRef.current !== null) {
        window.clearInterval(pollingRef.current);
      }
    };
  }, [examSittingRoomId, routeExamSittingRoomId]);

  if (!roomIdResolution.isValid || examSittingRoomId === null) {
    return (
      <CompactPage data-testid="proctor-live-page">
        <ProctorInvalidRoomState message={roomIdResolution.errorMessage} />
      </CompactPage>
    );
  }

  return (
    <CompactPage data-testid="proctor-live-page">
      <CompactPageHeader
        eyebrow="Proctor Portal"
        title="Theo dõi phòng thi"
        description="Theo dõi theo lượt cập nhật, chưa dùng WebSocket/SSE."
        secondaryActions={
          <button type="button" className="secondary-button" onClick={() => void loadRoster('refresh')} disabled={loading || refreshing}>
            {refreshing ? 'Đang tải...' : 'Làm mới thủ công'}
          </button>
        }
      />

      <CompactToolbar>
        <span className="muted">Room: {roster?.room_code ?? `#${examSittingRoomId}`}</span>
        <span className="muted">{lastUpdatedAt ? `Cập nhật: ${formatDateTime(lastUpdatedAt)}` : 'Chưa có dữ liệu'}</span>
        <span className="muted">
          {pollingEnabled ? `Tự động làm mới mỗi ${POLL_INTERVAL_MS / 1000} giây` : 'Đã dừng tự động làm mới vì tất cả thí sinh đã ở trạng thái kết thúc'}
        </span>
      </CompactToolbar>

      {error ? <ProctorErrorState message={error} onRetry={() => void loadRoster()} /> : null}
      {loading ? <ProctorLoadingState message="Đang tải trạng thái theo dõi..." /> : null}

      {!loading && !error && roster && roster.items.length === 0 ? (
        <ProctorEmptyState icon="📡" message="Không có dữ liệu session/submission cho phòng thi này." />
      ) : null}

      {!loading && !error && roster && roster.items.length > 0 ? (
        <CompactSurface tight title="Roster monitor" description="Bảng theo dõi backend-bound theo từng thí sinh/máy.">
        <div className="table-shell">
          <div className="table-scroll">
            <table className="table table-compact">
              <thead>
                <tr>
                  <th>Mã SV</th>
                  <th>Máy</th>
                  <th>Phiên thi</th>
                  <th>Bài nộp</th>
                  <th>Trạng thái máy</th>
                  <th>Lần thấy gần nhất</th>
                  <th>Bắt đầu</th>
                  <th>Nộp bài</th>
                  <th>Thao tác</th>
                </tr>
              </thead>
              <tbody>
                {roster.items.map((item) => (
                  <tr key={`${item.student_id}-${item.station_id}`}>
                    <td>{item.student_code}</td>
                    <td>{item.station_code}</td>
                    <td><ProctorStatusBadge kind="session" value={item.session_status} /></td>
                    <td><ProctorStatusBadge kind="submission" value={item.submission_status} /></td>
                    <td><ProctorStatusBadge kind="readiness" value={item.latest_health_status} /></td>
                    <td>{formatDateTime(item.last_seen_at)}</td>
                    <td>{formatDateTime(item.started_at)}</td>
                    <td>{formatDateTime(item.submitted_at ?? item.sealed_at)}</td>
                    <td>
                      {Number.isInteger(item.student_id) && item.student_id > 0 ? (
                        <button type="button" className="secondary-button" onClick={() => setSelectedCandidate(item)}>
                          Thu hồi đăng nhập bị kẹt
                        </button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        </CompactSurface>
      ) : null}

      <RevokeStaleSessionDialog
        isOpen={selectedCandidate !== null}
        examSittingRoomId={examSittingRoomId}
        studentId={selectedCandidate?.student_id ?? null}
        studentCode={selectedCandidate?.student_code ?? '-'}
        studentName={selectedCandidate?.full_name ?? '-'}
        onClose={() => setSelectedCandidate(null)}
        onCompleted={async () => {
          await loadRoster('refresh');
        }}
      />
    </CompactPage>
  );
}

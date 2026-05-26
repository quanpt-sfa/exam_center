import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { CompactPage } from '../../shared/components/compact/CompactPage';
import { CompactPageHeader } from '../../shared/components/compact/CompactPageHeader';
import { CompactStatBar } from '../../shared/components/compact/CompactStatBar';
import { CompactSurface } from '../../shared/components/compact/CompactSurface';
import { CompactToolbar } from '../../shared/components/compact/CompactToolbar';
import { getProctorRoomReadiness, getProctorRoomRoster } from './api/proctorApi';
import type { ProctorRoomReadinessResponse, ProctorRoomRosterResponse } from './api/contracts';
import { ProctorEmptyState } from './components/ProctorEmptyState';
import { ProctorErrorState } from './components/ProctorErrorState';
import { ProctorInvalidRoomState } from './components/ProctorInvalidRoomState';
import { ProctorLoadingState } from './components/ProctorLoadingState';
import { ProctorStatusBadge } from './components/ProctorStatusBadge';
import { deriveReadinessSummary, deriveRosterSummary } from './proctorDisplay';
import { resolveExamSittingRoomId } from './proctorRoute';

export function ProctorRoomWorkspacePage() {
  const params = useParams<{ examSittingRoomId: string }>();
  const routeExamSittingRoomId = params.examSittingRoomId;
  const roomIdResolution = resolveExamSittingRoomId(routeExamSittingRoomId);
  const examSittingRoomId = roomIdResolution.isValid ? roomIdResolution.examSittingRoomId : null;
  const [roster, setRoster] = useState<ProctorRoomRosterResponse | null>(null);
  const [readiness, setReadiness] = useState<ProctorRoomReadinessResponse | null>(null);
  const [rosterLoading, setRosterLoading] = useState(true);
  const [readinessLoading, setReadinessLoading] = useState(true);
  const [rosterError, setRosterError] = useState<string | null>(null);
  const [readinessError, setReadinessError] = useState<string | null>(null);

  async function loadWorkspace() {
    setRosterLoading(true);
    setReadinessLoading(true);
    setRosterError(null);
    setReadinessError(null);

    const [rosterResult, readinessResult] = await Promise.allSettled([
      getProctorRoomRoster(examSittingRoomId),
      getProctorRoomReadiness(examSittingRoomId),
    ]);

    if (rosterResult.status === 'fulfilled') {
      setRoster(rosterResult.value);
    } else {
      setRoster(null);
      setRosterError(rosterResult.reason instanceof Error ? rosterResult.reason.message : 'Không tải được roster phòng thi.');
    }
    setRosterLoading(false);

    if (readinessResult.status === 'fulfilled') {
      setReadiness(readinessResult.value);
    } else {
      setReadiness(null);
      setReadinessError(readinessResult.reason instanceof Error ? readinessResult.reason.message : 'Không tải được readiness phòng thi.');
    }
    setReadinessLoading(false);
  }

  useEffect(() => {
    if (!roomIdResolution.isValid || examSittingRoomId === null) {
      setRosterLoading(false);
      setReadinessLoading(false);
      setRosterError(roomIdResolution.errorMessage);
      setReadinessError(roomIdResolution.errorMessage);
      return;
    }
    void loadWorkspace();
  }, [examSittingRoomId, routeExamSittingRoomId]);

  if (!roomIdResolution.isValid || examSittingRoomId === null) {
    return (
      <CompactPage data-testid="proctor-room-workspace-page">
        <ProctorInvalidRoomState message={roomIdResolution.errorMessage} />
      </CompactPage>
    );
  }

  const summary = deriveRosterSummary(roster?.items ?? []);
  const readinessSummary = deriveReadinessSummary(readiness?.items ?? []);
  const roomCode = roster?.room_code ?? readiness?.room_code ?? `#${examSittingRoomId}`;

  return (
    <CompactPage data-testid="proctor-room-workspace-page">
      <CompactPageHeader
        eyebrow="Proctor Portal"
        title={`Không gian phòng thi ${roomCode}`}
        description="Tổng hợp roster, readiness và các thao tác vận hành phòng thi theo dữ liệu backend."
        secondaryActions={
          <Link className="secondary-button" to="/proctor/sittings">
            Tất cả phòng
          </Link>
        }
        primaryActions={
          <button type="button" className="secondary-button" onClick={() => void loadWorkspace()} disabled={rosterLoading || readinessLoading}>
            {rosterLoading || readinessLoading ? 'Đang tải...' : 'Làm mới thủ công'}
          </button>
        }
      />

      <CompactToolbar>
        <span className="muted">Room: {roomCode}</span>
        <span className="muted">Roster: {summary.total}</span>
        <span className="muted">Readiness devices: {readinessSummary.total}</span>
        <span className="muted">Need-check: {readinessSummary.warning + readinessSummary.error}</span>
      </CompactToolbar>

      <CompactStatBar
        items={[
          { label: 'Đang thi', value: summary.in_progress },
          { label: 'Đã nộp/niêm phong', value: summary.submitted },
          { label: 'Gián đoạn', value: summary.interrupted },
          { label: 'Ready devices', value: readinessSummary.ready },
        ]}
      />

      <CompactSurface
        tight
        title="Luồng thao tác"
        description="Đi theo thứ tự Attendance → Live → Incidents → Close Room."
      >
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--gap-sm)' }}>
          <Link className="secondary-button" to={`/proctor/sitting-rooms/${examSittingRoomId}/attendance`}>
            Danh sách thí sinh
          </Link>
          <Link className="secondary-button" to={`/proctor/sitting-rooms/${examSittingRoomId}/live`}>
            Theo dõi phòng thi
          </Link>
          <Link className="secondary-button" to={`/proctor/sitting-rooms/${examSittingRoomId}/incidents`}>
            Sự cố phòng thi
          </Link>
          <Link className="secondary-button" to={`/proctor/sitting-rooms/${examSittingRoomId}/close`}>
            Close Room
          </Link>
        </div>
      </CompactSurface>

      <CompactSurface tight title="Tổng quan thí sinh" description="Roster thật từ backend.">
        {rosterLoading ? <ProctorLoadingState message="Đang tải roster phòng thi..." /> : null}
        {!rosterLoading && rosterError ? <ProctorErrorState title="Không tải được roster" message={rosterError} onRetry={() => void loadWorkspace()} /> : null}

        {!rosterLoading && !rosterError ? (
          <CompactStatBar
            items={[
              { label: 'Tổng thí sinh', value: summary.total },
              { label: 'Đang thi', value: summary.in_progress },
              { label: 'Đã nộp / niêm phong', value: summary.submitted },
              { label: 'Gián đoạn', value: summary.interrupted },
            ]}
          />
        ) : null}

        {!rosterLoading && !rosterError && roster && roster.items.length > 0 ? (
          <div className="table-shell" style={{ marginTop: 'var(--gap-sm)' }}>
            <div className="table-scroll">
              <table className="table table-compact">
                <thead>
                  <tr>
                    <th>Mã SV</th>
                    <th>Họ tên</th>
                    <th>Máy</th>
                    <th>Phiên thi</th>
                    <th>Bài nộp</th>
                  </tr>
                </thead>
                <tbody>
                  {roster.items.slice(0, 8).map((item) => (
                    <tr key={`${item.student_id}-${item.station_id}`}>
                      <td>{item.student_code}</td>
                      <td>{item.full_name}</td>
                      <td>{item.station_code}</td>
                      <td><ProctorStatusBadge kind="session" value={item.session_status} /></td>
                      <td><ProctorStatusBadge kind="submission" value={item.submission_status} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : null}

        {!rosterLoading && !rosterError && roster && roster.items.length === 0 ? (
          <ProctorEmptyState icon="🪑" message="Roster phòng thi hiện đang trống." />
        ) : null}
      </CompactSurface>

      <CompactSurface tight title="Tình trạng readiness" description="Readiness thật theo payload backend.">
        {readinessLoading ? <ProctorLoadingState message="Đang tải readiness phòng thi..." /> : null}
        {!readinessLoading && readinessError ? <ProctorErrorState title="Không tải được readiness" message={readinessError} onRetry={() => void loadWorkspace()} /> : null}

        {!readinessLoading && !readinessError ? (
          <CompactStatBar
            items={[
              { label: 'Tổng máy', value: readinessSummary.total },
              { label: 'Sẵn sàng', value: readinessSummary.ready },
              { label: 'Cần kiểm tra', value: readinessSummary.warning + readinessSummary.error },
              { label: 'Lệch vị trí', value: readinessSummary.mismatch },
            ]}
          />
        ) : null}

        {!readinessLoading && !readinessError && readiness && readiness.items.length > 0 ? (
          <div className="table-shell" style={{ marginTop: 'var(--gap-sm)' }}>
            <div className="table-scroll">
              <table className="table table-compact">
                <thead>
                  <tr>
                    <th>Máy</th>
                    <th>Thiết bị</th>
                    <th>Trạng thái máy</th>
                    <th>Lệch vị trí</th>
                  </tr>
                </thead>
                <tbody>
                  {readiness.items.map((item) => (
                    <tr key={`${item.station_code ?? 'unknown'}-${item.asset_tag ?? 'no-asset'}`}>
                      <td>{item.station_code ?? '-'}</td>
                      <td>{item.asset_tag ?? '-'}</td>
                      <td><ProctorStatusBadge kind="readiness" value={item.health_status} /></td>
                      <td>{item.mismatch ? 'Có' : 'Không'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : null}

        {!readinessLoading && !readinessError && readiness && readiness.items.length === 0 ? (
          <ProctorEmptyState icon="🖥" message="Chưa có dữ liệu readiness cho phòng thi này." />
        ) : null}
      </CompactSurface>
    </CompactPage>
  );
}

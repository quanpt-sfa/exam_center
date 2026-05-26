import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { CompactPage } from '../../shared/components/compact/CompactPage';
import { CompactPageHeader } from '../../shared/components/compact/CompactPageHeader';
import { CompactStatBar } from '../../shared/components/compact/CompactStatBar';
import { CompactSurface } from '../../shared/components/compact/CompactSurface';
import { listMySittingRooms } from './api/proctorApi';
import type { ProctorAssignedRoom } from './api/contracts';
import { ProctorEmptyState } from './components/ProctorEmptyState';
import { ProctorErrorState } from './components/ProctorErrorState';
import { ProctorLoadingState } from './components/ProctorLoadingState';
import { ProctorStatusBadge } from './components/ProctorStatusBadge';
import { formatDateTime } from './proctorDisplay';

export function ProctorSittingsPage() {
  const [rooms, setRooms] = useState<ProctorAssignedRoom[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function loadRooms() {
    setLoading(true);
    setError(null);
    try {
      setRooms(await listMySittingRooms());
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Không tải được danh sách phòng được phân công.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadRooms();
  }, []);

  return (
    <CompactPage data-testid="proctor-sittings-page">
      <CompactPageHeader
        eyebrow="Proctor Portal"
        title="Ca thi được phân công"
        description="Danh sách này chỉ dùng dữ liệu thật từ backend cho các phòng thi được giao cho tài khoản hiện tại."
        primaryActions={
          <button type="button" className="secondary-button" onClick={() => void loadRooms()} disabled={loading}>
            {loading ? 'Đang tải...' : 'Tải lại'}
          </button>
        }
      />

      {error ? (
        <ProctorErrorState title="Không tải được danh sách phòng" message={error} onRetry={() => void loadRooms()} />
      ) : null}

      {loading ? <ProctorLoadingState message="Đang tải danh sách phòng được phân công..." /> : null}

      {!loading && !error && rooms.length === 0 ? (
        <ProctorEmptyState icon="🧑" message="Hiện chưa có phòng thi nào được phân công cho tài khoản này." actionLabel="Tải lại" onAction={() => void loadRooms()} />
      ) : null}

      {!loading && !error && rooms.length > 0 ? (
        <div style={{ display: 'grid', gap: 'var(--gap-sm)' }}>
          {rooms.map((room) => (
            <CompactSurface
              key={room.exam_sitting_room_id}
              title={`${room.room_code} - ${room.sitting_code}`}
              description={`${room.sitting_name}${room.room_name ? ` · ${room.room_name}` : ''}`}
              actions={
                <div style={{ display: 'flex', gap: 'var(--gap-xs)', alignItems: 'center', flexWrap: 'wrap' }}>
                  <ProctorStatusBadge kind="raw" value={room.sitting_status} />
                  <ProctorStatusBadge kind="raw" value={room.room_status} />
                </div>
              }
            >
              <p className="muted" style={{ marginTop: 0 }}>
                {formatDateTime(room.scheduled_start_at)} - {formatDateTime(room.scheduled_end_at)}
              </p>
              <CompactStatBar
                items={[
                  { label: 'Sinh viên', value: room.assigned_student_count },
                  { label: 'Máy đã gán', value: room.assigned_station_count },
                  { label: 'Sức chứa', value: room.capacity_allocated ?? '-' },
                ]}
              />
              <div style={{ display: 'flex', gap: 'var(--gap-sm)', flexWrap: 'wrap', marginTop: 'var(--gap-sm)' }}>
                <Link className="primary-button" to={`/proctor/sitting-rooms/${room.exam_sitting_room_id}`}>
                  Mở không gian phòng thi
                </Link>
                <Link className="secondary-button" to={`/proctor/sitting-rooms/${room.exam_sitting_room_id}/attendance`}>
                  Danh sách thí sinh
                </Link>
                <Link className="secondary-button" to={`/proctor/sitting-rooms/${room.exam_sitting_room_id}/live`}>
                  Theo dõi phòng thi
                </Link>
                <Link className="secondary-button" to={`/proctor/sitting-rooms/${room.exam_sitting_room_id}/incidents`}>
                  Sự cố phòng thi
                </Link>
              </div>
            </CompactSurface>
          ))}
        </div>
      ) : null}
    </CompactPage>
  );
}

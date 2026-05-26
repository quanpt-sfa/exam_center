import { CompactSurface } from '../../../shared/components/compact/CompactSurface';
import type { MasterDataRow } from '../masterDataApi';

export function EntityFilters({
  selectedRoomId,
  rooms,
  onRoomChange,
}: {
  selectedRoomId: number | null;
  rooms: MasterDataRow[];
  onRoomChange: (roomId: number | null) => void;
}) {
  return (
    <CompactSurface className="master-data-filter-surface" tight>
      <label htmlFor="facility-room-selector">
        Phòng thi / phòng máy
        <select
          id="facility-room-selector"
          value={selectedRoomId ?? ''}
          onChange={(event) => onRoomChange(event.target.value ? Number(event.target.value) : null)}
        >
          <option value="">Chọn phòng</option>
          {rooms.map((room) => (
            <option key={String(room.room_id)} value={String(room.room_id)}>
              {String(room.room_code)} - {String(room.room_name)}
            </option>
          ))}
        </select>
      </label>
    </CompactSurface>
  );
}

import type { ReactNode } from 'react';
import { CompactSurface } from '../../../shared/components/compact/CompactSurface';
import { CompactToolbar } from '../../../shared/components/compact/CompactToolbar';
import { useLocale } from '../../../app/locale';
import type { MasterDataRow } from '../masterDataApi';
import type { EntityFieldConfig, MasterDataEntityKey } from '../types';
import { resolveDisplayLabel } from '../utils/displayLabel';
import { resolveMasterDataFieldLayout } from '../utils/fieldLayout';
import { EntityFilters } from './EntityFilters';

function FacilityFormField({
  field,
  fieldId,
  locale,
  children,
}: {
  field: EntityFieldConfig;
  fieldId: string;
  locale: 'vi' | 'en';
  children: (controlClassName: string) => ReactNode;
}) {
  const layout = resolveMasterDataFieldLayout(field, field.name);
  const displayLabel = resolveDisplayLabel(field.label, locale) || field.name;
  const controlClassName = `master-data-control master-data-control--${layout.fieldSize}`;

  return (
    <div className={layout.className} {...layout.dataAttributes}>
      <label htmlFor={fieldId}>{displayLabel}</label>
      {children(controlClassName)}
    </div>
  );
}

export function FacilityPanel({
  activeKey,
  selectedRoomId,
  roomItems,
  bulkPattern,
  bulkRows,
  bulkStart,
  bulkEnd,
  bulkZeroPad,
  bulkPreview,
  deviceAssignDeviceId,
  deviceAssignStationId,
  retireDeviceId,
  onRoomChange,
  onBulkPatternChange,
  onBulkRowsChange,
  onBulkStartChange,
  onBulkEndChange,
  onBulkZeroPadChange,
  onBulkGenerateStations,
  bulkGenerating,
  onDeviceAssignDeviceIdChange,
  onDeviceAssignStationIdChange,
  onAssignDeviceToStation,
  assigningDevice,
  onRetireDeviceIdChange,
  onRetireDevice,
  retiringDevice,
}: {
  activeKey: MasterDataEntityKey;
  selectedRoomId: number | null;
  roomItems: MasterDataRow[];
  bulkPattern: 'grid' | 'numeric';
  bulkRows: string;
  bulkStart: string;
  bulkEnd: string;
  bulkZeroPad: string;
  bulkPreview: string;
  deviceAssignDeviceId: string;
  deviceAssignStationId: string;
  retireDeviceId: string;
  onRoomChange: (roomId: number | null) => void;
  onBulkPatternChange: (value: 'grid' | 'numeric') => void;
  onBulkRowsChange: (value: string) => void;
  onBulkStartChange: (value: string) => void;
  onBulkEndChange: (value: string) => void;
  onBulkZeroPadChange: (value: string) => void;
  onBulkGenerateStations: () => void;
  bulkGenerating: boolean;
  onDeviceAssignDeviceIdChange: (value: string) => void;
  onDeviceAssignStationIdChange: (value: string) => void;
  onAssignDeviceToStation: () => void;
  assigningDevice: boolean;
  onRetireDeviceIdChange: (value: string) => void;
  onRetireDevice: () => void;
  retiringDevice: boolean;
}) {
  const { locale } = useLocale();
  const showRoomFilter = activeKey === 'stations' || activeKey === 'device-readiness';
  const bulkPatternId = 'facility-bulk-pattern';
  const bulkRowsId = 'facility-bulk-rows';
  const bulkStartId = 'facility-bulk-start';
  const bulkEndId = 'facility-bulk-end';
  const bulkZeroPadId = 'facility-bulk-zero-pad';

  const assignDeviceId = 'facility-assign-device-id';
  const assignStationId = 'facility-assign-station-id';
  const retireDeviceIdField = 'facility-retire-device-id';

  return (
    <>
      {showRoomFilter ? <EntityFilters selectedRoomId={selectedRoomId} rooms={roomItems} onRoomChange={onRoomChange} /> : null}

      {activeKey === 'stations' ? (
        <CompactSurface
          className="facility-action-surface"
          title="Tạo nhanh vị trí máy"
          description="Sinh nhanh station code theo dải số hoặc dạng lưới để giữ workflow vận hành gọn trên một hàng thao tác."
          tight
        >
          <div className="master-data-form master-data-form--compact facility-action-form" data-form-context="stations-bulk">
            <FacilityFormField field={{ name: 'station_bulk_pattern', label: 'Dạng tạo', fieldKind: 'select', fieldSize: 'sm', type: 'select' }} fieldId={bulkPatternId} locale={locale}>
              {(controlClassName) => (
                <select id={bulkPatternId} className={controlClassName} value={bulkPattern} onChange={(event) => onBulkPatternChange(event.target.value as 'grid' | 'numeric')}>
                  <option value="grid">Dạng dãy chữ-số</option>
                  <option value="numeric">Dạng số thứ tự</option>
                </select>
              )}
            </FacilityFormField>
            {bulkPattern === 'grid' ? (
              <FacilityFormField field={{ name: 'station_bulk_rows', label: 'Nhãn hàng', fieldKind: 'shortName', fieldSize: 'md' }} fieldId={bulkRowsId} locale={locale}>
                {(controlClassName) => <input id={bulkRowsId} className={controlClassName} value={bulkRows} onChange={(event) => onBulkRowsChange(event.target.value)} placeholder="A,B,C" />}
              </FacilityFormField>
            ) : null}
            <FacilityFormField field={{ name: 'station_bulk_start', label: 'Số bắt đầu', fieldKind: 'numeric', fieldSize: 'xs', type: 'number' }} fieldId={bulkStartId} locale={locale}>
              {(controlClassName) => <input id={bulkStartId} className={controlClassName} type="number" value={bulkStart} onChange={(event) => onBulkStartChange(event.target.value)} />}
            </FacilityFormField>
            <FacilityFormField field={{ name: 'station_bulk_end', label: 'Số kết thúc', fieldKind: 'numeric', fieldSize: 'xs', type: 'number' }} fieldId={bulkEndId} locale={locale}>
              {(controlClassName) => <input id={bulkEndId} className={controlClassName} type="number" value={bulkEnd} onChange={(event) => onBulkEndChange(event.target.value)} />}
            </FacilityFormField>
            <FacilityFormField field={{ name: 'station_bulk_zero_pad', label: 'Zero pad', fieldKind: 'numeric', fieldSize: 'xs', type: 'number' }} fieldId={bulkZeroPadId} locale={locale}>
              {(controlClassName) => <input id={bulkZeroPadId} className={controlClassName} type="number" value={bulkZeroPad} onChange={(event) => onBulkZeroPadChange(event.target.value)} />}
            </FacilityFormField>
            <div className="master-data-field field-span-full facility-inline-meta" data-field-kind="note" data-field-size="full" data-grid-span={12}>
              <span className="muted">Xem trước: {bulkPreview}</span>
            </div>
            <div className="master-data-field field-span-full master-data-form-actions facility-action-submit" data-field-kind="status" data-field-size="full" data-grid-span={12}>
              <button type="button" className="primary-button compact-button" onClick={onBulkGenerateStations} disabled={bulkGenerating} aria-busy={bulkGenerating}>
                {bulkGenerating ? 'Đang tạo...' : 'Tạo vị trí'}
              </button>
            </div>
          </div>
        </CompactSurface>
      ) : null}

      {activeKey === 'devices' ? (
        <CompactSurface className="facility-action-surface" title="Thao tác thiết bị" tight>
          <div className="master-data-form master-data-form--compact facility-action-form" data-form-context="device-actions">
            <FacilityFormField field={{ name: 'deviceAssignDeviceId', label: 'ID thiết bị', fieldKind: 'id', fieldSize: 'sm', inputMode: 'numeric' }} fieldId={assignDeviceId} locale={locale}>
              {(controlClassName) => <input id={assignDeviceId} className={controlClassName} value={deviceAssignDeviceId} inputMode="numeric" onChange={(event) => onDeviceAssignDeviceIdChange(event.target.value)} />}
            </FacilityFormField>
            <FacilityFormField field={{ name: 'deviceAssignStationId', label: 'ID vị trí máy', fieldKind: 'id', fieldSize: 'sm', inputMode: 'numeric' }} fieldId={assignStationId} locale={locale}>
              {(controlClassName) => <input id={assignStationId} className={controlClassName} value={deviceAssignStationId} inputMode="numeric" onChange={(event) => onDeviceAssignStationIdChange(event.target.value)} />}
            </FacilityFormField>
            <CompactToolbar className="master-data-field field-span-sm facility-inline-toolbar" data-field-kind="status" data-field-size="sm" data-grid-span={3}>
              <button type="button" className="secondary-button compact-button" onClick={onAssignDeviceToStation} disabled={assigningDevice} aria-busy={assigningDevice}>
                {assigningDevice ? 'Đang gán...' : 'Gán vào vị trí'}
              </button>
            </CompactToolbar>
            <FacilityFormField field={{ name: 'retireDeviceId', label: 'ID thiết bị ngừng sử dụng', fieldKind: 'id', fieldSize: 'sm', inputMode: 'numeric' }} fieldId={retireDeviceIdField} locale={locale}>
              {(controlClassName) => <input id={retireDeviceIdField} className={controlClassName} value={retireDeviceId} inputMode="numeric" onChange={(event) => onRetireDeviceIdChange(event.target.value)} />}
            </FacilityFormField>
            <div className="master-data-field field-span-sm facility-inline-placeholder" aria-hidden="true" data-field-kind="status" data-field-size="sm" data-grid-span={3} />
            <CompactToolbar className="master-data-field field-span-sm facility-inline-toolbar" data-field-kind="status" data-field-size="sm" data-grid-span={3}>
              <button type="button" className="secondary-button compact-button" onClick={onRetireDevice} disabled={retiringDevice} aria-busy={retiringDevice}>
                {retiringDevice ? 'Đang ngừng sử dụng...' : 'Ngừng sử dụng'}
              </button>
            </CompactToolbar>
          </div>
        </CompactSurface>
      ) : null}
    </>
  );
}

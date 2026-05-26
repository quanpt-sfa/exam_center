import { type FormEvent, useEffect, useMemo, useRef, useState } from 'react';
import {
  assignDeviceToStation,
  buildBulkGenerateStationsPayload,
  bulkGenerateStations,
  retireDevice,
} from '../../facility/facilityApi';
import type { MasterDataRow } from '../api/contracts';
import { findMasterDataEntity, masterDataEntities } from '../registry/masterDataEntities';
import type { EntityConfig, EntityFieldConfig, EntityFormErrors, EntityListParams, EntityState, LookupFieldState, MasterDataEntityKey } from '../types';
import { buildFormFromRow, buildInitialForm } from '../utils/payload';
import { courseOptionLabel, departmentOptionLabel, programOptionLabel } from '../utils/formatters';
import { hasValidBulkRange, parseNumericId, validateEntityForm } from '../utils/validation';
import { ConfirmationDialog } from './ConfirmationDialog';
import { EntityCreatePanel } from './EntityCreatePanel';
import { EntityListPanel } from './EntityListPanel';
import { EntityNavigation } from './EntityNavigation';
import { FacilityPanel } from './FacilityPanel';

function buildDefaultListParams(config: EntityConfig): EntityListParams {
  return {
    page: 1,
    page_size: config.listFeatures.defaultPageSize,
    query: '',
    status: '',
  };
}

function getRowEntityId(config: EntityConfig, row: MasterDataRow): number | null {
  const rawValue = row[config.primaryKey];
  const entityId = Number(rawValue);
  return Number.isFinite(entityId) ? entityId : null;
}

function getRowDisplayLabel(config: EntityConfig, row: MasterDataRow): string | null {
  const candidateKeys = [
    config.primaryKey,
    'department_name',
    'department_code',
    'course_name',
    'course_code',
    'class_name',
    'class_code',
    'full_name',
    'student_code',
    'instructor_code',
    'type_name',
    'room_name',
    'room_code',
    'station_code',
    'device_name',
    'asset_tag',
  ];

  const values = candidateKeys
    .map((key) => row[key])
    .filter((value, index, allValues) => value != null && String(value).trim() !== '' && allValues.indexOf(value) === index)
    .slice(0, 2)
    .map((value) => String(value).trim());

  return values.length > 0 ? values.join(' - ') : null;
}

export function MasterDataShell({
  entities,
  activeKey,
  onActiveKeyChange,
}: {
  entities: EntityConfig[];
  activeKey: MasterDataEntityKey;
  onActiveKeyChange: (key: MasterDataEntityKey) => void;
}) {
  const availableKeys = useMemo(() => new Set(entities.map((entity) => entity.key)), [entities]);
  const activeConfig = useMemo(() => {
    if (availableKeys.has(activeKey)) {
      return findMasterDataEntity(activeKey);
    }
    return entities[0];
  }, [activeKey, availableKeys, entities]);
  const hydratedEntities = useMemo(() => {
    const requiredKeys = new Set(entities.map((entity) => entity.key));
    for (const entity of entities) {
      for (const field of entity.fields) {
        if (field.lookup === 'departments') requiredKeys.add('departments');
        if (field.lookup === 'programs') requiredKeys.add('programs');
        if (field.lookup === 'courses') requiredKeys.add('courses');
      }
      if (entity.key === 'stations' || entity.key === 'device-readiness') {
        requiredKeys.add('rooms');
      }
    }
    return masterDataEntities.filter((entity) => requiredKeys.has(entity.key));
  }, [entities]);
  const [formByEntity, setFormByEntity] = useState<Record<string, Record<string, string>>>(() =>
    Object.fromEntries(hydratedEntities.map((config) => [config.key, buildInitialForm(config)]))
  );
  const [stateByEntity, setStateByEntity] = useState<Record<string, EntityState>>(() =>
    Object.fromEntries(
      hydratedEntities.map((config) => [
        config.key,
        { rows: [], pagination: undefined, loading: Boolean(config.api.list), error: null, submitting: false, message: null },
      ])
    )
  );
  const [listParamsByEntity, setListParamsByEntity] = useState<Record<string, EntityListParams>>(() =>
    Object.fromEntries(hydratedEntities.map((config) => [config.key, buildDefaultListParams(config)]))
  );
  const [uiErrorByEntity, setUiErrorByEntity] = useState<Record<string, string | null>>(() =>
    Object.fromEntries(hydratedEntities.map((config) => [config.key, null]))
  );
  const [formErrors, setFormErrors] = useState<EntityFormErrors>({});
  const [editingEntityId, setEditingEntityId] = useState<number | null>(null);
  const [selectedRoomId, setSelectedRoomId] = useState<number | null>(null);
  const [bulkPattern, setBulkPattern] = useState<'grid' | 'numeric'>('grid');
  const [bulkRows, setBulkRows] = useState('A,B,C');
  const [bulkStart, setBulkStart] = useState('1');
  const [bulkEnd, setBulkEnd] = useState('6');
  const [bulkZeroPad, setBulkZeroPad] = useState('0');
  const [deviceAssignDeviceId, setDeviceAssignDeviceId] = useState('');
  const [deviceAssignStationId, setDeviceAssignStationId] = useState('');
  const [retireDeviceId, setRetireDeviceId] = useState('');
  const [bulkGenerating, setBulkGenerating] = useState(false);
  const [assigningDevice, setAssigningDevice] = useState(false);
  const [retiringDevice, setRetiringDevice] = useState(false);
  const [pendingDeactivateId, setPendingDeactivateId] = useState<number | null>(null);
  const [confirmDialogState, setConfirmDialogState] = useState<{ entityId: number; row: MasterDataRow; label: string | null } | null>(null);
  const [confirmDialogError, setConfirmDialogError] = useState<string | null>(null);
  const submitInFlightRef = useRef(false);
  const deactivateInFlightRef = useRef<number | null>(null);
  const bulkInFlightRef = useRef(false);
  const assignInFlightRef = useRef(false);
  const retireInFlightRef = useRef(false);

  const entityState = stateByEntity[activeConfig.key];
  const form = formByEntity[activeConfig.key];
  const listParams = listParamsByEntity[activeConfig.key] ?? buildDefaultListParams(activeConfig);
  const roomItems = stateByEntity.rooms?.rows ?? [];
  const isEditMode = editingEntityId !== null;
  const activeRoomContext = activeConfig.key === 'stations' || activeConfig.key === 'device-readiness' ? selectedRoomId : null;

  function missingContextError(config: EntityConfig, action: 'load' | 'create'): string {
    if (config.key === 'device-readiness') {
      return 'Vui lòng chọn phòng để xem tình trạng thiết bị.';
    }
    if (config.key === 'stations' && action === 'create') {
      return 'Vui lòng chọn phòng trước khi tạo vị trí máy.';
    }
    if (config.key === 'stations') {
      return 'Vui lòng chọn phòng trước khi tải vị trí máy.';
    }
    return 'Thiếu ngữ cảnh để tải dữ liệu.';
  }

  async function loadEntity(config: EntityConfig, paramsOverride?: EntityListParams) {
    if (!config.api.list) {
      setStateByEntity((current) => ({
        ...current,
        [config.key]: { ...current[config.key], rows: [], pagination: undefined, loading: false, error: null },
      }));
      return;
    }

    setStateByEntity((current) => ({
      ...current,
      [config.key]: { ...current[config.key], loading: true, error: null },
    }));

    const params = paramsOverride ?? listParamsByEntity[config.key] ?? buildDefaultListParams(config);
    const response = await config.api.list({ selectedRoomId, params });

    if (response === null) {
      setStateByEntity((current) => ({
        ...current,
        [config.key]: {
          ...current[config.key],
          rows: [],
          pagination: undefined,
          loading: false,
          error: missingContextError(config, 'load'),
        },
      }));
      return;
    }

    setStateByEntity((current) => ({
      ...current,
      [config.key]: response.ok
        ? {
            ...current[config.key],
            rows: response.data.items,
            pagination: response.data.pagination,
            loading: false,
            error: null,
          }
        : { ...current[config.key], rows: [], pagination: undefined, loading: false, error: response.error.message },
    }));

    if (config.key === 'rooms' && response.ok && !selectedRoomId) {
      const firstRoom = response.data.items.find((item) => item.room_id != null);
      if (firstRoom?.room_id != null) {
        setSelectedRoomId(Number(firstRoom.room_id));
      }
    }
  }

  useEffect(() => {
    void loadEntity(activeConfig);
  }, [activeConfig, activeRoomContext, listParams.page, listParams.page_size, listParams.query, listParams.status]);

  useEffect(() => {
    const preloadKeys = ['departments', 'programs', 'rooms', 'courses'] as const;
    for (const key of preloadKeys) {
      const config = hydratedEntities.find((entity) => entity.key === key);
      if (config) {
        void loadEntity(config);
      }
    }
  }, [hydratedEntities]);

  useEffect(() => {
    setEditingEntityId(null);
    setFormErrors({});
    submitInFlightRef.current = false;
    deactivateInFlightRef.current = null;
    setPendingDeactivateId(null);
    setConfirmDialogState(null);
    setConfirmDialogError(null);
    setUiErrorByEntity((current) => ({ ...current, [activeConfig.key]: null }));
    setListParamsByEntity((current) => ({
      ...current,
      [activeConfig.key]: buildDefaultListParams(activeConfig),
    }));
    setFormByEntity((current) => ({
      ...current,
      [activeConfig.key]: buildInitialForm(activeConfig),
    }));
  }, [activeConfig]);

  useEffect(() => {
    if (selectedRoomId) {
      return;
    }
    const firstRoomId = roomItems.find((row) => row.room_id != null)?.room_id;
    if (firstRoomId != null) {
      setSelectedRoomId(Number(firstRoomId));
    }
  }, [roomItems, selectedRoomId]);

  const bulkPreview = useMemo(() => {
    const start = Number(bulkStart);
    const end = Number(bulkEnd);
    const zeroPad = Number(bulkZeroPad || '0');
    if (!Number.isFinite(start) || !Number.isFinite(end) || end < start) {
      return '';
    }
    const numbers = Array.from({ length: end - start + 1 }, (_, idx) => {
      const value = start + idx;
      return zeroPad > 0 ? String(value).padStart(zeroPad, '0') : String(value);
    });
    if (bulkPattern === 'numeric') {
      return numbers.slice(0, 12).join(', ');
    }
    const labels = bulkRows
      .split(',')
      .map((item) => item.trim().toUpperCase())
      .filter(Boolean);
    const preview: string[] = [];
    for (const label of labels) {
      for (const number of numbers) {
        preview.push(`${label}${number}`);
        if (preview.length >= 12) {
          return preview.join(', ');
        }
      }
    }
    return preview.join(', ');
  }, [bulkPattern, bulkRows, bulkStart, bulkEnd, bulkZeroPad]);

  function updateFormValue(fieldName: string, value: string) {
    setFormByEntity((current) => {
      const nextForm = {
        ...current[activeConfig.key],
        [fieldName]: value,
      };

      if (Object.keys(formErrors).length > 0) {
        setFormErrors(validateEntityForm(activeConfig.fields, nextForm, getOptionsForField));
      }

      return {
        ...current,
        [activeConfig.key]: nextForm,
      };
    });
  }

  function updateListParams(partial: Partial<EntityListParams>) {
    setListParamsByEntity((current) => {
      const currentParams = current[activeConfig.key] ?? buildDefaultListParams(activeConfig);
      return {
        ...current,
        [activeConfig.key]: {
          ...currentParams,
          ...partial,
        },
      };
    });
  }

  function startEdit(row: MasterDataRow) {
    const entityId = getRowEntityId(activeConfig, row);
    if (entityId === null) {
      return;
    }
    setEditingEntityId(entityId);
    setFormErrors({});
    setFormByEntity((current) => ({
      ...current,
      [activeConfig.key]: buildFormFromRow(activeConfig, row),
    }));
  }

  function cancelEdit() {
    setEditingEntityId(null);
    setFormErrors({});
    setFormByEntity((current) => ({
      ...current,
      [activeConfig.key]: buildInitialForm(activeConfig),
    }));
  }

  function getOptionsForField(field: EntityFieldConfig): Array<{ label: string; value: string }> {
    if (field.lookup === 'departments') {
      return stateByEntity.departments?.rows
        .filter((row) => row.department_id != null)
        .map((row) => ({ value: String(row.department_id), label: departmentOptionLabel(row) })) ?? [];
    }

    if (field.lookup === 'programs') {
      return stateByEntity.programs?.rows
        .filter((row) => row.program_id != null)
        .map((row) => ({ value: String(row.program_id), label: programOptionLabel(row) })) ?? [];
    }

    if (field.lookup === 'courses') {
      return stateByEntity.courses?.rows
        .filter((row) => row.course_id != null)
        .map((row) => ({ value: String(row.course_id), label: courseOptionLabel(row) })) ?? [];
    }

    return field.options ?? [];
  }

  function getLookupState(field: EntityFieldConfig): LookupFieldState {
    if (!field.lookup || field.type !== 'select') {
      return {
        disabled: false,
        loading: false,
        error: null,
        allowManualFallback: false,
        showManualFallback: false,
      };
    }

    const lookupEntityState = stateByEntity[field.lookup];
    const hasOptions = getOptionsForField(field).length > 0;
    const allowManualFallback = field.allowManualLookupFallback === true;
    const loading = Boolean(lookupEntityState?.loading && !hasOptions);
    const error = lookupEntityState?.error ?? null;
    const showManualFallback = Boolean(error && allowManualFallback);

    return {
      disabled: loading || Boolean(error && !allowManualFallback),
      loading,
      error: error ? (allowManualFallback ? 'Không tải được danh mục. Có thể nhập ID thủ công.' : 'Không tải được danh mục. Hãy thử tải lại.') : null,
      allowManualFallback,
      showManualFallback,
    };
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitInFlightRef.current || entityState.submitting) {
      return;
    }

    const nextErrors = validateEntityForm(activeConfig.fields, formByEntity[activeConfig.key], getOptionsForField);
    setFormErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0 || activeConfig.capabilities.readOnly) {
      return;
    }

    const entityKey = activeConfig.key;
    const context = { selectedRoomId, params: listParams };
    const wasEditing = editingEntityId !== null;
    setStateByEntity((current) => ({
      ...current,
      [entityKey]: { ...current[entityKey], submitting: true, error: null, message: null },
    }));
    submitInFlightRef.current = true;

    try {
      const response =
        editingEntityId === null
          ? await activeConfig.api.create?.(formByEntity[entityKey], context)
          : await activeConfig.api.update?.(editingEntityId, formByEntity[entityKey], context);

      if (response === null) {
        setStateByEntity((current) => ({
          ...current,
          [entityKey]: {
            ...current[entityKey],
            error: missingContextError(activeConfig, 'create'),
            message: null,
          },
        }));
        return;
      }

      if (!response.ok) {
        setStateByEntity((current) => ({
          ...current,
          [entityKey]: {
            ...current[entityKey],
            error: response.error.message,
            message: null,
          },
        }));
        return;
      }

      setFormByEntity((current) => ({
        ...current,
        [entityKey]: buildInitialForm(activeConfig),
      }));
      setEditingEntityId(null);
      setFormErrors({});
      setStateByEntity((current) => ({
        ...current,
        [entityKey]: {
          ...current[entityKey],
          message: wasEditing ? 'Đã cập nhật master data.' : 'Đã lưu master data.',
        },
      }));
      await loadEntity(activeConfig);
    } finally {
      submitInFlightRef.current = false;
      setStateByEntity((current) => ({
        ...current,
        [entityKey]: { ...current[entityKey], submitting: false },
      }));
    }
  }

  async function handleDeactivate(row: MasterDataRow) {
    const entityId = getRowEntityId(activeConfig, row);
    if (entityId === null || !activeConfig.api.deactivate) {
      return;
    }
    if (deactivateInFlightRef.current === entityId) {
      return;
    }

    setConfirmDialogError(null);
    setConfirmDialogState({ entityId, row, label: getRowDisplayLabel(activeConfig, row) });
  }

  async function confirmDeactivate() {
    if (!confirmDialogState || !activeConfig.api.deactivate || deactivateInFlightRef.current === confirmDialogState.entityId) {
      return;
    }

    const entityId = confirmDialogState.entityId;
    const dialogState = confirmDialogState;
    deactivateInFlightRef.current = entityId;
    setPendingDeactivateId(entityId);
    setConfirmDialogError(null);
    setUiErrorByEntity((current) => ({ ...current, [activeConfig.key]: null }));

    const response = await activeConfig.api.deactivate(entityId, { selectedRoomId, params: listParams });
    if (!response.ok) {
      setConfirmDialogState((current) => current ?? dialogState);
      setConfirmDialogError(response.error.message);
      setUiErrorByEntity((current) => ({ ...current, [activeConfig.key]: response.error.message }));
      setStateByEntity((current) => ({
        ...current,
        [activeConfig.key]: { ...current[activeConfig.key], error: response.error.message, message: null },
      }));
      deactivateInFlightRef.current = null;
      setPendingDeactivateId(null);
      return;
    }

    if (editingEntityId === entityId) {
      cancelEdit();
    }

    setConfirmDialogState(null);
    setConfirmDialogError(null);
    setUiErrorByEntity((current) => ({ ...current, [activeConfig.key]: null }));

    setStateByEntity((current) => ({
      ...current,
      [activeConfig.key]: { ...current[activeConfig.key], error: null, message: 'Đã ngưng sử dụng bản ghi.' },
    }));
    await loadEntity(activeConfig);
    deactivateInFlightRef.current = null;
    setPendingDeactivateId(null);
  }

  async function handleBulkGenerateStations() {
    if (bulkInFlightRef.current) {
      return;
    }
    if (!selectedRoomId) {
      setStateByEntity((current) => ({
        ...current,
        stations: { ...current.stations, error: 'Vui lòng chọn phòng trước khi tạo nhanh vị trí máy.' },
      }));
      return;
    }
    const payload = buildBulkGenerateStationsPayload({
      pattern: bulkPattern,
      rows: bulkRows,
      start: bulkStart,
      end: bulkEnd,
      zeroPad: bulkZeroPad,
    });
    if (!payload || !hasValidBulkRange(bulkStart, bulkEnd)) {
      setStateByEntity((current) => ({
        ...current,
        stations: { ...current.stations, error: 'Dải số vị trí máy không hợp lệ.' },
      }));
      return;
    }
    bulkInFlightRef.current = true;
    setBulkGenerating(true);
    setUiErrorByEntity((current) => ({ ...current, stations: null }));
    try {
      const response = await bulkGenerateStations(selectedRoomId, payload);
      if (!response.ok) {
        setUiErrorByEntity((current) => ({ ...current, stations: response.error.message }));
        setStateByEntity((current) => ({
          ...current,
          stations: { ...current.stations, error: response.error.message, message: null },
        }));
        return;
      }
      setStateByEntity((current) => ({
        ...current,
        stations: { ...current.stations, error: null, message: 'Đã tạo vị trí máy.' },
      }));
      await loadEntity(findMasterDataEntity('stations'));
    } finally {
      bulkInFlightRef.current = false;
      setBulkGenerating(false);
    }
  }

  async function handleAssignDeviceToStation() {
    if (assignInFlightRef.current) {
      return;
    }
    const deviceId = parseNumericId(deviceAssignDeviceId);
    const stationId = parseNumericId(deviceAssignStationId);
    if (deviceId === null || stationId === null) {
      return;
    }
    assignInFlightRef.current = true;
    setAssigningDevice(true);
    setUiErrorByEntity((current) => ({ ...current, devices: null }));
    try {
      const response = await assignDeviceToStation(deviceId, { station_id: stationId });
      if (!response.ok) {
        setUiErrorByEntity((current) => ({ ...current, devices: response.error.message }));
        setStateByEntity((current) => ({
          ...current,
          devices: { ...current.devices, error: response.error.message, message: null },
        }));
        return;
      }
      setStateByEntity((current) => ({
        ...current,
        devices: { ...current.devices, error: null, message: 'Đã gán thiết bị vào vị trí.' },
      }));
      setDeviceAssignDeviceId('');
      setDeviceAssignStationId('');
      await loadEntity(findMasterDataEntity('devices'));
    } finally {
      assignInFlightRef.current = false;
      setAssigningDevice(false);
    }
  }

  async function handleRetireDevice() {
    if (retireInFlightRef.current) {
      return;
    }
    const deviceId = parseNumericId(retireDeviceId);
    if (deviceId === null) {
      return;
    }
    retireInFlightRef.current = true;
    setRetiringDevice(true);
    setUiErrorByEntity((current) => ({ ...current, devices: null }));
    try {
      const response = await retireDevice(deviceId, { reason: 'Ngưng sử dụng' });
      if (!response.ok) {
        setUiErrorByEntity((current) => ({ ...current, devices: response.error.message }));
        setStateByEntity((current) => ({
          ...current,
          devices: { ...current.devices, error: response.error.message, message: null },
        }));
        return;
      }
      setStateByEntity((current) => ({
        ...current,
        devices: { ...current.devices, error: null, message: 'Đã ngưng sử dụng thiết bị.' },
      }));
      setRetireDeviceId('');
      await loadEntity(findMasterDataEntity('devices'));
    } finally {
      retireInFlightRef.current = false;
      setRetiringDevice(false);
    }
  }

  const supportsCreate = activeConfig.capabilities.create.status === 'available' && Boolean(activeConfig.api.create);
  const supportsUpdate = activeConfig.capabilities.update.status === 'available' && Boolean(activeConfig.api.update);
  const supportsDeactivate = activeConfig.capabilities.deactivate.status === 'available' && Boolean(activeConfig.api.deactivate);
  const canSubmit = activeConfig.fields.length > 0 && !activeConfig.capabilities.readOnly && (isEditMode ? supportsUpdate : supportsCreate);

  return (
    <div className="compact-page compact-page--flush">
      <div className="master-data-layout">
        <EntityNavigation entities={entities} activeKey={activeConfig.key} onSelect={onActiveKeyChange} />

        <ConfirmationDialog
          open={confirmDialogState !== null}
          title="Xác nhận ngưng sử dụng"
          body="Thao tác này sẽ ngưng sử dụng bản ghi đã chọn. Dữ liệu sẽ không bị xóa vĩnh viễn."
          targetLabel={confirmDialogState?.label}
          error={confirmDialogError}
          confirmLabel="Ngưng sử dụng"
          cancelLabel="Hủy"
          confirming={pendingDeactivateId !== null}
          onConfirm={() => void confirmDeactivate()}
          onCancel={() => {
            if (pendingDeactivateId !== null) {
              return;
            }
            setConfirmDialogError(null);
            setConfirmDialogState(null);
          }}
        />

        <EntityListPanel
          entity={activeConfig}
          rows={entityState.rows}
          pagination={entityState.pagination}
          loading={entityState.loading}
          error={uiErrorByEntity[activeConfig.key] ?? entityState.error}
          message={entityState.message}
          listParams={listParams}
          onQueryChange={(query) => updateListParams({ query, page: 1 })}
          onStatusChange={(status) => updateListParams({ status, page: 1 })}
          onPageChange={(page) => updateListParams({ page })}
          onPageSizeChange={(pageSize) => updateListParams({ page_size: pageSize, page: 1 })}
          onReload={() => void loadEntity(activeConfig)}
          onEdit={supportsUpdate ? (row) => startEdit(row) : undefined}
          onDeactivate={supportsDeactivate ? (row) => void handleDeactivate(row) : undefined}
          getDeactivateDisabled={supportsDeactivate ? (row) => getRowEntityId(activeConfig, row) === pendingDeactivateId : undefined}
          emptyState={
            <>
              <FacilityPanel
                activeKey={activeConfig.key}
                selectedRoomId={selectedRoomId}
                roomItems={roomItems}
                bulkPattern={bulkPattern}
                bulkRows={bulkRows}
                bulkStart={bulkStart}
                bulkEnd={bulkEnd}
                bulkZeroPad={bulkZeroPad}
                bulkPreview={bulkPreview}
                deviceAssignDeviceId={deviceAssignDeviceId}
                deviceAssignStationId={deviceAssignStationId}
                retireDeviceId={retireDeviceId}
                onRoomChange={setSelectedRoomId}
                onBulkPatternChange={setBulkPattern}
                onBulkRowsChange={setBulkRows}
                onBulkStartChange={setBulkStart}
                onBulkEndChange={setBulkEnd}
                onBulkZeroPadChange={setBulkZeroPad}
                onBulkGenerateStations={() => void handleBulkGenerateStations()}
                bulkGenerating={bulkGenerating}
                onDeviceAssignDeviceIdChange={setDeviceAssignDeviceId}
                onDeviceAssignStationIdChange={setDeviceAssignStationId}
                onAssignDeviceToStation={() => void handleAssignDeviceToStation()}
                assigningDevice={assigningDevice}
                onRetireDeviceIdChange={setRetireDeviceId}
                onRetireDevice={() => void handleRetireDevice()}
                retiringDevice={retiringDevice}
              />

              {canSubmit ? (
                <EntityCreatePanel
                  entity={activeConfig}
                  mode={isEditMode ? 'edit' : 'create'}
                  form={form}
                  fieldErrors={formErrors}
                  submitting={entityState.submitting}
                  submitDisabled={!canSubmit}
                  onSubmit={handleSubmit}
                  onChange={updateFormValue}
                  onCancel={isEditMode ? cancelEdit : undefined}
                  getOptionsForField={getOptionsForField}
                  getLookupState={getLookupState}
                />
              ) : (
                <div className="empty-state">
                  {activeConfig.createNote ?? activeConfig.capabilities.create.note ?? 'Danh mục này chưa có form nhập mới.'}
                </div>
              )}
            </>
          }
        />
      </div>
    </div>
  );
}

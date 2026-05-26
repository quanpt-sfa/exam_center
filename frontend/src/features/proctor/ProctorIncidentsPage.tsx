import { FormEvent, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { CompactPage } from '../../shared/components/compact/CompactPage';
import { CompactPageHeader } from '../../shared/components/compact/CompactPageHeader';
import { CompactSurface } from '../../shared/components/compact/CompactSurface';
import { CompactToolbar } from '../../shared/components/compact/CompactToolbar';
import { IconActionButton, PrimaryActionSlot, ToolbarActionGroup } from '../../shared/components/compact/IconActionButton';
import { createProctorIncident, listProctorRoomIncidents, updateProctorIncident } from './api/proctorApi';
import type { ProctorIncident } from './api/contracts';
import { ProctorEmptyState } from './components/ProctorEmptyState';
import { ProctorErrorState } from './components/ProctorErrorState';
import { ProctorInvalidRoomState } from './components/ProctorInvalidRoomState';
import { ProctorLoadingState } from './components/ProctorLoadingState';
import { ProctorStatusBadge } from './components/ProctorStatusBadge';
import {
  canProctorResolveIncident,
  formatDateTime,
  getAllowedProctorIncidentTransitions,
  incidentTypeLabel,
  isIncidentTerminal,
  requiresResolutionNoteForTransition,
} from './proctorDisplay';
import { resolveExamSittingRoomId } from './proctorRoute';

type IncidentFieldErrors = {
  examAssignmentId?: string;
  stationId?: string;
  deviceId?: string;
};

type IncidentUpdateDialogState = {
  mode: 'IN_PROGRESS' | 'RESOLVED';
  incident: ProctorIncident;
};

export function ProctorIncidentsPage() {
  const params = useParams<{ examSittingRoomId: string }>();
  const routeExamSittingRoomId = params.examSittingRoomId;
  const roomIdResolution = resolveExamSittingRoomId(routeExamSittingRoomId);
  const examSittingRoomId = roomIdResolution.isValid ? roomIdResolution.examSittingRoomId : null;
  const [incidentType, setIncidentType] = useState('DEVICE_FAILURE');
  const [description, setDescription] = useState('');
  const [examAssignmentId, setExamAssignmentId] = useState('');
  const [stationId, setStationId] = useState('');
  const [deviceId, setDeviceId] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [createdIncident, setCreatedIncident] = useState<ProctorIncident | null>(null);
  const [fieldErrors, setFieldErrors] = useState<IncidentFieldErrors>({});
  const [incidents, setIncidents] = useState<ProctorIncident[]>([]);
  const [loading, setLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);
  const [updateDialog, setUpdateDialog] = useState<IncidentUpdateDialogState | null>(null);
  const [updateSubmitting, setUpdateSubmitting] = useState(false);
  const [updateError, setUpdateError] = useState<string | null>(null);
  const [resolutionNote, setResolutionNote] = useState('');
  const [resolutionNoteError, setResolutionNoteError] = useState<string | null>(null);

  async function loadIncidents() {
    if (!roomIdResolution.isValid || examSittingRoomId === null) {
      setLoading(false);
      setListError(roomIdResolution.errorMessage);
      return;
    }

    setLoading(true);
    setListError(null);
    try {
      setIncidents(await listProctorRoomIncidents(examSittingRoomId));
    } catch (loadError) {
      setListError(loadError instanceof Error ? loadError.message : 'Không tải được danh sách sự cố.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!roomIdResolution.isValid || examSittingRoomId === null) {
      setLoading(false);
      setListError(roomIdResolution.errorMessage);
      return;
    }

    void loadIncidents();
  }, [examSittingRoomId, routeExamSittingRoomId]);

  function parseOptionalPositiveInteger(value: string, fieldLabel: string): { value?: number; error?: string } {
    const trimmed = value.trim();
    if (!trimmed) {
      return {};
    }

    if (!/^[1-9]\d*$/.test(trimmed)) {
      return { error: `${fieldLabel} phải là số nguyên dương lớn hơn 0.` };
    }

    return { value: Number(trimmed) };
  }

  function openUpdateDialog(mode: IncidentUpdateDialogState['mode'], incident: ProctorIncident) {
    setUpdateDialog({ mode, incident });
    setUpdateError(null);
    setResolutionNote('');
    setResolutionNoteError(null);
  }

  function closeUpdateDialog() {
    if (updateSubmitting) {
      return;
    }
    setUpdateDialog(null);
    setUpdateError(null);
    setResolutionNote('');
    setResolutionNoteError(null);
  }

  async function handleConfirmUpdate() {
    if (updateDialog === null || updateSubmitting) {
      return;
    }

    const nextPayload =
      updateDialog.mode === 'IN_PROGRESS'
        ? { incident_status: 'IN_PROGRESS' as const }
        : (() => {
            const trimmedResolutionNote = resolutionNote.trim();
            if (!trimmedResolutionNote) {
              setResolutionNoteError('Vui lòng nhập ghi chú xử lý.');
              return null;
            }
            return {
              incident_status: 'RESOLVED' as const,
              resolution_note: trimmedResolutionNote,
            };
          })();

    if (nextPayload === null) {
      return;
    }

    setUpdateSubmitting(true);
    setUpdateError(null);

    try {
      await updateProctorIncident(updateDialog.incident.incident_id, nextPayload);
      await loadIncidents();
      setUpdateDialog(null);
      setResolutionNote('');
      setResolutionNoteError(null);
    } catch (error) {
      setUpdateError(error instanceof Error ? error.message : 'Không cập nhật được sự cố.');
    } finally {
      setUpdateSubmitting(false);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting || !roomIdResolution.isValid || examSittingRoomId === null) {
      if (!roomIdResolution.isValid) {
        setSubmitError(roomIdResolution.errorMessage);
      }
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    setCreatedIncident(null);
    setFieldErrors({});
    try {
      const nextAssignmentId = parseOptionalPositiveInteger(examAssignmentId, 'Mã phân công');
      const nextStationId = parseOptionalPositiveInteger(stationId, 'Mã máy trạm');
      const nextDeviceId = parseOptionalPositiveInteger(deviceId, 'Mã thiết bị');
      const nextFieldErrors: IncidentFieldErrors = {
        examAssignmentId: nextAssignmentId.error,
        stationId: nextStationId.error,
        deviceId: nextDeviceId.error,
      };

      if (nextFieldErrors.examAssignmentId || nextFieldErrors.stationId || nextFieldErrors.deviceId) {
        setFieldErrors(nextFieldErrors);
        setSubmitting(false);
        return;
      }

      const payload = {
        incident_type: incidentType,
        description,
        ...(nextAssignmentId.value ? { exam_assignment_id: nextAssignmentId.value } : {}),
        ...(nextStationId.value ? { station_id: nextStationId.value } : {}),
        ...(nextDeviceId.value ? { device_id: nextDeviceId.value } : {}),
      };

      const created = await createProctorIncident(examSittingRoomId, payload);
      setCreatedIncident(created);
      setDescription('');
      setExamAssignmentId('');
      setStationId('');
      setDeviceId('');
      setFieldErrors({});

      try {
        await loadIncidents();
      } catch {
        // loadIncidents already records the list failure state.
      }
    } catch (submitError) {
      setSubmitError(submitError instanceof Error ? submitError.message : 'Không tạo được sự cố.');
    } finally {
      setSubmitting(false);
    }
  }

  if (!roomIdResolution.isValid || examSittingRoomId === null) {
    return (
      <CompactPage data-testid="proctor-incidents-page">
        <ProctorInvalidRoomState message={roomIdResolution.errorMessage} />
      </CompactPage>
    );
  }

  return (
    <CompactPage data-testid="proctor-incidents-page">
      <CompactPageHeader
        eyebrow="Proctor Portal"
        title="Sự cố phòng thi"
        description="Lịch sử sự cố phòng thi được tải trực tiếp từ backend theo từng phòng thi."
      />

      <CompactToolbar>
        <span className="muted">Room: #{examSittingRoomId}</span>
        <span className="muted">Không hỗ trợ PROCTOR void action.</span>
        <span className="muted">Terminal statuses giữ read-only.</span>
      </CompactToolbar>

      {submitError ? <ProctorErrorState title="Không tạo được sự cố" message={submitError} /> : null}
      {createdIncident ? (
        <CompactSurface tight title="Sự cố vừa tạo">
          <p style={{ margin: '0 0 var(--sp-2) 0' }}><strong>ID:</strong> {createdIncident.incident_id}</p>
          <p style={{ margin: '0 0 var(--sp-2) 0' }}><strong>Loại:</strong> {incidentTypeLabel(createdIncident.incident_type)}</p>
          <div style={{ marginBottom: 'var(--sp-2)' }}><ProctorStatusBadge kind="incident-status" value={createdIncident.incident_status} /></div>
          <p className="muted" style={{ margin: 0 }}>{createdIncident.description || 'Không có mô tả.'}</p>
        </CompactSurface>
      ) : null}

      <CompactSurface
        tight
        title="Lịch sử sự cố phòng thi"
        actions={
          <IconActionButton
            icon="refresh"
            label={loading ? 'Đang tải...' : 'Thử tải lại'}
            onClick={() => void loadIncidents()}
            disabled={loading}
          />
        }
      >
        {listError ? (
          <ProctorErrorState
            title="Không tải được danh sách sự cố"
            message={listError}
            retryLabel="Thử tải lại"
            onRetry={() => void loadIncidents()}
          />
        ) : null}

        {loading ? <ProctorLoadingState message="Đang tải danh sách sự cố..." /> : null}

        {!loading && !listError && incidents.length === 0 ? (
          <ProctorEmptyState icon="📝" message="Chưa có sự cố nào được ghi nhận" />
        ) : null}

        {!loading && !listError && incidents.length > 0 ? (
          <div style={{ display: 'grid', gap: 'var(--gap-sm)' }}>
            {incidents.map((incident) => {
              const allowedTransitions = getAllowedProctorIncidentTransitions(incident.incident_status);
              const canMarkInProgress = allowedTransitions.includes('IN_PROGRESS');
              const canMarkResolved = canProctorResolveIncident(incident.incident_status);
              const readOnlyMessage = isIncidentTerminal(incident.incident_status)
                ? 'Sự cố đang ở trạng thái cuối, chỉ có thể xem.'
                : allowedTransitions.length === 0
                  ? 'Trạng thái này chưa hỗ trợ cập nhật từ giao diện giám thị.'
                  : null;

              return (
                <article key={incident.incident_id} className="compact-surface compact-surface--tight" aria-label={`Sự cố ${incident.incident_id}`}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--sp-3)', flexWrap: 'wrap', marginBottom: 'var(--sp-3)' }}>
                    <div>
                      <h4 style={{ margin: '0 0 var(--sp-2) 0' }}>{incidentTypeLabel(incident.incident_type)}</h4>
                      <p className="muted" style={{ margin: 0 }}>ID sự cố: {incident.incident_id}</p>
                    </div>
                    <div style={{ display: 'grid', gap: 'var(--sp-2)', justifyItems: 'start' }}>
                      <div>
                        <span className="muted" style={{ display: 'block', marginBottom: 'var(--sp-1)' }}>Trạng thái</span>
                        <ProctorStatusBadge kind="incident-status" value={incident.incident_status} />
                      </div>
                    </div>
                  </div>

                  <p style={{ margin: '0 0 var(--sp-3) 0' }}>{incident.description || 'Không có mô tả.'}</p>

                  {incident.incident_status === 'RESOLVED' && incident.resolution_note ? (
                    <div className="card" style={{ marginBottom: 'var(--sp-3)', background: 'var(--surface-body)' }}>
                      <p style={{ margin: 0 }}><strong>Ghi chú xử lý:</strong> {incident.resolution_note}</p>
                    </div>
                  ) : null}

                  <dl style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 'var(--sp-3)', margin: 0 }}>
                    <div>
                      <dt className="muted">Thời điểm ghi nhận</dt>
                      <dd style={{ margin: 0 }}>{formatDateTime(incident.reported_at)}</dd>
                    </div>
                    {incident.exam_assignment_id !== null ? (
                      <div>
                        <dt className="muted">Mã phân công</dt>
                        <dd style={{ margin: 0 }}>{incident.exam_assignment_id}</dd>
                      </div>
                    ) : null}
                    {incident.station_id !== null ? (
                      <div>
                        <dt className="muted">Mã trạm</dt>
                        <dd style={{ margin: 0 }}>{incident.station_id}</dd>
                      </div>
                    ) : null}
                    {incident.device_id !== null ? (
                      <div>
                        <dt className="muted">Mã thiết bị</dt>
                        <dd style={{ margin: 0 }}>{incident.device_id}</dd>
                      </div>
                    ) : null}
                    {incident.resolved_at ? (
                      <div>
                        <dt className="muted">Thời điểm xử lý</dt>
                        <dd style={{ margin: 0 }}>{formatDateTime(incident.resolved_at)}</dd>
                      </div>
                    ) : null}
                    {incident.updated_at ? (
                      <div>
                        <dt className="muted">Thời điểm cập nhật</dt>
                        <dd style={{ margin: 0 }}>{formatDateTime(incident.updated_at)}</dd>
                      </div>
                    ) : null}
                    {incident.updated_by !== null ? (
                      <div>
                        <dt className="muted">ID người cập nhật</dt>
                        <dd style={{ margin: 0 }}>{incident.updated_by}</dd>
                      </div>
                    ) : null}
                    {incident.resolved_by !== null ? (
                      <div>
                        <dt className="muted">ID người xử lý</dt>
                        <dd style={{ margin: 0 }}>{incident.resolved_by}</dd>
                      </div>
                    ) : null}
                  </dl>

                  <div style={{ marginTop: 'var(--sp-3)', display: 'flex', flexWrap: 'wrap', gap: 'var(--sp-2)', alignItems: 'center' }}>
                    <ToolbarActionGroup>
                      {canMarkInProgress ? (
                        <IconActionButton
                          icon="check"
                          label="Đánh dấu đang xử lý"
                          onClick={() => openUpdateDialog('IN_PROGRESS', incident)}
                        />
                      ) : null}
                    </ToolbarActionGroup>
                    <PrimaryActionSlot>
                      {canMarkResolved ? (
                        <button
                          type="button"
                          className="primary-button"
                          onClick={() => openUpdateDialog('RESOLVED', incident)}
                        >
                          Đánh dấu đã xử lý
                        </button>
                      ) : null}
                    </PrimaryActionSlot>
                    {readOnlyMessage ? <span className="muted">{readOnlyMessage}</span> : null}
                  </div>
                </article>
              );
            })}
          </div>
        ) : null}
      </CompactSurface>

      {updateDialog ? (
        <div
          role="alertdialog"
          aria-modal="true"
          aria-labelledby="incident-update-dialog-title"
          style={{
            position: 'fixed',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 'var(--sp-4)',
            zIndex: 220,
          }}
        >
          <div
            onClick={updateSubmitting ? undefined : closeUpdateDialog}
            style={{
              position: 'absolute',
              inset: 0,
              backgroundColor: 'rgba(15, 23, 42, 0.45)',
            }}
          />
          <div
            style={{
              position: 'relative',
              width: '100%',
              maxWidth: '560px',
              backgroundColor: 'var(--surface-card)',
              borderRadius: 'var(--radius-lg)',
              boxShadow: 'var(--shadow-xl)',
              border: '1px solid var(--clr-gray-200)',
              overflow: 'hidden',
            }}
          >
            <div style={{ padding: 'var(--sp-5)' }}>
              <h2 id="incident-update-dialog-title" style={{ margin: '0 0 var(--sp-2) 0' }}>
                {updateDialog.mode === 'IN_PROGRESS' ? 'Xác nhận chuyển sang đang xử lý' : 'Xác nhận đánh dấu đã xử lý'}
              </h2>
              <p className="muted" style={{ marginBottom: 'var(--sp-3)' }}>
                {updateDialog.mode === 'IN_PROGRESS'
                  ? 'Sự cố sẽ được chuyển sang trạng thái đang xử lý.'
                  : 'Sự cố sẽ được chuyển sang trạng thái đã xử lý và yêu cầu ghi chú xử lý.'}
              </p>
              <div className="card" style={{ margin: 0, background: 'var(--surface-body)' }}>
                <p style={{ margin: 0 }}><strong>ID sự cố:</strong> {updateDialog.incident.incident_id}</p>
                <p style={{ margin: 'var(--sp-2) 0 0 0' }}><strong>Loại:</strong> {incidentTypeLabel(updateDialog.incident.incident_type)}</p>
                <p style={{ margin: 'var(--sp-2) 0 0 0' }}><strong>Trạng thái hiện tại:</strong> {updateDialog.incident.incident_status}</p>
              </div>
              {updateDialog.mode === 'RESOLVED' ? (
                <label style={{ display: 'grid', gap: 'var(--sp-2)', marginTop: 'var(--sp-3)' }}>
                  Ghi chú xử lý
                  <textarea
                    value={resolutionNote}
                    onChange={(event) => {
                      setResolutionNote(event.target.value);
                      if (resolutionNoteError !== null) {
                        setResolutionNoteError(null);
                      }
                    }}
                    rows={4}
                  />
                </label>
              ) : null}
              {resolutionNoteError ? <p className="error" style={{ marginTop: 'var(--sp-3)' }}>{resolutionNoteError}</p> : null}
              {updateError ? <p className="error" style={{ marginTop: 'var(--sp-3)' }}>{updateError}</p> : null}
              {updateDialog.mode === 'RESOLVED' && requiresResolutionNoteForTransition(updateDialog.incident.incident_status, 'RESOLVED') ? (
                <p className="muted" style={{ marginTop: 'var(--sp-3)', marginBottom: 0 }}>
                  Ghi chú xử lý là bắt buộc khi chuyển sự cố sang trạng thái đã xử lý.
                </p>
              ) : null}
            </div>
            <footer
              style={{
                display: 'flex',
                justifyContent: 'flex-end',
                gap: 'var(--sp-2)',
                padding: 'var(--sp-3) var(--sp-5)',
                backgroundColor: 'var(--surface-body)',
                borderTop: '1px solid var(--clr-gray-200)',
              }}
            >
              <button type="button" className="secondary-button" onClick={closeUpdateDialog} disabled={updateSubmitting}>
                Hủy
              </button>
              <button type="button" className="primary-button" onClick={() => void handleConfirmUpdate()} disabled={updateSubmitting}>
                {updateSubmitting
                  ? 'Đang cập nhật...'
                  : updateDialog.mode === 'IN_PROGRESS'
                    ? 'Xác nhận đang xử lý'
                    : 'Xác nhận đã xử lý'}
              </button>
            </footer>
          </div>
        </div>
      ) : null}

      <CompactSurface tight title="Tạo sự cố mới" description="Form tạo sự cố backend-bound, không có lịch sử giả lập hoặc metadata editor tùy ý.">
      <form onSubmit={(event) => void handleSubmit(event)} style={{ display: 'grid', gap: 'var(--sp-3)' }}>
        <label>
          Loại sự cố
          <select value={incidentType} onChange={(event) => setIncidentType(event.target.value)}>
            <option value="DEVICE_FAILURE">DEVICE_FAILURE</option>
            <option value="NETWORK_FAILURE">NETWORK_FAILURE</option>
            <option value="POWER_FAILURE">POWER_FAILURE</option>
            <option value="LOGIN_ISSUE">LOGIN_ISSUE</option>
            <option value="IDENTITY_MISMATCH">IDENTITY_MISMATCH</option>
            <option value="ADMIN_NOTE">ADMIN_NOTE</option>
          </select>
        </label>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 'var(--sp-3)' }}>
          <label>
            Mã phân công (tùy chọn)
            <input
              value={examAssignmentId}
              onChange={(event) => {
                setExamAssignmentId(event.target.value);
                setFieldErrors((prev) => ({ ...prev, examAssignmentId: undefined }));
              }}
              inputMode="numeric"
            />
            <span className="muted" style={{ display: 'block' }}>
              Để trống nếu bạn không biết chính xác mã nội bộ từ dữ liệu phòng thi.
            </span>
            {fieldErrors.examAssignmentId ? <span className="error">{fieldErrors.examAssignmentId}</span> : null}
          </label>
          <label>
            Mã máy trạm (tùy chọn)
            <input
              value={stationId}
              onChange={(event) => {
                setStationId(event.target.value);
                setFieldErrors((prev) => ({ ...prev, stationId: undefined }));
              }}
              inputMode="numeric"
            />
            {fieldErrors.stationId ? <span className="error">{fieldErrors.stationId}</span> : null}
          </label>
          <label>
            Mã thiết bị (tùy chọn)
            <input
              value={deviceId}
              onChange={(event) => {
                setDeviceId(event.target.value);
                setFieldErrors((prev) => ({ ...prev, deviceId: undefined }));
              }}
              inputMode="numeric"
            />
            {fieldErrors.deviceId ? <span className="error">{fieldErrors.deviceId}</span> : null}
          </label>
        </div>

        <label>
          Mô tả
          <textarea value={description} onChange={(event) => setDescription(event.target.value)} rows={4} />
        </label>

        <div>
          <button type="submit" className="primary-button" disabled={submitting}>
            {submitting ? 'Đang gửi...' : 'Ghi nhận sự cố'}
          </button>
        </div>
      </form>
        </CompactSurface>
      </CompactPage>
  );
}

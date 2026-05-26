import { useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import { CompactPage } from '../../shared/components/compact/CompactPage';
import { CompactPageHeader } from '../../shared/components/compact/CompactPageHeader';
import { CompactSurface } from '../../shared/components/compact/CompactSurface';
import { CompactToolbar } from '../../shared/components/compact/CompactToolbar';
import { IconActionButton, PrimaryActionSlot, RowActionGroup } from '../../shared/components/compact/IconActionButton';
import type {
  AttendanceVerificationMethod,
  AttendanceVerificationStatus,
  CheckInAssignmentPayload,
  ProctorAttendanceItem,
  ProctorAttendanceResponse,
  ScanCheckInMethod,
} from './api/contracts';
import {
  checkInAssignment,
  listProctorRoomAttendance,
  markAssignmentAbsent,
  scanCheckInAttendance,
  verifyAssignmentIdentity,
} from './api/proctorApi';
import { ProctorEmptyState } from './components/ProctorEmptyState';
import { ProctorErrorState } from './components/ProctorErrorState';
import { ProctorInvalidRoomState } from './components/ProctorInvalidRoomState';
import { ProctorLoadingState } from './components/ProctorLoadingState';
import { ProctorRoomHeader } from './components/ProctorRoomHeader';
import { ProctorStatusBadge } from './components/ProctorStatusBadge';
import { RevokeStaleSessionDialog } from './components/RevokeStaleSessionDialog';
import { formatDateTime, verificationMethodLabel, verificationStatusLabel } from './proctorDisplay';
import { resolveExamSittingRoomId } from './proctorRoute';

const SCAN_METHOD_OPTIONS: Array<{ value: ScanCheckInMethod; label: string }> = [
  { value: 'BARCODE', label: 'Barcode' },
  { value: 'MAGSTRIPE', label: 'Magstripe' },
  { value: 'QR_CODE', label: 'QR Code' },
];

type AttendanceDialogState =
  | { mode: 'check-in'; item: ProctorAttendanceItem }
  | { mode: 'mark-absent'; item: ProctorAttendanceItem }
  | { mode: 'verify-identity'; item: ProctorAttendanceItem }
  | null;

function isEligibleForManualCheckIn(item: ProctorAttendanceItem): boolean {
  return String(item.assignment_status).trim().toUpperCase() === 'ASSIGNED';
}

function isEligibleForMarkAbsent(item: ProctorAttendanceItem): boolean {
  return String(item.assignment_status).trim().toUpperCase() === 'ASSIGNED';
}

function canVerifyIdentity(item: ProctorAttendanceItem): boolean {
  const status = String(item.assignment_status).trim().toUpperCase();
  return status !== 'CANCELLED' && status !== 'VOIDED';
}

function isValidStudentId(value: number): boolean {
  return Number.isInteger(value) && value > 0;
}

function formatActorId(value: number | null): string {
  return value === null ? '-' : String(value);
}

function AttendanceActionDialog({
  state,
  submitting,
  error,
  absentNote,
  absentReasonCode,
  verifyStatus,
  verifyMethod,
  verifyNote,
  onClose,
  onAbsentNoteChange,
  onAbsentReasonCodeChange,
  onVerifyStatusChange,
  onVerifyMethodChange,
  onVerifyNoteChange,
  onConfirm,
}: {
  state: AttendanceDialogState;
  submitting: boolean;
  error: string | null;
  absentNote: string;
  absentReasonCode: string;
  verifyStatus: AttendanceVerificationStatus;
  verifyMethod: AttendanceVerificationMethod;
  verifyNote: string;
  onClose: () => void;
  onAbsentNoteChange: (value: string) => void;
  onAbsentReasonCodeChange: (value: string) => void;
  onVerifyStatusChange: (value: AttendanceVerificationStatus) => void;
  onVerifyMethodChange: (value: AttendanceVerificationMethod) => void;
  onVerifyNoteChange: (value: string) => void;
  onConfirm: () => void;
}) {
  if (state === null) {
    return null;
  }

  const title =
    state.mode === 'check-in'
      ? 'Xác nhận check-in thủ công'
      : state.mode === 'mark-absent'
        ? 'Đánh dấu vắng'
        : 'Xác minh danh tính';

  return (
    <div
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="attendance-action-dialog-title"
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
        onClick={submitting ? undefined : onClose}
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
          <h2 id="attendance-action-dialog-title" style={{ margin: '0 0 var(--sp-2) 0' }}>{title}</h2>
          <div className="card" style={{ margin: 0, background: 'var(--surface-body)' }}>
            <p style={{ margin: 0 }}><strong>Mã SV:</strong> {state.item.student_code}</p>
            <p style={{ margin: 'var(--sp-2) 0 0 0' }}><strong>Họ tên:</strong> {state.item.full_name}</p>
            <p style={{ margin: 'var(--sp-2) 0 0 0' }}><strong>Máy:</strong> {state.item.station_code ?? '-'}</p>
          </div>

          {state.mode === 'check-in' ? (
            <p className="muted" style={{ marginTop: 'var(--sp-3)' }}>
              Hành động này gọi backend check-in thật theo `exam_assignment_id` và sẽ tải lại danh sách sau khi thành công.
            </p>
          ) : null}

          {state.mode === 'mark-absent' ? (
            <div style={{ display: 'grid', gap: 'var(--sp-3)', marginTop: 'var(--sp-3)' }}>
              <label style={{ display: 'grid', gap: 'var(--sp-1)' }}>
                <span>Ghi chú bắt buộc</span>
                <textarea value={absentNote} onChange={(event) => onAbsentNoteChange(event.target.value)} rows={3} />
              </label>
              <label style={{ display: 'grid', gap: 'var(--sp-1)' }}>
                <span>Mã lý do</span>
                <input value={absentReasonCode} onChange={(event) => onAbsentReasonCodeChange(event.target.value)} maxLength={100} />
              </label>
            </div>
          ) : null}

          {state.mode === 'verify-identity' ? (
            <div style={{ display: 'grid', gap: 'var(--sp-3)', marginTop: 'var(--sp-3)' }}>
              <label style={{ display: 'grid', gap: 'var(--sp-1)' }}>
                <span>Trạng thái xác minh</span>
                <select value={verifyStatus} onChange={(event) => onVerifyStatusChange(event.target.value as AttendanceVerificationStatus)}>
                  <option value="VERIFIED">VERIFIED</option>
                  <option value="REJECTED">REJECTED</option>
                </select>
              </label>
              <label style={{ display: 'grid', gap: 'var(--sp-1)' }}>
                <span>Phương thức xác minh</span>
                <select value={verifyMethod} onChange={(event) => onVerifyMethodChange(event.target.value as AttendanceVerificationMethod)}>
                  <option value="PHOTO_ID">PHOTO_ID</option>
                  <option value="MANUAL">MANUAL</option>
                  <option value="OTHER">OTHER</option>
                </select>
              </label>
              <label style={{ display: 'grid', gap: 'var(--sp-1)' }}>
                <span>Ghi chú</span>
                <textarea value={verifyNote} onChange={(event) => onVerifyNoteChange(event.target.value)} rows={3} />
              </label>
            </div>
          ) : null}

          {error ? <p className="error" style={{ marginTop: 'var(--sp-3)' }}>{error}</p> : null}
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
          <button type="button" className="secondary-button" onClick={onClose} disabled={submitting}>Hủy</button>
          <button type="button" className="primary-button" onClick={onConfirm} disabled={submitting}>
            {submitting
              ? 'Đang gửi...'
              : state.mode === 'check-in'
                ? 'Xác nhận check-in'
                : state.mode === 'mark-absent'
                  ? 'Xác nhận vắng'
                  : 'Lưu xác minh'}
          </button>
        </footer>
      </div>
    </div>
  );
}

export function ProctorAttendancePage() {
  const params = useParams<{ examSittingRoomId: string }>();
  const routeExamSittingRoomId = params.examSittingRoomId;
  const roomIdResolution = resolveExamSittingRoomId(routeExamSittingRoomId);
  const examSittingRoomId = roomIdResolution.isValid ? roomIdResolution.examSittingRoomId : null;
  const [attendance, setAttendance] = useState<ProctorAttendanceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<{ kind: 'success' | 'error'; message: string } | null>(null);
  const [selectedCandidate, setSelectedCandidate] = useState<ProctorAttendanceItem | null>(null);
  const [dialogState, setDialogState] = useState<AttendanceDialogState>(null);
  const [dialogSubmitting, setDialogSubmitting] = useState(false);
  const [dialogError, setDialogError] = useState<string | null>(null);
  const [absentNote, setAbsentNote] = useState('');
  const [absentReasonCode, setAbsentReasonCode] = useState('');
  const [verifyStatus, setVerifyStatus] = useState<AttendanceVerificationStatus>('VERIFIED');
  const [verifyMethod, setVerifyMethod] = useState<AttendanceVerificationMethod>('PHOTO_ID');
  const [verifyNote, setVerifyNote] = useState('');
  const [scanMethod, setScanMethod] = useState<ScanCheckInMethod>('BARCODE');
  const [scanDeviceId, setScanDeviceId] = useState('');
  const [scanInput, setScanInput] = useState('');
  const [scanSubmitting, setScanSubmitting] = useState(false);
  const [scanError, setScanError] = useState<string | null>(null);
  const [scanSuccess, setScanSuccess] = useState<string | null>(null);
  const scanInputRef = useRef<HTMLInputElement | null>(null);

  async function loadAttendance() {
    if (examSittingRoomId === null) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setAttendance(await listProctorRoomAttendance(examSittingRoomId));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Không tải được danh sách điểm danh.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!roomIdResolution.isValid || examSittingRoomId === null) {
      setLoading(false);
      setError(roomIdResolution.errorMessage);
      return;
    }
    void loadAttendance();
  }, [examSittingRoomId, routeExamSittingRoomId]);

  useEffect(() => {
    if (dialogState === null) {
      setDialogSubmitting(false);
      setDialogError(null);
      setAbsentNote('');
      setAbsentReasonCode('');
      setVerifyStatus('VERIFIED');
      setVerifyMethod('PHOTO_ID');
      setVerifyNote('');
      return;
    }
    setDialogSubmitting(false);
    setDialogError(null);
    if (dialogState.mode === 'verify-identity') {
      setVerifyStatus('VERIFIED');
      setVerifyMethod('PHOTO_ID');
      setVerifyNote('');
    }
  }, [dialogState]);

  if (!roomIdResolution.isValid || examSittingRoomId === null) {
    return (
      <CompactPage data-testid="proctor-attendance-page">
        <ProctorInvalidRoomState message={roomIdResolution.errorMessage} />
      </CompactPage>
    );
  }

  async function handleConfirmDialogAction() {
    if (dialogState === null || dialogSubmitting) {
      return;
    }

    setDialogSubmitting(true);
    setDialogError(null);
    setFeedback(null);

    try {
      if (dialogState.mode === 'check-in') {
        const payload: CheckInAssignmentPayload = { checkin_method: 'MANUAL' };
        await checkInAssignment(examSittingRoomId, dialogState.item.exam_assignment_id, payload);
        await loadAttendance();
        setFeedback({ kind: 'success', message: `Đã check-in ${dialogState.item.student_code}.` });
      } else if (dialogState.mode === 'mark-absent') {
        await markAssignmentAbsent(examSittingRoomId, dialogState.item.exam_assignment_id, {
          note: absentNote,
          reason_code: absentReasonCode.trim() || null,
        });
        await loadAttendance();
        setFeedback({ kind: 'success', message: `Đã đánh dấu vắng ${dialogState.item.student_code}.` });
      } else {
        await verifyAssignmentIdentity(examSittingRoomId, dialogState.item.exam_assignment_id, {
          verification_status: verifyStatus,
          verification_method: verifyMethod,
          note: verifyNote.trim() || null,
        });
        await loadAttendance();
        setFeedback({ kind: 'success', message: `Đã lưu xác minh danh tính cho ${dialogState.item.student_code}.` });
      }
      setDialogState(null);
    } catch (mutationError) {
      setDialogError(mutationError instanceof Error ? mutationError.message : 'Không thể thực hiện thao tác lúc này.');
    } finally {
      setDialogSubmitting(false);
    }
  }

  async function handleScanSubmit(event?: React.FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    if (scanSubmitting || examSittingRoomId === null) {
      return;
    }

    const normalizedScanValue = scanInput.trim();
    if (!normalizedScanValue) {
      setScanError('Vui lòng nhập mã scan trước khi gửi.');
      scanInputRef.current?.focus();
      return;
    }

    setScanSubmitting(true);
    setScanError(null);
    setScanSuccess(null);
    setFeedback(null);

    try {
      const result = await scanCheckInAttendance(examSittingRoomId, {
        checkin_method: scanMethod,
        scan_value: normalizedScanValue,
        scan_device_id: scanDeviceId.trim() || null,
      });
      await loadAttendance();
      setScanInput('');
      setScanSuccess(`Đã check-in ${result.student_code} - ${result.full_name}.`);
      setFeedback({ kind: 'success', message: `Scan thành công: ${result.student_code} - ${result.full_name}.` });
      scanInputRef.current?.focus();
    } catch (scanSubmitError) {
      setScanInput('');
      setScanError(scanSubmitError instanceof Error ? scanSubmitError.message : 'Scan thất bại.');
      scanInputRef.current?.focus();
    } finally {
      setScanSubmitting(false);
    }
  }

  return (
    <CompactPage data-testid="proctor-attendance-page">
      <CompactPageHeader
        eyebrow="Proctor Portal"
        title="Điểm danh phòng thi"
        description="Danh sách này dùng contract attendance thật từ backend. Mọi thao tác check-in/vắng/xác minh đều tải lại từ backend sau khi thành công."
        secondaryActions={
          <IconActionButton
            icon="refresh"
            label={loading ? 'Đang tải...' : 'Làm mới thủ công'}
            onClick={() => void loadAttendance()}
            disabled={loading || dialogSubmitting || scanSubmitting}
          />
        }
      />

      <CompactToolbar>
        <span className="muted">Room: {attendance?.room_code ?? `#${examSittingRoomId}`}</span>
        <span className="muted">Scanner mode: Barcode / Magstripe / QR Code</span>
        <span className="muted">QR_CCCD chưa hiển thị trên UI.</span>
      </CompactToolbar>

      {feedback ? (
        <p className={feedback.kind === 'success' ? 'success-message' : 'error'} style={{ marginBottom: 'var(--sp-3)' }}>
          {feedback.message}
        </p>
      ) : null}

      <CompactSurface tight title="Scan check-in" description="Dùng cho keyboard-wedge scanner. Không hiển thị lại raw scan sau khi gửi.">
      <form onSubmit={(event) => void handleScanSubmit(event)}>
        <div style={{ display: 'grid', gap: 'var(--sp-3)' }}>
          <div style={{ display: 'grid', gap: 'var(--sp-3)', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))' }}>
            <label style={{ display: 'grid', gap: 'var(--sp-1)' }}>
              <span>Phương thức scan</span>
              <select value={scanMethod} onChange={(event) => setScanMethod(event.target.value as ScanCheckInMethod)}>
                {SCAN_METHOD_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </select>
            </label>
            <label style={{ display: 'grid', gap: 'var(--sp-1)' }}>
              <span>Thiết bị scan</span>
              <input value={scanDeviceId} onChange={(event) => setScanDeviceId(event.target.value)} placeholder="scanner-desk-01" maxLength={255} />
            </label>
          </div>
          <label style={{ display: 'grid', gap: 'var(--sp-1)' }}>
            <span>Dữ liệu scan</span>
            <input
              ref={scanInputRef}
              value={scanInput}
              onChange={(event) => setScanInput(event.target.value)}
              placeholder="Quét mã rồi nhấn Enter"
              autoComplete="off"
              maxLength={2000}
            />
          </label>
          {scanError ? <p className="error" style={{ margin: 0 }}>{scanError}</p> : null}
          {scanSuccess ? <p className="success-message" style={{ margin: 0 }}>{scanSuccess}</p> : null}
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button type="submit" className="primary-button" disabled={scanSubmitting}>
              {scanSubmitting ? 'Đang scan...' : 'Scan check-in'}
            </button>
          </div>
        </div>
      </form>
      </CompactSurface>

      {error ? <ProctorErrorState message={error} onRetry={() => void loadAttendance()} /> : null}
      {loading ? <ProctorLoadingState message="Đang tải danh sách điểm danh..." /> : null}
      {!loading && !error && attendance && attendance.items.length === 0 ? (
        <ProctorEmptyState icon="🧾" message="Chưa có thí sinh nào trong danh sách điểm danh của phòng thi này." />
      ) : null}

      {!loading && !error && attendance && attendance.items.length > 0 ? (
        <CompactSurface tight title="Roster điểm danh" description="Table-first identity + trạng thái điểm danh/check-in/backend session.">
        <div className="table-shell">
          <div className="table-scroll">
            <table className="table table-compact">
              <thead>
                <tr>
                  <th>Ảnh</th>
                  <th>Mã SV</th>
                  <th>Họ tên</th>
                  <th>Máy</th>
                  <th>Điểm danh</th>
                  <th>Xác minh</th>
                  <th>Check-in</th>
                  <th>Verified</th>
                  <th>Phiên</th>
                  <th>Thao tác</th>
                </tr>
              </thead>
              <tbody>
                {attendance.items.map((item) => (
                  <tr key={item.exam_assignment_id}>
                    <td>
                      {item.photo_url ? (
                        <img
                          src={item.photo_url}
                          alt={`Ảnh ${item.student_code}`}
                          style={{ width: '36px', height: '36px', objectFit: 'cover', borderRadius: '10px' }}
                        />
                      ) : (
                        <span className="muted">{item.student_code.slice(0, 2).toUpperCase()}</span>
                      )}
                    </td>
                    <td>{item.student_code}</td>
                    <td>{item.full_name}</td>
                    <td>{item.station_code ?? '-'}</td>
                    <td>
                      <div style={{ display: 'grid', gap: 'var(--sp-1)' }}>
                        <ProctorStatusBadge kind="assignment" value={item.assignment_status} />
                        <span className="muted">{item.station_assignment_status ? <ProctorStatusBadge kind="station-assignment" value={item.station_assignment_status} /> : 'Không có'}</span>
                      </div>
                    </td>
                    <td>
                      <div style={{ display: 'grid', gap: 'var(--sp-1)' }}>
                        <span>{verificationStatusLabel(item.latest_verification_status)}</span>
                        <span className="muted">{verificationMethodLabel(item.latest_verification_method)}</span>
                      </div>
                    </td>
                    <td>
                      <div style={{ display: 'grid', gap: 'var(--sp-1)' }}>
                        <span>{formatDateTime(item.checked_in_at)}</span>
                        <span className="muted">By: {formatActorId(item.checked_in_by)}</span>
                      </div>
                    </td>
                    <td>
                      <div style={{ display: 'grid', gap: 'var(--sp-1)' }}>
                        <span>{formatDateTime(item.latest_verified_at)}</span>
                        <span className="muted">By: {formatActorId(item.latest_verified_by)}</span>
                      </div>
                    </td>
                    <td>
                      <div style={{ display: 'grid', gap: 'var(--sp-1)' }}>
                        <ProctorStatusBadge kind="session" value={item.session_status} />
                        <ProctorStatusBadge kind="submission" value={item.submission_status} />
                      </div>
                    </td>
                    <td>
                      <div style={{ display: 'grid', gap: 'var(--sp-2)' }}>
                        <PrimaryActionSlot>
                          {isEligibleForManualCheckIn(item) ? (
                            <button type="button" className="primary-button" onClick={() => setDialogState({ mode: 'check-in', item })}>
                              Check-in
                            </button>
                          ) : null}
                        </PrimaryActionSlot>
                        <RowActionGroup>
                          {isEligibleForMarkAbsent(item) ? (
                            <IconActionButton icon="x" label="Đánh dấu vắng" onClick={() => setDialogState({ mode: 'mark-absent', item })} />
                          ) : null}
                          {canVerifyIdentity(item) ? (
                            <IconActionButton icon="check" label="Xác minh danh tính" onClick={() => setDialogState({ mode: 'verify-identity', item })} />
                          ) : null}
                          {isValidStudentId(item.student_id) ? (
                            <IconActionButton
                              icon="x"
                              label="Thu hồi đăng nhập bị kẹt"
                              onClick={() => setSelectedCandidate(item)}
                            />
                          ) : null}
                        </RowActionGroup>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        </CompactSurface>
      ) : null}

      <AttendanceActionDialog
        state={dialogState}
        submitting={dialogSubmitting}
        error={dialogError}
        absentNote={absentNote}
        absentReasonCode={absentReasonCode}
        verifyStatus={verifyStatus}
        verifyMethod={verifyMethod}
        verifyNote={verifyNote}
        onClose={() => setDialogState(null)}
        onAbsentNoteChange={setAbsentNote}
        onAbsentReasonCodeChange={setAbsentReasonCode}
        onVerifyStatusChange={setVerifyStatus}
        onVerifyMethodChange={setVerifyMethod}
        onVerifyNoteChange={setVerifyNote}
        onConfirm={() => void handleConfirmDialogAction()}
      />

      <RevokeStaleSessionDialog
        isOpen={selectedCandidate !== null}
        examSittingRoomId={examSittingRoomId}
        studentId={selectedCandidate?.student_id ?? null}
        studentCode={selectedCandidate?.student_code ?? '-'}
        studentName={selectedCandidate?.full_name ?? '-'}
        onClose={() => setSelectedCandidate(null)}
        onCompleted={async () => {
          await loadAttendance();
        }}
      />
    </CompactPage>
  );
}
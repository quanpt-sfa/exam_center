import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { CompactPage } from '../../shared/components/compact/CompactPage';
import { CompactPageHeader } from '../../shared/components/compact/CompactPageHeader';
import { CompactStatBar } from '../../shared/components/compact/CompactStatBar';
import { CompactSurface } from '../../shared/components/compact/CompactSurface';
import { CompactToolbar } from '../../shared/components/compact/CompactToolbar';
import { IconActionButton } from '../../shared/components/compact/IconActionButton';
import type { ProctorClosePreflightResponse, ProctorCloseRoomBlocker, ProctorCloseRoomResponse } from './api/contracts';
import { closeProctorRoom, getProctorRoomClosePreflight } from './api/proctorApi';
import { ProctorErrorState } from './components/ProctorErrorState';
import { ProctorInvalidRoomState } from './components/ProctorInvalidRoomState';
import { ProctorLoadingState } from './components/ProctorLoadingState';
import { resolveExamSittingRoomId } from './proctorRoute';

function formatReadableToken(value: string): string {
  const normalized = String(value ?? '').trim();
  if (!normalized) {
    return 'Unknown';
  }
  return normalized.replace(/_/g, ' ');
}

function normalizeCloseStatus(value: string | null | undefined): string {
  return String(value ?? '').trim().toUpperCase();
}

function buildSafeCloseContext() {
  const randomId = typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID()
    : `close-${Date.now()}`;

  return {
    ui_source: 'proctor_close_room_page',
    client_request_id: randomId,
  };
}

function describeError(error: unknown): string {
  if (typeof error === 'object' && error !== null && 'message' in error) {
    const message = String((error as { message?: unknown }).message ?? 'Không thể hoàn tất thao tác đóng phòng.');
    const code = 'code' in error ? String((error as { code?: unknown }).code ?? '') : '';
    return code ? `${code}: ${message}` : message;
  }
  return error instanceof Error ? error.message : 'Không thể hoàn tất thao tác đóng phòng.';
}

function CloseBlockerList({ title, items, emptyMessage }: { title: string; items: ProctorCloseRoomBlocker[]; emptyMessage: string }) {
  return (
    <CompactSurface tight title={title}>
      {items.length === 0 ? <p className="muted">{emptyMessage}</p> : null}
      {items.length > 0 ? (
        <div style={{ display: 'grid', gap: 'var(--sp-3)' }}>
          {items.map((item, index) => (
            <article
              key={`${item.code}-${index}`}
              className="card"
              style={{
                margin: 0,
                backgroundColor: 'var(--surface-body)',
                borderColor: item.severity === 'warning' ? 'var(--clr-warning-light)' : 'var(--clr-danger-light)',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--sp-3)', flexWrap: 'wrap' }}>
                <div>
                  <h4 style={{ margin: '0 0 var(--sp-1) 0' }}>{item.message}</h4>
                  <p className="muted" style={{ margin: 0 }}>
                    Code: {formatReadableToken(item.code)} | Severity: {formatReadableToken(item.severity)}
                  </p>
                </div>
                <strong>{item.count}</strong>
              </div>
              {item.details && item.details.length > 0 ? (
                <ul style={{ margin: 'var(--sp-3) 0 0 1.25rem', padding: 0 }}>
                  {item.details.slice(0, 5).map((detail, detailIndex) => (
                    <li key={detailIndex}>
                      <span>{Object.entries(detail).map(([key, value]) => `${key}: ${String(value)}`).join(' | ')}</span>
                    </li>
                  ))}
                </ul>
              ) : null}
            </article>
          ))}
        </div>
      ) : null}
    </CompactSurface>
  );
}

function CloseConfirmationDialog({
  roomCode,
  closeNote,
  submitting,
  error,
  onClose,
  onConfirm,
}: {
  roomCode: string;
  closeNote: string;
  submitting: boolean;
  error: string | null;
  onClose: () => void;
  onConfirm: () => void;
}) {
  return (
    <div
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="close-room-dialog-title"
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
          <h2 id="close-room-dialog-title" style={{ margin: '0 0 var(--sp-2) 0' }}>Xác nhận đóng phòng thi</h2>
          <p className="muted" style={{ marginTop: 0 }}>
            Hành động này sẽ gọi backend close-room thật cho phòng {roomCode} và tải lại preflight sau khi hoàn tất.
          </p>
          <div className="card" style={{ margin: 0, background: 'var(--surface-body)' }}>
            <p style={{ margin: 0 }}><strong>Ghi chú đóng phòng:</strong> {closeNote.trim() || 'Không có ghi chú.'}</p>
          </div>
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
            {submitting ? 'Đang đóng phòng...' : 'Xác nhận đóng phòng'}
          </button>
        </footer>
      </div>
    </div>
  );
}

export function ProctorCloseRoomPage() {
  const params = useParams<{ examSittingRoomId: string }>();
  const routeExamSittingRoomId = params.examSittingRoomId;
  const roomIdResolution = resolveExamSittingRoomId(routeExamSittingRoomId);
  const examSittingRoomId = roomIdResolution.isValid ? roomIdResolution.examSittingRoomId : null;
  const [preflight, setPreflight] = useState<ProctorClosePreflightResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [closeNote, setCloseNote] = useState('');
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [closeResult, setCloseResult] = useState<ProctorCloseRoomResponse | null>(null);

  async function loadPreflight() {
    if (examSittingRoomId === null) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setPreflight(await getProctorRoomClosePreflight(examSittingRoomId));
    } catch (loadError) {
      setPreflight(null);
      setError(describeError(loadError));
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
    void loadPreflight();
  }, [examSittingRoomId, routeExamSittingRoomId]);

  if (!roomIdResolution.isValid || examSittingRoomId === null) {
    return (
      <CompactPage data-testid="proctor-close-room-page">
        <ProctorInvalidRoomState message={roomIdResolution.errorMessage} />
      </CompactPage>
    );
  }

  const roomCode = preflight?.room_code ?? `#${examSittingRoomId}`;
  const normalizedRoomStatus = normalizeCloseStatus(preflight?.room_status);
  const alreadyClosed = normalizedRoomStatus === 'CLOSED' || closeResult?.status === 'already_closed';
  const canClose = Boolean(preflight?.can_close) && normalizedRoomStatus !== 'CLOSED';

  async function handleConfirmClose() {
    if (examSittingRoomId === null || preflight === null || submitting || !canClose) {
      return;
    }

    setSubmitting(true);
    setSubmitError(null);
    try {
      const result = await closeProctorRoom(examSittingRoomId, {
        close_note: closeNote.trim() || null,
        confirm_no_blockers: true,
        context_json: buildSafeCloseContext(),
      });
      setCloseResult(result);
      setConfirmOpen(false);
      await loadPreflight();
    } catch (mutationError) {
      setCloseResult(null);
      setSubmitError(describeError(mutationError));
      setConfirmOpen(false);
      await loadPreflight();
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <CompactPage data-testid="proctor-close-room-page">
      <CompactPageHeader
        eyebrow="Proctor Portal"
        title={`Close Room ${roomCode}`}
        description="Đóng phòng thi theo preflight và mutation do backend quyết định. Giao diện không suy diễn điều kiện đóng phòng."
        secondaryActions={
          <IconActionButton
            icon="refresh"
            label={loading ? 'Đang tải...' : 'Làm mới preflight'}
            onClick={() => void loadPreflight()}
            disabled={loading || submitting}
          />
        }
      />

      <CompactToolbar>
        <span className="muted">Room status: {preflight?.room_status ?? '-'}</span>
        <span className="muted">Can close: {preflight?.can_close ? 'Yes' : 'No'}</span>
        <span className="muted">Generated at: {preflight?.generated_at ?? '-'}</span>
      </CompactToolbar>

      {closeResult ? (
        <CompactSurface tight title="Kết quả đóng phòng">
          <p style={{ margin: '0 0 var(--sp-2) 0' }}><strong>Trạng thái:</strong> {formatReadableToken(closeResult.status)}</p>
          <p style={{ margin: '0 0 var(--sp-2) 0' }}><strong>Trạng thái mới:</strong> {formatReadableToken(closeResult.new_status)}</p>
          <p className="muted" style={{ margin: 0 }}>
            {closeResult.closed_at ? `Đóng lúc ${closeResult.closed_at}` : 'Backend chưa trả về thời điểm đóng phòng.'}
          </p>
        </CompactSurface>
      ) : null}

      {submitError ? <ProctorErrorState title="Không đóng được phòng" message={submitError} onRetry={() => void loadPreflight()} retryLabel="Tải lại preflight" /> : null}

      {loading ? <ProctorLoadingState message="Đang tải close preflight..." /> : null}

      {!loading && error ? <ProctorErrorState title="Không tải được close preflight" message={error} onRetry={() => void loadPreflight()} /> : null}

      {!loading && !error && preflight ? (
        <div style={{ display: 'grid', gap: 'var(--sp-4)' }}>
          <CompactSurface tight title="Tóm tắt trạng thái phòng">
            <dl style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 'var(--sp-3)', margin: 0 }}>
              <div>
                <dt className="muted">Room status</dt>
                <dd style={{ margin: 0 }}>{preflight.room_status}</dd>
              </div>
              <div>
                <dt className="muted">Can close</dt>
                <dd style={{ margin: 0 }}>{preflight.can_close ? 'Yes' : 'No'}</dd>
              </div>
              <div>
                <dt className="muted">Generated at</dt>
                <dd style={{ margin: 0 }}>{preflight.generated_at}</dd>
              </div>
              <div>
                <dt className="muted">Room code</dt>
                <dd style={{ margin: 0 }}>{roomCode}</dd>
              </div>
            </dl>
          </CompactSurface>

          <CompactSurface tight title="Counts from backend">
            <CompactStatBar
              items={[
                { label: 'Total assignments', value: preflight.counts.total_assignments },
                { label: 'Checked in', value: preflight.counts.checked_in_count },
                { label: 'Absent', value: preflight.counts.absent_count },
                { label: 'Pending attendance', value: preflight.counts.pending_attendance_count },
                { label: 'Open incidents', value: preflight.counts.open_incident_count },
                { label: 'Incidents in progress', value: preflight.counts.in_progress_incident_count },
                { label: 'Active sessions', value: preflight.counts.active_session_count },
                { label: 'Interrupted sessions', value: preflight.counts.interrupted_session_count },
                { label: 'Pending submissions', value: preflight.counts.pending_submission_count },
                { label: 'Stale heartbeats', value: preflight.counts.stale_heartbeat_count },
              ]}
            />
          </CompactSurface>

          <CloseBlockerList title="Blockers" items={preflight.blockers} emptyMessage="Không có blocker nào từ backend." />
          <CloseBlockerList title="Warnings" items={preflight.warnings} emptyMessage="Không có warning nào từ backend." />

          <CompactSurface tight title="Đóng phòng thi">
            {alreadyClosed ? <p className="muted">Phòng này đã ở trạng thái CLOSED. Giao diện chỉ hiển thị thông tin đọc.</p> : null}
            {!alreadyClosed && !preflight.can_close ? <p className="muted">Backend hiện không cho phép đóng phòng này. Vui lòng xử lý các blocker trước.</p> : null}
            <label style={{ display: 'grid', gap: 'var(--sp-1)', marginBottom: 'var(--sp-3)' }}>
              <span>Close note</span>
              <textarea
                rows={4}
                value={closeNote}
                onChange={(event) => setCloseNote(event.target.value)}
                placeholder="Ghi chú đóng phòng nếu cần"
                disabled={submitting || alreadyClosed}
              />
            </label>
            {canClose ? (
              <button type="button" className="primary-button" onClick={() => setConfirmOpen(true)} disabled={submitting}>
                {submitting ? 'Đang đóng phòng...' : 'Close Room'}
              </button>
            ) : (
              <button type="button" className="secondary-button" disabled>
                Close Room unavailable
              </button>
            )}
          </CompactSurface>
        </div>
      ) : null}

      {confirmOpen && preflight ? (
        <CloseConfirmationDialog
          roomCode={roomCode}
          closeNote={closeNote}
          submitting={submitting}
          error={submitError}
          onClose={() => {
            if (!submitting) {
              setConfirmOpen(false);
            }
          }}
          onConfirm={() => void handleConfirmClose()}
        />
      ) : null}
    </CompactPage>
  );
}
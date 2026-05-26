import { useEffect, useState } from 'react';
import { revokeStudentStaleSession } from '../api/proctorApi';

type RevokeStaleSessionDialogProps = {
  isOpen: boolean;
  examSittingRoomId: number;
  studentId: number | null;
  studentCode: string;
  studentName: string;
  onClose: () => void;
  onCompleted: () => Promise<void> | void;
};

export function RevokeStaleSessionDialog({
  isOpen,
  examSittingRoomId,
  studentId,
  studentCode,
  studentName,
  onClose,
  onCompleted,
}: RevokeStaleSessionDialogProps) {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resultMessage, setResultMessage] = useState<string | null>(null);
  const [completedStatus, setCompletedStatus] = useState<'revoked' | 'no_active_session' | null>(null);

  useEffect(() => {
    if (!isOpen) {
      setSubmitting(false);
      setError(null);
      setResultMessage(null);
      setCompletedStatus(null);
    }
  }, [isOpen]);

  if (!isOpen) {
    return null;
  }

  async function handleConfirm() {
    if (submitting || completedStatus !== null || studentId === null || !Number.isFinite(examSittingRoomId) || examSittingRoomId <= 0) {
      return;
    }

    setSubmitting(true);
    setError(null);
    setResultMessage(null);

    try {
      const result = await revokeStudentStaleSession(examSittingRoomId, studentId);
      if (result.status === 'no_active_session') {
        setResultMessage('Sinh viên hiện không có phiên đăng nhập đang hoạt động.');
      } else {
        setResultMessage('Đã thu hồi phiên đăng nhập bị kẹt.');
      }
      setCompletedStatus(result.status);
      await onCompleted();
    } catch (revokeError) {
      setError(revokeError instanceof Error ? revokeError.message : 'Không thể thu hồi phiên đăng nhập lúc này.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="revoke-session-title"
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
          maxWidth: '520px',
          backgroundColor: 'var(--surface-card)',
          borderRadius: 'var(--radius-lg)',
          boxShadow: 'var(--shadow-xl)',
          border: '1px solid var(--clr-gray-200)',
          overflow: 'hidden',
        }}
      >
        <div style={{ padding: 'var(--sp-5)' }}>
          <h2 id="revoke-session-title" style={{ margin: '0 0 var(--sp-2) 0' }}>Thu hồi phiên đăng nhập bị kẹt</h2>
          <p className="muted" style={{ marginBottom: 'var(--sp-3)' }}>
            Thao tác này thu hồi phiên đăng nhập đang hoạt động của sinh viên trong phòng thi này. Sinh viên sẽ cần đăng nhập lại.
          </p>
          <div className="card" style={{ margin: 0, background: 'var(--surface-body)' }}>
            <p style={{ margin: 0 }}><strong>Mã sinh viên:</strong> {studentCode || '-'}</p>
            <p style={{ margin: 'var(--sp-2) 0 0 0' }}><strong>Họ tên:</strong> {studentName || '-'}</p>
          </div>
          {studentId === null ? <p className="error" style={{ marginTop: 'var(--sp-3)' }}>Không có định danh sinh viên hợp lệ để thu hồi phiên.</p> : null}
          {error ? <p className="error" style={{ marginTop: 'var(--sp-3)' }}>{error}</p> : null}
          {resultMessage ? <p className="success-message" style={{ marginTop: 'var(--sp-3)' }}>{resultMessage}</p> : null}
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
          <button type="button" className="secondary-button" onClick={onClose} disabled={submitting}>
            {completedStatus ? 'Đóng' : 'Hủy'}
          </button>
          <button type="button" className="primary-button" onClick={() => void handleConfirm()} disabled={submitting || completedStatus !== null || studentId === null}>
            {submitting ? 'Đang thu hồi...' : 'Thu hồi phiên'}
          </button>
        </footer>
      </div>
    </div>
  );
}
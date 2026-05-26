import { useEffect } from 'react';

type ConfirmDialogProps = {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: 'primary' | 'danger' | 'warning';
};

export function ConfirmDialog({
  isOpen,
  onClose,
  onConfirm,
  title,
  message,
  confirmLabel = 'Xác nhận',
  cancelLabel = 'Hủy',
  variant = 'primary',
}: ConfirmDialogProps) {
  // Listen for Escape key to close
  useEffect(() => {
    if (!isOpen) return;

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        onClose();
      }
    }

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  let confirmBtnBg = 'var(--clr-primary-600)';
  let confirmBtnHoverBg = 'var(--clr-primary-700)';

  if (variant === 'danger') {
    confirmBtnBg = 'var(--clr-danger)';
    confirmBtnHoverBg = 'var(--clr-danger-hover, #be123c)';
  } else if (variant === 'warning') {
    confirmBtnBg = 'var(--clr-warning)';
    confirmBtnHoverBg = 'var(--clr-warning-hover, #b45309)';
  }

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 200,
        padding: 'var(--sp-4)',
      }}
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="confirm-title"
      aria-describedby="confirm-message"
    >
      {/* Backdrop overlay */}
      <div
        onClick={onClose}
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(15, 23, 42, 0.4)',
          backdropFilter: 'blur(1px)',
        }}
      />

      {/* Dialog Body */}
      <div
        style={{
          position: 'relative',
          width: '100%',
          maxWidth: '440px',
          backgroundColor: 'var(--surface-card)',
          borderRadius: 'var(--radius-lg)',
          boxShadow: 'var(--shadow-xl)',
          border: '1px solid var(--clr-gray-250, #e2e8f0)',
          display: 'flex',
          flexDirection: 'column',
          zIndex: 201,
          animation: 'dialogFadeIn 0.2s cubic-bezier(0.16, 1, 0.3, 1) forwards',
        }}
      >
        <style dangerouslySetInnerHTML={{ __html: `
          @keyframes dialogFadeIn {
            from { opacity: 0; transform: scale(0.95); }
            to { opacity: 1; transform: scale(1); }
          }
        `}} />

        <div style={{ padding: 'var(--sp-5)' }}>
          <h2
            id="confirm-title"
            style={{
              margin: '0 0 var(--sp-2) 0',
              fontSize: 'var(--text-lg)',
              fontWeight: 'var(--fw-bold)',
              color: 'var(--text-primary)',
            }}
          >
            {title}
          </h2>
          <p
            id="confirm-message"
            style={{
              margin: 0,
              fontSize: 'var(--text-sm)',
              color: 'var(--text-secondary)',
              lineHeight: 'var(--leading-relaxed)',
            }}
          >
            {message}
          </p>
        </div>

        {/* Dialog Actions footer */}
        <footer
          style={{
            display: 'flex',
            justifyContent: 'flex-end',
            gap: 'var(--sp-2)',
            padding: 'var(--sp-3) var(--sp-5)',
            backgroundColor: 'var(--surface-body)',
            borderTop: '1px solid var(--clr-gray-200)',
            borderBottomLeftRadius: 'var(--radius-lg)',
            borderBottomRightRadius: 'var(--radius-lg)',
          }}
        >
          <button
            type="button"
            className="secondary-button"
            onClick={onClose}
            style={{ minWidth: '80px' }}
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            className="primary-button"
            onClick={() => {
              onConfirm();
              onClose();
            }}
            style={{
              backgroundColor: confirmBtnBg,
              color: '#fff',
              minWidth: '100px',
              border: 'none',
            }}
          >
            {confirmLabel}
          </button>
        </footer>
      </div>
    </div>
  );
}

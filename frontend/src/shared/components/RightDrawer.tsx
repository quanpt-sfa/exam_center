import { useEffect } from 'react';

type RightDrawerProps = {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  size?: 'sm' | 'md' | 'lg';
};

export function RightDrawer({ isOpen, onClose, title, children, size = 'md' }: RightDrawerProps) {
  // Listen for Escape key
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

  const widthMap = {
    sm: '360px',
    md: '540px',
    lg: '720px',
  };

  const drawerWidth = widthMap[size];

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        display: 'flex',
        justifyContent: 'flex-end',
        zIndex: 100,
      }}
      role="dialog"
      aria-modal="true"
      aria-label={title}
    >
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(15, 23, 42, 0.4)',
          backdropFilter: 'blur(2px)',
          transition: 'opacity 0.2s ease-in-out',
        }}
      />

      {/* Drawer Body */}
      <div
        style={{
          position: 'relative',
          width: '100%',
          maxWidth: drawerWidth,
          height: '100%',
          backgroundColor: 'var(--surface-card)',
          boxShadow: '-4px 0 24px rgba(15, 23, 42, 0.15)',
          display: 'flex',
          flexDirection: 'column',
          zIndex: 101,
          animation: 'drawerSlideIn 0.25s cubic-bezier(0.16, 1, 0.3, 1) forwards',
        }}
      >
        {/* Style block for local drawer slide-in animation */}
        <style dangerouslySetInnerHTML={{ __html: `
          @keyframes drawerSlideIn {
            from { transform: translateX(100%); }
            to { transform: translateX(0); }
          }
        `}} />

        {/* Drawer Header */}
        <header
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: 'var(--sp-4) var(--sp-5)',
            borderBottom: '1px solid var(--clr-gray-200)',
          }}
        >
          <h2
            style={{
              margin: 0,
              fontSize: 'var(--text-lg)',
              fontWeight: 'var(--fw-bold)',
              color: 'var(--text-primary)',
            }}
          >
            {title}
          </h2>
          <button
            type="button"
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              fontSize: 'var(--text-lg)',
              cursor: 'pointer',
              color: 'var(--text-secondary)',
              padding: 'var(--sp-1)',
              borderRadius: 'var(--radius-md)',
              lineHeight: 1,
            }}
            aria-label="Đóng ngăn chứa"
          >
            ✕
          </button>
        </header>

        {/* Drawer Scrollable Content */}
        <div
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: 'var(--sp-5)',
          }}
        >
          {children}
        </div>
      </div>
    </div>
  );
}

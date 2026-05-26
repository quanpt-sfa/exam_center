import type { CurrentUser } from '../features/auth/authApi';

type StudentExamLayoutProps = {
  user: CurrentUser | null;
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
  children: React.ReactNode;
};

export function StudentExamLayout({ user, theme, onToggleTheme, children }: StudentExamLayoutProps) {
  return (
    <div className="app-shell" style={{ flexDirection: 'column', minHeight: '100vh', background: 'var(--surface-body)' }}>
      {/* Distraction-minimized Exam Topbar */}
      <header
        className="topbar"
        style={{
          left: 0,
          position: 'sticky',
          background: 'var(--surface-card)',
          borderBottom: '1px solid var(--clr-gray-200)',
          display: 'flex',
          alignItems: 'center',
          padding: '0 var(--sp-4)',
          height: 'var(--topbar-height)',
          justifyContent: 'space-between',
        }}
        role="banner"
      >
        {/* Left Side: Connection Status dot + Brand/Mode */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-2)' }}>
          <span
            style={{
              height: '8px',
              width: '8px',
              borderRadius: '50%',
              background: 'var(--clr-success)',
              display: 'inline-block',
            }}
            title="Đang trực tuyến"
          />
          <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', fontWeight: 'var(--fw-medium)' }}>
            HỆ THỐNG THI TRỰC TUYẾN
          </span>
        </div>

        {/* Right Side: Theme Toggle & Compact Student Identity Display */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-4)' }}>
          <button
            type="button"
            className="topbar__action-link topbar__theme-toggle"
            onClick={onToggleTheme}
            title="Đổi giao diện"
          >
            {theme === 'light' ? '🌙' : '☀️'}
          </button>

          {user && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--sp-2)',
                padding: 'var(--sp-1) var(--sp-3)',
                borderRadius: 'var(--radius-full)',
                background: 'var(--clr-gray-100)',
                fontSize: 'var(--text-sm)',
              }}
            >
              <div
                style={{
                  width: '24px',
                  height: '24px',
                  borderRadius: '50%',
                  background: 'var(--clr-primary-100)',
                  color: 'var(--clr-primary-700)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontWeight: 'var(--fw-semibold)',
                  fontSize: 'var(--text-xs)',
                }}
              >
                👤
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.1 }}>
                <span style={{ fontWeight: 'var(--fw-semibold)' }}>{user.display_name || user.username}</span>
                <span style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>SV ID: {user.user_id}</span>
              </div>
            </div>
          )}
        </div>
      </header>

      {/* Main Distraction-free Content */}
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        {children}
      </main>
    </div>
  );
}

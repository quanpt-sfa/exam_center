import { useState } from 'react';
import type { CurrentUser } from '../features/auth/authApi';
import { Sidebar } from '../app/Sidebar';
import { Topbar } from '../app/Topbar';

type AdminLayoutProps = {
  user: CurrentUser | null;
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
  onLogout: () => void;
  children: React.ReactNode;
};

export function AdminLayout({ user, theme, onToggleTheme, onLogout, children }: AdminLayoutProps) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  return (
    <div className="app-shell">
      <Sidebar
        user={user}
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed((c) => !c)}
      />

      <div className={`app-main${sidebarCollapsed ? ' sidebar-collapsed' : ''}`}>
        <Topbar
          user={user}
          theme={theme}
          onToggleSidebar={() => setSidebarCollapsed((c) => !c)}
          onToggleTheme={onToggleTheme}
          onLogout={onLogout}
        />
        <main className="main-content">
          {children}
        </main>
      </div>
    </div>
  );
}

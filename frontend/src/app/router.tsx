import { lazy, Suspense, useEffect, useState, type ReactNode } from 'react';
import { BrowserRouter, Link, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { LoginPage } from '../features/auth/LoginPage';
import { ChangePasswordPage } from '../features/auth/ChangePasswordPage';
import { getCurrentUser, logout, type CurrentUser } from '../features/auth/authApi';
import { clearAuthTokens, getAccessToken, getRefreshToken } from '../shared/auth/tokenStorage';
import { AdminLayout } from '../layouts/AdminLayout';
import { StudentPortalLayout } from '../layouts/StudentPortalLayout';
import { StudentExamLayout } from '../layouts/StudentExamLayout';
import { Sidebar } from './Sidebar';
import { Topbar } from './Topbar';

const AccountAdminPage = lazy(() => import('../features/accounts/AccountAdminPage').then((module) => ({ default: module.AccountAdminPage })));
const SettingsPage = lazy(() => import('../features/settings/SettingsPage').then((module) => ({ default: module.SettingsPage })));
const DashboardPage = lazy(() => import('../features/dashboard/DashboardPage').then((module) => ({ default: module.DashboardPage })));
const ExamListPage = lazy(() => import('../features/examTaking/ExamListPage').then((module) => ({ default: module.ExamListPage })));
const ExamSetupPage = lazy(() => import('../features/examSetup/ExamSetupPage').then((module) => ({ default: module.ExamSetupPage })));
const ExamSetupLandingPage = lazy(() => import('../features/examSetup/ExamSetupLandingPage').then((module) => ({ default: module.ExamSetupLandingPage })));
const ExamAuthoringPage = lazy(() => import('../features/examSetup/authoring/ExamAuthoringPage').then((module) => ({ default: module.ExamAuthoringPage })));
const DeliverySetupPage = lazy(() => import('../features/examSetup/delivery/DeliverySetupPage').then((module) => ({ default: module.DeliverySetupPage })));
const ExamTakingPage = lazy(() => import('../features/examTaking/ExamTakingPage').then((module) => ({ default: module.ExamTakingPage })));
const MasterDataPage = lazy(() => import('../features/masterData/MasterDataPage').then((module) => ({ default: module.MasterDataPage })));
const AcademicMasterDataPage = lazy(() => import('../features/masterData/academic/AcademicMasterDataPage').then((module) => ({ default: module.AcademicMasterDataPage })));
const PeopleMasterDataPage = lazy(() => import('../features/masterData/people/PeopleMasterDataPage').then((module) => ({ default: module.PeopleMasterDataPage })));
const FacilityPage = lazy(() => import('../features/facility/FacilityPage').then((module) => ({ default: module.FacilityPage })));
const ImportCenterPage = lazy(() => import('../features/imports/ImportCenterPage').then((module) => ({ default: module.ImportCenterPage })));
const SubmissionProcessingResultPage = lazy(() =>
  import('../features/submissionProcessing/SubmissionProcessingResultPage').then((module) => ({ default: module.SubmissionProcessingResultPage }))
);
const ProctorAttendancePage = lazy(() => import('../features/proctor/ProctorAttendancePage').then((module) => ({ default: module.ProctorAttendancePage })));
const ProctorCloseRoomPage = lazy(() => import('../features/proctor/ProctorCloseRoomPage').then((module) => ({ default: module.ProctorCloseRoomPage })));
const ProctorIncidentsPage = lazy(() => import('../features/proctor/ProctorIncidentsPage').then((module) => ({ default: module.ProctorIncidentsPage })));
const ProctorLivePage = lazy(() => import('../features/proctor/ProctorLivePage').then((module) => ({ default: module.ProctorLivePage })));
const ProctorRoomWorkspacePage = lazy(() => import('../features/proctor/ProctorRoomWorkspacePage').then((module) => ({ default: module.ProctorRoomWorkspacePage })));
const ProctorSittingsPage = lazy(() => import('../features/proctor/ProctorSittingsPage').then((module) => ({ default: module.ProctorSittingsPage })));
const GradebookPage = lazy(() => import('../features/gradebook/GradebookPage').then((module) => ({ default: module.GradebookPage })));
const GradebookSubmissionDetailPage = lazy(() =>
  import('../features/gradebook/GradebookSubmissionDetailPage').then((module) => ({ default: module.GradebookSubmissionDetailPage }))
);

function RouteSuspense({ children }: { children: ReactNode }) {
  return <Suspense fallback={<p className="muted">Đang tải trang...</p>}>{children}</Suspense>;
}

type MenuItem = {
  label: string;
  path: string;
  roles?: string[];
  permissions?: string[];
};

function normalizeRole(role: string): string {
  return role.trim().toUpperCase();
}

function canShowMenuItem(item: MenuItem, user: CurrentUser): boolean {
  const userRoles = new Set(user.roles.map(normalizeRole));
  const userPermissions = new Set((user.permissions ?? []).map((permission) => permission.trim()));

  const roleAllowed = !item.roles || item.roles.some((role) => userRoles.has(normalizeRole(role)));
  const permissionAllowed =
    !item.permissions || item.permissions.length === 0 || item.permissions.some((permission) => userPermissions.has(permission));

  if (item.roles && item.permissions) {
    return roleAllowed || permissionAllowed;
  }

  return roleAllowed && permissionAllowed;
}

function AccessDenied() {
  return (
    <section className="card">
      <h2>Không có quyền truy cập</h2>
      <p className="muted">Tài khoản hiện tại không có quyền mở trang này.</p>
      <Link to="/dashboard">Quay lại dashboard</Link>
    </section>
  );
}

function RequireAuth({
  children,
  user,
  loading,
  authError,
  roles,
  permissions,
}: {
  children: React.ReactNode;
  user: CurrentUser | null;
  loading: boolean;
  authError?: string | null;
  roles?: string[];
  permissions?: string[];
}) {
  if (!getAccessToken() && !getRefreshToken()) {
    return <Navigate to="/login" replace />;
  }

  if (loading) {
    return <p className="muted">Đang kiểm tra phiên đăng nhập...</p>;
  }

  if (authError) {
    return (
      <section className="card">
        <h2>Không tải được phiên đăng nhập</h2>
        <p className="error">{authError}</p>
        <Link to="/login">Quay lại đăng nhập</Link>
      </section>
    );
  }

  if (!user) {
    return <p className="muted">Đang kiểm tra phiên đăng nhập...</p>;
  }

  if (!canShowMenuItem({ label: 'route', path: '', roles, permissions }, user)) {
    return <AccessDenied />;
  }

  return <>{children}</>;
}

function AppRoutes({
  user,
  authLoading,
  authError,
}: {
  user: CurrentUser | null;
  authLoading: boolean;
  authError: string | null;
}) {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/dashboard"
        element={
          <RequireAuth user={user} loading={authLoading} authError={authError}>
            <RouteSuspense>
              <DashboardPage />
            </RouteSuspense>
          </RequireAuth>
        }
      />
      <Route
        path="/change-password"
        element={
          <RequireAuth user={user} loading={authLoading} authError={authError}>
            <RouteSuspense>
              <ChangePasswordPage />
            </RouteSuspense>
          </RequireAuth>
        }
      />
      <Route
        path="/admin/dashboard"
        element={
          <RequireAuth user={user} loading={authLoading} authError={authError} roles={['ADMIN']}>
            <Navigate to="/dashboard" replace />
          </RequireAuth>
        }
      />
      <Route
        path="/admin/accounts"
        element={
          <RequireAuth user={user} loading={authLoading} authError={authError} roles={['ADMIN']}>
            <RouteSuspense>
              <AccountAdminPage />
            </RouteSuspense>
          </RequireAuth>
        }
      />
      <Route
        path="/admin/settings"
        element={
          <RequireAuth user={user} loading={authLoading} authError={authError} roles={['ADMIN']}>
            <RouteSuspense>
              <SettingsPage />
            </RouteSuspense>
          </RequireAuth>
        }
      />
      <Route
        path="/admin/subjects"
        element={
          <RequireAuth user={user} loading={authLoading} authError={authError} roles={['ADMIN']} permissions={['master_data:read', 'master_data:write']}>
            <Navigate to="/admin/master-data/academic" replace />
          </RequireAuth>
        }
      />
      <Route
        path="/admin/exam-setup"
        element={
          <RequireAuth user={user} loading={authLoading} authError={authError} roles={['ADMIN']} permissions={['master_data:read', 'delivery:manage']}>
            <RouteSuspense>
              <ExamSetupLandingPage />
            </RouteSuspense>
          </RequireAuth>
        }
      />
      <Route
        path="/admin/exam-setup/authoring"
        element={
          <RequireAuth user={user} loading={authLoading} authError={authError} roles={['ADMIN']} permissions={['master_data:read', 'delivery:manage']}>
            <RouteSuspense>
              <ExamAuthoringPage />
            </RouteSuspense>
          </RequireAuth>
        }
      />
      <Route
        path="/admin/exam-setup/delivery"
        element={
          <RequireAuth user={user} loading={authLoading} authError={authError} roles={['ADMIN']} permissions={['master_data:read', 'delivery:manage']}>
            <RouteSuspense>
              <DeliverySetupPage />
            </RouteSuspense>
          </RequireAuth>
        }
      />
      <Route
        path="/admin/master-data"
        element={
          <RequireAuth user={user} loading={authLoading} authError={authError} roles={['ADMIN']} permissions={['master_data:read', 'master_data:write']}>
            <RouteSuspense>
              <MasterDataPage />
            </RouteSuspense>
          </RequireAuth>
        }
      />
      <Route
        path="/admin/master-data/academic"
        element={
          <RequireAuth user={user} loading={authLoading} authError={authError} roles={['ADMIN']} permissions={['master_data:read', 'master_data:write']}>
            <RouteSuspense>
              <AcademicMasterDataPage />
            </RouteSuspense>
          </RequireAuth>
        }
      />
      <Route
        path="/admin/master-data/people"
        element={
          <RequireAuth user={user} loading={authLoading} authError={authError} roles={['ADMIN']} permissions={['master_data:read', 'master_data:write']}>
            <RouteSuspense>
              <PeopleMasterDataPage />
            </RouteSuspense>
          </RequireAuth>
        }
      />
      <Route
        path="/admin/facility"
        element={
          <RequireAuth user={user} loading={authLoading} authError={authError} roles={['ADMIN']} permissions={['master_data:read', 'master_data:write']}>
            <RouteSuspense>
              <FacilityPage />
            </RouteSuspense>
          </RequireAuth>
        }
      />
      <Route
        path="/admin/imports"
        element={
          <RequireAuth user={user} loading={authLoading} authError={authError} roles={['ADMIN']} permissions={['master_data:read', 'master_data:write']}>
            <RouteSuspense>
              <ImportCenterPage />
            </RouteSuspense>
          </RequireAuth>
        }
      />
      <Route
        path="/master-data"
        element={
          <RequireAuth user={user} loading={authLoading} authError={authError} roles={['ADMIN']} permissions={['master_data:read', 'master_data:write']}>
            <Navigate to="/admin/master-data" replace />
          </RequireAuth>
        }
      />
      <Route
        path="/exams"
        element={
          <RequireAuth user={user} loading={authLoading} authError={authError} roles={['STUDENT', 'SV', 'SINHVIEN']}>
            <RouteSuspense>
              <ExamListPage />
            </RouteSuspense>
          </RequireAuth>
        }
      />
      <Route
        path="/exams/:id"
        element={
          <RequireAuth user={user} loading={authLoading} authError={authError} roles={['STUDENT', 'SV', 'SINHVIEN']}>
            <RouteSuspense>
              <ExamTakingPage />
            </RouteSuspense>
          </RequireAuth>
        }
      />
      <Route
        path="/submissions/:examSubmissionId/result"
        element={
          <RequireAuth user={user} loading={authLoading} authError={authError}>
            <RouteSuspense>
              <SubmissionProcessingResultPage />
            </RouteSuspense>
          </RequireAuth>
        }
      />
      <Route
        path="/proctor/sittings"
        element={
          <RequireAuth user={user} loading={authLoading} authError={authError} roles={['PROCTOR', 'ADMIN']}>
            <RouteSuspense>
              <ProctorSittingsPage />
            </RouteSuspense>
          </RequireAuth>
        }
      />
      <Route
        path="/proctor/sitting-rooms/:examSittingRoomId"
        element={
          <RequireAuth user={user} loading={authLoading} authError={authError} roles={['PROCTOR', 'ADMIN']}>
            <RouteSuspense>
              <ProctorRoomWorkspacePage />
            </RouteSuspense>
          </RequireAuth>
        }
      />
      <Route
        path="/proctor/sitting-rooms/:examSittingRoomId/attendance"
        element={
          <RequireAuth user={user} loading={authLoading} authError={authError} roles={['PROCTOR', 'ADMIN']}>
            <RouteSuspense>
              <ProctorAttendancePage />
            </RouteSuspense>
          </RequireAuth>
        }
      />
      <Route
        path="/proctor/sitting-rooms/:examSittingRoomId/live"
        element={
          <RequireAuth user={user} loading={authLoading} authError={authError} roles={['PROCTOR', 'ADMIN']}>
            <RouteSuspense>
              <ProctorLivePage />
            </RouteSuspense>
          </RequireAuth>
        }
      />
      <Route
        path="/proctor/sitting-rooms/:examSittingRoomId/incidents"
        element={
          <RequireAuth user={user} loading={authLoading} authError={authError} roles={['PROCTOR', 'ADMIN']}>
            <RouteSuspense>
              <ProctorIncidentsPage />
            </RouteSuspense>
          </RequireAuth>
        }
      />
      <Route
        path="/proctor/sitting-rooms/:examSittingRoomId/close"
        element={
          <RequireAuth user={user} loading={authLoading} authError={authError} roles={['PROCTOR', 'ADMIN']}>
            <RouteSuspense>
              <ProctorCloseRoomPage />
            </RouteSuspense>
          </RequireAuth>
        }
      />
      <Route
        path="/proctor/*"
        element={
          <RequireAuth user={user} loading={authLoading} authError={authError} roles={['PROCTOR', 'ADMIN']}>
            <Navigate to="/proctor/sittings" replace />
          </RequireAuth>
        }
      />
      <Route
        path="/grading/gradebook"
        element={
          <RequireAuth user={user} loading={authLoading} authError={authError} roles={['ADMIN', 'ACADEMIC_OFFICER', 'INSTRUCTOR']}>
            <RouteSuspense>
              <GradebookPage />
            </RouteSuspense>
          </RequireAuth>
        }
      />
      <Route
        path="/grading/gradebook/submissions/:submissionId"
        element={
          <RequireAuth user={user} loading={authLoading} authError={authError} roles={['ADMIN', 'ACADEMIC_OFFICER', 'INSTRUCTOR']}>
            <RouteSuspense>
              <GradebookSubmissionDetailPage />
            </RouteSuspense>
          </RequireAuth>
        }
      />
    </Routes>
  );
}

type RouteLayout = 'blank' | 'student-exam' | 'student-portal' | 'admin';
type AuthPolicy = 'public' | 'required';

type RouteMeta = {
  layout: RouteLayout;
  auth: AuthPolicy;
};

function getRouteMeta(pathname: string): RouteMeta {
  if (pathname === '/' || pathname === '/login') {
    return { layout: 'blank', auth: 'public' };
  }

  if (pathname === '/change-password') {
    return { layout: 'blank', auth: 'required' };
  }

  if (/^\/exams\/[^/]+/.test(pathname)) {
    return { layout: 'student-exam', auth: 'required' };
  }

  if (pathname === '/exams') {
    return { layout: 'student-portal', auth: 'required' };
  }

  return { layout: 'admin', auth: 'required' };
}

function AppShell() {
  const location = useLocation();
  const navigate = useNavigate();
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [authLoading, setAuthLoading] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    const saved = localStorage.getItem('theme');
    if (saved === 'light' || saved === 'dark') {
      return saved;
    }
    return typeof window !== 'undefined' && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  function handleToggleTheme() {
    setTheme((t) => (t === 'light' ? 'dark' : 'light'));
  }

  const routeMeta = getRouteMeta(location.pathname);
  const layout = routeMeta.layout;
  const requiresAuth = routeMeta.auth === 'required';

  useEffect(() => {
    let cancelled = false;

    async function loadCurrentUser() {
      if (!requiresAuth) {
        setUser(null);
        setAuthLoading(false);
        setAuthError(null);
        return;
      }

      if (!getAccessToken() && !getRefreshToken()) {
        setUser(null);
        setAuthLoading(false);
        setAuthError(null);
        return;
      }

      setAuthLoading(true);
      setAuthError(null);
      const response = await getCurrentUser();
      if (cancelled) {
        return;
      }

      if (response.ok) {
        setUser(response.data);
        setAuthLoading(false);
        return;
      }

      if (response.error.code === 'unauthorized' || response.error.code === 'unauthenticated' || response.error.code === 'invalid_token') {
        clearAuthTokens();
        setAuthLoading(false);
        setAuthError(null);
        navigate('/login', { replace: true });
        return;
      }

      setUser(null);
      setAuthLoading(false);
      setAuthError(response.error.message || 'Không thể xác thực phiên đăng nhập.');
    }

    void loadCurrentUser();

    return () => {
      cancelled = true;
    };
  }, [requiresAuth, location.pathname]);

  async function handleLogout() {
    const refreshToken = getRefreshToken();
    if (getAccessToken()) {
      await logout(refreshToken).catch(() => null);
    }

    clearAuthTokens();
    setUser(null);
    setAuthError(null);
    navigate('/login', { replace: true });
  }

  if (layout === 'blank') {
    return <AppRoutes user={user} authLoading={authLoading} authError={authError} />;
  }

  if (layout === 'student-exam') {
    return (
      <StudentExamLayout user={user} theme={theme} onToggleTheme={handleToggleTheme}>
        <AppRoutes user={user} authLoading={authLoading} authError={authError} />
      </StudentExamLayout>
    );
  }

  if (layout === 'student-portal') {
    return (
      <StudentPortalLayout user={user} theme={theme} onToggleTheme={handleToggleTheme} onLogout={handleLogout}>
        <AppRoutes user={user} authLoading={authLoading} authError={authError} />
      </StudentPortalLayout>
    );
  }

  return (
    <AdminLayout user={user} theme={theme} onToggleTheme={handleToggleTheme} onLogout={handleLogout}>
      <AppRoutes user={user} authLoading={authLoading} authError={authError} />
    </AdminLayout>
  );
}

export function AppRouter() {
  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <AppShell />
    </BrowserRouter>
  );
}

import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  AdminDashboardRequestError,
  getAdminDashboardAlerts,
  getAdminDashboardSummary,
} from './adminDashboardApi';
import { AdminDashboardAlertPanel } from './AdminDashboardAlertPanel';
import type { AdminDashboardAlert, AdminDashboardSummary } from './adminDashboardContracts';
import { CompactPage } from '../../shared/components/compact/CompactPage';
import { CompactPageHeader } from '../../shared/components/compact/CompactPageHeader';
import { CompactStatBar } from '../../shared/components/compact/CompactStatBar';
import { CompactSurface } from '../../shared/components/compact/CompactSurface';
import { IconActionButton } from '../../shared/components/compact/IconActionButton';

const adminModules = [
  {
    title: 'Tài khoản & Phân quyền',
    description: 'Xem tài khoản người dùng, đặt lại mật khẩu mặc định và phân công vai trò.',
    path: '/admin/accounts',
    icon: '👤',
  },
  {
    title: 'Master Data',
    description: 'Nhập dữ liệu nền cho khoa, môn học, sinh viên lớp học hành chính và giảng viên.',
    path: '/admin/master-data',
    icon: '📁',
  },
  {
    title: 'Quản lý môn học',
    description: 'Danh mục môn học, học phần và cấu hình định mức CLO/mức độ khó.',
    path: '/admin/subjects',
    icon: '📚',
  },
  {
    title: 'Thiết lập ca thi',
    description: 'Chuẩn bị đề thi, chia phòng, phân chỗ ngồi sinh viên và phân công giám thị gác thi.',
    path: '/admin/exam-setup',
    icon: '⚙️',
  },
  {
    title: 'Danh sách bài làm',
    description: 'Theo dõi tiến trình làm bài thi trực tiếp và quản lý các bài nộp của sinh viên.',
    path: '/exams',
    icon: '✍️',
  },
];

type AdminDashboardLoadState = {
  summary: AdminDashboardSummary | null;
  alerts: AdminDashboardAlert[];
  loading: boolean;
  error: AdminDashboardRequestError | null;
};

type MetricCardProps = {
  label: string;
  value: number;
  helper?: string;
  tone?: 'default' | 'warning' | 'critical' | 'success';
};

function formatTimestamp(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat('vi-VN', {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(parsed);
}

function metricToneStyles(tone: MetricCardProps['tone']) {
  switch (tone) {
    case 'critical':
      return {
        border: '1px solid rgba(220, 38, 38, 0.25)',
        background: 'var(--clr-danger-light)',
        valueColor: 'var(--clr-danger)',
      };
    case 'warning':
      return {
        border: '1px solid rgba(217, 119, 6, 0.25)',
        background: 'var(--clr-warning-light)',
        valueColor: 'var(--clr-warning)',
      };
    case 'success':
      return {
        border: '1px solid rgba(22, 163, 74, 0.2)',
        background: 'var(--clr-success-light)',
        valueColor: 'var(--clr-success)',
      };
    default:
      return {
        border: '1px solid var(--clr-gray-200)',
        background: 'var(--surface-card)',
        valueColor: 'var(--clr-primary-600)',
      };
  }
}

function MetricCard({ label, value, helper, tone = 'default' }: MetricCardProps) {
  const styles = metricToneStyles(tone);
  return (
    <article
      className="stat-tile"
      style={{
        padding: 'var(--surface-padding-sm)',
        borderRadius: 'var(--radius-md)',
        border: styles.border,
        background: styles.background,
      }}
    >
      <span
        style={{
          fontSize: '1.25rem',
          fontWeight: 'var(--fw-bold)',
          color: styles.valueColor,
          display: 'block',
          marginBottom: 'var(--sp-1)',
        }}
      >
        {value}
      </span>
      <p
        style={{
          margin: 0,
          fontSize: 'var(--text-xs)',
          fontWeight: 'var(--fw-semibold)',
          color: 'var(--text-secondary)',
          textTransform: 'uppercase',
        }}
      >
        {label}
      </p>
      {helper ? (
        <p style={{ margin: 'var(--sp-2) 0 0 0', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>{helper}</p>
      ) : null}
    </article>
  );
}

function SummaryList({ items }: { items: Array<{ label: string; value: number }> }) {
  return (
    <dl className="dashboard-summary-grid" style={{ margin: 0 }}>
      {items.map((item) => (
        <div key={item.label} className="dashboard-summary-tile">
          <dt style={{ fontSize: 'var(--text-xs)', textTransform: 'uppercase', color: 'var(--text-secondary)' }}>{item.label}</dt>
          <dd style={{ margin: 'var(--sp-1) 0 0 0', fontSize: 'var(--text-lg)', fontWeight: 'var(--fw-bold)' }}>{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}

export function AdminDashboardPage() {
  const [state, setState] = useState<AdminDashboardLoadState>({
    summary: null,
    alerts: [],
    loading: true,
    error: null,
  });

  async function loadDashboard() {
    setState((previous) => ({ ...previous, loading: true, error: null }));
    try {
      const [summary, alertsResponse] = await Promise.all([
        getAdminDashboardSummary(),
        getAdminDashboardAlerts({ limit: 50 }),
      ]);
      setState({
        summary,
        alerts: alertsResponse.items,
        loading: false,
        error: null,
      });
    } catch (error) {
      if (error instanceof AdminDashboardRequestError) {
        setState({ summary: null, alerts: [], loading: false, error });
        return;
      }
      setState({
        summary: null,
        alerts: [],
        loading: false,
        error: new AdminDashboardRequestError({
          code: 'unknown_error',
          message: error instanceof Error ? error.message : 'Unknown dashboard error',
          details: {},
          request_id: null,
          status: 0,
        }),
      });
    }
  }

  useEffect(() => {
    void loadDashboard();
  }, []);

  const staleOrInterruptedCount = useMemo(
    () => state.alerts.filter((alert) => ['SESSION_STALE', 'SESSION_INTERRUPTED'].includes(String(alert.type).toUpperCase())).length,
    [state.alerts]
  );

  if (state.loading) {
    return <p className="muted">Đang tải dashboard quản trị...</p>;
  }

  if (state.error || !state.summary) {
    return (
      <section className="card">
        <h2>Không tải được dashboard quản trị</h2>
        <p className="error">{state.error?.message ?? 'Dashboard contract chưa sẵn sàng.'}</p>
        {state.error?.code ? <p className="muted">Error code: {state.error.code}</p> : null}
        <IconActionButton icon="refresh" variant="primary-button" label="Tải lại dashboard" onClick={() => void loadDashboard()} showLabel={true} />
      </section>
    );
  }

  const summary = state.summary;
  const unresolvedIncidents = summary.incidents.open + summary.incidents.in_progress;
  const gradingAttentionCount = summary.grading.needs_review + summary.grading.failed;

  return (
    <CompactPage>
      <CompactPageHeader
        eyebrow="Admin Dashboard"
        title="Bảng điều khiển quản trị"
        description="Trung tâm điều phối vận hành ca thi theo dữ liệu thật từ backend contracts."
        secondaryActions={<p className="muted" style={{ margin: 0 }}>Generated at: {formatTimestamp(summary.generated_at)}</p>}
        actions={
          <IconActionButton icon="refresh" label="Tải lại dashboard" onClick={() => void loadDashboard()} />
        }
      />

      <section className="dashboard-stats" aria-label="Chỉ số vận hành ca thi">
        <MetricCard label="Ca thi hôm nay" value={summary.sittings.today} />
        <MetricCard label="Ca thi đang mở" value={summary.sittings.open} tone={summary.sittings.open > 0 ? 'success' : 'default'} />
        <MetricCard label="Phòng thi đang mở" value={summary.live.open_rooms} />
        <MetricCard
          label="Thí sinh chưa bắt đầu trong ca đang mở"
          value={summary.live.not_started_in_open_sittings}
          tone={summary.live.not_started_in_open_sittings > 0 ? 'warning' : 'success'}
        />
        <MetricCard label="Thí sinh mất heartbeat/interrupted" value={staleOrInterruptedCount} tone={staleOrInterruptedCount > 0 ? 'critical' : 'success'} />
        <MetricCard label="Incident chưa xử lý" value={unresolvedIncidents} tone={unresolvedIncidents > 0 ? 'critical' : 'success'} />
        <MetricCard label="Phòng không thể đóng" value={summary.close_room.blocked_rooms} tone={summary.close_room.blocked_rooms > 0 ? 'critical' : 'success'} />
        <MetricCard label="Bài cần review/chấm lỗi" value={gradingAttentionCount} tone={gradingAttentionCount > 0 ? 'warning' : 'success'} />
      </section>

      <CompactSurface
        className="dashboard-section"
        aria-label="Exam setup readiness"
        title="Exam setup readiness"
        description="Theo dõi số ca thi đã lên lịch, mở, sắp diễn ra và chưa sẵn sàng."
      >
        <div className="dashboard-section-stack">
          <SummaryList
            items={[
              { label: 'Ca thi hôm nay', value: summary.sittings.today },
              { label: 'Ca thi đang mở', value: summary.sittings.open },
              { label: 'Ca thi 24h tới', value: summary.sittings.upcoming_24h },
              { label: 'Ca thi chưa sẵn sàng', value: summary.sittings.not_ready },
            ]}
          />
          <div>
            <h4 style={{ marginTop: 0 }}>Setup blockers</h4>
            <SummaryList
              items={[
                { label: 'Ca thi chưa có đề đã publish', value: summary.setup.sittings_without_published_exam },
                { label: 'Ca thi chưa prepare runtime', value: summary.setup.sittings_not_prepared },
                { label: 'Phòng thiếu giám thị', value: summary.setup.rooms_missing_proctors },
                { label: 'Phòng thiếu máy sẵn sàng', value: summary.setup.rooms_missing_ready_stations },
                { label: 'Sinh viên chưa gán chỗ', value: summary.setup.students_unassigned },
                { label: 'Import job lỗi', value: summary.setup.failed_import_jobs },
              ]}
            />
          </div>
        </div>
      </CompactSurface>

      <div className="dashboard-section-grid">
        <CompactSurface
          className="dashboard-section"
          aria-label="Live exam operation"
          title="Live exam operation"
          description="Các chỉ số check-in, bắt đầu bài thi và trạng thái phòng đang vận hành."
        >
          <SummaryList
            items={[
              { label: 'Phòng thi đang mở', value: summary.live.open_rooms },
              { label: 'Thí sinh đã check-in', value: summary.live.checked_in },
              { label: 'Thí sinh chưa check-in', value: summary.live.not_checked_in },
              { label: 'Phiên đã bắt đầu', value: summary.live.started },
              { label: 'Đã check-in nhưng chưa bắt đầu', value: summary.live.checked_in_not_started },
              { label: 'Chưa bắt đầu trong ca đang mở', value: summary.live.not_started_in_open_sittings },
              { label: 'Phiên bị gián đoạn', value: summary.live.interrupted },
              { label: 'Bài đã niêm phong', value: summary.live.sealed },
            ]}
          />
        </CompactSurface>

        <CompactSurface
          className="dashboard-section"
          aria-label="Submission and grading status"
          title="Submission and grading status"
          description="Theo dõi backlog chấm, bài đã tính điểm và các trường hợp cần can thiệp."
        >
          <SummaryList
            items={[
              { label: 'Job chờ chấm', value: summary.grading.pending },
              { label: 'Job đang chạy', value: summary.grading.running },
              { label: 'Bài đã compute điểm', value: summary.grading.computed },
              { label: 'Bài cần review', value: summary.grading.needs_review },
              { label: 'Job chấm lỗi', value: summary.grading.failed },
            ]}
          />
        </CompactSurface>
      </div>

      <CompactSurface
        className="dashboard-section"
        aria-label="Incidents and operational alerts"
        title="Incidents and operational alerts"
        description="Tổng hợp incident đang mở, đang xử lý và cảnh báo hành động từ backend."
      >
        <div className="dashboard-section-stack">
          <CompactStatBar
            items={[
              { label: 'Incident đang mở', value: summary.incidents.open },
              { label: 'Incident đang xử lý', value: summary.incidents.in_progress },
              { label: 'Đã xử lý hôm nay', value: summary.incidents.resolved_today },
              { label: 'Phòng block khi đóng', value: summary.close_room.blocked_rooms },
              { label: 'Phòng đã đóng', value: summary.close_room.closed_rooms },
            ]}
          />
          <AdminDashboardAlertPanel alerts={state.alerts} />
        </div>
      </CompactSurface>

      <CompactSurface
        className="dashboard-section"
        aria-label="System health"
        title="System health"
        description="Chỉ số phiên đăng nhập, lockout và worker health đã được backend hỗ trợ."
      >
        <div className="dashboard-health-grid">
          <SummaryList
            items={[
              { label: 'Phiên đăng nhập đang hoạt động', value: summary.system.active_user_sessions },
              { label: 'Tài khoản đang bị lockout', value: summary.system.locked_accounts },
              { label: 'Worker unhealthy', value: summary.system.workers_unhealthy },
            ]}
          />
        </div>
      </CompactSurface>

      <CompactSurface className="dashboard-section" title="Chức năng quản trị">
        <div className="admin-module-grid" aria-label="Module quản trị">
          {adminModules.map((module) => (
            <article className="admin-module-card admin-module-card--compact" key={module.path}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-2)', marginBottom: 'var(--sp-2)' }}>
                  <span style={{ fontSize: 'var(--text-lg)' }} role="img" aria-hidden="true">
                    {module.icon}
                  </span>
                  <h4 style={{ margin: 0, fontSize: 'var(--text-sm)', fontWeight: 'var(--fw-semibold)', color: 'var(--text-primary)' }}>
                    {module.title}
                  </h4>
                </div>
                <p style={{ margin: '0 0 var(--gap-sm) 0', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', lineHeight: 'var(--leading-relaxed)' }}>
                  {module.description}
                </p>
              </div>
              <Link className="secondary-button compact-button" to={module.path} style={{ alignSelf: 'flex-start', fontSize: 'var(--text-xs)' }}>
                Mở phân hệ →
              </Link>
            </article>
          ))}
        </div>
      </CompactSurface>
    </CompactPage>
  );
}

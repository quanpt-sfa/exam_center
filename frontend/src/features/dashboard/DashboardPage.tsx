import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { canAccessMasterData, hasRole, type CurrentUser } from '../auth/authApi';
import { AdminDashboardPage } from './AdminDashboardPage';
import { hasStudentRole, loadDashboardData, type StudentExamClass } from './dashboardApi';
import { ProctorDashboardPanel } from '../proctor/ProctorDashboardPanel';
import {
  getStudentExamActionLabel,
  getStudentExamStatusLabel,
  isActionableStudentExam,
  isCompletedStudentExam,
  isLiveStudentExam,
} from '../examTaking/studentExamUi';

type LoadState = {
  user: CurrentUser | null;
  exams: StudentExamClass[];
  loading: boolean;
  error: string | null;
};

const adminRoles = new Set(['ADMIN']);

function hasAdminRole(user: CurrentUser): boolean {
  return user.roles.some((role) => adminRoles.has(String(role).toUpperCase()));
}

function hasProctorRole(user: CurrentUser): boolean {
  return user.roles.some((role) => String(role).toUpperCase() === 'PROCTOR');
}

function formatDate(value?: string | null): string {
  if (!value) {
    return 'Chưa có';
  }

  const parsed = new Date(value);
  if (!Number.isNaN(parsed.getTime())) {
    return new Intl.DateTimeFormat('vi-VN').format(parsed);
  }

  return String(value);
}

function formatTime(value?: string | null): string {
  if (!value) {
    return 'Chưa có';
  }

  const parsed = new Date(value);
  if (!Number.isNaN(parsed.getTime())) {
    return new Intl.DateTimeFormat('vi-VN', {
      hour: '2-digit',
      minute: '2-digit',
    }).format(parsed);
  }

  const match = String(value).match(/^(\d{1,2}):(\d{2})/);
  if (match) {
    return `${match[1].padStart(2, '0')}:${match[2]}`;
  }

  return String(value);
}

function scoreLabel(exam: StudentExamClass): string {
  const normalized = String(exam.status || '').toLowerCase();
  if (normalized === 'started') {
    return 'Đang làm bài';
  }
  if ((normalized === 'submitted' || normalized === 'graded') && exam.total_score != null) {
    return Number(exam.total_score).toFixed(2);
  }
  if (normalized === 'submitted' || normalized === 'graded') {
    return 'Đang chấm';
  }
  return 'Chưa có';
}

function statusMeta(exam: StudentExamClass) {
  return {
    submissionStatus: exam.status,
    isOpen: exam.is_open,
    hasResult: Boolean(exam.exam_submission_id),
  };
}

function statusClassName(exam: StudentExamClass): string {
  const label = getStudentExamStatusLabel(statusMeta(exam));
  if (label === 'Đã hoàn thành') {
    return 'status-completed';
  }
  if (label === 'Đang mở') {
    return 'status-in_progress';
  }
  if (label === 'Sẵn sàng vào thi') {
    return 'status-ready_to_start';
  }
  return 'status-unknown';
}

function isCompletedExam(exam: StudentExamClass): boolean {
  return isCompletedStudentExam(statusMeta(exam));
}

function isStartedExam(exam: StudentExamClass): boolean {
  return isLiveStudentExam(statusMeta(exam));
}

function actionLabel(exam: StudentExamClass): string {
  return getStudentExamActionLabel(statusMeta(exam));
}

function StudentDashboard({ user, exams }: { user: CurrentUser; exams: StudentExamClass[] }) {
  const stats = useMemo(() => {
    return {
      total: exams.length,
      open: exams.filter((exam) => exam.is_open).length,
      started: exams.filter(isStartedExam).length,
      completed: exams.filter(isCompletedExam).length,
    };
  }, [exams]);

  const primaryExam = useMemo(() => {
    return exams.find((exam) => isActionableStudentExam(statusMeta(exam))) || exams.find((exam) => exam.is_open) || exams[0];
  }, [exams]);

  return (
    <>
      <section className="dashboard-hero student-dashboard-hero">
        <div>
          <p className="eyebrow">Dashboard sinh viên</p>
          <h2>{user.display_name || user.username || 'Sinh viên'}</h2>
          <p>Theo dõi lớp thi được đăng ký, phòng thi, chỗ ngồi, trạng thái làm bài và kết quả xử lý sau khi nộp.</p>
        </div>
        {primaryExam ? (
          <div className="dashboard-focus">
            <span>Ca gần nhất</span>
            <strong>{primaryExam.test_class_name}</strong>
            <small>
              {formatDate(primaryExam.start_date)} · {formatTime(primaryExam.start_time)} - {formatTime(primaryExam.end_time)}
            </small>
          </div>
        ) : null}
      </section>

      <section className="dashboard-stats student-dashboard-stats" aria-label="Tổng quan lớp thi">
        <div className="stat-tile stat-total">
          <span>{stats.total}</span>
          <p>Lớp thi</p>
        </div>
        <div className="stat-tile stat-open">
          <span>{stats.open}</span>
          <p>Đang mở</p>
        </div>
        <div className="stat-tile stat-working">
          <span>{stats.started}</span>
          <p>Đang thi</p>
        </div>
        <div className="stat-tile stat-done">
          <span>{stats.completed}</span>
          <p>Đã hoàn thành</p>
        </div>
      </section>

      <section className="dashboard-section">
        <div className="section-heading">
          <h3>Lớp đang được đăng ký thi</h3>
          <Link to="/exams">Xem danh sách bài thi</Link>
        </div>

        {exams.length === 0 ? (
          <div className="empty-state">
            Hiện tại bạn chưa có lớp thi đang mở. Vui lòng liên hệ giảng viên hoặc quản trị viên.
          </div>
        ) : (
          <div className="student-exam-list">
            {exams.map((exam) => (
              <article className="exam-dashboard-card student-exam-card" key={exam.test_class_id}>
                <div className="exam-card-header">
                  <div>
                    <h4>
                      {exam.subject_code ? `${exam.subject_code} - ` : ''}
                      {exam.subject_name || exam.test_class_name}
                    </h4>
                    <p>{exam.class_name || exam.test_class_name}</p>
                  </div>
                  <div className="exam-status-cluster">
                    <span className={exam.is_open ? 'status-pill status-open' : 'status-pill status-closed'}>
                      {exam.is_open ? 'Đang mở' : 'Đã đóng'}
                    </span>
                    <span className={`status-pill ${statusClassName(exam)}`}>{getStudentExamStatusLabel(statusMeta(exam))}</span>
                  </div>
                </div>

                <dl className="exam-detail-grid student-exam-detail-grid">
                  <div>
                    <dt>Lớp thi</dt>
                    <dd>{exam.test_class_name}</dd>
                  </div>
                  <div>
                    <dt>Ngày thi</dt>
                    <dd>
                      {formatDate(exam.start_date)}
                      {exam.end_date && exam.end_date !== exam.start_date ? ` - ${formatDate(exam.end_date)}` : ''}
                    </dd>
                  </div>
                  <div>
                    <dt>Giờ thi</dt>
                    <dd>
                      {formatTime(exam.start_time)} - {formatTime(exam.end_time)}
                    </dd>
                  </div>
                  <div>
                    <dt>Thời gian</dt>
                    <dd>{exam.duration ? `${exam.duration} phút` : 'Chưa có'}</dd>
                  </div>
                  <div>
                    <dt>Phòng thi</dt>
                    <dd>{exam.room || 'Chưa có'}</dd>
                  </div>
                  <div>
                    <dt>Số máy</dt>
                    <dd>{exam.seat_number || 'Chưa có'}</dd>
                  </div>
                  <div>
                    <dt>Ca thi</dt>
                    <dd>{exam.slot_name || 'Chưa có'}</dd>
                  </div>
                  <div>
                    <dt>Điểm số</dt>
                    <dd>{scoreLabel(exam)}</dd>
                  </div>
                </dl>

                <div className="exam-card-actions">
                  {isCompletedExam(exam) && exam.exam_submission_id ? (
                    <Link className="secondary-button action-link" to={`/submissions/${exam.exam_submission_id}/result`}>
                      {actionLabel(exam)}
                    </Link>
                  ) : exam.is_open ? (
                    <Link className="primary-button action-link" to={`/exams/${exam.test_class_id}`}>
                      {actionLabel(exam)}
                    </Link>
                  ) : (
                    <button className="secondary-button" type="button" disabled>
                      Lớp thi đã đóng
                    </button>
                  )}
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </>
  );
}

function StaffDashboard({ user }: { user: CurrentUser }) {
  const quickActions = [
    {
      title: 'Danh sách bài thi',
      description: 'Theo dõi các lớp thi đang mở, truy cập bài thi và xem trạng thái làm bài.',
      path: '/exams',
      cta: 'Mở danh sách',
      visible: true,
    },
    {
      title: 'Bảng điểm',
      description: 'Xem tiến độ chấm, kết quả tổng hợp và các dấu hiệu cần xử lý tiếp.',
      path: '/grading/gradebook',
      cta: 'Mở bảng điểm',
      visible: hasRole(user, ['ADMIN', 'ACADEMIC_OFFICER', 'INSTRUCTOR']),
    },
    {
      title: 'Master data',
      description: 'Quản lý dữ liệu nền học thuật, con người và cơ sở vật chất khi được cấp quyền.',
      path: '/master-data',
      cta: 'Mở master data',
      visible: canAccessMasterData(user),
    },
    {
      title: 'Phòng giám thị',
      description: 'Xem các phòng đang được phân công coi thi và thao tác giám sát liên quan.',
      path: '/proctor/sittings',
      cta: 'Mở phòng giám thị',
      visible: hasRole(user, ['PROCTOR']),
    },
  ].filter((action) => action.visible);

  return (
    <>
      <section className="dashboard-hero">
        <div>
          <p className="eyebrow">Dashboard giảng viên</p>
          <h2>{user.display_name || user.username || 'Người dùng'}</h2>
          <p>
            Truy cập nhanh các phân hệ phù hợp với vai trò hiện tại. Các nút không được cấp quyền sẽ không hiển thị.
          </p>
        </div>
        <div className="dashboard-focus">
          <span>Vai trò hiện tại</span>
          <strong>{user.roles.join(', ') || 'Chưa có'}</strong>
          <small>{quickActions.length} thao tác sẵn sàng</small>
        </div>
      </section>

      <section className="dashboard-section">
        <div className="section-heading">
          <h3>Truy cập nhanh</h3>
        </div>
        <div className="admin-module-grid" aria-label="Tác vụ dành cho giảng viên và nhân sự">
          {quickActions.map((action) => (
            <article className="admin-module-card" key={action.path}>
              <div>
                <h4>{action.title}</h4>
                <p>{action.description}</p>
              </div>
              <Link className="secondary-button compact-button" to={action.path}>
                {action.cta}
              </Link>
            </article>
          ))}
        </div>
      </section>
    </>
  );
}

export function DashboardPage() {
  const [state, setState] = useState<LoadState>({
    user: null,
    exams: [],
    loading: true,
    error: null,
  });

  useEffect(() => {
    async function loadDashboard() {
      const response = await loadDashboardData();
      if (!response.ok) {
        setState({
          user: null,
          exams: [],
          loading: false,
          error: response.error,
        });
        return;
      }

      setState({
        user: response.user,
        exams: response.exams,
        loading: false,
        error: null,
      });
    }

    void loadDashboard();
  }, []);

  if (state.loading) {
    return <p className="muted">Đang tải dashboard...</p>;
  }

  if (state.error) {
    return (
      <section className="card">
        <h2>Không tải được dashboard</h2>
        <p className="error">{state.error}</p>
        <Link to="/login">Quay lại đăng nhập</Link>
      </section>
    );
  }

  if (!state.user) {
    return null;
  }

  if (hasAdminRole(state.user)) {
    return <AdminDashboardPage />;
  }

  if (hasStudentRole(state.user)) {
    return <StudentDashboard user={state.user} exams={state.exams} />;
  }

  if (hasProctorRole(state.user)) {
    return <ProctorDashboardPanel allowSessionRevoke={true} />;
  }

  return <StaffDashboard user={state.user} />;
}

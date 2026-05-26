import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { listExams, type ExamListItem } from './examTakingApi';
import {
  getStudentExamActionLabel,
  getStudentExamStatusLabel,
  isActionableStudentExam,
  isCompletedStudentExam,
  isLiveStudentExam,
  isReadyStudentExam,
} from './studentExamUi';

function examTitle(exam: ExamListItem): string {
  return exam.sitting_name || exam.exam_name || exam.session_code || `Ca thi #${exam.exam_session_id}`;
}

function subjectLabel(exam: ExamListItem): string | null {
  if (exam.course_code && exam.course_name) {
    return `${exam.course_code} - ${exam.course_name}`;
  }
  return exam.course_name || exam.course_code || null;
}

function statusMeta(exam: ExamListItem) {
  return {
    submissionStatus: exam.submission_status,
    sessionStatus: exam.session_status,
    hasResult: Boolean(exam.exam_submission_id),
  };
}

function actionLabel(exam: ExamListItem): string {
  return getStudentExamActionLabel(statusMeta(exam));
}

function featuredActionLabel(exam: ExamListItem): string {
  if (isLiveStudentExam(statusMeta(exam))) {
    return 'Đi tới ca đang mở';
  }
  if (isReadyStudentExam(statusMeta(exam))) {
    return 'Đi tới ca sẵn sàng';
  }
  return actionLabel(exam);
}

function actionPath(exam: ExamListItem): string {
  if (isCompletedStudentExam(statusMeta(exam)) && exam.exam_submission_id) {
    return `/submissions/${exam.exam_submission_id}/result`;
  }
  return `/exams/${exam.exam_session_id}`;
}

function statusLabel(exam: ExamListItem): string {
  return getStudentExamStatusLabel(statusMeta(exam));
}

export function ExamListPage() {
  const [exams, setExams] = useState<ExamListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadExams() {
      const response = await listExams();
      if (!response.success) {
        setError(response.error.message);
        setLoading(false);
        return;
      }

      setExams(response.data);
      setLoading(false);
    }

    void loadExams();
  }, []);

  const featuredExam = exams.find((exam) => isLiveStudentExam(statusMeta(exam))) || exams.find((exam) => isActionableStudentExam(statusMeta(exam))) || null;
  const remainingExams = featuredExam ? exams.filter((exam) => exam.exam_session_id !== featuredExam.exam_session_id) : exams;

  return (
    <>
      <section className="dashboard-hero student-dashboard-hero">
        <div>
          <p className="eyebrow">Cổng bài thi</p>
          <h2>Danh sách ca thi</h2>
          <p>
            Trang này dùng để xem toàn bộ ca thi được phân công. Khi có một ca đang mở hoặc sẵn sàng bắt đầu, nó sẽ được tách riêng để bạn vào đúng bài thi cụ thể.
          </p>
        </div>
        <div className="dashboard-actions">
          <Link className="secondary-link" to="/dashboard">
            Quay lại dashboard
          </Link>
          {featuredExam ? (
            <Link className="primary-button action-link" to={actionPath(featuredExam)}>
              {featuredActionLabel(featuredExam)}
            </Link>
          ) : null}
        </div>
      </section>

      {loading ? <p className="muted">Đang tải ca thi...</p> : null}
      {error ? <p className="error">{error}</p> : null}

      {!loading && !error ? (
        exams.length === 0 ? (
          <section className="dashboard-section">
            <div className="empty-state">Chưa có ca thi nào được phân công.</div>
          </section>
        ) : (
          <>
            {featuredExam ? (
              <section className="dashboard-section">
                <div className="section-heading">
                  <div>
                    <h3>Ca thi cần vào ngay</h3>
                    <p className="muted">Phân biệt với danh sách tổng bên dưới: đây là ca thi cụ thể đang mở hoặc đã sẵn sàng bắt đầu.</p>
                  </div>
                </div>

                <article className="exam-list-item" key={`featured-${featuredExam.exam_session_id}`}>
                  <div>
                    <p className="eyebrow">{subjectLabel(featuredExam) ?? 'Môn thi'}</p>
                    <h3>{examTitle(featuredExam)}</h3>
                    <p className="muted">
                      {featuredExam.room_code ? `Phòng ${featuredExam.room_code}` : 'Chưa có phòng'}
                      {featuredExam.seat_no ? ` · Chỗ ${featuredExam.seat_no}` : ''}
                    </p>
                    <div className="exam-status-cluster">
                      <span className={`status-pill ${isLiveStudentExam(statusMeta(featuredExam)) ? 'status-open' : 'status-assigned'}`}>{statusLabel(featuredExam)}</span>
                    </div>
                  </div>
                  <Link className="primary-button action-link" to={actionPath(featuredExam)}>
                    {actionLabel(featuredExam)}
                  </Link>
                </article>
              </section>
            ) : null}

            <section className="dashboard-section">
              <div className="section-heading">
                <div>
                  <h3>Tất cả ca thi được phân công</h3>
                  <p className="muted">Danh sách này bao gồm cả ca đang mở, sắp thi và đã hoàn thành.</p>
                </div>
              </div>

              <div className="exam-list-grid">
                {remainingExams.map((exam) => (
                  <article className="exam-list-item" key={exam.exam_session_id}>
                    <div>
                      <p className="eyebrow">{subjectLabel(exam) ?? 'Môn thi'}</p>
                      <h3>{examTitle(exam)}</h3>
                      <p className="muted">
                        {exam.room_code ? `Phòng ${exam.room_code}` : 'Chưa có phòng'}
                        {exam.seat_no ? ` · Chỗ ${exam.seat_no}` : ''}
                      </p>
                      <p className="status-line">Trạng thái: {statusLabel(exam)}</p>
                    </div>
                    <Link className="primary-button action-link" to={actionPath(exam)}>
                      {actionLabel(exam)}
                    </Link>
                  </article>
                ))}
              </div>
            </section>
          </>
        )
      ) : null}
    </>
  );
}

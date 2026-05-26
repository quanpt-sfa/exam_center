import { ExamSetupSurfaceHeader } from './components/ExamSetupSurfaceHeader';
import { WorkflowCard } from './components/WorkflowCard';

export function ExamSetupLandingPage() {
  return (
    <div className="exam-setup-page" data-testid="exam-setup-landing-page">
      <ExamSetupSurfaceHeader
        eyebrow="Exam setup"
        title="Thiết lập trước khi thi"
        description="Tách riêng soạn đề và thiết lập ca thi để thao tác theo đúng workflow quản trị hiện có."
      />

      <section className="master-data-layout" style={{ alignItems: 'stretch' }}>
        <div className="master-data-workspace" style={{ display: 'grid', gap: 'var(--sp-5)' }}>
          <section className="card">
            <h3>Chọn workflow</h3>
            <p className="muted">
              Trang này chỉ điều hướng. Soạn đề và thiết lập ca thi đã được tách sang hai bề mặt riêng để giảm lẫn trạng thái.
            </p>
          </section>

          <div className="setup-overview-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))' }}>
            <WorkflowCard
              title="Exam Authoring"
              description="Quản lý đề gốc, phiên bản đề, cấu hình delivery cho version, câu hỏi và cấu hình chấm."
              to="/admin/exam-setup/authoring"
              items={[
                'Đề gốc và phiên bản đề',
                'Delivery profile và paper assets',
                'Câu hỏi, grading profile, expected answers',
                'Version readiness đang có',
              ]}
            />
            <WorkflowCard
              title="Delivery Setup"
              description="Thiết lập ca thi, gắn phiên bản đề, thí sinh, phòng thi, giám thị, chỗ ngồi và các thao tác mở ca đã nối backend."
              to="/admin/exam-setup/delivery"
              items={[
                'Exam sittings và trạng thái ca thi',
                'Rooms, assignments, proctors, seating',
                'Sitting readiness, prepare runtime, open sitting',
                'Không bao gồm Proctor Portal',
              ]}
            />
          </div>
        </div>
      </section>
    </div>
  );
}
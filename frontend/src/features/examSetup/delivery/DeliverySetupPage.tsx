import { ExamSetupPage, type SetupSectionKey } from '../ExamSetupPage';

const deliverySectionKeys: SetupSectionKey[] = [
  'sittings',
  'sitting-version',
  'sitting-class-sections',
  'assignments',
  'rooms',
  'seating',
  'proctors',
  'readiness',
  'publish',
];

export function DeliverySetupPage() {
  return (
    <ExamSetupPage
      allowedSectionKeys={deliverySectionKeys}
      initialSectionKey="sittings"
      surfaceEyebrow="Delivery setup"
      surfaceTitle="Delivery Setup"
      surfaceDescription="Thiết lập ca thi, gắn phiên bản đề và chuẩn bị các cấu hình delivery đã nối backend."
      testId="delivery-setup-page"
    />
  );
}
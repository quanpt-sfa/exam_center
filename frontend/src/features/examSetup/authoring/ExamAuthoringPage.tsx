import { ExamSetupPage, type SetupSectionKey } from '../ExamSetupPage';

const authoringSectionKeys: SetupSectionKey[] = [
  'blueprint',
  'exam-version',
  'delivery-type',
  'paper',
  'questions',
  'response-profile',
  'grading-profile',
  'expected-answer',
  'version-readiness',
];

export function ExamAuthoringPage() {
  return (
    <ExamSetupPage
      allowedSectionKeys={authoringSectionKeys}
      initialSectionKey="blueprint"
      surfaceEyebrow="Exam authoring"
      surfaceTitle="Exam Authoring"
      surfaceDescription="Soạn đề, quản lý phiên bản đề và cấu hình question/grading cho từng exam version."
      testId="exam-authoring-page"
    />
  );
}
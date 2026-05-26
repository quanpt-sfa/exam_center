import { PublicSystemSettings } from './settingsApi';

export const DEFAULT_ACADEMY_NAME = 'Học viện Công nghệ Bưu chính Viễn thông';
export const DEFAULT_SUPPORT_EMAIL = 'support@academy.edu.vn';
export const DEFAULT_SUPPORT_HOTLINE = '0123-456-789';
export const DEFAULT_EXAM_REGULATIONS = `1. Thí sinh phải có mặt tại phòng thi trước giờ bắt đầu làm bài ít nhất 15 phút.
2. Thí sinh xuất trình Thẻ sinh viên hoặc giấy tờ tùy thân có ảnh khi cán bộ coi thi yêu cầu.
3. Tuyệt đối không mang tài liệu, điện thoại di động, thiết bị thông minh hoặc các vật dụng cấm vào phòng thi.
4. Mọi hành vi gian lận sẽ bị xử lý kỷ luật đình chỉ thi ngay lập tức.`;
export const DEFAULT_LOGO_URL = null;

export const DEFAULT_PUBLIC_SETTINGS: PublicSystemSettings = {
  academy_name: DEFAULT_ACADEMY_NAME,
  portal_logo_url: DEFAULT_LOGO_URL,
  exam_regulations: DEFAULT_EXAM_REGULATIONS,
  support_email: DEFAULT_SUPPORT_EMAIL,
  support_hotline: DEFAULT_SUPPORT_HOTLINE,
};

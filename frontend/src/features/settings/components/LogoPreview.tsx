import { useState, useEffect } from 'react';

interface LogoPreviewProps {
  url?: string | null;
  fallbackText: string;
}

export function LogoPreview({ url, fallbackText }: LogoPreviewProps) {
  const [hasError, setHasError] = useState(false);

  useEffect(() => {
    setHasError(false);
  }, [url]);

  const initials = fallbackText ? fallbackText.slice(0, 2).toUpperCase() : 'ES';

  return (
    <div className="logo-preview-box">
      <div className="logo-preview-img-container">
        {url && !hasError ? (
          <img
            src={url}
            alt="Logo Preview"
            onError={() => setHasError(true)}
            className="logo-preview-img"
          />
        ) : (
          initials
        )}
      </div>
      <div>
        <span className="logo-preview-title">Xem trước Logo</span>
        <span className="muted logo-preview-copy">
          {url && !hasError ? 'Đã tải thành công đường dẫn Logo' : 'Không có logo hoặc lỗi tải ảnh, hiển thị mặc định'}
        </span>
      </div>
    </div>
  );
}

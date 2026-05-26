import type { ExamSessionPaperAsset } from './types';

function normalizeMime(mime: string | null | undefined): string {
  return String(mime || '').trim().toLowerCase();
}

function isImageMime(mime: string): boolean {
  return mime.startsWith('image/');
}

function isPdfMime(mime: string): boolean {
  return mime === 'application/pdf';
}

export function VisualPaperViewer({
  asset,
  watermarkText,
}: {
  asset: ExamSessionPaperAsset;
  watermarkText: string;
}) {
  const mime = normalizeMime(asset.mime_type);
  const contentUrl = String(asset.content_url || '').trim();

  if (!contentUrl) {
    return (
      <section className="visual-paper-panel" aria-label="Visual paper">
        <p className="form-error">Không có đường dẫn tài liệu đề thi.</p>
      </section>
    );
  }

  return (
    <section
      className="visual-paper-panel"
      aria-label="Visual paper"
      onContextMenu={(event) => {
        event.preventDefault();
      }}
    >
      <div className="visual-paper-header">
        <h3>Tài liệu đề thi</h3>
        <p className="muted">Đang xem qua API bảo vệ. Mục tiêu là giảm sao chép văn bản.</p>
      </div>

      <div className="visual-paper-stage">
        <div className="visual-paper-watermark" aria-hidden="true">
          {watermarkText}
        </div>
        {isImageMime(mime) ? (
          <img
            className="visual-paper-image"
            src={contentUrl}
            alt={asset.original_filename || 'Visual paper'}
            draggable={false}
          />
        ) : isPdfMime(mime) ? (
          <>
            {/* PDF can still expose selectable text depending on original file structure. */}
            <iframe className="visual-paper-pdf" src={contentUrl} title="Visual paper PDF" />
          </>
        ) : (
          <div className="form-error">Loại tài liệu chưa được hỗ trợ trên giao diện này.</div>
        )}
      </div>
      <p className="visual-paper-warning">
        Hiển thị dạng ảnh/PDF chỉ giảm khả năng sao chép văn bản; không ngăn được chụp màn hình.
      </p>
    </section>
  );
}

import { useEffect, useMemo, useState } from 'react';
import type { StudentCandidateProfile } from './types';

interface ExamTakerIdentityPanelProps {
  candidate?: StudentCandidateProfile | null;
  compact?: boolean;
}

function candidateInitials(fullName?: string | null): string {
  const tokens = String(fullName || '')
    .trim()
    .split(/\s+/)
    .filter(Boolean);

  if (tokens.length === 0) return 'TS';
  if (tokens.length === 1) return tokens[0].slice(0, 2).toUpperCase();

  return `${tokens[0][0] || ''}${tokens[tokens.length - 1][0] || ''}`.toUpperCase();
}

function canRenderPhoto(url?: string | null): boolean {
  const normalized = String(url || '').trim();
  if (!normalized) return false;

  try {
    const origin = typeof window !== 'undefined' ? window.location.origin : 'http://localhost';
    const parsed = new URL(normalized, origin);
    return parsed.protocol === 'http:' || parsed.protocol === 'https:';
  } catch {
    return false;
  }
}

export function ExamTakerIdentityPanel({ candidate, compact = false }: ExamTakerIdentityPanelProps) {
  const [imageFailed, setImageFailed] = useState(false);

  useEffect(() => {
    setImageFailed(false);
  }, [candidate?.photo_url]);

  const initials = useMemo(() => candidateInitials(candidate?.full_name), [candidate?.full_name]);
  const photoUrl = canRenderPhoto(candidate?.photo_url) ? String(candidate?.photo_url) : null;

  if (!candidate) {
    return (
      <section
        className={`exam-taker-identity-panel${compact ? ' is-compact' : ''}`}
        aria-label="Thông tin thí sinh"
      >
        <div className="identity-avatar identity-avatar-fallback" aria-hidden="true">
          TS
        </div>
        <div className="identity-summary">
          <p className="identity-kicker">Thí sinh</p>
          <strong>Chưa có dữ liệu định danh</strong>
          <p className="muted">Backend chưa cung cấp họ tên hoặc mã sinh viên cho phiên thi này.</p>
        </div>
      </section>
    );
  }

  return (
    <section
      className={`exam-taker-identity-panel${compact ? ' is-compact' : ''}`}
      aria-label="Thông tin thí sinh"
    >
      <div className="identity-avatar-frame">
        {photoUrl && !imageFailed ? (
          <img
            className="identity-avatar"
            src={photoUrl}
            alt={candidate.full_name}
            onError={() => setImageFailed(true)}
          />
        ) : (
          <div className="identity-avatar identity-avatar-fallback" aria-label={`Ảnh thay thế của ${candidate.full_name}`}>
            {initials}
          </div>
        )}
      </div>

      <div className="identity-summary">
        <p className="identity-kicker">Thí sinh</p>
        <strong>{candidate.full_name}</strong>
        <p>
          Mã sinh viên: <span>{candidate.student_code}</span>
        </p>
      </div>
    </section>
  );
}

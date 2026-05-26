import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { GradebookRequestError, getGradebookSubmissionDetail } from './gradebookApi';
import type { GradebookSubmissionDetail } from './contracts';
import { CompactPage } from '../../shared/components/compact/CompactPage';
import { CompactPageHeader } from '../../shared/components/compact/CompactPageHeader';
import { CompactSurface } from '../../shared/components/compact/CompactSurface';
import { CompactToolbar } from '../../shared/components/compact/CompactToolbar';
import { CompactStatBar } from '../../shared/components/compact/CompactStatBar';

type StatusTone = 'success' | 'warning' | 'danger' | 'neutral';

function parseSubmissionId(raw: string | undefined): number | null {
  if (typeof raw !== 'string') {
    return null;
  }

  const numeric = Number(raw);
  if (!Number.isInteger(numeric) || numeric <= 0) {
    return null;
  }

  return numeric;
}

function formatNullable(value: string | number | null | undefined, fallback = 'Not available'): string {
  if (value == null) {
    return fallback;
  }
  if (typeof value === 'string' && value.trim() === '') {
    return fallback;
  }
  return String(value);
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return 'Not available';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat('en-GB', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}

function formatNumber(value: number | null | undefined): string {
  return value == null ? 'Not available' : String(value);
}

function formatScore(rawScore: number | null | undefined, maxScore: number | null | undefined): string {
  if (rawScore == null || maxScore == null) {
    return 'Not graded yet';
  }
  return `${rawScore} / ${maxScore}`;
}

function formatPercentage(value: string | number | null | undefined): string {
  if (value == null || value === '') {
    return 'Not available';
  }
  return `${value}%`;
}

function getStatusLabel(value: string | null | undefined): string {
  return value && value.trim() ? value : 'UNKNOWN';
}

function isFailedStatus(status: string): boolean {
  return status === 'FAILED' || status === 'ERROR';
}

function isPendingStatus(status: string): boolean {
  return status === 'PENDING' || status === 'NOT_DISPATCHED';
}

function getStatusTone(status: string | null | undefined): StatusTone {
  if (status === 'COMPUTED' || status === 'FINALIZED' || status === 'AUTO_SCORED') {
    return 'success';
  }
  if (status === 'NEEDS_REVIEW') {
    return 'warning';
  }
  if (isFailedStatus(status ?? '')) {
    return 'danger';
  }
  if (isPendingStatus(status ?? '')) {
    return 'neutral';
  }
  return 'neutral';
}

function getStatusClassName(status: string | null | undefined): string {
  return `gradebook-status-badge is-${getStatusTone(status)}`;
}

function hasNeedsReviewSignal(data: GradebookSubmissionDetail): boolean {
  if (data.submission.needs_review) {
    return true;
  }

  if (data.question_scores.some((item) => item.requires_manual_review || item.score_status === 'NEEDS_REVIEW')) {
    return true;
  }

  return data.manual_reviews.some((item) => item.review_status !== 'RESOLVED' && item.review_status !== 'REJECTED');
}

function renderMetricCard(title: string, value: string, caption: string, tone: StatusTone = 'neutral') {
  return (
    <article className={`gradebook-summary-card is-${tone}`}>
      <span>{title}</span>
      <strong>{value}</strong>
      <small>{caption}</small>
    </article>
  );
}

export function GradebookSubmissionDetailPage() {
  const { submissionId: submissionIdRaw } = useParams<{ submissionId: string }>();
  const submissionId = parseSubmissionId(submissionIdRaw);
  const [data, setData] = useState<GradebookSubmissionDetail | null>(null);
  const [loading, setLoading] = useState(submissionId !== null);
  const [error, setError] = useState<GradebookRequestError | null>(null);

  useEffect(() => {
    if (submissionId === null) {
      setLoading(false);
      return;
    }

    let cancelled = false;

    async function loadDetail() {
      setLoading(true);
      setError(null);
      try {
        const response = await getGradebookSubmissionDetail(submissionId);
        if (!cancelled) {
          setData(response);
        }
      } catch (loadError) {
        if (!cancelled) {
          setData(null);
          setError(
            loadError instanceof GradebookRequestError
              ? loadError
              : new GradebookRequestError({
                  code: 'request_failed',
                  message: 'Unable to load submission review detail.',
                  details: {},
                  request_id: null,
                  status: 0,
                })
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadDetail();

    return () => {
      cancelled = true;
    };
  }, [submissionId]);

  if (submissionId === null) {
    return (
      <CompactPage className="gradebook-detail-shell" data-testid="gradebook-submission-detail-page" role="alert" aria-live="polite">
        <h2>Invalid submission ID</h2>
        <p className="muted">Open this page from the gradebook list to review a real backend submission.</p>
      </CompactPage>
    );
  }

  const needsReview = data ? hasNeedsReviewSignal(data) : false;

  return (
    <CompactPage className="gradebook-detail-shell" data-testid="gradebook-submission-detail-page">
      <CompactPageHeader
        eyebrow="Bang diem"
        title="Submission result review"
        description="Backend score records, question score records, grading jobs, and manual review summaries only. Answer contents and uploaded files are intentionally not previewed in this MVP."
        secondaryActions={
          <Link className="secondary-button" to="/grading/gradebook">
            Back to gradebook
          </Link>
        }
      />

      <CompactToolbar>
        <span className="muted">Submission ID: {submissionId}</span>
        <span className="muted">Manual review controls: read-only in current scope</span>
        <span className="muted">Variant grouping/order toggle: not available from current API contract</span>
      </CompactToolbar>

      {loading ? <p className="muted">Loading backend result review detail...</p> : null}

      {!loading && error ? (
        <section className="gradebook-alert is-danger" role="alert" aria-live="polite">
          <h3>{error.status === 404 ? 'Submission not found' : 'Unable to load submission review detail'}</h3>
          <p className="error">{error.message}</p>
          <p className="muted">Error code: {error.code}</p>
        </section>
      ) : null}

      {!loading && !error && data ? (
        <div className="gradebook-detail-grid">
          {needsReview ? (
            <section className="gradebook-alert is-warning" aria-live="polite">
              <h3>Needs review</h3>
              <p>
                This submission still has backend review signals. Manual review remains read-only in this MVP; no
                resolve or override control is exposed here.
              </p>
            </section>
          ) : null}

          <CompactStatBar
            items={[
              { label: 'Submission ID', value: String(data.submission.exam_submission_id) },
              { label: 'Grading status', value: getStatusLabel(data.submission.grading_status) },
              { label: 'Final score', value: data.score ? formatScore(data.score.final_score, data.score.total_max_score) : 'Not graded yet' },
              { label: 'Needs review', value: needsReview ? 'Yes' : 'No' },
            ]}
          />

          <section className="gradebook-detail-columns">
            <CompactSurface className="gradebook-detail-card" title="Submission summary" tight>
              <dl className="gradebook-definition-list">
                <div>
                  <dt>Candidate</dt>
                  <dd>{formatNullable(data.submission.student_full_name, 'Unnamed candidate')}</dd>
                </div>
                <div>
                  <dt>Student code</dt>
                  <dd>{formatNullable(data.submission.student_code)}</dd>
                </div>
                <div>
                  <dt>Exam</dt>
                  <dd>{formatNullable(data.submission.exam_title)}</dd>
                </div>
                <div>
                  <dt>Sitting</dt>
                  <dd>{`#${data.submission.exam_sitting_id}`}</dd>
                </div>
                <div>
                  <dt>Room</dt>
                  <dd>{data.submission.room_name ? `${data.submission.room_name}` : 'Not assigned'}</dd>
                </div>
                <div>
                  <dt>Submission status</dt>
                  <dd>
                    <span className={getStatusClassName(data.submission.submission_status)}>
                      {getStatusLabel(data.submission.submission_status)}
                    </span>
                  </dd>
                </div>
                <div>
                  <dt>Sealed at</dt>
                  <dd>{formatDateTime(data.submission.sealed_at)}</dd>
                </div>
                <div>
                  <dt>Last graded</dt>
                  <dd>{formatDateTime(data.submission.last_graded_at)}</dd>
                </div>
              </dl>
            </CompactSurface>

            <CompactSurface className="gradebook-detail-card" title="Score summary" tight>
              {data.score ? (
                <dl className="gradebook-definition-list">
                  <div>
                    <dt>Score status</dt>
                    <dd>
                      <span className={getStatusClassName(data.score.score_status)}>{getStatusLabel(data.score.score_status)}</span>
                    </dd>
                  </div>
                  <div>
                    <dt>Final score</dt>
                    <dd>{formatScore(data.score.final_score, data.score.total_max_score)}</dd>
                  </div>
                  <div>
                    <dt>Total raw score</dt>
                    <dd>{formatNumber(data.score.total_raw_score)}</dd>
                  </div>
                  <div>
                    <dt>Total max score</dt>
                    <dd>{formatNumber(data.score.total_max_score)}</dd>
                  </div>
                  <div>
                    <dt>Scored at</dt>
                    <dd>{formatDateTime(data.score.scored_at)}</dd>
                  </div>
                  <div>
                    <dt>Finalized at</dt>
                    <dd>{formatDateTime(data.score.finalized_at)}</dd>
                  </div>
                </dl>
              ) : (
                <p className="muted">No current submission score record is available yet. The backend has not finalized a score for this submission.</p>
              )}
            </CompactSurface>
          </section>

          <CompactSurface className="gradebook-detail-card" title="Question scores" description="Per-question backend grading records only. No answer body or file content is rendered here." tight>

            {data.question_scores.length === 0 ? (
              <p className="muted">No question score rows are available yet.</p>
            ) : (
              <div className="gradebook-table-wrap compact-data-table">
                <table data-testid="gradebook-question-scores-table" className="table-compact">
                  <thead>
                    <tr>
                      <th>Question</th>
                      <th>Mode / type</th>
                      <th>Status</th>
                      <th>Raw / max</th>
                      <th>Percent</th>
                      <th>Comparison</th>
                      <th>Needs review</th>
                      <th>Notes</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.question_scores.map((item) => {
                      const questionLabel =
                        item.question_title ??
                        (item.question_order != null ? `Question ${item.question_order}` : null) ??
                        (item.generated_exam_question_id != null ? `Question #${item.generated_exam_question_id}` : `Score row #${item.question_score_id}`);
                      const gradingMode =
                        item.grading_mode ??
                        item.answer_language ??
                        item.input_source ??
                        item.scored_engine_code ??
                        'Backend-defined';
                      const comparisonDetail = item.comparison_status ?? item.comparison_method ?? 'Not available';
                      const noteParts = [item.error_code, item.error_message, item.feedback].filter(
                        (value): value is string => Boolean(value && value.trim())
                      );

                      return (
                        <tr key={item.question_score_id}>
                          <td>
                            <div className="gradebook-table-cell-stack">
                              <strong>{questionLabel}</strong>
                              {item.generated_exam_question_id != null ? <span>Variant ID #{item.generated_exam_question_id}</span> : null}
                              {item.question_order != null ? <span>Display order #{item.question_order}</span> : <span>Display order unavailable</span>}
                              <span>Row #{item.question_score_id}</span>
                            </div>
                          </td>
                          <td>
                            <div className="gradebook-table-cell-stack">
                              <span>{gradingMode}</span>
                              {item.scored_engine_code ? <span>Engine {item.scored_engine_code}</span> : null}
                            </div>
                          </td>
                          <td>
                            <span className={getStatusClassName(item.score_status)}>{getStatusLabel(item.score_status)}</span>
                          </td>
                          <td>{formatScore(item.raw_score, item.max_score)}</td>
                          <td>
                            <div className="gradebook-table-cell-stack">
                              <span>{formatPercentage(item.score_percent)}</span>
                              {item.normalized_score != null ? <span>Normalized {item.normalized_score}</span> : null}
                            </div>
                          </td>
                          <td>{comparisonDetail}</td>
                          <td>{item.requires_manual_review ? 'Needs review' : 'No review flag'}</td>
                          <td>
                            {noteParts.length > 0 ? (
                              <ul className="gradebook-inline-list">
                                {noteParts.map((part) => (
                                  <li key={`${item.question_score_id}-${part}`}>{part}</li>
                                ))}
                              </ul>
                            ) : (
                              <span className="muted">No backend note.</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </CompactSurface>

          <section className="gradebook-detail-columns">
            <CompactSurface className="gradebook-detail-card" title="Manual reviews" tight>
              {data.manual_reviews.length === 0 ? (
                <p className="muted">No manual review rows are attached to this submission.</p>
              ) : (
                <div className="gradebook-table-wrap">
                  <table className="table-compact">
                    <thead>
                      <tr>
                        <th>Review ID</th>
                        <th>Status</th>
                        <th>Reason</th>
                        <th>Created</th>
                        <th>Resolved</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.manual_reviews.map((item) => (
                        <tr key={item.manual_review_id}>
                          <td>{item.manual_review_id}</td>
                          <td>
                            <span className={getStatusClassName(item.review_status)}>{getStatusLabel(item.review_status)}</span>
                          </td>
                          <td>{formatNullable(item.review_reason)}</td>
                          <td>{formatDateTime(item.created_at)}</td>
                          <td>{formatDateTime(item.resolved_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CompactSurface>

            <CompactSurface className="gradebook-detail-card" title="Grading jobs and events" tight>
              <div className="gradebook-detail-stacked-list">
                <div>
                  <strong>Jobs</strong>
                  <span>{data.jobs.length}</span>
                </div>
                <div>
                  <strong>Events</strong>
                  <span>{data.events.length}</span>
                </div>
              </div>

              {data.jobs.length > 0 ? (
                <div className="gradebook-table-wrap">
                  <table className="table-compact">
                    <thead>
                      <tr>
                        <th>Job ID</th>
                        <th>Status</th>
                        <th>Mode</th>
                        <th>Attempt</th>
                        <th>Error</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.jobs.map((item) => (
                        <tr key={item.grading_job_id}>
                          <td>{item.grading_job_id}</td>
                          <td>
                            <span className={getStatusClassName(item.grading_status)}>{getStatusLabel(item.grading_status)}</span>
                          </td>
                          <td>{formatNullable(item.grading_mode)}</td>
                          <td>{item.attempt_count}</td>
                          <td>{formatNullable(item.error_code)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="muted">No grading jobs were returned for this submission.</p>
              )}

              {data.events.length > 0 ? (
                <ul className="gradebook-inline-list" aria-label="Grading events">
                  {data.events.map((item) => (
                    <li key={item.grading_event_id}>
                      {formatNullable(item.event_type)} at {formatDateTime(item.event_at)}
                    </li>
                  ))}
                </ul>
              ) : null}
            </CompactSurface>
          </section>
        </div>
      ) : null}
    </CompactPage>
  );
}

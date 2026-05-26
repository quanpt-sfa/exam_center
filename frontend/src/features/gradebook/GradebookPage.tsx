import { useEffect, useState, type FormEvent } from 'react';
import { useSearchParams } from 'react-router-dom';
import { GradebookRequestError, listGradebookSubmissions } from './gradebookApi';
import type { GradebookFilters, GradebookListResponse, GradebookRow } from './contracts';
import { CompactPage } from '../../shared/components/compact/CompactPage';
import { CompactPageHeader } from '../../shared/components/compact/CompactPageHeader';
import { CompactSurface } from '../../shared/components/compact/CompactSurface';
import { CompactToolbar } from '../../shared/components/compact/CompactToolbar';
import { CompactStatBar } from '../../shared/components/compact/CompactStatBar';
import { IconActionButton, RowActionGroup } from '../../shared/components/compact/IconActionButton';

const DEFAULT_LIMIT = 50;
const DEFAULT_OFFSET = 0;

const GRADING_STATUS_OPTIONS = [
  { value: '', label: 'All grading states' },
  { value: 'COMPUTED', label: 'Computed' },
  { value: 'NEEDS_REVIEW', label: 'Needs review' },
  { value: 'PENDING', label: 'Pending' },
  { value: 'NOT_DISPATCHED', label: 'Not dispatched' },
  { value: 'FAILED', label: 'Failed' },
];

const SUBMISSION_STATUS_OPTIONS = [
  { value: '', label: 'All submission states' },
  { value: 'DRAFT', label: 'Draft' },
  { value: 'IN_PROGRESS', label: 'In progress' },
  { value: 'SUBMITTED', label: 'Submitted' },
  { value: 'SEALED', label: 'Sealed' },
];

type GradebookFilterForm = {
  exam_id: string;
  exam_sitting_id: string;
  exam_sitting_room_id: string;
  student_query: string;
  grading_status: string;
  submission_status: string;
  needs_review: string;
};

type ParsedGradebookFilters = {
  filters: GradebookFilters;
  form: GradebookFilterForm;
  errors: string[];
  limit: number;
  offset: number;
};

type StatusTone = 'success' | 'warning' | 'danger' | 'neutral';

function createDefaultFilterForm(): GradebookFilterForm {
  return {
    exam_id: '',
    exam_sitting_id: '',
    exam_sitting_room_id: '',
    student_query: '',
    grading_status: '',
    submission_status: '',
    needs_review: '',
  };
}

function parsePositiveInteger(rawValue: string | null, label: string, errors: string[]): number | undefined {
  if (rawValue == null || rawValue.trim() === '') {
    return undefined;
  }

  const parsed = Number(rawValue);
  if (!Number.isInteger(parsed) || parsed <= 0) {
    errors.push(`${label} must be a positive integer.`);
    return undefined;
  }

  return parsed;
}

function parseNonNegativeInteger(rawValue: string | null, label: string, errors: string[]): number | undefined {
  if (rawValue == null || rawValue.trim() === '') {
    return undefined;
  }

  const parsed = Number(rawValue);
  if (!Number.isInteger(parsed) || parsed < 0) {
    errors.push(`${label} must be zero or a positive integer.`);
    return undefined;
  }

  return parsed;
}

function parseGradebookFilters(searchParams: URLSearchParams): ParsedGradebookFilters {
  const errors: string[] = [];
  const form = createDefaultFilterForm();
  const filters: GradebookFilters = {};

  form.exam_id = searchParams.get('exam_id') ?? '';
  form.exam_sitting_id = searchParams.get('exam_sitting_id') ?? '';
  form.exam_sitting_room_id = searchParams.get('exam_sitting_room_id') ?? '';
  form.student_query = searchParams.get('student_query') ?? '';
  form.grading_status = searchParams.get('grading_status') ?? '';
  form.submission_status = searchParams.get('submission_status') ?? '';
  form.needs_review = searchParams.get('needs_review') ?? '';

  const examId = parsePositiveInteger(form.exam_id, 'Exam ID filter', errors);
  const examSittingId = parsePositiveInteger(form.exam_sitting_id, 'Exam sitting ID filter', errors);
  const roomId = parsePositiveInteger(form.exam_sitting_room_id, 'Room filter', errors);
  const limit = parsePositiveInteger(searchParams.get('limit'), 'Limit', errors) ?? DEFAULT_LIMIT;
  const offset = parseNonNegativeInteger(searchParams.get('offset'), 'Offset', errors) ?? DEFAULT_OFFSET;

  if (limit > 200) {
    errors.push('Limit cannot be greater than 200.');
  }

  if (examId !== undefined) {
    filters.exam_id = examId;
  }
  if (examSittingId !== undefined) {
    filters.exam_sitting_id = examSittingId;
  }
  if (roomId !== undefined) {
    filters.exam_sitting_room_id = roomId;
  }
  if (form.student_query.trim()) {
    filters.student_query = form.student_query.trim();
  }
  if (form.grading_status) {
    filters.grading_status = form.grading_status;
  }
  if (form.submission_status) {
    filters.submission_status = form.submission_status;
  }
  if (form.needs_review === 'true') {
    filters.needs_review = true;
  } else if (form.needs_review === 'false') {
    filters.needs_review = false;
  }

  filters.limit = Math.min(limit, 200);
  filters.offset = offset;

  return {
    filters,
    form,
    errors,
    limit: Math.min(limit, 200),
    offset,
  };
}

function buildSearchParams(form: GradebookFilterForm, limit = DEFAULT_LIMIT, offset = DEFAULT_OFFSET): URLSearchParams {
  const nextParams = new URLSearchParams();

  if (form.exam_id.trim()) {
    nextParams.set('exam_id', form.exam_id.trim());
  }
  if (form.exam_sitting_id.trim()) {
    nextParams.set('exam_sitting_id', form.exam_sitting_id.trim());
  }
  if (form.exam_sitting_room_id.trim()) {
    nextParams.set('exam_sitting_room_id', form.exam_sitting_room_id.trim());
  }
  if (form.student_query.trim()) {
    nextParams.set('student_query', form.student_query.trim());
  }
  if (form.grading_status) {
    nextParams.set('grading_status', form.grading_status);
  }
  if (form.submission_status) {
    nextParams.set('submission_status', form.submission_status);
  }
  if (form.needs_review) {
    nextParams.set('needs_review', form.needs_review);
  }
  if (limit !== DEFAULT_LIMIT) {
    nextParams.set('limit', String(limit));
  }
  if (offset !== DEFAULT_OFFSET) {
    nextParams.set('offset', String(offset));
  }

  return nextParams;
}

function formatNullable(value: string | null | undefined, fallback = 'Not available'): string {
  return value && value.trim() ? value : fallback;
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

function formatScore(score: string | null, maxScore: string | null): string {
  if (score == null || maxScore == null) {
    return 'Not graded yet';
  }
  return `${score} / ${maxScore}`;
}

function formatPercentage(value: string | null): string {
  return value == null ? 'Not available' : `${value}%`;
}

function isPendingStatus(status: string): boolean {
  return status === 'PENDING' || status === 'NOT_DISPATCHED';
}

function isFailedStatus(status: string): boolean {
  return status === 'FAILED' || status === 'ERROR';
}

function getStatusTone(status: string | null | undefined): StatusTone {
  if (status === 'COMPUTED') {
    return 'success';
  }
  if (status === 'NEEDS_REVIEW') {
    return 'warning';
  }
  if (isFailedStatus(status ?? '')) {
    return 'danger';
  }
  return 'neutral';
}

function getStatusLabel(status: string | null | undefined): string {
  return status && status.trim() ? status : 'UNKNOWN';
}

function getStatusClassName(status: string | null | undefined): string {
  const tone = getStatusTone(status);
  return `gradebook-status-badge is-${tone}`;
}

function getPageCounts(items: GradebookRow[]) {
  let computed = 0;
  let pending = 0;
  let review = 0;
  let failed = 0;

  for (const item of items) {
    const status = getStatusLabel(item.grading_status);
    if (status === 'COMPUTED') {
      computed += 1;
    } else if (status === 'NEEDS_REVIEW' || item.needs_review) {
      review += 1;
    } else if (isPendingStatus(status)) {
      pending += 1;
    } else if (isFailedStatus(status)) {
      failed += 1;
    }
  }

  return { computed, pending, review, failed };
}

export function GradebookPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [filters, setFilters] = useState<GradebookFilterForm>(() => parseGradebookFilters(searchParams).form);
  const [data, setData] = useState<GradebookListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<GradebookRequestError | null>(null);
  const [reloadTick, setReloadTick] = useState(0);

  const queryState = parseGradebookFilters(searchParams);
  const queryKey = searchParams.toString();
  const pageCounts = getPageCounts(data?.items ?? []);
  const currentPage = Math.floor(queryState.offset / queryState.limit) + 1;
  const totalPages = data ? Math.max(1, Math.ceil(data.total / queryState.limit)) : 1;
  const pageStart = data && data.items.length > 0 ? queryState.offset + 1 : 0;
  const pageEnd = data ? queryState.offset + data.items.length : 0;
  const hasPreviousPage = queryState.offset > 0;
  const hasNextPage = Boolean(data) && queryState.offset + data.items.length < data.total;

  useEffect(() => {
    setFilters(queryState.form);
  }, [queryKey]);

  useEffect(() => {
    if (queryState.errors.length > 0) {
      setLoading(false);
      setData(null);
      setError(null);
      return;
    }

    let cancelled = false;

    async function loadGradebook() {
      setLoading(true);
      setError(null);
      try {
        const response = await listGradebookSubmissions(queryState.filters);
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
                  message: 'Unable to load the gradebook.',
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

    void loadGradebook();

    return () => {
      cancelled = true;
    };
  }, [queryKey, reloadTick]);

  function handleFilterSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSearchParams(buildSearchParams(filters));
  }

  function handleClearFilters() {
    setFilters(createDefaultFilterForm());
    setSearchParams(new URLSearchParams());
  }

  function handlePageChange(nextOffset: number) {
    setSearchParams(buildSearchParams(filters, queryState.limit, nextOffset));
  }

  return (
    <CompactPage data-testid="gradebook-page">
      <CompactPageHeader
        eyebrow="Bang diem"
        title="Gradebook"
        description="Backend-computed and finalized scores only. SQL auto-grading states shown here reflect grading jobs and score records returned by the backend; the frontend does not recompute totals."
        primaryActions={
          <button type="button" className="secondary-button" onClick={() => setReloadTick((current) => current + 1)} disabled={loading}>
            {loading ? 'Loading...' : 'Refresh'}
          </button>
        }
      />

      <CompactToolbar>
        <span className="muted">Review mode: backend-authoritative, read-only summary</span>
        <span className="muted">Question-order grouping toggle: unavailable in current contract</span>
      </CompactToolbar>

      <CompactSurface className="gradebook-page-shell" title="Submission queue" tight>
      <form className="gradebook-filter-form" data-testid="gradebook-filter-form" onSubmit={handleFilterSubmit}>
        <CompactToolbar>
        <label>
          Exam ID
          <input
            type="number"
            min="1"
            value={filters.exam_id}
            onChange={(event) => setFilters((current) => ({ ...current, exam_id: event.target.value }))}
          />
        </label>
        <label>
          Sitting ID
          <input
            type="number"
            min="1"
            value={filters.exam_sitting_id}
            onChange={(event) => setFilters((current) => ({ ...current, exam_sitting_id: event.target.value }))}
          />
        </label>
        <label>
          Room ID
          <input
            type="number"
            min="1"
            value={filters.exam_sitting_room_id}
            onChange={(event) => setFilters((current) => ({ ...current, exam_sitting_room_id: event.target.value }))}
          />
        </label>
        <label>
          Student search
          <input
            type="search"
            value={filters.student_query}
            onChange={(event) => setFilters((current) => ({ ...current, student_query: event.target.value }))}
            placeholder="Student code or full name"
          />
        </label>
        <label>
          Grading status
          <select
            value={filters.grading_status}
            onChange={(event) => setFilters((current) => ({ ...current, grading_status: event.target.value }))}
          >
            {GRADING_STATUS_OPTIONS.map((option) => (
              <option key={option.value || 'all'} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Submission status
          <select
            value={filters.submission_status}
            onChange={(event) => setFilters((current) => ({ ...current, submission_status: event.target.value }))}
          >
            {SUBMISSION_STATUS_OPTIONS.map((option) => (
              <option key={option.value || 'all'} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Needs review
          <select
            value={filters.needs_review}
            onChange={(event) => setFilters((current) => ({ ...current, needs_review: event.target.value }))}
          >
            <option value="">All review states</option>
            <option value="true">Needs review</option>
            <option value="false">Does not need review</option>
          </select>
        </label>
        <div className="gradebook-filter-actions">
          <button type="submit" className="primary-button">
            Apply filters
          </button>
          <button type="button" className="secondary-button" onClick={handleClearFilters}>
            Clear filters
          </button>
        </div>
        </CompactToolbar>
      </form>

      {queryState.errors.length > 0 ? (
        <section className="gradebook-alert is-danger" role="alert" aria-live="polite">
          <h3>Invalid filters</h3>
          <ul>
            {queryState.errors.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      ) : null}

      {loading ? (
        <section className="gradebook-alert" aria-live="polite">
          <p className="muted">Loading backend gradebook rows...</p>
        </section>
      ) : null}

      {!loading && error ? (
        <section className="gradebook-alert is-danger" role="alert" aria-live="polite">
          <h3>Unable to load the gradebook</h3>
          <p className="error">{error.message}</p>
          <p className="muted">Error code: {error.code}</p>
        </section>
      ) : null}

      {!loading && !error && data && data.items.length === 0 ? (
        <section className="empty-state" aria-live="polite">
          <h3>No submissions match these filters</h3>
          <p>Try widening the backend-supported filters or clear them to return to the default list.</p>
        </section>
      ) : null}

      {!loading && !error && data && data.items.length > 0 ? (
        <div className="gradebook-table-section">
          <div className="gradebook-table-toolbar">
            <p className="muted">
              Showing {pageStart}-{pageEnd} of {data.total} matching submissions. Page {currentPage} of {totalPages}.
            </p>
          </div>
          <div className="gradebook-table-wrap compact-data-table">
            <table data-testid="gradebook-table" className="table-compact">
              <thead>
                <tr>
                  <th>Candidate</th>
                  <th>Exam / sitting / room</th>
                  <th>Submission status</th>
                  <th>Sealed at</th>
                  <th>Grading status</th>
                  <th>Score summary</th>
                  <th>Last graded</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((item) => (
                  <tr key={item.exam_submission_id}>
                    <td>
                      <div className="gradebook-table-cell-stack">
                        <strong>{formatNullable(item.student_full_name)}</strong>
                        <span>{formatNullable(item.student_code)}</span>
                      </div>
                    </td>
                    <td>
                      <div className="gradebook-table-cell-stack">
                        <strong>{formatNullable(item.exam_title)}</strong>
                        <span>Sitting #{item.exam_sitting_id}</span>
                        <span>{item.room_name ? `Room ${item.room_name}` : 'Room not assigned'}</span>
                      </div>
                    </td>
                    <td>
                      <span className={getStatusClassName(item.submission_status)}>{getStatusLabel(item.submission_status)}</span>
                    </td>
                    <td>{formatDateTime(item.sealed_at)}</td>
                    <td>
                      <span className={getStatusClassName(item.grading_status)}>{getStatusLabel(item.grading_status)}</span>
                    </td>
                    <td>
                      <div className="gradebook-table-cell-stack">
                        <strong>{formatScore(item.total_score, item.max_score)}</strong>
                        <span>{formatPercentage(item.percentage)}</span>
                        <span>{item.needs_review ? 'Needs review' : 'No review flag'}</span>
                      </div>
                    </td>
                    <td>{formatDateTime(item.last_graded_at)}</td>
                    <td>
                      <IconActionButton
                        icon="view"
                        to={`/grading/gradebook/submissions/${item.exam_submission_id}`}
                        label={`View detail for submission ${item.exam_submission_id}`}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <RowActionGroup className="gradebook-pagination">
            <IconActionButton
              icon="chevron-left"
              label="Previous page"
              onClick={() => handlePageChange(Math.max(DEFAULT_OFFSET, queryState.offset - queryState.limit))}
              disabled={!hasPreviousPage}
            />
            <IconActionButton
              icon="chevron-right"
              label="Next page"
              onClick={() => handlePageChange(queryState.offset + queryState.limit)}
              disabled={!hasNextPage}
            />
          </RowActionGroup>

          <CompactStatBar
            items={[
              { label: 'Matching submissions', value: data.total, hint: 'Across the current backend query.' },
              { label: 'Computed on this page', value: pageCounts.computed, hint: 'Current page only.' },
              { label: 'Pending / not dispatched', value: pageCounts.pending, hint: 'Current page only.' },
              { label: 'Needs review', value: pageCounts.review, hint: 'Current page only.' },
              { label: 'Failed / error', value: pageCounts.failed, hint: 'Current page only.' },
            ]}
          />
        </div>
      ) : null}
      </CompactSurface>
    </CompactPage>
  );
}

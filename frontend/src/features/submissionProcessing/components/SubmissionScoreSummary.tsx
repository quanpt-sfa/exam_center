import { ProcessingStatusResponse } from '../types';

type SubmissionScoreSummaryProps = {
  data: ProcessingStatusResponse;
};

export function SubmissionScoreSummary({ data }: SubmissionScoreSummaryProps) {
  const total = data.score.total_score;
  const max = data.score.max_score;

  if (total === null || max === null) {
    return null;
  }

  return (
    <section className="card" aria-label="Score summary">
      <h3>Score Summary</h3>
      <p><strong>Total score:</strong> {total}</p>
      <p><strong>Maximum score:</strong> {max}</p>
      <p><strong>Score status:</strong> {data.score.score_status ?? 'N/A'}</p>
      <p><strong>Finalized at:</strong> {data.score.finalized_at ?? 'Not finalized'}</p>
    </section>
  );
}

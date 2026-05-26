import { ProcessingStatusResponse } from '../types';

type ProcessingProgressPanelProps = {
  data: ProcessingStatusResponse;
};

export function ProcessingProgressPanel({ data }: ProcessingProgressPanelProps) {
  return (
    <section className="card" aria-label="Processing progress">
      <h3>Processing Progress</h3>
      <p><strong>Capture required:</strong> {data.capture.required ? 'Yes' : 'No'}</p>
      <p>
        <strong>Tasks:</strong> {data.tasks.completed} completed / {data.tasks.total} total
      </p>
      <p>
        <strong>Queued:</strong> {data.tasks.queued} | <strong>Running:</strong> {data.tasks.running} | <strong>Waiting capture:</strong> {data.tasks.waiting_capture}
      </p>
      <p>
        <strong>Failed:</strong> {data.tasks.failed} | <strong>Needs review:</strong> {data.tasks.needs_review}
      </p>
      <p>
        <strong>Results:</strong> {data.results.question_score_count} scored questions
      </p>
    </section>
  );
}

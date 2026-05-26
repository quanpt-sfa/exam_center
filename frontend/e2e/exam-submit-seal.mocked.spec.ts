import { expect, test } from '@playwright/test';

const user = {
  user_id: 2,
  username: 'ue2e_student_owner',
  display_name: 'UE2E Student Owner',
  roles: ['STUDENT'],
  permissions: [],
};

const completedStatus = {
  exam_submission_id: 12001,
  overall_status: 'COMPLETED',
  is_terminal: true,
  can_retry: false,
  pending_reason: null,
  failure_reason: null,
  seal: {
    submission_seal_id: 9001,
    seal_status: 'SEALED',
    sealed_at: '2026-05-14T08:00:00Z',
    sealed_answer_count: 1,
    has_sealed_answer: true,
  },
  capture: {
    required: false,
    status: null,
    capture_job_id: null,
    capture_profile_id: null,
    artifact_count: 0,
    dataset_count: 0,
    latest_event_type: null,
    latest_error_code: null,
    latest_error_message_sanitized: null,
  },
  grading: {
    grading_job_id: 3001,
    grading_job_status: 'COMPLETED',
    grading_run_id: 4001,
    grading_run_status: 'COMPLETED',
    worker_id: null,
    claimed_at: null,
    finished_at: '2026-05-14T08:01:00Z',
    latest_event_type: 'GRADING_COMPLETED',
  },
  tasks: {
    total: 1,
    queued: 0,
    running: 0,
    waiting_capture: 0,
    completed: 1,
    failed: 0,
    needs_review: 0,
    by_input_source: { SEALED_TEXT_ANSWER: 1 },
    by_answer_language: { SQL: 1 },
  },
  results: {
    actual_result_count: 1,
    comparison_count: 1,
    question_score_count: 1,
  },
  score: {
    submission_score_id: 7001,
    total_score: 5,
    max_score: 5,
    score_status: 'FINAL',
    finalized_at: '2026-05-14T08:01:00Z',
  },
  timestamps: {
    created_at: '2026-05-14T07:55:00Z',
    updated_at: '2026-05-14T08:01:00Z',
    latest_activity_at: '2026-05-14T08:01:00Z',
  },
};

test.describe('UE2E-B browser flow with mocked Backend API', () => {
  test('student login to exam answer autosave seal and result redirect', async ({ page }) => {
    const autosaveRequests: unknown[] = [];
    const sealRequests: unknown[] = [];

    await page.route('**/api/v1/**', async (route) => {
      const request = route.request();
      const url = new URL(request.url());
      const path = url.pathname;

      if (request.method() === 'POST' && path === '/api/v1/auth/login') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ok: true,
            data: {
              access_token: 'mock-access-token',
              refresh_token: 'mock-refresh-token',
              user,
            },
            error: null,
          }),
        });
        return;
      }

      if (request.method() === 'GET' && path === '/api/v1/auth/me') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ ok: true, data: user, error: null }),
        });
        return;
      }

      if (request.method() === 'GET' && path === '/api/v1/exam-sessions') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ok: true,
            data: {
              items: [
                {
                  exam_session_id: 99,
                  session_code: 'UE2E-SQL-01',
                  session_status: 'READY_TO_START',
                  assignment_status: 'ASSIGNED',
                  sitting_name: 'UE2E SQL ca 01',
                  course_code: 'DB101',
                  course_name: 'Databases',
                  room_code: 'LAB1',
                  seat_no: 'A01',
                },
              ],
            },
            error: null,
          }),
        });
        return;
      }

      if (request.method() === 'GET' && path === '/api/v1/exam-sessions/99/taking-payload') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ok: true,
            data: {
              session: {
                exam_session_id: 99,
                session_code: 'UE2E-SQL-01',
                session_status: 'IN_PROGRESS',
              },
              submission: {
                exam_submission_id: 12001,
                exam_session_id: 99,
                generated_exam_instance_id: 7001,
                submission_status: 'DRAFT',
              },
              paper: {
                exam_session_id: 99,
                generated_exam_instance_id: 7001,
                generation_status: 'GENERATED',
                questions: [
                  {
                    generated_exam_question_id: 501,
                    question_order: 1,
                    question_code: 'Q1',
                    question_type: 'TEXTBOX_SQL',
                    rendered_question_text: 'Write a SQL query for active students.',
                    rendered_question_payload_json: {},
                    score: 5,
                  },
                ],
              },
              timer: {
                remaining_seconds: 3600,
              },
            },
            error: null,
          }),
        });
        return;
      }

      if (request.method() === 'POST' && path === '/api/v1/submissions/12001/answers/autosave') {
        autosaveRequests.push(request.postDataJSON());
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ok: true,
            data: {
              exam_submission_id: 12001,
              batch_status: 'APPLIED',
              idempotent: false,
              server_ack_revision: 1,
              items: [],
            },
            error: null,
          }),
        });
        return;
      }

      if (request.method() === 'POST' && path === '/api/v1/submissions/12001/seal') {
        sealRequests.push(request.postDataJSON());
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ok: true,
            data: {
              exam_submission_id: 12001,
              submission_seal_id: 9001,
              seal_status: 'SEALED',
              submission_status: 'SUBMITTED',
              idempotent: false,
            },
            error: null,
          }),
        });
        return;
      }

      if (request.method() === 'GET' && path === '/api/v1/submissions/12001/processing-status') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ ok: true, data: completedStatus, error: null }),
        });
        return;
      }

      await route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({
          error: {
            code: 'not_mocked',
            message: `No mocked route for ${request.method()} ${path}`,
            details: {},
            request_id: null,
          },
        }),
      });
    });

    page.on('dialog', (dialog) => dialog.accept());

    await page.goto('/login');
    await page.locator('#identifier').fill('ue2e_student_owner');
    await page.locator('#password').fill('123');
    await page.locator('button[type="submit"]').click();

    await expect(page.getByText('UE2E SQL ca 01').first()).toBeVisible();
    await page.getByRole('link', { name: /Vào lớp thi|Vao lop thi/i }).click();
    await expect(page.getByText('Write a SQL query for active students.')).toBeVisible();

    await page.getByLabel(/Câu trả lời|Cau tra loi/i).fill('select * from students where active = true');
    await expect.poll(() => autosaveRequests.length, { timeout: 4000 }).toBeGreaterThan(0);

    await page.getByRole('button', { name: /Nộp bài|Nop bai/i }).click();
    await expect.poll(() => sealRequests.length, { timeout: 4000 }).toBe(1);
    await expect(page).toHaveURL(/\/submissions\/12001\/result$/);
    await expect(page.getByText(/Status:\s*Completed/i)).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Score Summary' })).toBeVisible();
  });
});

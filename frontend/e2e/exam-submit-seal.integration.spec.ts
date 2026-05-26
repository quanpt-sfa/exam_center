import { expect, test } from '@playwright/test';

import { authenticateAs } from './support/auth';
import { integrationEnabled, integrationSkipReason, ownerPersona } from './support/env';
import { assertNoForbiddenTokens } from './support/redaction';
import {
  cleanupByPrefix,
  enqueueGradingForSubmission,
  seedAuthPrincipals,
  seedSubmitSealFlow,
} from './support/seed';
import { runWorkerOnce } from './support/worker';

test.describe('UE2E-B submit/seal integration', () => {
  test('scenario 2 - student login to list/taking/autosave/seal/result terminal status', async ({ page, request }) => {
    test.setTimeout(240_000);

    if (!integrationEnabled()) {
      test.skip(true, integrationSkipReason());
    }

    const suffix = `${Date.now()}-${Math.floor(Math.random() * 10_000)}`;
    const seedPrefix = `ue2e-submit-seal-${suffix}`;

    cleanupByPrefix(seedPrefix);
    const seed = seedSubmitSealFlow(suffix);

    try {
      const auth = await authenticateAs(page, ownerPersona());
      if (!auth.ok) {
        throw new Error(auth.reason || 'Auth strategy is not configured for UE2E-B integration.');
      }

      await page.goto('/exams');
      const examEntryLink = page.locator(`a[href="/exams/${seed.exam_session_id}"]`).first();
      await expect(examEntryLink).toBeVisible({ timeout: 20_000 });
      await examEntryLink.click();

      await expect(page).toHaveURL(new RegExp(`/exams/${seed.exam_session_id}$`));

      const textarea = page.getByLabel(/Câu trả lời|Cau tra loi/i);
      await expect(textarea).toBeVisible();
      await expect(textarea).toHaveValue(seed.seeded_answer_text);

      const answerText = 'SELECT 1 AS value UNION ALL SELECT 2 AS value ORDER BY value';
      await textarea.fill(answerText);
      await page.getByRole('button', { name: /Lưu ngay|Luu ngay/i }).click();

      const savedLabel = page.getByText(/Đã lưu|Da luu/i);
      const failedLabel = page.getByText(/Lưu thất bại|Luu that bai/i);
      await expect
        .poll(
          async () => {
            if (await savedLabel.isVisible()) {
              return 'saved';
            }
            if (await failedLabel.isVisible()) {
              return 'failed';
            }
            return 'pending';
          },
          { timeout: 15_000 }
        )
        .toBe('saved');

      await page.reload();
      const recoveredTextarea = page.getByLabel(/Câu trả lời|Cau tra loi/i);
      await expect(recoveredTextarea).toHaveValue(answerText, { timeout: 10_000 });

      page.once('dialog', (dialog) => dialog.accept());
      await page.getByRole('button', { name: /Nộp bài|Nop bai/i }).click();

      await expect(page).toHaveURL(new RegExp(`/submissions/${seed.exam_submission_id}/result$`));
      await expect(page.getByRole('heading', { name: 'Submission Result' })).toBeVisible();

      const authSeed = seedAuthPrincipals();
      const apiBaseUrl = (process.env.API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
      const dispatchResponse = await request.post(
        `${apiBaseUrl}/api/v1/submissions/${seed.exam_submission_id}/dispatch`,
        {
          headers: {
            Authorization: `Bearer ${authSeed.tokens.admin_access_token}`,
          },
        },
      );
      expect(dispatchResponse.ok(), `Dispatch API failed with ${dispatchResponse.status()}`).toBe(true);
      enqueueGradingForSubmission(seed.exam_submission_id, seedPrefix);

      const statusHeading = page.getByRole('heading', { name: 'Submission Processing Status' });
      await expect(statusHeading).toBeVisible();
      const statusPanel = statusHeading.locator('xpath=ancestor::section[1]');
      await expect(statusPanel).toContainText(/queued for grading|being graded|automatic checking is running|processing/i);

      for (let attempt = 0; attempt < 8; attempt += 1) {
        const worker = runWorkerOnce({
          submissionId: seed.exam_submission_id,
          actorUserId: seed.owner_user_id,
          includeCaptureRole: false,
          boundedIdleCycles: 20,
        });

        expect(
          worker.exitCode,
          `Worker run-all invocation failed (attempt ${attempt + 1}):\n${worker.stdout}\n${worker.stderr}`,
        ).toBe(0);

        if (await page.getByText(/Status:\s*Completed/i).isVisible()) {
          break;
        }
      }

      await expect(page.getByText(/Status:\s*Completed/i)).toBeVisible({ timeout: 90_000 });
      await expect(page.getByText(/Processing completed\./i)).toBeVisible();
      await expect(page.getByRole('heading', { name: 'Score Summary' })).toBeVisible();

      const renderedText = await page.locator('body').innerText();
      assertNoForbiddenTokens(renderedText, 'submit/seal integration rendered text');
    } finally {
      cleanupByPrefix(seedPrefix);
    }
  });
});

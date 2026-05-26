import { expect, test } from '@playwright/test';

import { authenticateAs } from './support/auth';
import {
  integrationEnabled,
  integrationSkipReason,
  ownerPersona,
} from './support/env';
import { assertNoForbiddenTokens } from './support/redaction';
import { cleanupByPrefix, seedTextboxSubmission } from './support/seed';
import { runWorkerOnce } from './support/worker';

test.describe('UE2E-A submission processing textbox', () => {
  test('scenario 1 - direct TEXTBOX_SQL hybrid happy path', async ({ page }) => {
    test.setTimeout(180_000);

    if (!integrationEnabled()) {
      test.skip(true, integrationSkipReason());
    }

    const suffix = `${Date.now()}-${Math.floor(Math.random() * 10_000)}`;
    const seedPrefix = `ue2e-textbox-${suffix}`;
    cleanupByPrefix(seedPrefix);
    const seed = seedTextboxSubmission(suffix);

    const auth = await authenticateAs(page, ownerPersona());
    if (!auth.ok) {
      throw new Error(auth.reason || 'Auth strategy is not configured for UE2E-A.');
    }

    await page.goto(`/submissions/${seed.exam_submission_id}/result`);
    await expect(page.getByRole('heading', { name: 'Submission Result' })).toBeVisible();
    const statusHeading = page.getByRole('heading', { name: 'Submission Processing Status' });
    await expect(statusHeading).toBeVisible();

    const statusPanel = statusHeading.locator('xpath=ancestor::section[1]');
    await expect(statusPanel).toContainText(/queued for grading|being graded|automatic checking is running|processing/i);

    for (let attempt = 0; attempt < 3; attempt += 1) {
      const worker = runWorkerOnce({
        submissionId: seed.exam_submission_id,
        actorUserId: seed.owner_user_id,
        includeCaptureRole: false,
        boundedIdleCycles: 6,
      });

      expect(
        worker.exitCode,
        `Worker run-all invocation failed (attempt ${attempt + 1}):\n${worker.stdout}\n${worker.stderr}`,
      ).toBe(0);

      const completedVisible = await page.getByText(/Status:\s*Completed/i).isVisible();
      if (completedVisible) {
        break;
      }
    }

    await expect(page.getByText(/Status:\s*Completed/i)).toBeVisible({ timeout: 90_000 });
    await expect(page.getByText(/Processing completed\./i)).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Score Summary' })).toBeVisible();
    await expect(page.getByText(/Automatic checking has stopped\./i)).toBeVisible();

    const renderedText = await page.locator('body').innerText();
    assertNoForbiddenTokens(renderedText, 'textbox scenario rendered text');

    cleanupByPrefix(seedPrefix);
  });
});

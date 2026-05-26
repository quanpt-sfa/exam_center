import { expect, test } from '@playwright/test';

import { authenticateAs } from './support/auth';
import { integrationEnabled, integrationSkipReason, ownerPersona } from './support/env';
import { assertNoForbiddenTokens } from './support/redaction';
import { cleanupByPrefix, seedCaptureFailureSubmission } from './support/seed';

test.describe('UE2E-A submission processing failures', () => {
  test('scenario 3 - capture failure shows sanitized terminal failure state', async ({ page }) => {
    test.setTimeout(120_000);

    if (!integrationEnabled()) {
      test.skip(true, integrationSkipReason());
    }

    const suffix = `${Date.now()}-${Math.floor(Math.random() * 10_000)}`;
    const seedPrefix = `ue2e-failure-${suffix}`;
    cleanupByPrefix(seedPrefix);
    const seed = seedCaptureFailureSubmission(suffix);

    const auth = await authenticateAs(page, ownerPersona());
    if (!auth.ok) {
      throw new Error(auth.reason || 'Auth strategy is not configured for UE2E-A.');
    }

    await page.goto(`/submissions/${seed.exam_submission_id}/result`);

    await expect(page.getByRole('heading', { name: 'Submission Processing Status' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Processing failed' })).toBeVisible();
    await expect(
      page.getByRole('alert').getByText(/Capture step failed\.|Grading step failed\./i),
    ).toBeVisible();
    await expect(page.getByText(/Automatic checking has stopped\./i)).toBeVisible();

    const renderedText = await page.locator('body').innerText();
    assertNoForbiddenTokens(renderedText, 'failure scenario rendered text');

    cleanupByPrefix(seedPrefix);
  });
});

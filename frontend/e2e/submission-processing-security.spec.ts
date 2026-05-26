import { expect, test } from '@playwright/test';

import { authenticateAs } from './support/auth';
import {
  integrationEnabled,
  integrationSkipReason,
  nonOwnerPersona,
  ownerPersona,
} from './support/env';
import { assertNoForbiddenTokens } from './support/redaction';
import { cleanupByPrefix, seedTextboxSubmission } from './support/seed';

test.describe('UE2E-A submission processing security', () => {
  test('scenario 5 - unauthorized student cannot view another student result', async ({ page }) => {
    test.setTimeout(120_000);

    if (!integrationEnabled()) {
      test.skip(true, integrationSkipReason());
    }

    const suffix = `${Date.now()}-${Math.floor(Math.random() * 10_000)}`;
    const seedPrefix = `ue2e-textbox-${suffix}`;
    cleanupByPrefix(seedPrefix);
    const seed = seedTextboxSubmission(suffix);

    const auth = await authenticateAs(page, nonOwnerPersona());
    if (!auth.ok) {
      throw new Error(auth.reason || 'Auth strategy is not configured for unauthorized scenario.');
    }

    await page.goto(`/submissions/${seed.exam_submission_id}/result`);
    await expect(page.getByRole('heading', { name: /Access denied/i })).toBeVisible();
    await expect(page.getByText(/not allowed to view this submission status/i)).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Score Summary' })).toHaveCount(0);

    const renderedText = await page.locator('body').innerText();
    assertNoForbiddenTokens(renderedText, 'unauthorized scenario rendered text');

    cleanupByPrefix(seedPrefix);
  });

  test('scenario 6 - unknown submission shows not found without leaking internals', async ({ page }) => {
    if (!integrationEnabled()) {
      test.skip(true, integrationSkipReason());
    }

    const auth = await authenticateAs(page, ownerPersona());
    if (!auth.ok) {
      throw new Error(auth.reason || 'Auth strategy is not configured for unknown submission scenario.');
    }

    await page.goto('/submissions/987654321/result');
    await expect(page.getByRole('heading', { name: /Submission not found/i })).toBeVisible();
    await expect(page.getByText(/requested submission could not be found/i)).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Score Summary' })).toHaveCount(0);

    const renderedText = await page.locator('body').innerText();
    assertNoForbiddenTokens(renderedText, 'unknown submission scenario rendered text');
  });
});

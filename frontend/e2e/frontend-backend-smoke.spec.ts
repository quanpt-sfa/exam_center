import { expect, test } from '@playwright/test';

import { apiBaseUrl } from './support/env';

test('frontend login shell loads against standalone backend', async ({ page, request }) => {
  const healthResponse = await request.get(`${apiBaseUrl()}/api/v1/health`);
  expect(healthResponse.ok()).toBeTruthy();

  const healthPayload = await healthResponse.json();
  expect(healthPayload.ok).toBe(true);
  expect(healthPayload.data?.status).toBe('ok');

  await page.goto('/login');

  await expect(page.getByTestId('academy-name')).toBeVisible();
  await expect(page.getByRole('heading', { name: /Ch\u00e0o m\u1eebng tr\u1edf l\u1ea1i/i })).toBeVisible();
  await expect(page.getByLabel(/T\u00e0i kho\u1ea3n ho\u1eb7c email/i)).toBeVisible();
  await expect(page.getByTestId('password-input')).toBeVisible();
  await expect(page.getByRole('button', { name: /^\u0110\u0103ng nh\u1eadp$/i })).toBeVisible();
  await expect(page.getByTestId('support-info')).toContainText('Email:');
});

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
  await expect(page.getByRole('heading', { name: /đăng nhập|dang nhap/i })).toBeVisible();
  await expect(page.getByLabel(/mật khẩu|mat khau/i)).toBeVisible();
  await expect(page.getByRole('button', { name: /đăng nhập|dang nhap/i })).toBeVisible();
  await expect(page.getByTestId('support-info')).toContainText('Email:');
});

import { defineConfig } from '@playwright/test';

const frontendBaseUrl = (process.env.FRONTEND_BASE_URL || 'http://127.0.0.1:5173').replace(/\/$/, '');
const isCi = Boolean(process.env.CI);

export default defineConfig({
  testDir: './e2e',
  timeout: 120_000,
  expect: {
    timeout: 10_000,
  },
  forbidOnly: isCi,
  retries: isCi ? 1 : 0,
  workers: isCi ? 1 : undefined,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: frontendBaseUrl,
    trace: 'retain-on-failure',
    video: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
});

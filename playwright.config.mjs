import { defineConfig } from '@playwright/test';

const liveBaseUrl = process.env.E2E_BASE_URL;
const localWebServer = {
  command: 'npm run preview -- --host 127.0.0.1 --port 4173',
  url: 'http://127.0.0.1:4173',
  reuseExistingServer: !process.env.CI,
  timeout: 30_000,
};

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: 'list',
  timeout: 30_000,
  use: {
    baseURL: liveBaseUrl || 'http://127.0.0.1:4173',
    browserName: 'chromium',
    headless: true,
    trace: 'retain-on-failure',
  },
  ...(!liveBaseUrl ? { webServer: localWebServer } : {}),
});

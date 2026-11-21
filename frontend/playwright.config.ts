import { defineConfig, devices } from '@playwright/test'

/**
 * Phase 4 E2E: runs against a locally running mousehole frontend.
 * Default target is the Docker production stack (http://127.0.0.1:8090);
 * all /api/v1 calls are mocked by the spec, so no model/API cost is incurred.
 */
export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? 'http://127.0.0.1:8090',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    acceptDownloads: true,
  },
  projects: [
    {
      name: 'chromium',
      // Use the locally installed Microsoft Edge instead of downloading
      // Playwright's Chromium build (slow network environments).
      use: { ...devices['Desktop Chrome'], channel: 'msedge' },
    },
  ],
})

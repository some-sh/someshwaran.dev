import { existsSync } from 'node:fs'

import { defineConfig, devices } from '@playwright/test'

import { ADMIN_KEY } from './testConfig'

const PORT = 8000

// Some sandboxes pre-install a Chromium build at a fixed path instead of
// letting `npx playwright install` fetch one matching the exact
// @playwright/test version — a real CI runner won't have this path, so
// only override when it's actually present.
const SANDBOX_CHROMIUM_PATH = '/opt/pw-browsers/chromium'
const sandboxExecutablePath = existsSync(SANDBOX_CHROMIUM_PATH) ? SANDBOX_CHROMIUM_PATH : undefined

export default defineConfig({
  testDir: './tests',
  // The whole suite shares one app instance and one DB — including the
  // single global "default resume" flag — so tests need to run in a
  // known order, not in parallel across workers.
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  // 'github' annotates failures inline on the run; the html report is what
  // CI uploads as an artifact so a failure can actually be inspected.
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: 'retain-on-failure',
  },
  webServer: {
    command: './run-server.sh',
    url: `http://127.0.0.1:${PORT}/health`,
    timeout: 120_000,
    reuseExistingServer: !process.env.CI,
    env: { E2E_ADMIN_KEY: ADMIN_KEY },
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        ...(sandboxExecutablePath && {
          launchOptions: { executablePath: sandboxExecutablePath },
        }),
      },
    },
  ],
})

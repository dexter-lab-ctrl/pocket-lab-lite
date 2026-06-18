import { defineConfig, devices } from '@playwright/test';
import { existsSync, readFileSync } from 'node:fs';

const pocketLabBrowserChannel = process.env.POCKETLAB_PLAYWRIGHT_CHANNEL;
const pocketLabBrowserExecutablePath = process.env.POCKETLAB_PLAYWRIGHT_EXECUTABLE_PATH;

function isWslUbuntu(): boolean {
  try {
    const version = readFileSync('/proc/version', 'utf8').toLowerCase();
    return version.includes('microsoft');
  } catch {
    return false;
  }
}

function detectSystemChrome(): string | undefined {
  const candidates = [
    '/usr/bin/google-chrome',
    '/usr/bin/google-chrome-stable',
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser'
  ];

  return candidates.find((candidate) => existsSync(candidate));
}

const detectedSystemChrome =
  !pocketLabBrowserChannel && !pocketLabBrowserExecutablePath && isWslUbuntu()
    ? detectSystemChrome()
    : undefined;

// Ubuntu 26.04 WSL2 cannot install Playwright-managed ffmpeg today.
// When using the WSL2 system Chrome fallback, disable video by default so
// plain `npx playwright test` remains reproducible. Screenshots and traces
// remain enabled for failure diagnostics.
const pocketLabVideoMode =
  process.env.POCKETLAB_PLAYWRIGHT_VIDEO === '1'
    ? 'retain-on-failure'
    : detectedSystemChrome
      ? 'off'
      : 'retain-on-failure';

const pocketLabBrowserUse = {
  ...devices['Desktop Chrome'],
  ...(pocketLabBrowserChannel
    ? { channel: pocketLabBrowserChannel as 'chrome' | 'msedge' }
    : detectedSystemChrome
      ? { channel: 'chrome' as const }
      : {}),
  ...(pocketLabBrowserExecutablePath
    ? { launchOptions: { executablePath: pocketLabBrowserExecutablePath } }
    : {})
};

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 45_000,
  expect: { timeout: 8_000 },
  retries: process.env.CI ? 2 : 0,
  outputDir: '.pocketlab-dev/test-results',
  reporter: [
    ['html', { outputFolder: '.pocketlab-dev/playwright-report', open: 'never' }],
    ['json', { outputFile: '.pocketlab-dev/validation/playwright-results.json' }],
    ['junit', { outputFile: '.pocketlab-dev/validation/playwright-junit.xml' }],
    ['list']
  ],
  use: {
    baseURL: process.env.POCKETLAB_FRONTEND_URL || 'http://127.0.0.1:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: pocketLabVideoMode
  },
  projects: [
    {
      name: pocketLabBrowserChannel ? `chromium-${pocketLabBrowserChannel}` : 'chromium',
      use: pocketLabBrowserUse
    }
  ],
  webServer: process.env.POCKETLAB_SKIP_WEB_SERVER ? undefined : {
    command: 'npm run dev -- --host 127.0.0.1',
    url: 'http://127.0.0.1:5173',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000
  }
});

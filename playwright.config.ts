import { defineConfig, devices } from '@playwright/test';
import { resolveLiteBrowser } from './scripts/dev/lite/resolve-browser.mjs';

const mode = process.env.LITE_E2E_MODE || 'mocked';
const live = mode === 'live';
const browser = resolveLiteBrowser();
const launchOptions = browser.executable_path
  ? { executablePath: browser.executable_path }
  : undefined;
const baseURL = live
  ? (process.env.LITE_BASE_URL || 'http://127.0.0.1:8443')
  : (process.env.LITE_FRONTEND_URL || 'http://127.0.0.1:5173');

const commonUse = {
  baseURL,
  launchOptions,
  trace: 'retain-on-failure' as const,
  screenshot: 'only-on-failure' as const,
  video: browser.wsl && process.env.POCKETLAB_PLAYWRIGHT_VIDEO !== '1'
    ? ('off' as const)
    : ('retain-on-failure' as const),
  serviceWorkers: live ? ('allow' as const) : ('allow' as const),
};

const mockedHar = (project: string) => ({
  path: `.pocketlab-dev/raw-har/${project}.har`,
  content: 'omit' as const,
  mode: 'minimal' as const,
  urlFilter: '**/api/lite/**',
});

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 45_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 2 : 1,
  outputDir: '.pocketlab-dev/test-results',
  globalSetup: './tests/e2e/global-setup.ts',
  reporter: [
    ['list'],
    ['html', { outputFolder: '.pocketlab-dev/playwright-report', open: 'never' }],
    ['json', { outputFile: '.pocketlab-dev/validation/playwright-results.json' }],
    ['junit', { outputFile: '.pocketlab-dev/validation/playwright-junit.xml' }],
  ],
  metadata: {
    pocketlab_lite_mode: mode,
    browser_name: browser.browser,
    browser_executable: browser.executable_path || 'playwright-managed',
    browser_version: browser.version,
    browser_launch_mode: browser.launch_mode,
  },
  use: commonUse,
  projects: [
    {
      name: 'mocked-desktop',
      testMatch: /lite-(mocked|accessibility|visual(?:-devices)?|parity)\.spec\.ts/,
      use: { ...devices['Desktop Chrome'], ...commonUse, recordHar: mockedHar('mocked-desktop') },
    },
    {
      name: 'mocked-mobile',
      testMatch: /lite-(mocked|accessibility|visual(?:-devices)?|parity)\.spec\.ts/,
      use: { ...devices['Pixel 7'], ...commonUse, recordHar: mockedHar('mocked-mobile') },
    },
    {
      name: 'live-desktop',
      testMatch: /lite-live\.spec\.ts/,
      use: { ...devices['Desktop Chrome'], ...commonUse },
    },
    {
      name: 'live-mobile',
      testMatch: /lite-live\.spec\.ts/,
      use: { ...devices['Pixel 7'], ...commonUse },
    },
  ],
  webServer: live || process.env.POCKETLAB_SKIP_WEB_SERVER
    ? undefined
    : {
        command: 'npm run dev:mock -- --host 127.0.0.1',
        url: baseURL,
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
        env: { ...process.env, VITE_POCKETLAB_MOCKS: '1' },
      },
});

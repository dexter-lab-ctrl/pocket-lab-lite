import { fileURLToPath } from 'node:url';
import { defineConfig, devices } from '@playwright/test';
import { resolveLiteBrowser } from './scripts/dev/lite/resolve-browser.mjs';
import { mkdirSync } from 'node:fs';
import { resolve, dirname } from 'node:path';

const browser = resolveLiteBrowser();
const launchOptions = browser.executable_path ? { executablePath: browser.executable_path } : undefined;
const baseURL = process.env.LITE_DOCS_URL || 'http://127.0.0.1:8001/pocket-lab-lite/';
const python = process.env.POCKETLAB_DEV_PYTHON || process.env.PYTHON || '.venv/bin/python';

const repoRoot = dirname(fileURLToPath(import.meta.url));
const pocketLabDevScratchRoot = resolve(
  repoRoot,
  process.env.POCKETLAB_DEV_TMPDIR || '.pocketlab-dev/tmp',
);
const pocketLabDocsTempDir = resolve(
  pocketLabDevScratchRoot,
  'playwright',
);

mkdirSync(pocketLabDocsTempDir, { recursive: true });

process.env.POCKETLAB_DEV_TMPDIR = pocketLabDevScratchRoot;
process.env.TMPDIR = pocketLabDocsTempDir;
process.env.TMP = pocketLabDocsTempDir;
process.env.TEMP = pocketLabDocsTempDir;

export default defineConfig({
  testDir: './tests/docs',
  timeout: 45_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  outputDir: '.pocketlab-dev/docs-test-results',
  reporter: [
    ['list'],
    ['html', { outputFolder: '.pocketlab-dev/docs-playwright-report', open: 'never' }],
    ['junit', { outputFile: '.pocketlab-dev/validation/docs-playwright-junit.xml' }],
  ],
  use: {
    baseURL,
    launchOptions,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'off',
  },
  projects: [
    { name: 'docs-desktop', use: { ...devices['Desktop Chrome'], launchOptions } },
    { name: 'docs-mobile', use: { ...devices['Pixel 7'], launchOptions } },
  ],
  webServer: process.env.POCKETLAB_SKIP_DOCS_WEB_SERVER ? undefined : {
    command: `${python} -m mkdocs serve --strict --dev-addr 127.0.0.1:8001`,
    url: baseURL,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    env: {
      ...process.env,
      TMPDIR: pocketLabDocsTempDir,
      TMP: pocketLabDocsTempDir,
      TEMP: pocketLabDocsTempDir,
    },
  },
});

#!/usr/bin/env node
import { readFileSync } from 'node:fs';
import { spawn } from 'node:child_process';
import { chromium } from '@playwright/test';
import { resolveLiteBrowser } from '../../dev/lite/resolve-browser.mjs';

const index = JSON.parse(readFileSync('storybook-static/index.json', 'utf8'));
const entries = Object.values(index.entries || {}).filter((entry) => entry.type === 'story' && String(entry.title || '').startsWith('Pocket Lab Lite/'));
if (entries.length < 70) throw new Error(`Expected at least 70 Lite stories, found ${entries.length}`);

const storybookPort = Number.parseInt(process.env.LITE_STORYBOOK_TEST_PORT || '6007', 10);
if (!Number.isInteger(storybookPort) || storybookPort < 1024 || storybookPort > 65535) {
  throw new Error(`Invalid LITE_STORYBOOK_TEST_PORT: ${process.env.LITE_STORYBOOK_TEST_PORT || ''}`);
}
const storybookOrigin = `http://127.0.0.1:${storybookPort}`;
const server = spawn('python3', ['-m', 'http.server', String(storybookPort), '--bind', '127.0.0.1', '--directory', 'storybook-static'], {
  stdio: ['ignore', 'pipe', 'pipe'],
});
let serverError = '';
server.stderr.on('data', (chunk) => { serverError += String(chunk); });
const stop = () => { if (!server.killed) server.kill('SIGTERM'); };
process.on('exit', stop);

async function waitForStorybookServer(timeoutMs = 15_000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (server.exitCode !== null) {
      throw new Error(`Storybook static server exited early (${server.exitCode}): ${serverError.trim()}`);
    }
    try {
      const response = await fetch(`${storybookOrigin}/index.json`, { cache: 'no-store' });
      if (response.ok) return;
    } catch {
      // Bounded readiness retry while the local static server starts.
    }
    await new Promise((resolve) => setTimeout(resolve, 150));
  }
  throw new Error(`Storybook static server was not ready at ${storybookOrigin}: ${serverError.trim()}`);
}

async function waitForStoryRender(page, entry, timeoutMs = 20_000) {
  const storyRoot = page.locator('[data-pocketlab-lite-storybook="true"]');
  try {
    await storyRoot.waitFor({ state: 'visible', timeout: timeoutMs });
    await page.waitForFunction(() => {
      const root = document.querySelector('#storybook-root');
      const frame = document.querySelector('[data-pocketlab-lite-storybook="true"]');
      return Boolean(root && frame && (root.textContent || '').trim().length > 0);
    }, null, { timeout: timeoutMs });
  } catch (error) {
    const diagnostics = await page.evaluate(() => ({
      readyState: document.readyState,
      title: document.title,
      rootText: (document.querySelector('#storybook-root')?.textContent || '').trim().slice(0, 500),
      rootHtml: (document.querySelector('#storybook-root')?.innerHTML || '').slice(0, 1200),
      bodyText: (document.body?.innerText || '').trim().slice(0, 500),
    })).catch(() => ({}));
    throw new Error(`${entry.id}: Storybook render did not settle: ${error.message}\n${JSON.stringify(diagnostics, null, 2)}`);
  }
}

await waitForStorybookServer();

const selected = [];
const seenTitles = new Set();
for (const entry of entries) {
  if (!seenTitles.has(entry.title)) {
    selected.push(entry);
    seenTitles.add(entry.title);
  }
}
const browserInfo = resolveLiteBrowser();
const browser = await chromium.launch({ headless: true, ...(browserInfo.executable_path ? { executablePath: browserInfo.executable_path } : {}) });
const failures = [];
try {
  for (const entry of selected) {
    const page = await browser.newPage({ viewport: { width: 390, height: 844 }, reducedMotion: 'reduce' });
    const errors = [];
    page.on('pageerror', (error) => errors.push(error.message));
    await page.goto(`${storybookOrigin}/iframe.html?id=${encodeURIComponent(entry.id)}&viewMode=story`, { waitUntil: 'domcontentloaded' });
    await waitForStoryRender(page, entry);
    const rootText = await page.locator('#storybook-root').innerText().catch(() => '');
    if (!rootText.trim()) failures.push(`${entry.id}: empty render`);
    if (errors.length) failures.push(`${entry.id}: ${errors.join('; ')}`);
    await page.close();
  }

  const home = entries.find((entry) => entry.title === 'Pocket Lab Lite/Home' && entry.name === 'Healthy');
  if (home) {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' });
    await page.goto(`${storybookOrigin}/iframe.html?id=${encodeURIComponent(home.id)}&viewMode=story`, { waitUntil: 'domcontentloaded' });
    await waitForStoryRender(page, home);
    const devices = page.getByRole('button', { name: /^Devices/i }).locator(':visible').first();
    await devices.click();
    await page.locator('[data-lite-screen-id="devices"]').waitFor({ state: 'visible' });
    await page.close();
  } else {
    failures.push('Healthy Home story missing');
  }
} finally {
  await browser.close();
  stop();
}
if (failures.length) {
  console.error(failures.join('\n'));
  process.exit(1);
}
console.log(`PASS ${selected.length} representative Storybook renders and navigation interaction using ${browserInfo.version}`);

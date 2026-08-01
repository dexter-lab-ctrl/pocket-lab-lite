#!/usr/bin/env node
import { readFileSync } from 'node:fs';
import { spawn } from 'node:child_process';
import { chromium } from '@playwright/test';
import { resolveLiteBrowser } from '../../dev/lite/resolve-browser.mjs';

const index = JSON.parse(readFileSync('storybook-static/index.json', 'utf8'));
const entries = Object.values(index.entries || {}).filter((entry) => entry.type === 'story' && String(entry.title || '').startsWith('Pocket Lab Lite/'));
if (entries.length < 70) throw new Error(`Expected at least 70 Lite stories, found ${entries.length}`);

const server = spawn('python3', ['-m', 'http.server', '6006', '--directory', 'storybook-static'], { stdio: 'ignore' });
const stop = () => { if (!server.killed) server.kill('SIGTERM'); };
process.on('exit', stop);
await new Promise((resolve) => setTimeout(resolve, 1200));

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
    await page.goto(`http://127.0.0.1:6006/iframe.html?id=${encodeURIComponent(entry.id)}&viewMode=story`, { waitUntil: 'networkidle' });
    const rootText = await page.locator('#storybook-root').innerText().catch(() => '');
    if (!rootText.trim()) failures.push(`${entry.id}: empty render`);
    if (errors.length) failures.push(`${entry.id}: ${errors.join('; ')}`);
    await page.close();
  }

  const home = entries.find((entry) => entry.title === 'Pocket Lab Lite/Home' && entry.name === 'Healthy');
  if (home) {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' });
    await page.goto(`http://127.0.0.1:6006/iframe.html?id=${encodeURIComponent(home.id)}&viewMode=story`, { waitUntil: 'networkidle' });
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

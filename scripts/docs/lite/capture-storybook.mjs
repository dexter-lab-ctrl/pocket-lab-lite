#!/usr/bin/env node
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { spawn } from 'node:child_process';
import { chromium } from '@playwright/test';
import { resolveLiteBrowser } from '../../dev/lite/resolve-browser.mjs';

const storybookDir = 'storybook-static';
const index = JSON.parse(readFileSync(`${storybookDir}/index.json`, 'utf8'));
const entries = Object.values(index.entries || {}).filter((entry) => entry.type === 'story' && String(entry.title || '').startsWith('Pocket Lab Lite/'));
const preferred = new Map([
  ['Pocket Lab Lite/Home', 'healthy'],
  ['Pocket Lab Lite/Devices', 'server-host-online'],
  ['Pocket Lab Lite/Apps', 'catalog-ready'],
  ['Pocket Lab Lite/Recovery', 'recovery-ready'],
  ['Pocket Lab Lite/Security', 'quick-check-healthy'],
  ['Pocket Lab Lite/Identity', 'identity-summary'],
  ['Pocket Lab Lite/Rules', 'no-rules'],
]);
const selected = [];
for (const [title, suffix] of preferred) {
  selected.push(entries.find((entry) => entry.title === title && (entry.id.endsWith(`--${suffix}`) || entry.name.toLowerCase().replace(/\s+/g, '-').includes(suffix))) || entries.find((entry) => entry.title === title));
}
if (selected.some((entry) => !entry)) throw new Error('Storybook index is missing one or more required Lite tab stories.');

const server = spawn('python3', ['-m', 'http.server', '6006', '--directory', storybookDir], { stdio: 'ignore' });
const stop = () => { if (!server.killed) server.kill('SIGTERM'); };
process.on('exit', stop);
process.on('SIGINT', () => { stop(); process.exit(130); });
await new Promise((resolve) => setTimeout(resolve, 1200));

const resolved = resolveLiteBrowser();
const browser = await chromium.launch({ headless: true, ...(resolved.executable_path ? { executablePath: resolved.executable_path } : {}) });
const outputDir = 'docs/assets/lite-ui';
mkdirSync(outputDir, { recursive: true });
const manifest = { generated: true, browser: resolved, screenshots: [] };
try {
  for (const entry of selected) {
    for (const viewport of [{ name: 'mobile', width: 390, height: 844 }, { name: 'desktop', width: 1440, height: 1000 }]) {
      const page = await browser.newPage({ viewport: { width: viewport.width, height: viewport.height }, reducedMotion: 'reduce' });
      await page.goto(`http://127.0.0.1:6006/iframe.html?id=${encodeURIComponent(entry.id)}&viewMode=story`, { waitUntil: 'networkidle' });
      const file = `${outputDir}/${entry.title.split('/').pop().toLowerCase()}-${viewport.name}.png`;
      await page.screenshot({ path: file, fullPage: true, animations: 'disabled' });
      manifest.screenshots.push({ story_id: entry.id, viewport, file });
      await page.close();
    }
  }
} finally {
  await browser.close();
  stop();
}
writeFileSync(`${outputDir}/manifest.json`, `${JSON.stringify(manifest, null, 2)}\n`);
console.log(`Captured ${manifest.screenshots.length} Lite Storybook screenshots with ${resolved.version}`);

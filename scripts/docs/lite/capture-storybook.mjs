#!/usr/bin/env node
import { mkdirSync, readFileSync, renameSync, rmSync, writeFileSync } from 'node:fs';
import { spawn } from 'node:child_process';
import { chromium } from '@playwright/test';
import { resolveLiteBrowser } from '../../dev/lite/resolve-browser.mjs';

const storybookDir = 'storybook-static';
const outputDir = 'docs/generated/ui/screenshots';
const stagingDir = `docs/generated/ui/.screenshots-${process.pid}`;
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

rmSync(stagingDir, { recursive: true, force: true });
mkdirSync(stagingDir, { recursive: true });
const server = spawn('python3', ['-m', 'http.server', '6006', '--bind', '127.0.0.1', '--directory', storybookDir], { stdio: 'ignore' });
const stop = () => { if (!server.killed) server.kill('SIGTERM'); };
process.on('exit', stop);
process.on('SIGINT', () => { stop(); process.exit(130); });
await new Promise((resolve) => setTimeout(resolve, 1200));

const resolved = resolveLiteBrowser();
const browser = await chromium.launch({ headless: true, ...(resolved.executable_path ? { executablePath: resolved.executable_path } : {}) });
const manifest = {
  schema_revision: 1,
  generated: true,
  generated_at: process.env.SOURCE_GENERATED_AT || 'uncommitted',
  source_commit: process.env.SOURCE_COMMIT || 'uncommitted',
  generator: 'scripts/docs/lite/capture-storybook.mjs',
  browser: {
    mode: resolved.mode || 'external',
    version: resolved.version || 'unknown',
    executable: resolved.executable_path ? resolved.executable_path.split(/[\\/]/).pop() : 'playwright-managed',
  },
  screenshots: [],
};
try {
  for (const entry of selected) {
    for (const viewport of [{ name: 'mobile', width: 390, height: 844 }, { name: 'desktop', width: 1440, height: 1000 }]) {
      const page = await browser.newPage({ viewport: { width: viewport.width, height: viewport.height }, reducedMotion: 'reduce', colorScheme: 'light' });
      await page.goto(`http://127.0.0.1:6006/iframe.html?id=${encodeURIComponent(entry.id)}&viewMode=story`, { waitUntil: 'networkidle' });
      await page.addStyleTag({ content: '*,*::before,*::after{animation-duration:0s!important;animation-delay:0s!important;transition:none!important;caret-color:transparent!important}' });
      await page.evaluate(async () => { if (document.fonts?.ready) await document.fonts.ready; });
      const filename = `${entry.id}-${viewport.name}.png`;
      await page.screenshot({ path: `${stagingDir}/${filename}`, fullPage: true, animations: 'disabled' });
      manifest.screenshots.push({ story_id: entry.id, viewport, file: `${outputDir}/${filename}` });
      await page.close();
    }
  }
  writeFileSync(`${stagingDir}/manifest.json`, `${JSON.stringify(manifest, null, 2)}\n`);
  rmSync(outputDir, { recursive: true, force: true });
  renameSync(stagingDir, outputDir);
} finally {
  await browser.close();
  stop();
  rmSync(stagingDir, { recursive: true, force: true });
}
console.log(`Captured ${manifest.screenshots.length} deterministic Lite Storybook screenshots with ${resolved.version}`);

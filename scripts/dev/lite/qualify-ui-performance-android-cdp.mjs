import { chromium } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { mkdir, rm, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import {
  LITE_PERFORMANCE_SCHEMA_VERSION,
  sanitizeLitePerformanceName,
  summarizeLiteFrames,
} from '../../../src/performance/litePerformanceBudget.js';

const cdpUrl = String(process.env.LITE_ANDROID_CDP_URL || '').trim();
const baseUrl = String(process.env.LITE_BASE_URL || '').trim();
const outputDir = resolve('.pocketlab-dev/performance');
const screens = ['home', 'catalog', 'devices', 'security', 'identity', 'rules', 'recovery'];

function fail(message) {
  console.error(`[ui-performance-android] ${message}`);
  process.exit(1);
}

function sourceCommit() {
  const configured = String(process.env.LITE_PERF_SOURCE_COMMIT || process.env.GITHUB_SHA || '').trim();
  if (/^[0-9a-f]{40}$/.test(configured)) return configured;
  try {
    const value = execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).trim();
    if (/^[0-9a-f]{40}$/.test(value) && !/^0+$/.test(value)) return value;
  } catch {
    // Fall through to fail closed.
  }
  fail('UI performance evidence requires an exact 40-character source commit.');
}

function validateEndpoint(value, label) {
  let parsed;
  try {
    parsed = new URL(value);
  } catch {
    fail(`${label} must be a valid URL`);
  }
  if (!['http:', 'https:'].includes(parsed.protocol)) fail(`${label} must use http:// or https://`);
  if (parsed.username || parsed.password) fail(`${label} must not include credentials`);
  return parsed;
}

validateEndpoint(cdpUrl, 'LITE_ANDROID_CDP_URL');
const base = validateEndpoint(baseUrl, 'LITE_BASE_URL');

await rm(outputDir, { recursive: true, force: true });
await mkdir(outputDir, { recursive: true });

const browser = await chromium.connectOverCDP(cdpUrl);
const contexts = browser.contexts();
if (!contexts.length) fail('Android Chrome did not expose a browser context over CDP.');
const context = contexts[0];
const page = await context.newPage();

await page.addInitScript(() => {
  let active = null;
  window.__POCKETLAB_ANDROID_FRAME_SAMPLER__ = {
    start(name) {
      if (active?.raf) cancelAnimationFrame(active.raf);
      active?.observers?.forEach((observer) => observer.disconnect());
      const sample = {
        name: String(name || 'interaction').slice(0, 96),
        previous: null,
        intervals: [],
        longTasks: [],
        eventDurations: [],
        observers: [],
        raf: null,
      };
      active = sample;
      const frame = (timestamp) => {
        if (active !== sample) return;
        if (sample.previous !== null) sample.intervals.push(timestamp - sample.previous);
        sample.previous = timestamp;
        sample.raf = requestAnimationFrame(frame);
      };
      sample.raf = requestAnimationFrame(frame);

      if ('PerformanceObserver' in window) {
        try {
          const longTaskObserver = new PerformanceObserver((list) => {
            list.getEntries().forEach((entry) => sample.longTasks.push(Number(entry.duration) || 0));
          });
          longTaskObserver.observe({ entryTypes: ['longtask'] });
          sample.observers.push(longTaskObserver);
        } catch {}
        try {
          const eventObserver = new PerformanceObserver((list) => {
            list.getEntries().forEach((entry) => sample.eventDurations.push(Number(entry.duration) || 0));
          });
          eventObserver.observe({ type: 'event', buffered: false, durationThreshold: 16 });
          sample.observers.push(eventObserver);
        } catch {}
      }
    },
    stop() {
      if (!active) return null;
      const sample = active;
      active = null;
      if (sample.raf) cancelAnimationFrame(sample.raf);
      sample.observers.forEach((observer) => observer.disconnect());
      return {
        interaction: sample.name,
        intervals: sample.intervals.slice(0, 600),
        longTasks: sample.longTasks.slice(0, 120),
        eventDurations: sample.eventDurations.slice(0, 120),
      };
    },
  };
});

let failures = 0;
const commit = sourceCommit();

for (const screenId of screens) {
  const target = new URL(base.href);
  target.searchParams.set('screen', screenId);
  await page.goto(target.href, { waitUntil: 'domcontentloaded', timeout: 30_000 });
  await page.locator(`[data-lite-screen-id="${screenId}"]`).waitFor({ state: 'visible', timeout: 20_000 });
  await page.waitForTimeout(700);

  const interaction = sanitizeLitePerformanceName(`android-cdp:${screenId}:scroll`);
  await page.evaluate((name) => window.__POCKETLAB_ANDROID_FRAME_SAMPLER__?.start(name), interaction);
  await page.evaluate(() => window.scrollBy({ top: Math.max(220, Math.round(window.innerHeight * 0.5)), behavior: 'auto' }));
  await page.waitForTimeout(180);
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'auto' }));
  await page.waitForTimeout(1000);
  const raw = await page.evaluate(() => window.__POCKETLAB_ANDROID_FRAME_SAMPLER__?.stop?.() || null);
  if (!raw) fail(`frame sampler returned no evidence for ${screenId}`);

  const summary = summarizeLiteFrames(raw.intervals || [], {
    longTasks: raw.longTasks || [],
    eventDurations: raw.eventDurations || [],
    warmupFrames: 3,
  });

  const viewport = page.viewportSize();
  const report = {
    schema_version: LITE_PERFORMANCE_SCHEMA_VERSION,
    interaction,
    mode: 'live',
    qualification_surface: 'android-cdp',
    browser_project: 'android-cdp',
    source_commit: commit,
    sanitized: true,
    viewport: viewport ? { width: viewport.width, height: viewport.height } : null,
    ...summary,
  };

  const path = resolve(outputDir, `ui-performance-android-cdp-${screenId}.json`);
  await writeFile(path, JSON.stringify(report, null, 2) + '\n', 'utf8');
  const status = report.gate_passed ? 'PASS' : 'FAIL';
  console.log(`[ui-performance-android] ${status} ${screenId}: p95=${report.p95_frame_ms}ms smooth=${report.target_smooth_frame_ratio}`);
  if (!report.gate_passed) failures += 1;
}

await page.close();

if (failures) {
  console.error(`[ui-performance-android] ${failures} screen(s) exceeded the hard render gate.`);
  process.exit(1);
}

console.log('[ui-performance-android] all screen render gates passed');
process.exit(0);

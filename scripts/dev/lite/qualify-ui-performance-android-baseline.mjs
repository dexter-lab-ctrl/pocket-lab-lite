#!/usr/bin/env node
import { chromium } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import {
  LITE_PERFORMANCE_SCHEMA_VERSION,
  summarizeLiteFrames,
} from '../../../src/performance/litePerformanceBudget.js';

const MINIMUM_FRAME_COUNT = 20;
const DEFAULT_SAMPLES = 3;
const DEFAULT_SAMPLE_MS = 900;

function fail(message) {
  throw new Error(message);
}

function exactSourceCommit() {
  const configured = String(process.env.LITE_PERF_SOURCE_COMMIT || '').trim();
  if (/^[0-9a-f]{40}$/.test(configured) && !/^0+$/.test(configured)) return configured;
  const value = execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).trim();
  if (!/^[0-9a-f]{40}$/.test(value) || /^0+$/.test(value)) fail('invalid_source_commit');
  return value;
}

function endpoint(value, label) {
  const parsed = new URL(String(value || ''));
  if (!['http:', 'https:'].includes(parsed.protocol) || parsed.username || parsed.password) {
    fail(`${label}_invalid`);
  }
  return parsed;
}

async function installSampler(page) {
  await page.evaluate(() => {
    let active = null;
    window.__POCKETLAB_BASELINE_SAMPLER__ = {
      start() {
        active = { previous: null, intervals: [], longTasks: [], loaf: [], events: [], observers: [], raf: null };
        const sample = active;
        const tick = (timestamp) => {
          if (active !== sample) return;
          if (sample.previous !== null) sample.intervals.push(timestamp - sample.previous);
          sample.previous = timestamp;
          sample.raf = requestAnimationFrame(tick);
        };
        sample.raf = requestAnimationFrame(tick);
        if ('PerformanceObserver' in window) {
          try {
            const observer = new PerformanceObserver((list) => {
              list.getEntries().forEach((entry) => sample.longTasks.push(Number(entry.duration) || 0));
            });
            observer.observe({ entryTypes: ['longtask'] });
            sample.observers.push(observer);
          } catch {}
          try {
            const observer = new PerformanceObserver((list) => {
              list.getEntries().forEach((entry) => sample.loaf.push(Number(entry.duration) || 0));
            });
            observer.observe({ type: 'long-animation-frame', buffered: false });
            sample.observers.push(observer);
          } catch {}
          try {
            const observer = new PerformanceObserver((list) => {
              list.getEntries().forEach((entry) => sample.events.push(Number(entry.duration) || 0));
            });
            observer.observe({ type: 'event', buffered: false, durationThreshold: 16 });
            sample.observers.push(observer);
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
          intervals: sample.intervals.slice(0, 600),
          longTasks: sample.longTasks.slice(0, 120),
          longAnimationFrames: sample.loaf.slice(0, 120),
          eventDurations: sample.events.slice(0, 120),
        };
      },
    };
  });
}

async function collectSample(page, durationMs) {
  await page.evaluate(() => window.__POCKETLAB_BASELINE_SAMPLER__.start());
  await page.waitForTimeout(durationMs);
  const raw = await page.evaluate(() => window.__POCKETLAB_BASELINE_SAMPLER__.stop());
  const summary = summarizeLiteFrames(raw?.intervals || [], {
    longTasks: raw?.longTasks || [],
    longAnimationFrames: raw?.longAnimationFrames || [],
    eventDurations: raw?.eventDurations || [],
    warmupFrames: 3,
  });
  if (summary.frame_count < MINIMUM_FRAME_COUNT) fail(`baseline_insufficient_frames:${summary.frame_count}`);
  return summary;
}

export async function collectAndroidBaseline({
  cdpUrl,
  baseUrl,
  sampleCount = DEFAULT_SAMPLES,
  sampleMs = DEFAULT_SAMPLE_MS,
  label = 'control',
  output,
} = {}) {
  const commit = exactSourceCommit();
  const cdp = endpoint(cdpUrl || process.env.LITE_ANDROID_CDP_URL, 'cdp');
  const base = endpoint(baseUrl || process.env.LITE_BASE_URL, 'base');
  const browser = await chromium.connectOverCDP(cdp.toString());
  const contexts = browser.contexts();
  if (!contexts.length) fail('android_context_unavailable');
  const context = contexts[0];
  const page = await context.newPage();
  try {
    const controlUrl = new URL('/__pocketlab_qualification__/baseline-control.html', base);
    const response = await page.goto(controlUrl.toString(), { waitUntil: 'domcontentloaded', timeout: 30_000 });
    if (!response?.ok()) fail('baseline_control_unavailable');
    if (response.headers()['x-pocket-lab-candidate-sha'] !== commit) fail('baseline_control_sha_mismatch');
    const marker = await page.locator('[data-pocketlab-baseline-control="true"]').count();
    if (marker !== 1) fail('baseline_control_marker_missing');
    const meta = await page.locator('meta[name="pocketlab-candidate-sha"]').getAttribute('content');
    if (meta !== commit) fail('baseline_control_meta_mismatch');
    await page.bringToFront();
    await installSampler(page);
    const samples = [];
    const boundedCount = Math.max(3, Math.min(10, Number(sampleCount) || DEFAULT_SAMPLES));
    for (let index = 0; index < boundedCount; index += 1) {
      samples.push(await collectSample(page, Math.max(500, Math.min(2500, Number(sampleMs) || DEFAULT_SAMPLE_MS))));
      await page.waitForTimeout(120);
    }
    const report = {
      schema_version: LITE_PERFORMANCE_SCHEMA_VERSION,
      baseline_schema_version: '1.0.0',
      evidence_type: 'android-platform-baseline-control',
      label: String(label || 'control').replace(/[^a-zA-Z0-9._-]+/g, '-').slice(0, 80),
      source_commit: commit,
      qualification_surface: 'android-cdp-baseline-control',
      rendering_surface: 'physical-android-chrome',
      android_chrome_version: String(browser.version() || ''),
      candidate_control_verified: true,
      sample_count: samples.length,
      samples,
      captured_at: new Date().toISOString(),
      sanitized: true,
    };
    if (output) {
      const target = resolve(output);
      await mkdir(resolve(target, '..'), { recursive: true });
      await writeFile(target, JSON.stringify(report, null, 2) + '\n', 'utf8');
    }
    return report;
  } finally {
    await page.close().catch(() => {});
  }
}

async function main(argv = process.argv.slice(2)) {
  let output = '';
  let label = 'control';
  let samples = DEFAULT_SAMPLES;
  let sampleMs = DEFAULT_SAMPLE_MS;
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === '--output') output = argv[++index] || '';
    else if (value === '--label') label = argv[++index] || '';
    else if (value === '--samples') samples = Number(argv[++index]);
    else if (value === '--sample-ms') sampleMs = Number(argv[++index]);
    else fail(`unknown_argument:${value}`);
  }
  if (!output) fail('output_required');
  const report = await collectAndroidBaseline({ output, label, sampleCount: samples, sampleMs });
  console.log(`[ui-performance-android-baseline] captured ${report.sample_count} control samples (${report.label})`);
}

if (process.argv[1]?.endsWith('qualify-ui-performance-android-baseline.mjs')) {
  main().catch((error) => {
    console.error(`[ui-performance-android-baseline] ERROR: ${error?.message || error}`);
    process.exit(1);
  });
}

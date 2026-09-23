import { expect, type Page, type TestInfo } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import {
  LITE_PERFORMANCE_SCHEMA_VERSION,
  LITE_UI_PERFORMANCE_BUDGET,
  sanitizeLitePerformanceName,
  summarizeLiteFrames,
} from '../../src/performance/litePerformanceBudget.js';

type FrameSample = {
  interaction: string;
  intervals: number[];
  longTasks: number[];
  eventDurations: number[];
};

export type LitePerformanceReport = ReturnType<typeof summarizeLiteFrames> & {
  schema_version: string;
  interaction: string;
  mode: 'mocked' | 'live';
  browser_project: string;
  source_commit: string;
  sanitized: true;
};

function sourceCommit() {
  const configured = String(process.env.LITE_PERF_SOURCE_COMMIT || process.env.GITHUB_SHA || '').trim();
  if (/^[0-9a-f]{40}$/.test(configured)) return configured;
  try {
    const value = execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).trim();
    return /^[0-9a-f]{40}$/.test(value) ? value : '0'.repeat(40);
  } catch {
    return '0'.repeat(40);
  }
}

export async function installLiteFrameSampler(page: Page) {
  await page.addInitScript(() => {
    const globalWindow = window as typeof window & {
      __POCKETLAB_FRAME_SAMPLER__?: {
        start: (name: string) => void;
        stop: () => FrameSample | null;
      };
    };
    let active: {
      name: string;
      intervals: number[];
      longTasks: number[];
      eventDurations: number[];
      previous: number | null;
      raf: number | null;
      observers: PerformanceObserver[];
    } | null = null;

    const stopObservers = () => {
      active?.observers?.forEach((observer) => observer.disconnect());
      if (active?.raf) cancelAnimationFrame(active.raf);
    };

    globalWindow.__POCKETLAB_FRAME_SAMPLER__ = {
      start(name: string) {
        stopObservers();
        const sample = {
          name: String(name || 'interaction').slice(0, 96),
          intervals: [] as number[],
          longTasks: [] as number[],
          eventDurations: [] as number[],
          previous: null as number | null,
          raf: null as number | null,
          observers: [] as PerformanceObserver[],
        };
        active = sample;

        const frame = (timestamp: number) => {
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
          } catch {
            // Long Task API is optional.
          }
          try {
            const eventObserver = new PerformanceObserver((list) => {
              list.getEntries().forEach((entry) => sample.eventDurations.push(Number(entry.duration) || 0));
            });
            eventObserver.observe({ type: 'event', buffered: false, durationThreshold: 16 } as PerformanceObserverInit);
            sample.observers.push(eventObserver);
          } catch {
            // Event Timing API is optional.
          }
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
}

export async function measureLiteInteraction(
  page: Page,
  testInfo: TestInfo,
  interaction: string,
  action: () => Promise<void>,
  { settleMs = 900, mode = 'mocked' as 'mocked' | 'live' } = {},
): Promise<LitePerformanceReport> {
  const name = sanitizeLitePerformanceName(interaction);
  await page.evaluate((value) => {
    (window as any).__POCKETLAB_FRAME_SAMPLER__?.start(value);
  }, name);

  await action();
  await page.waitForTimeout(settleMs);

  const raw = await page.evaluate(() => (window as any).__POCKETLAB_FRAME_SAMPLER__?.stop?.() || null) as FrameSample | null;
  expect(raw, 'frame sampler must return a sample').toBeTruthy();

  const summary = summarizeLiteFrames(raw?.intervals || [], {
    longTasks: raw?.longTasks || [],
    eventDurations: raw?.eventDurations || [],
    warmupFrames: 3,
  });

  return {
    schema_version: LITE_PERFORMANCE_SCHEMA_VERSION,
    interaction: name,
    mode,
    browser_project: sanitizeLitePerformanceName(testInfo.project.name),
    source_commit: sourceCommit(),
    sanitized: true,
    ...summary,
  };
}

export function expectLitePerformanceBudget(report: LitePerformanceReport) {
  expect(report.frame_count, 'sample should contain enough rendered frames').toBeGreaterThanOrEqual(20);
  expect(report.gate_passed, `render budget violations: ${report.gate_violations.join(', ')}`).toBe(true);
  expect(report.gate_smooth_frame_ratio).toBeGreaterThanOrEqual(LITE_UI_PERFORMANCE_BUDGET.gate.minSmoothFrameRatio);
}

export async function writeLitePerformanceEvidence(testInfo: TestInfo, report: LitePerformanceReport) {
  const directory = resolve('.pocketlab-dev/performance');
  await mkdir(directory, { recursive: true });
  const fileName = [
    'ui-performance',
    sanitizeLitePerformanceName(testInfo.project.name),
    sanitizeLitePerformanceName(report.interaction),
    sanitizeLitePerformanceName(testInfo.testId).slice(0, 36),
  ].join('-') + '.json';
  await writeFile(resolve(directory, fileName), JSON.stringify(report, null, 2) + '\n', 'utf8');
}

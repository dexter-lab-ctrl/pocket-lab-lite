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
  longAnimationFrames: number[];
  eventDurations: number[];
};

type ReactCommitSummary = {
  commit_count: number;
  p95_commit_ms: number;
  max_commit_ms: number;
  target_met: boolean;
  gate_passed: boolean;
};

type LiteRuntimePerformanceSummary = {
  schema_version: string;
  commits: Record<string, ReactCommitSummary>;
  long_task_count: number;
  max_long_task_ms: number;
};

export type LitePerformanceReport = ReturnType<typeof summarizeLiteFrames> & {
  schema_version: string;
  interaction: string;
  performance_evidence_id: string | null;
  mode: 'mocked' | 'live';
  browser_project: string;
  source_commit: string;
  sanitized: true;
  react_profile_available: boolean;
  react_commit_count: number;
  react_commit_p95_ms: number;
  react_commit_max_ms: number;
  react_commit_target_met: boolean | null;
  react_commit_gate_passed: boolean | null;
};

function sourceCommit() {
  const configured = String(process.env.LITE_PERF_SOURCE_COMMIT || process.env.GITHUB_SHA || '').trim();
  if (/^[0-9a-f]{40}$/.test(configured)) return configured;
  try {
    const value = execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).trim();
    if (/^[0-9a-f]{40}$/.test(value) && !/^0+$/.test(value)) return value;
  } catch {
    // Fall through to the fail-closed error below.
  }
  throw new Error('UI performance evidence requires an exact 40-character source commit.');
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
      longAnimationFrames: number[];
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
          longAnimationFrames: [] as number[],
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
            const loafObserver = new PerformanceObserver((list) => {
              list.getEntries().forEach((entry) => sample.longAnimationFrames.push(Number(entry.duration) || 0));
            });
            loafObserver.observe({ type: 'long-animation-frame', buffered: false } as PerformanceObserverInit);
            sample.observers.push(loafObserver);
          } catch {
            // Long Animation Frame API is optional.
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
          longAnimationFrames: sample.longAnimationFrames.slice(0, 120),
          eventDurations: sample.eventDurations.slice(0, 120),
        };
      },
    };
  });
}

export async function exerciseLiteScroll(page: Page, durationMs = 720) {
  await page.evaluate(async (duration) => {
    const root = document.scrollingElement || document.documentElement;
    const startTop = root.scrollTop;
    const maxScroll = Math.max(0, root.scrollHeight - window.innerHeight);
    const distance = Math.min(maxScroll, Math.max(220, Math.round(window.innerHeight * 0.55)));

    await new Promise<void>((resolve) => {
      const startedAt = performance.now();
      const step = (now: number) => {
        const elapsed = now - startedAt;
        const phase = Math.min(1, elapsed / Math.max(240, duration));
        const wave = (1 - Math.cos(phase * Math.PI * 2)) / 2;
        if (distance > 0) root.scrollTop = Math.min(maxScroll, startTop + (distance * wave));
        if (phase < 1) {
          requestAnimationFrame(step);
        } else {
          root.scrollTop = startTop;
          resolve();
        }
      };
      requestAnimationFrame(step);
    });
  }, durationMs);
}

export async function measureLiteInteraction(
  page: Page,
  testInfo: TestInfo,
  interaction: string,
  action: () => Promise<void>,
  { settleMs = 900, mode = 'mocked' as 'mocked' | 'live', evidenceId = null } = {},
): Promise<LitePerformanceReport> {
  const name = sanitizeLitePerformanceName(interaction);
  const reactProfileAvailable = await page.evaluate(() => {
    const store = (window as any).__POCKETLAB_LITE_PERF__;
    if (store?.enabled === true && typeof store.resetSummary === 'function' && typeof store.readSummary === 'function') {
      store.resetSummary();
      return true;
    }
    return false;
  });

  await page.evaluate((value) => {
    (window as any).__POCKETLAB_FRAME_SAMPLER__?.start(value);
  }, name);

  await action();
  await page.waitForTimeout(settleMs);

  const raw = await page.evaluate(() => (window as any).__POCKETLAB_FRAME_SAMPLER__?.stop?.() || null) as FrameSample | null;
  expect(raw, 'frame sampler must return a sample').toBeTruthy();

  const runtimeSummary = await page.evaluate(() => {
    const store = (window as any).__POCKETLAB_LITE_PERF__;
    return typeof store?.readSummary === 'function' ? store.readSummary() : null;
  }) as LiteRuntimePerformanceSummary | null;

  const commitSummaries = Object.values(runtimeSummary?.commits || {});
  const reactCommitCount = commitSummaries.reduce((sum, item) => sum + (Number(item.commit_count) || 0), 0);
  const reactCommitP95 = Math.max(0, ...commitSummaries.map((item) => Number(item.p95_commit_ms) || 0));
  const reactCommitMax = Math.max(0, ...commitSummaries.map((item) => Number(item.max_commit_ms) || 0));
  const reactCommitTargetMet = reactProfileAvailable ? commitSummaries.every((item) => item.target_met === true) : null;
  const reactCommitGatePassed = reactProfileAvailable ? commitSummaries.every((item) => item.gate_passed === true) : null;

  const summary = summarizeLiteFrames(raw?.intervals || [], {
    longTasks: raw?.longTasks || [],
    longAnimationFrames: raw?.longAnimationFrames || [],
    eventDurations: raw?.eventDurations || [],
    warmupFrames: 3,
  });

  const report = {
    schema_version: LITE_PERFORMANCE_SCHEMA_VERSION,
    interaction: name,
    performance_evidence_id: evidenceId ? sanitizeLitePerformanceName(evidenceId) : null,
    mode,
    browser_project: sanitizeLitePerformanceName(testInfo.project.name),
    source_commit: sourceCommit(),
    sanitized: true,
    react_profile_available: reactProfileAvailable,
    react_commit_count: reactCommitCount,
    react_commit_p95_ms: reactCommitP95,
    react_commit_max_ms: reactCommitMax,
    react_commit_target_met: reactCommitTargetMet,
    react_commit_gate_passed: reactCommitGatePassed,
    ...summary,
  };
  // Persist the sample before the caller asserts the gate so target misses and
  // hard-gate violations remain inspectable evidence instead of disappearing
  // with a failed test.
  await writeLitePerformanceEvidence(testInfo, report);
  return report;
}

export function expectLitePerformanceBudget(report: LitePerformanceReport) {
  expect(report.frame_count, 'sample should contain enough rendered frames').toBeGreaterThanOrEqual(20);
  expect(
    report.gate_passed,
    `render budget violations: ${report.gate_violations.join(', ')}; p95=${report.p95_frame_ms}ms; max=${report.max_frame_interval_ms}ms; gate_smooth=${report.gate_smooth_frame_ratio}; long_task=${report.max_long_task_ms}ms; loaf=${report.max_long_animation_frame_ms}ms`,
  ).toBe(true);
  expect(report.gate_smooth_frame_ratio).toBeGreaterThanOrEqual(LITE_UI_PERFORMANCE_BUDGET.gate.minSmoothFrameRatio);
  if (report.mode === 'mocked') {
    expect(report.react_profile_available, 'mocked performance qualification must include React Profiler evidence').toBe(true);
  }
  if (report.react_profile_available) {
    expect(report.react_commit_gate_passed, `React commit p95 exceeded the hard gate: ${report.react_commit_p95_ms}ms`).toBe(true);
  }
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

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

export type LiteScrollDiagnostics = {
  scroll_container: string;
  scroll_behavior: string;
  scroll_overflow_y: string;
  body_overflow_y: string;
  scroll_height: number;
  client_height: number;
  viewport_height: number;
  initial_scroll_top: number;
  final_scroll_top: number;
  max_scroll_top: number;
  requested_distance: number;
  observed_min_scroll_top: number;
  observed_max_scroll_top: number;
  scroll_event_count: number;
  document_scroll_event_count: number;
  window_scroll_event_count: number;
  container_scroll_event_count: number;
  scroll_top_sample_count: number;
  scroll_top_change_count: number;
  scroll_raf_count: number;
  scroll_raf_interval_count: number;
  scroll_raf_p50_ms: number;
  scroll_raf_p95_ms: number;
  scroll_raf_max_ms: number;
  scroll_raf_approx_16_7ms_frames: number;
  scroll_raf_approx_33_3ms_frames: number;
  scroll_raf_over_40ms_frames: number;
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

export async function exerciseLiteScroll(
  page: Page,
  durationMs = 720,
  { collectDiagnostics = false }: { collectDiagnostics?: boolean } = {},
): Promise<LiteScrollDiagnostics | null> {
  return page.evaluate(async ({ duration, collectDiagnostics: shouldCollectDiagnostics }) => {
    const root = document.scrollingElement || document.documentElement;
    const startTop = root.scrollTop;
    const maxScroll = Math.max(0, root.scrollHeight - window.innerHeight);
    const distance = Math.min(maxScroll, Math.max(220, Math.round(window.innerHeight * 0.55)));
    const scrollIntervals: number[] = [];
    let previousFrame: number | null = null;
    let frameCount = 0;
    let documentScrollEventCount = 0;
    let windowScrollEventCount = 0;
    let containerScrollEventCount = 0;
    let scrollTopSampleCount = 0;
    let scrollTopChangeCount = 0;
    let observedMin = startTop;
    let observedMax = startTop;
    let previousObservedTop = startTop;
    const observeTop = () => {
      if (!shouldCollectDiagnostics) return;
      scrollTopSampleCount += 1;
      const currentTop = root.scrollTop;
      observedMin = Math.min(observedMin, currentTop);
      observedMax = Math.max(observedMax, currentTop);
      if (currentTop !== previousObservedTop) scrollTopChangeCount += 1;
      previousObservedTop = currentTop;
    };
    const onDocumentScroll = () => { documentScrollEventCount += 1; observeTop(); };
    const onWindowScroll = () => { windowScrollEventCount += 1; observeTop(); };
    const onContainerScroll = () => { containerScrollEventCount += 1; observeTop(); };
    if (shouldCollectDiagnostics) {
      document.addEventListener('scroll', onDocumentScroll, { passive: true });
      window.addEventListener('scroll', onWindowScroll, { passive: true });
      root.addEventListener('scroll', onContainerScroll, { passive: true });
    }

    const percentile = (values: number[], fraction: number) => {
      if (!values.length) return 0;
      const sorted = [...values].sort((left, right) => left - right);
      return sorted[Math.min(sorted.length - 1, Math.floor((sorted.length - 1) * fraction))];
    };

    await new Promise<void>((resolve) => {
      const startedAt = performance.now();
      const step = (now: number) => {
        if (shouldCollectDiagnostics) {
          observeTop();
          frameCount += 1;
          if (previousFrame !== null) scrollIntervals.push(now - previousFrame);
          previousFrame = now;
        }
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
    if (shouldCollectDiagnostics) {
      root.scrollTop = startTop;
      await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
      observeTop();
      document.removeEventListener('scroll', onDocumentScroll);
      window.removeEventListener('scroll', onWindowScroll);
      root.removeEventListener('scroll', onContainerScroll);
    }
    const finalTop = root.scrollTop;
    if (!shouldCollectDiagnostics) return null;
    const roundedIntervals = scrollIntervals.map((value) => Math.round(value * 10) / 10);
    return {
      scroll_container: `${root.tagName.toLowerCase()}${root.id ? `#${root.id}` : ''}${root.className && typeof root.className === 'string' ? `.${root.className.trim().split(/\s+/).slice(0, 2).join('.')}` : ''}`.slice(0, 160),
      scroll_behavior: getComputedStyle(root).scrollBehavior,
      scroll_overflow_y: getComputedStyle(root).overflowY,
      body_overflow_y: getComputedStyle(document.body).overflowY,
      scroll_height: root.scrollHeight,
      client_height: root.clientHeight,
      viewport_height: window.innerHeight,
      initial_scroll_top: Math.round(startTop * 10) / 10,
      final_scroll_top: Math.round(finalTop * 10) / 10,
      max_scroll_top: Math.round(maxScroll * 10) / 10,
      requested_distance: Math.round(distance * 10) / 10,
      observed_min_scroll_top: Math.round(observedMin * 10) / 10,
      observed_max_scroll_top: Math.round(observedMax * 10) / 10,
      scroll_event_count: Math.min(600, documentScrollEventCount + windowScrollEventCount + containerScrollEventCount),
      document_scroll_event_count: Math.min(600, documentScrollEventCount),
      window_scroll_event_count: Math.min(600, windowScrollEventCount),
      container_scroll_event_count: Math.min(600, containerScrollEventCount),
      scroll_top_sample_count: Math.min(600, scrollTopSampleCount),
      scroll_top_change_count: Math.min(600, scrollTopChangeCount),
      scroll_raf_count: Math.min(600, frameCount),
      scroll_raf_interval_count: Math.min(600, roundedIntervals.length),
      scroll_raf_p50_ms: Math.round(percentile(roundedIntervals, 0.5) * 10) / 10,
      scroll_raf_p95_ms: Math.round(percentile(roundedIntervals, 0.95) * 10) / 10,
      scroll_raf_max_ms: Math.round(Math.max(0, ...roundedIntervals) * 10) / 10,
      scroll_raf_approx_16_7ms_frames: roundedIntervals.filter((value) => value >= 14 && value <= 20).length,
      scroll_raf_approx_33_3ms_frames: roundedIntervals.filter((value) => value >= 28 && value <= 38).length,
      scroll_raf_over_40ms_frames: roundedIntervals.filter((value) => value > 40).length,
    } satisfies LiteScrollDiagnostics;
  }, { duration: durationMs, collectDiagnostics });
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

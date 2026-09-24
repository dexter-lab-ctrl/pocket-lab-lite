import React, { Profiler, useEffect } from 'react';
import {
  LITE_PERFORMANCE_SCHEMA_VERSION,
  isLiteScreenPerformanceId,
  sanitizeLitePerformanceName,
  summarizeReactCommits,
} from './litePerformanceBudget.js';

const PERF_ENABLED = import.meta.env.VITE_POCKETLAB_PERF_TEST === '1';
const MAX_COMMIT_SAMPLES = 240;

function performanceStore() {
  if (typeof window === 'undefined') return null;
  if (!window.__POCKETLAB_LITE_PERF__) {
    window.__POCKETLAB_LITE_PERF__ = {
      schema_version: LITE_PERFORMANCE_SCHEMA_VERSION,
      enabled: PERF_ENABLED,
      commits: {},
      long_tasks: [],
    };
  }
  return window.__POCKETLAB_LITE_PERF__;
}

function recordCommit(id, duration) {
  if (!PERF_ENABLED) return;
  const store = performanceStore();
  if (!store) return;
  const safeId = sanitizeLitePerformanceName(id);
  const bucket = Array.isArray(store.commits[safeId]) ? store.commits[safeId] : [];
  bucket.push(Number(duration) || 0);
  if (bucket.length > MAX_COMMIT_SAMPLES) bucket.splice(0, bucket.length - MAX_COMMIT_SAMPLES);
  store.commits[safeId] = bucket;
}

function onProfilerRender(id, _phase, actualDuration) {
  recordCommit(id, actualDuration);
}

export function useLitePerformanceRuntime() {
  useEffect(() => {
    if (typeof document === 'undefined') return undefined;
    const root = document.documentElement;
    const motionQuery = typeof window.matchMedia === 'function'
      ? window.matchMedia('(prefers-reduced-motion: reduce)')
      : null;
    const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection || null;
    const syncVisibility = () => {
      root.dataset.liteDocumentHidden = document.hidden ? 'true' : 'false';
    };
    const syncPowerPolicy = () => {
      const conservative = Boolean(motionQuery?.matches || connection?.saveData);
      root.dataset.litePowerSave = conservative ? 'true' : 'false';
    };
    syncVisibility();
    syncPowerPolicy();
    document.addEventListener('visibilitychange', syncVisibility);
    motionQuery?.addEventListener?.('change', syncPowerPolicy);
    connection?.addEventListener?.('change', syncPowerPolicy);

    let observer = null;
    if (PERF_ENABLED && typeof PerformanceObserver !== 'undefined') {
      try {
        observer = new PerformanceObserver((list) => {
          const store = performanceStore();
          if (!store) return;
          const values = list.getEntries()
            .map((entry) => Number(entry.duration) || 0)
            .filter((value) => value > 0);
          store.long_tasks.push(...values);
          if (store.long_tasks.length > 120) {
            store.long_tasks.splice(0, store.long_tasks.length - 120);
          }
        });
        observer.observe({ entryTypes: ['longtask'] });
      } catch {
        observer = null;
      }
    }

    if (PERF_ENABLED) {
      const store = performanceStore();
      store.resetSummary = () => {
        store.commits = {};
        store.long_tasks = [];
      };
      store.readSummary = () => {
        const commits = {};
        for (const [id, durations] of Object.entries(store.commits || {})) {
          commits[id] = summarizeReactCommits(durations, { screenTransition: isLiteScreenPerformanceId(id) });
        }
        return {
          schema_version: LITE_PERFORMANCE_SCHEMA_VERSION,
          commits,
          long_task_count: Array.isArray(store.long_tasks) ? store.long_tasks.length : 0,
          max_long_task_ms: Math.max(0, ...(store.long_tasks || [])),
        };
      };
    }

    return () => {
      document.removeEventListener('visibilitychange', syncVisibility);
      motionQuery?.removeEventListener?.('change', syncPowerPolicy);
      connection?.removeEventListener?.('change', syncPowerPolicy);
      observer?.disconnect?.();
    };
  }, []);
}

export function LitePerformanceProfiler({ id, children }) {
  if (!PERF_ENABLED) return children;
  return (
    <Profiler id={sanitizeLitePerformanceName(id)} onRender={onProfilerRender}>
      {children}
    </Profiler>
  );
}

export const LITE_PERFORMANCE_RUNTIME_ENABLED = PERF_ENABLED;

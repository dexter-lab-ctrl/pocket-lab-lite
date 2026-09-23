export const LITE_PERFORMANCE_SCHEMA_VERSION = '1.0.0';

export const LITE_UI_PERFORMANCE_BUDGET = Object.freeze({
  refreshHz: 60,
  frameBudgetMs: 16.67,
  target: Object.freeze({
    smoothFrameThresholdMs: 20,
    minSmoothFrameRatio: 0.95,
    severeFrameThresholdMs: 33.34,
    maxSevereFrameRatio: 0.01,
    maxP95FrameMs: 20,
    maxLongTaskMs: 50,
    maxInpMs: 200,
    maxReactCommitP95Ms: 8,
    maxScreenTransitionCommitP95Ms: 12,
  }),
  gate: Object.freeze({
    smoothFrameThresholdMs: 24,
    minSmoothFrameRatio: 0.90,
    severeFrameThresholdMs: 40,
    maxSevereFrameRatio: 0.05,
    maxP95FrameMs: 24,
    maxLongTaskMs: 80,
    maxInpMs: 250,
    maxReactCommitP95Ms: 16,
    maxScreenTransitionCommitP95Ms: 24,
  }),
});

export const LITE_PERFORMANCE_SCREENS = Object.freeze([
  'home',
  'catalog',
  'devices',
  'security',
  'identity',
  'rules',
  'recovery',
]);

export const LITE_PERFORMANCE_PRIMITIVES = Object.freeze([
  'page-shell',
  'card',
  'status-badge',
  'state-surface',
  'progressive-disclosure',
  'standard-list',
  'standard-list-item',
  'segmented-control',
  'skeleton-cards',
  'button',
  'refresh-control',
  'sheet',
  'backdrop',
]);

export const LITE_PERFORMANCE_INTERACTIONS = Object.freeze([
  'screen-steady',
  'screen-navigation',
  'manage-open',
  'manage-close',
  'overlay-open',
  'overlay-close',
  'list-scroll',
  'progress-update',
  'toast-settle',
  'refresh-feedback',
]);

function finite(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function round(value, places = 2) {
  const scale = 10 ** places;
  return Math.round(finite(value) * scale) / scale;
}

export function percentile(values = [], quantile = 0.95) {
  const numbers = (Array.isArray(values) ? values : [])
    .map((value) => finite(value, NaN))
    .filter(Number.isFinite)
    .sort((left, right) => left - right);
  if (!numbers.length) return 0;
  const clamped = Math.max(0, Math.min(1, finite(quantile, 0.95)));
  const index = Math.min(numbers.length - 1, Math.ceil(clamped * numbers.length) - 1);
  return round(numbers[Math.max(0, index)]);
}

export function sanitizeLitePerformanceName(value = 'unknown') {
  const safe = String(value || 'unknown')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9:._-]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 96);
  return safe || 'unknown';
}

export function summarizeLiteFrames(intervals = [], {
  longTasks = [],
  eventDurations = [],
  warmupFrames = 3,
} = {}) {
  const safeIntervals = (Array.isArray(intervals) ? intervals : [])
    .map((value) => finite(value, NaN))
    .filter((value) => Number.isFinite(value) && value >= 0)
    .slice(Math.max(0, Math.floor(finite(warmupFrames))));
  const safeLongTasks = (Array.isArray(longTasks) ? longTasks : [])
    .map((value) => finite(value, NaN))
    .filter(Number.isFinite);
  const safeEvents = (Array.isArray(eventDurations) ? eventDurations : [])
    .map((value) => finite(value, NaN))
    .filter(Number.isFinite);
  const target = LITE_UI_PERFORMANCE_BUDGET.target;
  const gate = LITE_UI_PERFORMANCE_BUDGET.gate;
  const count = safeIntervals.length;
  const ratio = (predicate) => count ? round(safeIntervals.filter(predicate).length / count, 4) : 1;

  const summary = {
    frame_count: count,
    p50_frame_ms: percentile(safeIntervals, 0.50),
    p95_frame_ms: percentile(safeIntervals, 0.95),
    max_frame_ms: round(Math.max(0, ...safeIntervals)),
    target_smooth_frame_ratio: ratio((value) => value <= target.smoothFrameThresholdMs),
    gate_smooth_frame_ratio: ratio((value) => value <= gate.smoothFrameThresholdMs),
    target_severe_frame_ratio: ratio((value) => value > target.severeFrameThresholdMs),
    gate_severe_frame_ratio: ratio((value) => value > gate.severeFrameThresholdMs),
    long_task_count: safeLongTasks.length,
    max_long_task_ms: round(Math.max(0, ...safeLongTasks)),
    max_event_duration_ms: round(Math.max(0, ...safeEvents)),
  };

  const targetMisses = [];
  if (summary.p95_frame_ms > target.maxP95FrameMs) targetMisses.push('p95_frame_ms');
  if (summary.target_smooth_frame_ratio < target.minSmoothFrameRatio) targetMisses.push('smooth_frame_ratio');
  if (summary.target_severe_frame_ratio > target.maxSevereFrameRatio) targetMisses.push('severe_frame_ratio');
  if (summary.max_long_task_ms > target.maxLongTaskMs) targetMisses.push('long_task_ms');
  if (summary.max_event_duration_ms > target.maxInpMs) targetMisses.push('event_duration_ms');

  const gateViolations = [];
  if (summary.p95_frame_ms > gate.maxP95FrameMs) gateViolations.push('p95_frame_ms');
  if (summary.gate_smooth_frame_ratio < gate.minSmoothFrameRatio) gateViolations.push('smooth_frame_ratio');
  if (summary.gate_severe_frame_ratio > gate.maxSevereFrameRatio) gateViolations.push('severe_frame_ratio');
  if (summary.max_long_task_ms > gate.maxLongTaskMs) gateViolations.push('long_task_ms');
  if (summary.max_event_duration_ms > gate.maxInpMs) gateViolations.push('event_duration_ms');

  return {
    ...summary,
    target_met: targetMisses.length === 0,
    target_misses: targetMisses,
    gate_passed: gateViolations.length === 0,
    gate_violations: gateViolations,
  };
}

export function summarizeReactCommits(durations = [], { screenTransition = false } = {}) {
  const values = (Array.isArray(durations) ? durations : [])
    .map((value) => finite(value, NaN))
    .filter(Number.isFinite);
  const targetLimit = screenTransition
    ? LITE_UI_PERFORMANCE_BUDGET.target.maxScreenTransitionCommitP95Ms
    : LITE_UI_PERFORMANCE_BUDGET.target.maxReactCommitP95Ms;
  const gateLimit = screenTransition
    ? LITE_UI_PERFORMANCE_BUDGET.gate.maxScreenTransitionCommitP95Ms
    : LITE_UI_PERFORMANCE_BUDGET.gate.maxReactCommitP95Ms;
  const p95 = percentile(values, 0.95);
  return {
    commit_count: values.length,
    p95_commit_ms: p95,
    max_commit_ms: round(Math.max(0, ...values)),
    target_met: p95 <= targetLimit,
    gate_passed: p95 <= gateLimit,
  };
}

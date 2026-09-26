export const LITE_ANDROID_BASELINE_SCHEMA_VERSION = '1.0.0';

export const LITE_ANDROID_BASELINE_POLICY = Object.freeze({
  minSamplesPerSide: 3,
  maxComparableP95DeltaMs: 6,
  maxComparableSmoothRatioDrop: 0.06,
  maxComparableSevereRatioIncrease: 0.02,
  maxComparableLongTaskDeltaMs: 10,
  maxComparableLoafDeltaMs: 10,
});

function finite(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function round(value, places = 2) {
  const scale = 10 ** places;
  return Math.round(finite(value) * scale) / scale;
}

export function median(values = []) {
  const numbers = (Array.isArray(values) ? values : [])
    .map((value) => finite(value, NaN))
    .filter(Number.isFinite)
    .sort((left, right) => left - right);
  if (!numbers.length) return 0;
  const middle = Math.floor(numbers.length / 2);
  if (numbers.length % 2) return round(numbers[middle]);
  return round((numbers[middle - 1] + numbers[middle]) / 2);
}

export function summarizeAndroidBaselineSamples(samples = []) {
  const safe = (Array.isArray(samples) ? samples : []).filter((sample) => sample && typeof sample === 'object');
  const metric = (name) => median(safe.map((sample) => sample[name]));
  return {
    sample_count: safe.length,
    p50_frame_ms: metric('p50_frame_ms'),
    p95_frame_ms: metric('p95_frame_ms'),
    max_frame_ms: metric('max_frame_ms'),
    target_smooth_frame_ratio: metric('target_smooth_frame_ratio'),
    gate_smooth_frame_ratio: metric('gate_smooth_frame_ratio'),
    target_severe_frame_ratio: metric('target_severe_frame_ratio'),
    gate_severe_frame_ratio: metric('gate_severe_frame_ratio'),
    max_long_task_ms: metric('max_long_task_ms'),
    max_long_animation_frame_ms: metric('max_long_animation_frame_ms'),
    max_event_duration_ms: metric('max_event_duration_ms'),
  };
}

export function compareAndroidBaseline({ baselineSamples = [], interactionSamples = [] } = {}) {
  const baseline = summarizeAndroidBaselineSamples(baselineSamples);
  const interaction = summarizeAndroidBaselineSamples(interactionSamples);
  const policy = LITE_ANDROID_BASELINE_POLICY;

  const result = {
    baseline,
    interaction,
    delta: {
      p95_frame_ms: round(interaction.p95_frame_ms - baseline.p95_frame_ms),
      smooth_frame_ratio: round(interaction.target_smooth_frame_ratio - baseline.target_smooth_frame_ratio, 4),
      severe_frame_ratio: round(interaction.target_severe_frame_ratio - baseline.target_severe_frame_ratio, 4),
      long_task_ms: round(interaction.max_long_task_ms - baseline.max_long_task_ms),
      long_animation_frame_ms: round(
        interaction.max_long_animation_frame_ms - baseline.max_long_animation_frame_ms,
      ),
      event_duration_ms: round(interaction.max_event_duration_ms - baseline.max_event_duration_ms),
    },
  };

  if (
    baseline.sample_count < policy.minSamplesPerSide
    || interaction.sample_count < policy.minSamplesPerSide
  ) {
    return {
      ...result,
      classification: 'INCONCLUSIVE',
      comparable: false,
      reasons: ['insufficient_samples'],
    };
  }

  const baselineAlreadyLimited = (
    baseline.p95_frame_ms > 20
    || baseline.target_smooth_frame_ratio < 0.95
    || baseline.target_severe_frame_ratio > 0.01
    || baseline.max_long_task_ms > 50
    || baseline.max_long_animation_frame_ms > 50
  );

  const appIncrementalCost = (
    result.delta.p95_frame_ms > policy.maxComparableP95DeltaMs
    || result.delta.smooth_frame_ratio < -policy.maxComparableSmoothRatioDrop
    || result.delta.severe_frame_ratio > policy.maxComparableSevereRatioIncrease
    || result.delta.long_task_ms > policy.maxComparableLongTaskDeltaMs
    || result.delta.long_animation_frame_ms > policy.maxComparableLoafDeltaMs
  );

  let classification = 'WITHIN_BASELINE';
  if (baselineAlreadyLimited && appIncrementalCost) classification = 'MIXED';
  else if (appIncrementalCost) classification = 'APP_INCREMENTAL_COST';
  else if (baselineAlreadyLimited) classification = 'PLATFORM_DOMINATED';

  const reasons = [];
  if (baselineAlreadyLimited) reasons.push('baseline_already_misses_absolute_target');
  if (result.delta.p95_frame_ms > policy.maxComparableP95DeltaMs) reasons.push('p95_delta');
  if (result.delta.smooth_frame_ratio < -policy.maxComparableSmoothRatioDrop) reasons.push('smooth_ratio_delta');
  if (result.delta.severe_frame_ratio > policy.maxComparableSevereRatioIncrease) reasons.push('severe_ratio_delta');
  if (result.delta.long_task_ms > policy.maxComparableLongTaskDeltaMs) reasons.push('long_task_delta');
  if (result.delta.long_animation_frame_ms > policy.maxComparableLoafDeltaMs) reasons.push('loaf_delta');

  return {
    ...result,
    classification,
    comparable: true,
    reasons,
  };
}

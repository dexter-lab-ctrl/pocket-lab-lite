// Safety-only display interpretation. FastAPI and profile-scoped projections remain authoritative.
// No scanner execution, browser persistence or fabricated fallback measurements.
export function isReportedSafetyScore(score, provenance) {
  return provenance === 'backend_reported'
    && typeof score === 'number' && Number.isFinite(score);
}
export function isMeasuredSafetyProgress(progress, optimistic = false) {
  return !optimistic && typeof progress?.percent === 'number'
    && Number.isFinite(progress.percent) && progress.percent >= 0 && progress.percent <= 100;
}
export function isSafetyCoverageReported(coverage, hasRun = false) {
  if (!hasRun || !coverage || typeof coverage !== 'object') return false;
  return ['checked_targets', 'partial_targets', 'timed_out_targets', 'skipped_targets', 'missing_targets', 'target_statuses']
    .some((key) => Array.isArray(coverage[key]));
}
export function areComparableSafetyRuns(a, b) {
  if (!a || !b || !a.run_id || !b.run_id || a.run_id === b.run_id) return false;
  const profileA = String(a.scan_profile || '').toLowerCase();
  const profileB = String(b.scan_profile || '').toLowerCase();
  if (!profileA || profileA !== profileB) return false;
  if (profileA === 'app' && (a.app_id || '') !== (b.app_id || '')) return false;
  const aScore = a.score;
  const bScore = b.score;
  return typeof aScore === 'number' && Number.isFinite(aScore)
    && typeof bScore === 'number' && Number.isFinite(bScore);
}
export function safetyCoverageQuality(coverage, hasRun) {
  if (!isSafetyCoverageReported(coverage, hasRun)) return 'unreported';
  const nonempty = (key) => Array.isArray(coverage[key]) && coverage[key].length > 0;
  if (nonempty('timed_out_targets') || nonempty('partial_targets') || nonempty('missing_targets') || nonempty('failed_targets')) return 'incomplete';
  return 'reported';
}

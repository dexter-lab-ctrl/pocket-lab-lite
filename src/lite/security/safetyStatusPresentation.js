// Presentation only: reflect FastAPI profile/run/tool records, never infer scan success
// from an empty finding array or a terminal run status alone.
const COMPLETE = new Set(['completed', 'succeeded', 'success', 'done']);
const RUN_COMPLETE = new Set(['completed', 'succeeded', 'success', 'healthy', 'done', 'degraded', 'partial']);
const ACTIVE = new Set(['queued', 'accepted', 'running', 'working', 'in_progress', 'pending']);
const FAILED = new Set(['failed', 'failure', 'error']);
const CANCELLED = new Set(['cancelled', 'canceled']);
const INCOMPLETE = new Set(['partial', 'degraded', 'review', 'missing_tool', 'timed_out', 'timeout']);

export function safetyToolPresentation(name, result = {}, steps = [], runStatus = '') {
  const raw = String(result?.status || '').trim().toLowerCase();
  const matched = (Array.isArray(steps) ? steps : []).find((step) =>
    String(step?.key || step?.title || '').toLowerCase().includes(name.toLowerCase()));
  const stepStatus = String(matched?.state || matched?.status || '').toLowerCase();
  if (FAILED.has(raw) || FAILED.has(stepStatus)) return { name, status: 'Failed', tone: 'danger', complete: false };
  if (INCOMPLETE.has(raw) || INCOMPLETE.has(stepStatus)) return { name, status: raw === 'missing_tool' ? 'Unavailable' : 'Incomplete', tone: 'warning', complete: false };
  if (CANCELLED.has(raw)) return { name, status: 'Cancelled', tone: 'neutral', complete: false };
  if (COMPLETE.has(raw) || stepStatus === 'done') return { name, status: 'Completed', tone: 'success', complete: true };
  if (ACTIVE.has(raw) || ACTIVE.has(stepStatus)) return { name, status: 'Pending', tone: 'neutral', complete: false };
  return { name, status: RUN_COMPLETE.has(runStatus) ? 'Not reported' : 'Pending', tone: 'neutral', complete: false };
}

export function deriveSafetyStatusPresentation({
  status = '', hasRun = false, running = false, profile = 'quick',
  toolResults = {}, executionSteps = [], criticalCount = 0,
  coverageReported = false, saved = false, offline = false,
} = {}) {
  const runStatus = String(status || '').trim().toLowerCase();
  const active = running || ACTIVE.has(runStatus);
  const failed = FAILED.has(runStatus);
  const cancelled = CANCELLED.has(runStatus);
  const completedRun = Boolean(hasRun && RUN_COMPLETE.has(runStatus) && !active && !failed && !cancelled);
  const scanners = (profile === 'app' ? ['Trivy'] : ['Lynis', 'Trivy'])
    .map((name) => safetyToolPresentation(name, toolResults?.[name.toLowerCase()], executionSteps, runStatus));
  const fullyReported = Boolean(completedRun && coverageReported && scanners.every((scanner) => scanner.complete));
  const count = Number.isFinite(Number(criticalCount)) ? Math.max(0, Number(criticalCount)) : 0;
  let headline = 'Not checked';
  let message = 'Run a Safety Check to see scanner results.';
  let tone = 'neutral';
  if (active) { headline = 'Safety check in progress'; message = 'Scanner findings are not yet final.'; tone = 'info'; }
  else if (failed) { headline = 'Safety check failed'; message = 'Review the failed check before relying on its findings.'; tone = 'danger'; }
  else if (cancelled) { headline = 'Safety check cancelled'; message = 'This check did not finish.'; tone = 'neutral'; }
  else if (saved || offline) { headline = hasRun ? 'Saved safety result' : 'Saved information unavailable'; message = 'Reconnect to confirm the current safety state.'; tone = 'neutral'; }
  else if (completedRun && fullyReported && count > 0) { headline = 'Needs review'; message = 'Review critical findings from the completed check.'; tone = 'danger'; }
  else if (completedRun && fullyReported) { headline = 'Check completed'; message = 'Required scanners and coverage are reported.'; tone = 'success'; }
  else if (completedRun) { headline = 'Check completed with limited detail'; message = 'Some scanner or coverage outcomes were not fully reported.'; tone = 'warning'; }
  else if (hasRun) { headline = 'Safety status unavailable'; message = 'A complete scanner outcome has not been reported.'; tone = 'neutral'; }
  const findingLabel = count > 0 ? `${count} critical finding${count === 1 ? '' : 's'} reported${fullyReported ? '' : ' so far'}`
    : fullyReported ? 'No critical findings reported' : 'Critical finding assessment not final';
  return {
    headline, message, tone, scanners, findingLabel,
    findingTone: count > 0 ? 'danger' : fullyReported ? 'success' : 'neutral',
    scopeLabel: !hasRun ? 'No check recorded' : coverageReported ? 'Coverage reported' : 'Coverage not reported',
    safeguard: 'Sensitive values and private paths are hidden from this view.',
    fullyReported,
  };
}

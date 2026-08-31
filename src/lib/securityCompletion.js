import { securityTerminalNeedsAttention, terminalSecurityProgress } from './securityProgressEvents.js';
import { sanitizeSecurityRunId } from './securityRunId.js';

function normalizeProfile(value = 'quick') {
  const profile = String(value || 'quick').trim().toLowerCase();
  return ['quick', 'full', 'app'].includes(profile) ? profile : 'quick';
}

// Claims a terminal event only when it belongs to the exact, actively observed
// backend run. Root ownership performs the resulting state/query/feedback work.
export function claimObservedSecurityCompletion(event = {}, observation = {}, completionIds = new Set()) {
  const runId = sanitizeSecurityRunId(event.run_id);
  const observedRunId = sanitizeSecurityRunId(observation.runId);
  if (!observation.active || !observedRunId || runId !== observedRunId) return null;
  if (!terminalSecurityProgress(event)) return null;

  const id = `security-completion:${runId}`;
  if (completionIds.has(id)) return null;
  completionIds.add(id);
  if (completionIds.size > 64) completionIds.delete(completionIds.values().next().value);

  const needsAttention = securityTerminalNeedsAttention(event);
  return {
    id,
    runId,
    observation: { active: false, runId: '' },
    profile: normalizeProfile(event.profile),
    needsAttention,
    haptic: needsAttention ? 'warning' : 'success',
    toast: {
      id,
      kind: needsAttention ? 'warning' : 'success',
      title: needsAttention ? 'Safety check needs attention' : 'Safety check completed',
      message: needsAttention ? 'Pocket Lab recorded a result that needs review.' : 'The latest safety result is ready to review.',
    },
  };
}

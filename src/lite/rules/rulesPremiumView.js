import { getLiteReasonPresentation, getLiteRulesActionLabel } from '../../lib/identityRulesPresentation.js';

// Deliberately accept only server-provided, display-safe facts. Unknown != blocked.
const words = (value) => typeof value === 'string' && value.trim() ? value.trim() : '';
export function rulesProtectionView(policy, { savedStateOnly = false, backendReachable = true, isExpired = false, enterprise = false } = {}) {
  const current = Boolean(policy && backendReachable && !savedStateOnly && !isExpired);
  const confirmed = current && policy.status === 'ready' && policy.engine?.healthy === true
    && policy.engine?.loopback_only === true && !policy.active_policy?.activation_in_progress
    && !policy.active_policy?.source_update_required;
  const saved = Boolean(savedStateOnly || (!backendReachable && policy));
  const state = saved ? (isExpired ? 'stale' : 'saved') : !policy || !backendReachable ? 'unavailable' : confirmed ? 'ready' : 'degraded';
  const presentation = {
    ready: ['Ready', 'Your important actions are protected.', 'Pocket Lab checks whether sensitive changes are permitted before they can continue.', 'healthy'],
    degraded: ['Needs attention', 'Protection needs attention.', 'Current Rules protection could not be fully confirmed. Sensitive changes remain subject to server safeguards.', 'degraded'],
    stale: ['Stale information', 'Protection is not confirmed.', 'Saved Rules information may be out of date. Current authorization requires a reachable server.', 'neutral'],
    saved: ['Saved information', 'Live protection is not confirmed.', 'You are viewing saved information. Sensitive changes require current server verification.', 'neutral'],
    unavailable: ['Unavailable', 'Protection status is unavailable.', 'Pocket Lab cannot currently confirm its protection state.', 'degraded'],
  }[state];
  return { state, label: presentation[0], headline: presentation[1], summary: presentation[2], tone: presentation[3],
    mode: enterprise ? 'Enterprise Mode' : 'Personal Mode',
    updateAttention: Boolean(policy?.active_policy?.source_update_required),
    revisionCurrent: confirmed && policy?.active_policy?.bundle_ready === true,
    canWrite: current };
}

export function rulesDecisionView(record, { simulated = false } = {}) {
  if (!record || typeof record !== 'object') return null;
  const isSimulation = simulated || record.simulated === true || record.simulation === true || record.mode === 'synthetic';
  const outcome = words(record.outcome).toLowerCase();
  const allowed = outcome === 'allow' || outcome === 'allowed' || (!outcome && record.allow === true);
  const blocked = outcome === 'deny' || outcome === 'denied' || outcome === 'block' || outcome === 'blocked' || (!outcome && record.allow === false);
  const stepUp = outcome === 'step_up_required';
  const approval = outcome === 'approval_required' || outcome === 'pending_approval';
  const status = isSimulation
    ? allowed ? 'Simulation allowed' : stepUp ? 'Simulation: passkey required' : approval ? 'Simulation: review required' : blocked ? 'Simulation blocked' : 'Simulation inconclusive'
    : allowed ? 'Authorization allowed' : blocked ? 'Blocked' : stepUp ? 'Passkey step-up required' : approval ? 'Independent approval required' : 'Decision not confirmed';
  const tone = isSimulation || (!allowed && !blocked) ? 'neutral' : allowed ? 'healthy' : 'degraded';
  const reason = words(record.reason_summary) || words(record.reason) || (words(record.reason_code)
    ? getLiteReasonPresentation(record.reason_code).message : '');
  const execution = words(record.execution_status) || words(record.execution_state);
  const safeExecution = ['accepted', 'running', 'completed', 'failed', 'unknown'].includes(execution.toLowerCase()) ? execution.toLowerCase() : '';
  return {
    id: words(record.decision_id) || null,
    status, tone, allowed, blocked, isSimulation, reason: reason || 'No additional reason was returned.',
    action: getLiteRulesActionLabel(record.action_id) || words(record.action_label) || 'Protected action',
    actor: words(record.actor_label) || words(record.actor?.display_name) || words(record.actor_type),
    target: words(record.target_label) || [words(record.target_type), words(record.target_id)].filter(Boolean).join(' · '),
    occurredAt: words(record.occurred_at) || words(record.evaluated_at),
    revision: words(record.policy_revision),
    constraints: Array.isArray(record.constraints) ? record.constraints.filter((v) => typeof v === 'string' && v.length < 240).slice(0, 12) : [],
    correlation: words(record.correlation_id),
    reasonCode: words(record.reason_code),
    execution: safeExecution,
    next: words(record.next_step) || (stepUp ? 'Follow the server-requested passkey step.' : approval ? 'Review must be completed by an eligible independent person.' : blocked ? 'Review the reason and request only an authorized change.' : allowed ? 'The operation may proceed separately; completion has not been established.' : 'Refer to the current server decision.'),
  };
}
export function rulesActivationView(operation) {
  const state = words(operation?.state).toLowerCase();
  const steps = [
    ['pending', 'Accepted'], ['validating', 'Checking'], ['switching', 'Applying'],
    ['restarting', 'Applying safely'], ['verifying', 'Verifying'], ['active', 'Succeeded'],
  ];
  const index = steps.findIndex(([id]) => id === state);
  const terminal = ['active', 'failed', 'rolled_back', 'not_completed', 'uncertain'].includes(state);
  return { state: state || 'unknown', steps: steps.map(([id, label], idx) => ({
    id, label, state: state === 'active' ? 'completed' : index < 0 ? 'unconfirmed' : idx < index ? 'reported' : idx === index ? 'current' : 'unconfirmed',
  })), terminal, recovery: ['rolling_back', 'rolled_back', 'failed', 'not_completed', 'uncertain'].includes(state) };
}

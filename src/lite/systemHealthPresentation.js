/**
 * Display-only System Health view model.
 * Canonical incident IDs, evidence and execution authority stay with FastAPI.
 * Unknown values are never turned into a claim of health, repair or connectivity.
 */
export const COMPONENT_NAMES = Object.freeze({
  api: 'Pocket Lab API', nats: 'Command connection', jetstream: 'Command connection',
  processes: 'Running services', agent: 'Device agent', supervisor: 'Agent supervisor',
  remote_access: 'Remote access', sqlite: 'Pocket Lab data',
  telemetry: 'Device monitoring', storage: 'Storage', security: 'Safety checks',
  worker: 'Command worker', caddy: 'Secure web access', app: 'App',
});

const PROCESS_NAMES = Object.freeze({
  'pocket-api': 'Pocket Lab API', 'pocket-worker': 'Command worker',
  'pocket-nats': 'Command service', 'pocket-node-agent': 'Device agent',
  'pocketlab-core-supervisor': 'Agent supervisor',
  'pocket-telemetry': 'Device monitoring', 'caddy-proxy': 'Secure web access',
  'pocketlab-app-photoprism': 'PhotoPrism',
});

export const RECOVERY_ACTION_LABELS = Object.freeze({
  'runtime.consumer.reconnect': 'Restore command connection',
  'device.agent.recover': 'Recover device agent',
  'app.repair': 'Repair app',
  'runtime.configuration.restore': 'Restore service configuration',
  'recovery.database.restore': 'Restore Pocket Lab data',
});

export const RECOVERY_AVAILABILITY_LABELS = Object.freeze({
  externally_managed: 'Managed by existing recovery service',
  guided_existing_flow: 'Available in existing controls',
  not_enabled: 'Not available',
  never_automatic: 'Requires manual confirmation',
});

export const INCIDENT_STATE_LABELS = Object.freeze({
  detected: 'Problem detected', diagnosing: 'Checking cause',
  diagnosed: 'Cause reviewed', repair_available: 'Recovery option recorded',
  repairing: 'Repair recorded as running', verifying: 'Verification recorded as running',
  blocked: 'Recovery blocked', failed: 'Recovery failed',
  manual_attention_required: 'Manual review required', resolved: 'Observed healthy',
});

export const RECOVERY_LIFECYCLE_LABELS = Object.freeze({
  requested: 'Request received', preflight_checked: 'Preflight checked', approval_required: 'Approval required',
  approved: 'Approved', admitted: 'Recovery queued', accepted: 'Accepted by recovery owner',
  executing: 'Working', awaiting_verification: 'Verification pending', verified: 'Verified recovery',
  denied: 'Recovery denied', blocked: 'Recovery blocked', expired: 'Request expired',
  cancelled: 'Recovery cancelled', execution_failed: 'Execution failed', verification_failed: 'Verification failed',
  verification_unavailable: 'Verification unavailable', manual_attention_required: 'Manual attention required',
});

const SAFE_LABEL = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,119}$/;

export function componentLabel(source, targetId, deviceLabel) {
  const sourceName = COMPONENT_NAMES[source] || 'Component';
  if (typeof targetId !== 'string' || !SAFE_LABEL.test(targetId)) return sourceName;
  if (COMPONENT_NAMES[targetId]) return COMPONENT_NAMES[targetId];
  if (source === 'agent' || source === 'supervisor' || source === 'telemetry') {
    return typeof deviceLabel === 'string' && deviceLabel.length <= 80 && /^[\p{L}\p{N} ._()-]+$/u.test(deviceLabel) ? deviceLabel : 'Device';
  }
  if (source === 'nats' && targetId.startsWith('consumer:')) return 'Command consumer';
  if (source === 'processes') return PROCESS_NAMES[targetId] || 'Running service';
  if (source === 'app') return targetId === 'photoprism' ? 'PhotoPrism' : 'App';
  if (source === 'system') return COMPONENT_NAMES[targetId] || 'System component';
  return sourceName;
}

export function safeTechnicalIdentifier(value) {
  return typeof value === 'string' && SAFE_LABEL.test(value) ? value : 'Unavailable';
}

export function healthStatusLabel(value) {
  const labels = {
    healthy: 'Healthy', online: 'Online', ready: 'Ready', connected: 'Connected',
    running: 'Running', normal: 'Healthy', degraded: 'Needs attention',
    unavailable: 'Unavailable', unhealthy: 'Needs attention',
    offline: 'Offline', stopped: 'Stopped', critical: 'Critical',
    errored: 'Error reported', failed: 'Failed', warning: 'Review needed',
    resolved: 'Observed healthy', current: 'Recent observation', saved: 'Saved observation',
    stale: 'Saved observation',
    unknown: 'Not confirmed', blocked: 'Blocked',
    agent_stopped_without_supervisor: 'Agent stopped, no supervisor',
  };
  return labels[String(value || '').toLowerCase()] || 'Not confirmed';
}

export function healthTimestamp(value) {
  if (!value || typeof value !== 'string') return 'Time unavailable';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? 'Time unavailable'
    : parsed.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

export function incidentEvidenceState(incident, saved = false) {
  if (incident?.current_monitoring === false || incident?.concern_state === 'historical_record') return 'historical';
  if (incident?.state === 'resolved' || incident?.concern_state === 'resolved_observation') return 'resolved';
  if (saved) return 'saved';
  if (incident?.concern_state === 'saved_concern') return 'saved';
  if (incident?.concern_state === 'current_concern') return 'current';
  // Backward-compatible reading of pre-H1 responses. Do not assume freshness.
  return incident?.evidence_freshness === 'current' ? 'current' : 'saved';
}

export function groupHealthIncidents(items, saved = false) {
  const groups = { current: [], saved: [], resolved: [], historical: [] };
  (Array.isArray(items) ? items : []).forEach((item) => {
    if (!item || typeof item !== 'object') return;
    groups[incidentEvidenceState(item, saved)].push(item);
  });
  return groups;
}

export function systemHealthPresentation(payload, saved = false) {
  if (!payload || typeof payload !== 'object') {
    return { state: 'unknown', title: 'System status is not confirmed',
      detail: 'No current System Health information is available.' };
  }
  const freshness = saved ? 'saved' : String(payload.freshness || 'unknown');
  if (saved || freshness === 'stale' || freshness === 'saved') {
    return { state: 'saved', title: 'Showing saved information',
      detail: 'Current health is not confirmed. Reconnect or refresh to check again.' };
  }
  if (freshness !== 'current') {
    return { state: 'unknown', title: 'System status needs confirmation',
      detail: 'Not enough current evidence is available to confirm health.' };
  }
  if (payload.status === 'attention') {
    return { state: 'attention', title: 'Some services need attention',
      detail: 'Review the current concerns and their supporting observations.' };
  }
  const savedConcerns = Number(payload.saved_problems ?? 0);
  if (payload.status === 'healthy' && Number(payload.unknown_services || 0) === 0 && savedConcerns === 0) {
    return { state: 'ready', title: 'Observed services are healthy',
      detail: 'Recent observations show no current problems; this is not proof of a repair.' };
  }
  return { state: 'unknown', title: 'Some health information needs review',
    detail: 'A saved concern or missing observation prevents a complete current assessment.' };
}

export function healthCounts(summary, groups, saved = false) {
  if (!summary || typeof summary !== 'object') return { current: '—', saved: '—', healthy: '—' };
  if (saved || summary.freshness !== 'current') {
    return { current: '—', saved: Math.max(0, Number(summary.active_problems || 0)), healthy: '—' };
  }
  const current = Number(summary.current_problems ??
    (summary.status === 'attention' ? summary.active_problems : groups.current.length));
  const savedCount = Number(summary.saved_problems ??
    Math.max(0, Number(summary.active_problems || 0) - current));
  return { current: Math.max(0, current || 0), saved: Math.max(0, savedCount || 0),
    healthy: Math.max(0, Number(summary.healthy_services || 0)) };
}

export function recoveryDestination(source) {
  if (['agent', 'supervisor', 'processes', 'remote_access', 'nats', 'system', 'telemetry'].includes(source)) return 'devices';
  if (source === 'security') return 'security';
  if (['storage', 'sqlite'].includes(source)) return 'recovery';
  if (source === 'app') return 'catalog';
  return null;
}

export function recoveryOperationLabel(operationId) {
  return RECOVERY_ACTION_LABELS[operationId] || 'Existing recovery option';
}

export function recoveryAvailabilityLabel(value) {
  return RECOVERY_AVAILABILITY_LABELS[value] || 'Availability not confirmed';
}

export function recoveryLifecycleLabel(value) {
  return RECOVERY_LIFECYCLE_LABELS[value] || 'Recovery status not confirmed';
}

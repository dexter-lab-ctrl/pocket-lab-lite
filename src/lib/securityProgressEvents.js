const TERMINAL_STATUSES = new Set([
  'succeeded', 'success', 'completed', 'complete', 'done',
  'degraded', 'failed', 'failure', 'cancelled', 'canceled',
]);
const ACTIVE_STATUSES = new Set([
  'queued', 'accepted', 'waiting', 'running', 'working', 'in_progress',
]);

function integerEventId(value) {
  const number = Number(value);
  return Number.isSafeInteger(number) && number > 0 ? number : 0;
}

function normalizedStatus(value) {
  return String(value || '').trim().toLowerCase().replace(/[\s-]+/g, '_');
}

function timestamp(value = {}) {
  const epoch = Number(value.updated_at_epoch_ms || 0);
  if (Number.isFinite(epoch) && epoch > 0) return epoch;
  const parsed = Date.parse(value.updated_at || value.completed_at || value.started_at || '');
  return Number.isFinite(parsed) ? parsed : 0;
}

export function terminalSecurityProgress(value = {}) {
  return TERMINAL_STATUSES.has(normalizedStatus(value.status));
}

export function activeSecurityProgress(value = {}) {
  return Boolean(value.active_scan) || ACTIVE_STATUSES.has(normalizedStatus(value.status));
}

export function normalizeSecurityProgressEvent(value = {}) {
  const status = normalizedStatus(value.status || 'idle');
  return {
    ...value,
    event_id: integerEventId(value.event_id),
    run_id: String(value.run_id || '').trim(),
    profile: String(value.profile || 'quick').trim().toLowerCase() || 'quick',
    app_id: value.app_id || null,
    status,
    stage: value.stage || status || 'idle',
    percent: Math.max(0, Math.min(100, Number(value.percent || 0))),
    updated_at_epoch_ms: timestamp(value),
    active_scan: Boolean(value.active_scan) || ACTIVE_STATUSES.has(status),
    replayed: Boolean(value.replayed),
    snapshot: Boolean(value.snapshot),
    sanitized: value.sanitized !== false,
  };
}

export function acceptSecurityProgressEvent(previous = null, incoming = {}) {
  const next = normalizeSecurityProgressEvent(incoming);
  const current = previous ? normalizeSecurityProgressEvent(previous) : null;
  const result = {
    accepted: true,
    reason: 'accepted',
    value: next,
    duplicateCompletion: false,
  };
  if (!current) return result;

  const currentId = integerEventId(current.event_id);
  const nextId = integerEventId(next.event_id);
  if (currentId && nextId && nextId === currentId) {
    return {
      accepted: false,
      reason: 'duplicate_event_id',
      value: current,
      duplicateCompletion: terminalSecurityProgress(current) && terminalSecurityProgress(next),
    };
  }
  if (currentId && nextId && nextId < currentId) {
    return { accepted: false, reason: 'stale_event_id', value: current, duplicateCompletion: false };
  }

  const currentRun = current.run_id;
  const nextRun = next.run_id;
  if (currentRun && nextRun && currentRun !== nextRun) {
    const nextIsNewer = (nextId && !currentId)
      || (nextId && currentId && nextId > currentId)
      || (!nextId && !currentId && timestamp(next) > timestamp(current));
    if (!nextIsNewer) {
      return { accepted: false, reason: 'stale_wrong_run', value: current, duplicateCompletion: false };
    }
    return result;
  }

  if (currentRun && nextRun === currentRun) {
    const currentTerminal = terminalSecurityProgress(current);
    const nextTerminal = terminalSecurityProgress(next);
    if (currentTerminal && !nextTerminal) {
      return { accepted: false, reason: 'terminal_outranks_active', value: current, duplicateCompletion: false };
    }
    if (currentTerminal && nextTerminal) {
      return {
        accepted: false,
        reason: 'duplicate_completion',
        value: current,
        duplicateCompletion: true,
      };
    }
    next.percent = Math.max(current.percent, next.percent);
    if (!nextId && !currentId && timestamp(next) < timestamp(current)) {
      return { accepted: false, reason: 'stale_timestamp', value: current, duplicateCompletion: false };
    }
  }
  return result;
}

export function progressPayloadFromSecurityEvent(event = {}) {
  const payload = normalizeSecurityProgressEvent(event);
  return {
    view_model: 'security-progress-s6-v1',
    active_scan: payload.active_scan,
    event_id: payload.event_id || null,
    run_id: payload.run_id || null,
    profile: payload.profile,
    app_id: payload.app_id || '',
    stage: payload.stage,
    status: payload.status,
    percent: payload.percent,
    message: payload.message || 'Working',
    revision: payload.event_id ? String(payload.event_id) : (payload.progress_revision || payload.revision || ''),
    progress_revision: payload.event_id ? String(payload.event_id) : (payload.progress_revision || payload.revision || ''),
    updated_at: payload.updated_at || null,
    updated_at_epoch_ms: payload.updated_at_epoch_ms || 0,
    replayed: payload.replayed,
    snapshot: payload.snapshot,
    source: payload.source || 'security_events_stream',
    sanitized: true,
  };
}

import { liteQueryKeys } from './liteQueryClient.js';
import { applyLiteSnapshotDatabaseInstance } from './liteSafeSnapshots.js';

export const LITE_REVISION_EVENT_SCHEMA = 1;
export const LITE_REVISION_CHANNEL_NAME = 'pocketlab-lite-revision-sync-v1';
export const LITE_REVISION_LEADER_KEY = 'pocketlab:lite:revision-stream-leader:v1';
export const LITE_REVISION_LEADER_TTL_MS = 20_000;
export const LITE_REVISION_CHANGED_EVENT = 'lite.revision.changed';
export const LITE_REVISION_RESET_EVENT = 'lite.revision.reset';
export const LITE_REVISION_MAX_CHANGED_IDS = 32;
export const LITE_REVISION_MAX_MESSAGE_BYTES = 8 * 1024;
export const LITE_REVISION_SUPPORTED_PROJECTION_VERSIONS = new Set([1, 2, 3, 4]);
export const LITE_REVISION_DOMAINS = new Set([
  'security', 'fleet', 'apps', 'recovery', 'commands', 'storage', 'audit',
]);
export const LITE_REVISION_REASONS = new Set([
  'domain_state_changed',
  'security_state_changed',
  'fleet_state_changed',
  'apps_state_changed',
  'app_subprojection_changed',
  'recovery_state_changed',
  'command_state_changed',
  'audit_state_changed',
  'storage_state_changed',
  'database_instance_changed',
  'cursor_too_old',
  'cursor_ahead',
  'malformed_cursor',
  'device_health_changed',
  'device_attention_changed',
  'device_connection_quality_changed',
  'device_resource_pressure_changed',
  'device_recovery_pattern_changed',
  'device_version_posture_changed',
  'device_dependency_impact_changed',
]);

const DOMAIN_QUERY_PREFIXES = {
  security: [['lite', 'security']],
  fleet: [['lite', 'fleet']],
  apps: [['lite', 'apps'], ['lite', 'app'], ['lite', 'catalog']],
  recovery: [['lite', 'recovery']],
  commands: [['lite', 'commands']],
  storage: [['lite', 'recovery'], ['lite', 'apps']],
  audit: [],
};

function safeString(value, max = 120) {
  return String(value || '').replace(/[\u0000-\u001f]/g, '').trim().slice(0, max);
}

function safeInteger(value, minimum = 0) {
  const number = Number(value);
  return Number.isSafeInteger(number) && number >= minimum ? number : null;
}

function serializedSize(value) {
  try {
    return new Blob([JSON.stringify(value)]).size;
  } catch {
    try {
      return JSON.stringify(value).length;
    } catch {
      return Number.POSITIVE_INFINITY;
    }
  }
}

function sanitizeChangedIds(value) {
  if (!Array.isArray(value) || value.length > LITE_REVISION_MAX_CHANGED_IDS) return null;
  const seen = new Set();
  const result = [];
  value.forEach((item) => {
    const id = safeString(item);
    if (!id || seen.has(id)) return;
    seen.add(id);
    result.push(id);
  });
  return result;
}

function sanitizeRevisionMap(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const result = {};
  for (const domain of LITE_REVISION_DOMAINS) {
    const revision = safeInteger(value[domain]);
    if (revision !== null) result[domain] = revision;
  }
  return result;
}

export function validateLiteRevisionEnvelope(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  if (serializedSize(value) > LITE_REVISION_MAX_MESSAGE_BYTES) return null;
  const type = safeString(value.type, 80);
  const databaseInstance = safeString(value.database_instance, 64);
  const eventId = safeInteger(value.event_id);
  const projectionVersion = safeInteger(value.projection_version, 1);
  if (!databaseInstance || eventId === null || projectionVersion === null) return null;
  if (!LITE_REVISION_SUPPORTED_PROJECTION_VERSIONS.has(projectionVersion)) return null;

  if (type === LITE_REVISION_RESET_EVENT) {
    const revisions = sanitizeRevisionMap(value.revisions);
    const reason = safeString(value.reason, 80);
    if (!revisions || !LITE_REVISION_REASONS.has(reason)) return null;
    return {
      type,
      event_id: eventId,
      database_instance: databaseInstance,
      revisions,
      reason,
      projection_version: projectionVersion,
      occurred_at: safeString(value.occurred_at, 48),
      sanitized: true,
    };
  }

  if (type !== LITE_REVISION_CHANGED_EVENT) return null;
  const domain = safeString(value.domain, 40);
  const revision = safeInteger(value.revision);
  const reason = safeString(value.reason, 80);
  const changedIds = sanitizeChangedIds(value.changed_ids);
  if (!LITE_REVISION_DOMAINS.has(domain) || revision === null || changedIds === null) return null;
  if (!LITE_REVISION_REASONS.has(reason)) return null;
  return {
    type,
    event_id: eventId,
    domain,
    revision,
    database_instance: databaseInstance,
    changed_ids: changedIds,
    reason,
    projection_version: projectionVersion,
    occurred_at: safeString(value.occurred_at, 48),
    sanitized: true,
  };
}

export function createLiteRevisionState(initial = {}) {
  return {
    databaseInstance: safeString(initial.databaseInstance, 64),
    lastEventId: safeInteger(initial.lastEventId) || 0,
    revisions: { ...(sanitizeRevisionMap(initial.revisions) || {}) },
  };
}

function invalidatePrefix(queryClient, queryKey) {
  return queryClient.invalidateQueries({ queryKey, exact: false, refetchType: 'active' });
}

export function invalidateLiteRevisionDomain(queryClient, domain, changedIds = []) {
  if (!queryClient || !LITE_REVISION_DOMAINS.has(domain)) return [];
  const work = (domain === 'fleet' ? [] : (DOMAIN_QUERY_PREFIXES[domain] || []))
    .map((queryKey) => invalidatePrefix(queryClient, queryKey));
  if (domain === 'apps') {
    changedIds.forEach((appId) => {
      work.push(queryClient.invalidateQueries({ queryKey: liteQueryKeys.appActions(appId), exact: false, refetchType: 'active' }));
    });
  }
  if (domain === 'security') {
    work.push(queryClient.invalidateQueries({ queryKey: liteQueryKeys.securityFreshness(), exact: false, refetchType: 'active' }));
  }
  if (domain === 'fleet') {
    work.push(queryClient.invalidateQueries({ queryKey: liteQueryKeys.fleet(), exact: true, refetchType: 'active' }));
    work.push(queryClient.invalidateQueries({ queryKey: liteQueryKeys.fleetHealthSummary(), exact: true, refetchType: 'active' }));
    changedIds.forEach((nodeId) => {
      work.push(queryClient.invalidateQueries({ queryKey: liteQueryKeys.device(nodeId), exact: true, refetchType: 'active' }));
      work.push(queryClient.invalidateQueries({ queryKey: liteQueryKeys.deviceHealth(nodeId), exact: true, refetchType: 'active' }));
      work.push(queryClient.invalidateQueries({
        predicate: (query) => Array.isArray(query.queryKey)
          && query.queryKey[0] === 'lite'
          && query.queryKey[1] === 'fleet'
          && query.queryKey[2] === 'device-health-history'
          && query.queryKey[3] === nodeId,
        refetchType: 'active',
      }));
    });
  }
  return work;
}

export function resetLiteRevisionState(queryClient, state, databaseInstance, revisions = {}) {
  const nextInstance = safeString(databaseInstance, 64);
  const changedInstance = Boolean(state.databaseInstance && state.databaseInstance !== nextInstance);
  state.databaseInstance = nextInstance;
  state.lastEventId = 0;
  state.revisions = { ...(sanitizeRevisionMap(revisions) || {}) };
  if (nextInstance) applyLiteSnapshotDatabaseInstance(nextInstance);
  if (changedInstance && queryClient) {
    queryClient.invalidateQueries({ queryKey: ['lite'], exact: false, refetchType: 'active' });
  }
  return { accepted: true, databaseInstanceChanged: changedInstance, reset: true };
}

export function applyLiteRevisionEnvelope(queryClient, state, rawEnvelope) {
  const event = validateLiteRevisionEnvelope(rawEnvelope);
  if (!event) return { accepted: false, reason: 'invalid_event' };
  if (event.type === LITE_REVISION_RESET_EVENT) {
    const result = resetLiteRevisionState(queryClient, state, event.database_instance, event.revisions);
    state.lastEventId = event.event_id;
    return { ...result, event };
  }
  if (state.databaseInstance && state.databaseInstance !== event.database_instance) {
    resetLiteRevisionState(queryClient, state, event.database_instance, {});
  } else if (!state.databaseInstance) {
    state.databaseInstance = event.database_instance;
    applyLiteSnapshotDatabaseInstance(event.database_instance);
  }
  if (event.event_id <= state.lastEventId) return { accepted: false, reason: 'duplicate_or_out_of_order', event };
  const previousRevision = safeInteger(state.revisions[event.domain]) || 0;
  if (event.revision <= previousRevision) {
    state.lastEventId = event.event_id;
    return { accepted: false, reason: 'revision_not_newer', event };
  }
  state.lastEventId = event.event_id;
  state.revisions[event.domain] = event.revision;
  invalidateLiteRevisionDomain(queryClient, event.domain, event.changed_ids);
  return { accepted: true, event };
}

export function applyLiteRevisionSnapshot(queryClient, state, rawSnapshot) {
  const databaseInstance = safeString(rawSnapshot?.database_instance, 64);
  const revisions = sanitizeRevisionMap(rawSnapshot?.revisions);
  if (!databaseInstance || !revisions) return { accepted: false, reason: 'invalid_snapshot' };
  if (state.databaseInstance && state.databaseInstance !== databaseInstance) {
    return resetLiteRevisionState(queryClient, state, databaseInstance, revisions);
  }
  if (!state.databaseInstance) {
    state.databaseInstance = databaseInstance;
    applyLiteSnapshotDatabaseInstance(databaseInstance);
  }
  const changedDomains = [];
  Object.entries(revisions).forEach(([domain, revision]) => {
    const previous = safeInteger(state.revisions[domain]) || 0;
    if (revision > previous) {
      state.revisions[domain] = revision;
      changedDomains.push(domain);
      invalidateLiteRevisionDomain(queryClient, domain, []);
    }
  });
  const latestEventId = safeInteger(rawSnapshot?.event_cursor?.latest_event_id);
  if (latestEventId !== null && latestEventId > state.lastEventId) state.lastEventId = latestEventId;
  return { accepted: true, changedDomains, databaseInstanceChanged: false };
}

export function createLiteRevisionSenderId() {
  try {
    return crypto.randomUUID();
  } catch {
    return `lite-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }
}

function readLiteRevisionLeader(storage, now = Date.now()) {
  if (!storage) return null;
  try {
    const parsed = JSON.parse(storage.getItem(LITE_REVISION_LEADER_KEY) || 'null');
    const owner = safeString(parsed?.owner, 80);
    const expiresAt = safeInteger(parsed?.expires_at);
    if (!owner || expiresAt === null || expiresAt <= now) return null;
    return { owner, expires_at: expiresAt };
  } catch {
    return null;
  }
}

export function acquireLiteRevisionLeadership(
  storage,
  senderId,
  { now = Date.now(), ttlMs = LITE_REVISION_LEADER_TTL_MS } = {},
) {
  const owner = safeString(senderId, 80);
  if (!storage || !owner) return false;
  const current = readLiteRevisionLeader(storage, now);
  if (current && current.owner !== owner) return false;
  const lease = { owner, expires_at: now + Math.max(5_000, Number(ttlMs) || LITE_REVISION_LEADER_TTL_MS) };
  try {
    storage.setItem(LITE_REVISION_LEADER_KEY, JSON.stringify(lease));
    return readLiteRevisionLeader(storage, now)?.owner === owner;
  } catch {
    return false;
  }
}

export function releaseLiteRevisionLeadership(storage, senderId) {
  const owner = safeString(senderId, 80);
  if (!storage || !owner) return false;
  try {
    // Explicit release is an ownership check, not a lease-freshness check.
    // Acquisition may use an injected clock in tests and recovery flows, so
    // comparing the stored expiry with Date.now() here can incorrectly make
    // the current owner unable to remove its own lease.
    const parsed = JSON.parse(storage.getItem(LITE_REVISION_LEADER_KEY) || 'null');
    const currentOwner = safeString(parsed?.owner, 80);
    if (currentOwner !== owner) return false;
    storage.removeItem(LITE_REVISION_LEADER_KEY);
    return true;
  } catch {
    return false;
  }
}

export function createLiteRevisionBroadcast({ senderId = createLiteRevisionSenderId(), onEnvelope } = {}) {
  if (typeof window === 'undefined' || typeof window.BroadcastChannel === 'undefined') {
    return { senderId, supported: false, post: () => false, close: () => {} };
  }
  let channel;
  try {
    channel = new window.BroadcastChannel(LITE_REVISION_CHANNEL_NAME);
  } catch {
    return { senderId, supported: false, post: () => false, close: () => {} };
  }
  const listener = (message) => {
    const data = message?.data;
    if (!data || data.schema_version !== LITE_REVISION_EVENT_SCHEMA || data.sender_id === senderId) return;
    const envelope = validateLiteRevisionEnvelope(data.envelope);
    if (envelope && typeof onEnvelope === 'function') onEnvelope(envelope);
  };
  channel.addEventListener('message', listener);
  return {
    senderId,
    supported: true,
    post(envelope) {
      const validated = validateLiteRevisionEnvelope(envelope);
      if (!validated) return false;
      const message = { schema_version: LITE_REVISION_EVENT_SCHEMA, sender_id: senderId, envelope: validated };
      if (serializedSize(message) > LITE_REVISION_MAX_MESSAGE_BYTES) return false;
      try {
        channel.postMessage(message);
        return true;
      } catch {
        return false;
      }
    },
    close() {
      channel.removeEventListener('message', listener);
      channel.close();
    },
  };
}

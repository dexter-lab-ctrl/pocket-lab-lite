const RESOURCE_KEYS = Object.freeze(['memory', 'storage', 'cpu_usage', 'temperature', 'load_average', 'uptime']);
const SOFTWARE_COMPONENTS = Object.freeze(['node_agent', 'supervisor']);
const UNSAFE_FACT_TEXT = /(token|password|secret|credential|api[_-]?key|bearer\s+|nats:\/\/|\/data\/data\/|\/storage\/emulated\/|\/home\/|\/mnt\/|\/root\/)/i;
const OBSERVATION_STATES = new Set([
  'available', 'current', 'stale', 'missing', 'unsupported', 'permission_denied',
  'unavailable', 'verification_pending', 'blocked', 'not_applicable',
]);

function object(value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : {};
}

function text(value, fallback = '') {
  return String(value ?? fallback).replace(/[\u0000-\u001f\u007f]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 160);
}

function safeMetadataText(value, fallback = '', limit = 160) {
  const candidate = text(value, fallback).slice(0, limit);
  return !candidate || UNSAFE_FACT_TEXT.test(candidate) ? text(fallback).slice(0, limit) : candidate;
}

export function finiteDeviceFactNumber(value, { min = 0, max = Number.MAX_SAFE_INTEGER } = {}) {
  if (value === null || value === undefined || value === '') return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= min && parsed <= max ? parsed : null;
}

function canonicalStatus(value, fallback = 'missing') {
  const status = text(value, fallback).toLowerCase().replace(/[\s-]+/g, '_');
  if (status === 'verified' || status === 'healthy' || status === 'ready') return 'available';
  return OBSERVATION_STATES.has(status) ? status : fallback;
}

function sanitizedObservedAt(value) {
  const candidate = text(value, '');
  if (!candidate) return null;
  const parsed = Date.parse(candidate);
  return Number.isFinite(parsed) ? candidate.slice(0, 64) : null;
}

function sanitizedResourceValue(metric, value) {
  const input = object(value);
  if (metric === 'memory') {
    const total = finiteDeviceFactNumber(input.total_mb);
    const free = finiteDeviceFactNumber(input.free_mb);
    const used = finiteDeviceFactNumber(input.used_mb);
    if (total === null || total <= 0 || free === null || free > total) return {};
    return { total_mb: total, free_mb: free, used_mb: used !== null ? Math.min(used, total) : Math.max(0, total - free) };
  }
  if (metric === 'storage') {
    const total = finiteDeviceFactNumber(input.total_mb);
    const free = finiteDeviceFactNumber(input.free_mb);
    return total !== null && total > 0 && free !== null && free <= total ? { total_mb: total, free_mb: free } : {};
  }
  if (metric === 'cpu_usage') {
    const usage = finiteDeviceFactNumber(input.usage_percent, { max: 100 });
    return usage !== null ? { usage_percent: usage } : {};
  }
  if (metric === 'temperature') {
    const celsius = finiteDeviceFactNumber(input.celsius, { min: 1, max: 150 });
    return celsius !== null ? { celsius } : {};
  }
  if (metric === 'load_average') {
    const one = finiteDeviceFactNumber(input.one_minute, { max: 100000 });
    const five = finiteDeviceFactNumber(input.five_minute, { max: 100000 });
    const fifteen = finiteDeviceFactNumber(input.fifteen_minute, { max: 100000 });
    return [one, five, fifteen].some((item) => item !== null)
      ? { one_minute: one, five_minute: five, fifteen_minute: fifteen }
      : {};
  }
  if (metric === 'uptime') {
    const seconds = finiteDeviceFactNumber(input.seconds, { max: 20 * 365 * 86400 });
    return seconds !== null ? { seconds } : {};
  }
  return {};
}

function sanitizedSoftwareFacts(value) {
  const source = object(value);
  const result = {};
  SOFTWARE_COMPONENTS.forEach((component) => {
    const item = object(source[component]);
    if (!Object.keys(item).length) return;
    const version = text(item.version, '').slice(0, 80);
    result[component] = {
      component,
      version: version || null,
      status: text(item.status, version ? 'current' : 'verification_pending').toLowerCase().replace(/[\s-]+/g, '_'),
      source: safeMetadataText(item.source, 'unknown', 80),
      observed_at: sanitizedObservedAt(item.observed_at),
      freshness: text(item.freshness, version ? 'unknown' : 'missing').toLowerCase().replace(/[\s-]+/g, '_'),
    };
  });
  return result;
}

function legacyResourceFacts(telemetry = {}) {
  const input = object(telemetry);
  const sampledAt = input.sampled_at || input.timestamp || input.time || null;
  const resources = {};
  const memoryTotal = finiteDeviceFactNumber(input.memory_total_mb ?? input.memoryTotalMB);
  const memoryFree = finiteDeviceFactNumber(input.memory_free_mb ?? input.memoryFreeMB);
  if (memoryTotal !== null && memoryTotal > 0 && memoryFree !== null && memoryFree <= memoryTotal) {
    resources.memory = { metric: 'memory', value: { total_mb: memoryTotal, free_mb: memoryFree, used_mb: Math.max(0, memoryTotal - memoryFree) }, status: 'available', collection_status: 'available', freshness: 'current', observed_at: sampledAt, source: 'legacy_telemetry', reason_code: 'legacy_telemetry_value' };
  }
  const storageTotal = finiteDeviceFactNumber(input.total_space_mb ?? input.totalSpaceMB);
  const storageFree = finiteDeviceFactNumber(input.free_space_mb ?? input.freeSpaceMB);
  if (storageTotal !== null && storageTotal > 0 && storageFree !== null && storageFree <= storageTotal) {
    resources.storage = { metric: 'storage', value: { total_mb: storageTotal, free_mb: storageFree }, status: 'available', collection_status: 'available', freshness: 'current', observed_at: sampledAt, source: 'legacy_telemetry', reason_code: 'legacy_telemetry_value' };
  }
  const cpu = finiteDeviceFactNumber(input.cpu_usage_percent, { max: 100 });
  if (cpu !== null) resources.cpu_usage = { metric: 'cpu_usage', value: { usage_percent: cpu }, status: 'available', collection_status: 'available', freshness: 'current', observed_at: sampledAt, source: 'legacy_telemetry', reason_code: 'legacy_telemetry_value' };
  const temperature = finiteDeviceFactNumber(input.cpu_temp_c ?? input.cpuTemp, { min: 1, max: 150 });
  if (temperature !== null) resources.temperature = { metric: 'temperature', value: { celsius: temperature }, status: 'available', collection_status: 'available', freshness: 'current', observed_at: sampledAt, source: 'legacy_telemetry', reason_code: 'legacy_telemetry_value' };
  return resources;
}

function healthResourceFacts(health = {}) {
  const resources = object(health.resources);
  const output = {};
  const map = {
    memory: ['memory', resources.memory?.available_mb != null ? { free_mb: resources.memory.available_mb, total_mb: resources.memory.total_mb } : null],
    storage: ['storage', resources.storage?.available_mb != null ? { free_mb: resources.storage.available_mb, total_mb: resources.storage.total_mb } : null],
    cpu_usage: ['load', resources.load?.usage_percent != null ? { usage_percent: resources.load.usage_percent } : null],
    temperature: ['temperature', resources.temperature?.celsius != null ? { celsius: resources.temperature.celsius } : null],
  };
  Object.entries(map).forEach(([metric, [key, value]]) => {
    const item = object(resources[key]);
    if (!Object.keys(item).length) return;
    output[metric] = {
      metric,
      value,
      status: canonicalStatus(item.observation_status || item.collection_status || (value ? 'available' : 'missing')),
      collection_status: canonicalStatus(item.collection_status || (value ? 'available' : 'missing')),
      freshness: text(item.freshness, 'missing'),
      observed_at: sanitizedObservedAt(item.observed_at),
      source: safeMetadataText(item.source, 'health_projection', 80),
      reason_code: safeMetadataText(item.reason_code, value ? 'health_projection' : 'resource_observation_missing', 80),
      health_status: text(item.status, 'unknown'),
      summary: text(item.summary),
    };
  });
  return output;
}

export function normalizeResourceObservation(metric, value = {}) {
  const item = object(value);
  const status = canonicalStatus(item.status || item.collection_status, 'missing');
  const collectionStatus = canonicalStatus(item.collection_status || item.status, status);
  return {
    metric,
    value: sanitizedResourceValue(metric, item.value),
    status,
    collection_status: collectionStatus,
    freshness: text(item.freshness, status === 'stale' ? 'stale' : status === 'available' ? 'current' : 'missing'),
    observed_at: sanitizedObservedAt(item.observed_at),
    source: safeMetadataText(item.source, 'unknown', 80),
    reason_code: safeMetadataText(item.reason_code, status, 80),
    support_state: text(item.support_state, status === 'unsupported' || status === 'not_applicable' ? 'unsupported' : 'unknown'),
    health_status: text(item.health_status || item.threshold_status || ''),
    summary: text(item.summary || ''),
  };
}

export function normalizeDeviceFacts(input = {}, { telemetry = null, health = null } = {}) {
  const root = object(input);
  const facts = object(root.device_facts && !root.resources ? root.device_facts : root);
  let resources = object(facts.resources);
  if (!Object.keys(resources).length && health) resources = healthResourceFacts(health);
  if (!Object.keys(resources).length && root.proactive_health) resources = healthResourceFacts(root.proactive_health);
  if (!Object.keys(resources).length && telemetry) resources = legacyResourceFacts(telemetry);
  if (!Object.keys(resources).length && root.telemetry) resources = legacyResourceFacts(root.telemetry);
  const normalized = {};
  RESOURCE_KEYS.forEach((metric) => {
    if (resources[metric]) normalized[metric] = normalizeResourceObservation(metric, resources[metric]);
  });
  return {
    schema_version: Math.max(1, Math.min(100, Math.trunc(finiteDeviceFactNumber(facts.schema_version, { min: 1, max: 100 }) || 1))),
    device_id: text(facts.device_id || root.id || root.node_id),
    resources: normalized,
    software: sanitizedSoftwareFacts(facts.software),
    observed_at: sanitizedObservedAt(facts.observed_at),
    sanitized: true,
  };
}

export function resourceFactValue(facts, metric, key) {
  const observation = object(object(facts).resources?.[metric]);
  if (!['available', 'current', 'stale'].includes(observation.status)) return null;
  return finiteDeviceFactNumber(observation.value?.[key]);
}

export function resourceFactAvailabilityLabel(observation = {}) {
  const status = canonicalStatus(observation.status || observation.collection_status, 'missing');
  return ({
    available: 'Available', current: 'Available', stale: 'Stale', missing: 'Not reported',
    unsupported: 'Unsupported', permission_denied: 'Permission denied', unavailable: 'Unavailable',
    verification_pending: 'Verification pending', blocked: 'Blocked', not_applicable: 'Not applicable',
  })[status] || 'Unavailable';
}

export const LITE_DEVICE_FACTS_RESOURCE_KEYS = RESOURCE_KEYS;

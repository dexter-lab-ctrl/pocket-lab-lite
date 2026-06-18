const KNOWN_STATUSES = new Set([
  'healthy',
  'warning',
  'degraded',
  'unhealthy',
  'unavailable',
  'maintenance',
  'unknown',
]);

export function normalizeHealthStatus(value) {
  const status = String(value || 'unknown').trim().toLowerCase();
  return KNOWN_STATUSES.has(status) ? status : 'unknown';
}

function toDisplayName(name) {
  return String(name || 'service').trim() || 'service';
}

export function normalizeHealthService(name, value) {
  const serviceName = toDisplayName(name);

  if (typeof value === 'string') {
    return {
      name: serviceName,
      status: normalizeHealthStatus(value),
      summary: '',
      url: '',
      last_checked_at: null,
      details: {},
    };
  }

  if (value && typeof value === 'object' && !Array.isArray(value)) {
    const status = normalizeHealthStatus(value.status || value.health || value.state);
    return {
      name: toDisplayName(value.name || value.service || value.target || serviceName),
      status,
      summary: typeof value.summary === 'string' ? value.summary : typeof value.message === 'string' ? value.message : '',
      url: typeof value.url === 'string' ? value.url : typeof value.endpoint === 'string' ? value.endpoint : '',
      last_checked_at: value.last_checked_at || value.lastCheck || value.checked_at || null,
      response_time_ms: typeof value.response_time_ms === 'number' ? value.response_time_ms : undefined,
      results_count: typeof value.results_count === 'number' ? value.results_count : undefined,
      details: { ...value, status },
    };
  }

  return {
    name: serviceName,
    status: 'unknown',
    summary: '',
    url: '',
    last_checked_at: null,
    details: {},
  };
}

export function normalizeHealthServices(services = {}) {
  if (Array.isArray(services)) {
    return services.map((value, index) => normalizeHealthService(value?.name || `service-${index + 1}`, value));
  }

  if (services && typeof services === 'object') {
    return Object.entries(services).map(([name, value]) => normalizeHealthService(name, value));
  }

  return [];
}

export function normalizeHealthCheck(check, index = 0) {
  const normalized = normalizeHealthService(check?.key || check?.name || `check-${index + 1}`, check);
  return {
    ...normalized,
    key: check?.key || normalized.name || `check-${index + 1}`,
    group: check?.group || check?.category || 'service',
  };
}

export function normalizeHealthPayload(payload = {}) {
  const services = normalizeHealthServices(payload.services);
  const checks = Array.isArray(payload.checks)
    ? payload.checks.map((check, index) => normalizeHealthCheck(check, index))
    : services.map((service, index) => ({ ...service, key: service.name || `service-${index + 1}`, group: 'service' }));

  const summary = {
    healthy: 0,
    warning: 0,
    degraded: 0,
    unhealthy: 0,
    unavailable: 0,
    maintenance: 0,
    unknown: 0,
    total: checks.length || services.length,
    ...(payload.summary || {}),
  };

  for (const key of ['healthy', 'warning', 'degraded', 'unhealthy', 'unavailable', 'maintenance', 'unknown']) {
    summary[key] = Number(summary[key] || 0);
  }
  summary.total = Number(summary.total || checks.length || services.length || 0);

  return {
    ...payload,
    status: normalizeHealthStatus(payload.status),
    services,
    checks,
    summary,
    gatus: {
      base_url: '',
      statuses_path: '/api/health-engine.json',
      reachable: false,
      ...(payload.gatus || {}),
    },
  };
}

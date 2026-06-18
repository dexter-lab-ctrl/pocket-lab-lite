export const telemetryNormal = {
  cpu_usage_percent: 18.5,
  memory_usage_mb: 742,
  memory_total_mb: 4096,
  free_space_mb: 22142,
  cpu_temp_c: 39.2,
  status: 'ok',
};

export const telemetryLowDisk = {
  cpu_usage_percent: 44.1,
  memory_usage_mb: 1880,
  memory_total_mb: 4096,
  free_space_mb: 512,
  cpu_temp_c: 48.8,
  status: 'warning',
  issues: ['low_disk'],
};

export const healthAllGreen = {
  overall: 'healthy',
  summary: { status: 'healthy', healthy: 6, degraded: 0, warning: 0 },
  services: {
    fastapi: 'healthy',
    nats: 'healthy',
    worker: 'healthy',
    vault: 'healthy',
    gitea: 'healthy',
    gatus: 'healthy',
  },
  checks: [
    { name: 'FastAPI ready', group: 'api', status: 'healthy', response_time_ms: 12, results_count: 3 },
    { name: 'NATS JetStream', group: 'events', status: 'healthy', response_time_ms: 8, results_count: 3 },
  ],
};

export const healthVaultSealed = {
  overall: 'degraded',
  summary: { status: 'degraded', healthy: 4, degraded: 1, warning: 0 },
  services: {
    fastapi: 'healthy',
    nats: 'healthy',
    worker: 'healthy',
    vault: { status: 'sealed', message: 'Vault is sealed' },
    gitea: 'healthy',
  },
  checks: [
    { name: 'Vault seal status', group: 'vault', status: 'degraded', response_time_ms: 25, summary: 'Vault is sealed' },
  ],
};

export const fleetAgents = {
  agents: [
    { node_id: 'android-lab-01', status: 'online', last_seen: '2026-06-02T10:00:00Z' },
    { node_id: 'edge-lab-02', status: 'offline', last_seen: '2026-06-01T10:00:00Z' },
  ],
};

export const driftDetected = {
  summary: { status: 'drift_detected', count: 2 },
  items: [
    { id: 'nats-config', severity: 'high', message: 'NATS config differs from desired state' },
    { id: 'caddy-ws-proxy', severity: 'medium', message: 'WebSocket proxy missing' },
  ],
};

export const releaseWorkflowRunning = {
  workflow_id: 'release-dev',
  status: 'running',
  stages: [
    { name: 'check', status: 'complete' },
    { name: 'backup', status: 'running' },
    { name: 'deploy', status: 'pending' },
  ],
};

export const recentEvents = {
  events: [
    { id: 'evt-1', subject: 'pocketlab.events.operation.accepted', operation: 'catalog_refresh', status: 'accepted', time: new Date().toISOString(), message: 'Catalog refresh accepted' },
    { id: 'evt-2', subject: 'pocketlab.events.health.ok', status: 'healthy', time: new Date().toISOString(), message: 'Control plane healthy' },
  ],
};

export const observabilityRuntimeHealthy = {
  status: 'healthy',
  checked_at: '2026-06-14T10:00:00Z',
  cached: false,
  cache_ttl_seconds: 30,
  services: {
    prometheus: { status: 'healthy', ready: true, latency_ms: 12, reason: 'Prometheus ready endpoint returned 200' },
    loki: { status: 'healthy', ready: true, latency_ms: 9, reason: 'Loki ready endpoint returned 200' },
    grafana: { status: 'healthy', healthy: true, latency_ms: 14, reason: 'Grafana health endpoint returned ok' },
    gatus: { status: 'healthy', reachable: true, latency_ms: 7, reason: 'Gatus health endpoint returned 200' },
    promtail: { status: 'healthy', shipping_logs: true, inferred: true, recent_log_count: 5, reason: 'Recent pm2_logs entries found in Loki' },
  },
  prometheus_targets: { status: 'healthy', up: 3, down: 0, total: 3, down_targets: [] },
  warnings: ['Promtail shipping status is inferred from recent Loki pm2_logs entries.'],
};

export const observabilityRuntimeDegraded = {
  ...observabilityRuntimeHealthy,
  status: 'degraded',
  checked_at: '2026-06-14T10:05:00Z',
  services: {
    ...observabilityRuntimeHealthy.services,
    loki: { status: 'unavailable', ready: false, latency_ms: 1500, reason: 'connection refused' },
    promtail: { status: 'unknown', shipping_logs: false, inferred: true, recent_log_count: 0, reason: 'Loki log query returned no response' },
  },
  prometheus_targets: {
    status: 'degraded',
    up: 2,
    down: 1,
    total: 3,
    down_targets: [{ job: 'worker', instance: '127.0.0.1:9000', health: 'down', last_error: 'scrape failed' }],
  },
};

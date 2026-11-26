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

export const healthNativeHealthy = {
  overall: 'healthy',
  source: 'prepared-lite-native',
  summary: { status: 'healthy', healthy: 7, degraded: 0, warning: 0 },
  services: {
    api: { status: 'healthy' },
    identity: { status: 'healthy' },
    nats: { status: 'healthy' },
    worker: { status: 'healthy' },
    processes: { status: 'healthy' },
    sqlite: { status: 'healthy' },
    storage: { status: 'healthy' },
  },
  components: { api: 'healthy', identity: 'healthy', nats: 'healthy', worker: 'healthy', sqlite: 'healthy', storage: 'healthy', remote_access: 'not_configured' },
};

export const healthNativeDegraded = {
  overall: 'degraded',
  source: 'prepared-lite-native',
  summary: { status: 'degraded', healthy: 4, degraded: 1, warning: 0 },
  services: {
    api: { status: 'healthy' },
    identity: { status: 'healthy' },
    nats: { status: 'degraded', summary: 'NATS/JetStream is unavailable.' },
    worker: { status: 'starting' },
    remote_access: { status: 'unavailable', optional: true },
  },
  components: { api: 'healthy', identity: 'healthy', nats: 'degraded', worker: 'starting', sqlite: 'healthy', storage: 'healthy', remote_access: 'unavailable' },
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

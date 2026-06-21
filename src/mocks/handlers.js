import { http, HttpResponse } from 'msw';
import { controlPlaneHealthy, controlPlaneNatsDown, workerDown } from './fixtures/controlPlane.js';
import { telemetryNormal, healthAllGreen, healthVaultSealed, fleetAgents, driftDetected, releaseWorkflowRunning, recentEvents, observabilityRuntimeHealthy, observabilityRuntimeDegraded } from './fixtures/pocketlab.js';

const scenario = () => (typeof window !== 'undefined' ? (window.localStorage.getItem('POCKETLAB_MOCK_SCENARIO') || 'healthy') : 'healthy');
const controlPlane = () => {
  if (scenario() === 'nats-down') return controlPlaneNatsDown;
  if (scenario() === 'worker-down') return workerDown;
  return controlPlaneHealthy;
};
const healthPayload = () => scenario() === 'vault-sealed' ? healthVaultSealed : healthAllGreen;
const observabilityPayload = () => scenario() === 'nats-down' || scenario() === 'worker-down' || scenario() === 'vault-sealed' ? observabilityRuntimeDegraded : observabilityRuntimeHealthy;

export const handlers = [
  http.get('/ready', () => HttpResponse.json(controlPlane(), { status: controlPlane().ready ? 200 : 503 })),
  http.get('/api', () => HttpResponse.json({ name: 'Pocket Lab FastAPI/NATS Control API', mode: 'msw' })),
  http.get('/api/nats/status', () => HttpResponse.json({ connected: controlPlane().nats, jetstream: controlPlane().jetstream, required: true, mode: 'msw' })),
  http.get('/api/workers/status', () => HttpResponse.json({ available: controlPlane().worker, workers: [{ name: 'pocketlab_worker', status: controlPlane().worker ? 'online' : 'offline' }] })),
  http.get('/api/telemetry.json', () => HttpResponse.json(telemetryNormal)),
  http.get('/api/health-engine.json', () => HttpResponse.json(healthPayload())),
  http.get('/api/observability/status', () => HttpResponse.json(observabilityPayload())),
  http.get('/api/logs/query', ({ request }) => {
    const url = new URL(request.url);
    const now = Date.now() * 1000000;
    const values = [
      [String(now - 3000000000), 'INFO Pocket Lab FastAPI log query stream ready'],
      [String(now - 2000000000), 'WARN Drift check found one pending review'],
      [String(now - 1000000000), 'INFO Runtime observability snapshot cached']
    ];
    return HttpResponse.json({
      status: 'success',
      data: { result: [{ stream: { job: 'pocketlab-fastapi' }, values }] },
      meta: { matched_count: values.length, query_time_ms: 12, query: url.searchParams.get('query') || '' }
    });
  }),
  http.get('/api/lite/status', () => HttpResponse.json({
    overall: 'healthy',
    checked_at: new Date().toISOString(),
    device: { name: 'pocket-lab-lite', mode: 'lite', resource_profile: 'low-power' },
    summary: { apps_available: 2, devices_known: 1, security_findings: 0, nats_connected: true, jetstream_enabled: true, live_sampler_running: true },
    telemetry: { status: 'healthy', cpu_temp_c: 42, cpu_usage_percent: 12, free_space_mb: 256000, memory_usage_mb: 512 },
    services: [
      { name: 'Control API', status: 'healthy', summary: 'Pocket Lab Lite API is serving local control-plane requests' },
      { name: 'Command Bus', status: 'healthy', summary: 'NATS / JetStream is ready for worker-owned operations' },
      { name: 'Worker Execution', status: 'healthy', summary: 'Worker heartbeat sampler is active' },
      { name: 'App Catalog', status: 'healthy', summary: '2 catalog items available' },
      { name: 'Identity & Access', status: 'healthy', summary: 'Vault is ready' },
      { name: 'Device Fleet', status: 'healthy', summary: '1 device record known to Pocket Lab Lite' },
    ],
  })),
  http.get('/api/lite/catalog', () => HttpResponse.json({ items: [
    { id: 'gitea', name: 'Gitea', status: 'available', summary: 'Local source store for app catalog workflows', installed: false },
    { id: 'vault', name: 'Vault', status: 'available', summary: 'Passwords and access protection', installed: true },
  ], count: 2, updated_at: new Date().toISOString() })),
  http.get('/api/lite/identity', () => HttpResponse.json({ status: 'healthy', summary: 'Vault is initialized and unsealed', actions: ['change_password'] })),
  http.get('/api/lite/security', () => HttpResponse.json({ status: 'healthy', summary: 'No critical issues in the current safety summary', findings_count: 0, checks_count: 4, last_checked: new Date().toISOString() })),
  http.get('/api/lite/fleet', () => HttpResponse.json({
    status: 'healthy',
    devices: [{
      id: 'local',
      name: 'This device',
      status: 'online',
      last_seen: new Date().toISOString(),
      remote_access: true,
      role: 'compute',
      role_label: 'App Host',
      capabilities: ['Run apps', 'Report device health'],
    }],
    count: 1,
    roles: [
      { role: 'compute', role_label: 'App Host', description: 'Runs apps and services for your Pocket Lab.' },
      { role: 'storage', role_label: 'Storage Node', description: 'Stores backups, files, or app data.' },
    ],
    latest_invite: null,
    updated_at: new Date().toISOString(),
  })),
  http.get('/api/lite/policy', () => HttpResponse.json({ status: 'healthy', summary: 'Protection rules are available in advisory mode', protection_enabled: false, requires_confirmation: true, allowed_actions: ['install_app', 'add_device', 'run_safety_check', 'backup_now'] })),
  http.get('/api/lite/recovery', () => HttpResponse.json({ status: 'unknown', summary: 'No backup activity has been recorded yet', actions: ['backup_now', 'restore'] })),
  http.post('/api/lite/catalog/install', async ({ request }) => {
    const body = await request.json().catch(() => ({}));
    return HttpResponse.json({ accepted: true, status: 'queued', job_id: `mock-install-${body.app_id || 'app'}` }, { status: 202 });
  }),
  http.post('/api/lite/identity/rotate', () => HttpResponse.json({ accepted: true, status: 'queued', command_id: 'mock-rotate-secret' }, { status: 202 })),
  http.post('/api/lite/security/scan', () => HttpResponse.json({ accepted: true, status: 'queued', command_id: 'mock-security-scan' }, { status: 202 })),
  http.post('/api/lite/fleet/devices/:nodeId/restart-agent', ({ params }) => HttpResponse.json({
    accepted: true,
    status: 'queued',
    delivery: 'queued',
    summary: 'Restart requested. If the device is offline, it will run after the agent reconnects.',
    node_id: params.nodeId,
    command_id: 'mock-restart-agent',
  }, { status: 202 })),
  http.post('/api/lite/fleet/add-device', async ({ request }) => {
    const body = await request.json().catch(() => ({}));
    const role = body.role === 'storage' ? 'storage' : 'compute';
    const roleLabel = role === 'storage' ? 'Storage Node' : 'App Host';
    const hostname = body.hostname || (role === 'storage' ? 'Pocket Lab Storage Node' : 'Pocket Lab App Host');
    const expiresAt = new Date(Date.now() + 30 * 60 * 1000).toISOString();
    return HttpResponse.json({
      accepted: true,
      status: 'invite_ready',
      summary: `Invite ready for ${hostname}.`,
      command_id: 'mock-add-device',
      job_id: 'mock-add-device',
      bootstrap_url: 'http://127.0.0.1:8443/api/lite/fleet/agent/bootstrap.sh?role=' + role + '&token=mock-invite-token',
      bootstrap_command: "curl -fsSL 'http://127.0.0.1:8443/api/lite/fleet/agent/bootstrap.sh?role=" + role + "&token=mock-invite-token' | bash",
      copy_text: "curl -fsSL 'http://127.0.0.1:8443/api/lite/fleet/agent/bootstrap.sh?role=" + role + "&token=mock-invite-token' | bash",
      invite: {
        url: 'http://127.0.0.1:8443/api/join.sh?role=' + role + '&token=mock-invite-token',
        bootstrap_url: 'http://127.0.0.1:8443/api/lite/fleet/agent/bootstrap.sh?role=' + role + '&token=mock-invite-token',
        bootstrap_command: "curl -fsSL 'http://127.0.0.1:8443/api/lite/fleet/agent/bootstrap.sh?role=" + role + "&token=mock-invite-token' | bash",
        copy_text: "curl -fsSL 'http://127.0.0.1:8443/api/lite/fleet/agent/bootstrap.sh?role=" + role + "&token=mock-invite-token' | bash",
        token_hint: 'mock…oken',
        hostname,
        role,
        role_label: roleLabel,
        expires_at: expiresAt,
        instructions: 'Open this invite on the new device while it is connected to the same Pocket Lab private network.',
      },
    }, { status: 202 });
  }),
  http.post('/api/lite/policy/apply', () => HttpResponse.json({ accepted: true, status: 'queued', command_id: 'mock-policy-apply' }, { status: 202 })),
  http.post('/api/lite/recovery/backup', () => HttpResponse.json({ accepted: true, status: 'queued', job_id: 'mock-backup-now' }, { status: 202 })),
  http.post('/api/lite/recovery/restore', async ({ request }) => {
    const body = await request.json().catch(() => ({}));
    if (!body.confirm) return HttpResponse.json({ detail: { status: 'confirmation_required', summary: 'Confirm restore before running it.' } }, { status: 409 });
    return HttpResponse.json({ accepted: true, status: 'queued', job_id: 'mock-restore-latest' }, { status: 202 });
  }),
  http.get('/api/catalog.json', () => HttpResponse.json({ items: [{ id: 'gitea', name: 'Gitea', operation: 'deploy_blueprint' }] })),
  http.get('/api/fleet.json', () => HttpResponse.json(fleetAgents)),
  http.get('/api/fleet/agents', () => HttpResponse.json(fleetAgents)),
  http.get('/api/drift/summary', () => HttpResponse.json(driftDetected)),
  http.get('/api/release/workflow', () => HttpResponse.json(releaseWorkflowRunning)),
  http.get('/api/events/recent', () => HttpResponse.json(recentEvents)),
  http.get('/api/events/status', () => HttpResponse.json({ status: 'ok', transport: 'mock', recent: recentEvents.events.length })),
  http.get('/api/workflows/status', () => HttpResponse.json({ status: 'ok', workflows: 1 })),
  http.get('/api/reliability/status', () => HttpResponse.json({ status: 'ok', dlq: 0 })),
  http.post('/api/operations/execute', async ({ request }) => {
    const body = await request.json().catch(() => ({}));
    const operation = body.operation || body.intent || 'unknown';
    if ([['retired compatibility intent', 'field'].join(' '), ['retired sync compatibility', 'task'].join(' '), ['retired IaC deploy compatibility', 'task'].join(' ')].includes(operation)) {
      return HttpResponse.json({ detail: 'legacy operations are retired' }, { status: 400 });
    }
    if (!controlPlane().ready) {
      return HttpResponse.json({ detail: 'NATS/JetStream worker execution is required; write action paused.' }, { status: 503 });
    }
    return HttpResponse.json({ accepted: true, job_id: `mock-${operation}-001`, operation, correlation_id: 'mock-correlation-001' }, { status: 202 });
  }),
];

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

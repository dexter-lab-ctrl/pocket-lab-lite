import React from 'react';
import { controlPlaneHealthy, controlPlaneNatsDown, workerDown } from '../mocks/fixtures/controlPlane.js';
import {
  telemetryNormal,
  telemetryLowDisk,
  healthAllGreen,
  healthVaultSealed,
  fleetAgents,
  driftDetected,
  releaseWorkflowRunning,
  recentEvents,
  observabilityRuntimeHealthy,
  observabilityRuntimeDegraded,
} from '../mocks/fixtures/pocketlab.js';

const originalFetchKey = '__pocketlabTier9OriginalFetch';
const originalWebSocketKey = '__pocketlabTier9OriginalWebSocket';

const jsonHeaders = { 'Content-Type': 'application/json' };

const catalogItems = {
  items: [
    { id: 'gitea', title: 'Gitea', name: 'Gitea', category: 'Source Control', description: 'Self-hosted Git service for Pocket Lab.', status: 'ready', operation: 'deploy_blueprint' },
    { id: 'vault', title: 'OpenBao / Vault', name: 'OpenBao / Vault', category: 'Secrets', description: 'Secrets and dynamic access broker.', status: 'ready', operation: 'deploy_blueprint' },
    { id: 'nats', title: 'NATS JetStream', name: 'NATS JetStream', category: 'Event Backbone', description: 'Durable command and lifecycle event bus.', status: 'installed', operation: 'deploy_blueprint' },
  ],
  updated_at: '2026-06-12T08:00:00Z',
};

const emptyCatalog = { items: [], updated_at: '2026-06-12T08:00:00Z' };

const driftSummary = {
  healthy: 7,
  drifted: 2,
  pending_approval: 1,
  failed: 0,
  last_scan_at: '2026-06-12T08:15:00Z',
  ...driftDetected.summary,
};

const driftJobs = [
  { job_id: 'drift-001', target: 'nats-config', status: 'diff_ready', severity: 'high', scope: 'service', summary: 'NATS stream retention differs from desired state.' },
  { job_id: 'drift-002', target: 'vault-policy', status: 'pending_approval', severity: 'medium', scope: 'policy', summary: 'Vault policy update requires approval.' },
];

const operationRuns = {
  runs: [
    { job_id: 'job-drift-001', operation: 'drift_scan', status: 'succeeded', updated_at: '2026-06-12T08:20:00Z' },
    { job_id: 'job-release-001', operation: 'release_sync', status: 'pending_approval', updated_at: '2026-06-12T08:18:00Z' },
    { job_id: 'job-backup-001', operation: 'backup_now', status: 'succeeded', updated_at: '2026-06-12T08:10:00Z' },
  ],
};

const releaseStatus = {
  current_version: 'v0.9.0-dev',
  latest_version: 'v0.9.1-dev',
  update_available: true,
  phase: 'available',
  last_checked_at: '2026-06-12T08:12:00Z',
  source: 'mock-fastapi',
};

const governanceSettings = {
  governanceMode: 'personal',
  enterpriseModeEnabled: false,
  source: 'storybook-mock-fastapi',
};

function response(body, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(body), { status, headers: jsonHeaders }));
}

function delayed(body, status = 200, ms = 1600) {
  return new Promise((resolve) => {
    window.setTimeout(() => resolve(new Response(JSON.stringify(body), { status, headers: jsonHeaders })), ms);
  });
}

function operationStatusForScenario(scenario, operation) {
  if (scenario === 'approval-required') {
    return { job_id: `storybook-${operation}-approval`, operation, status: 'pending_approval', message: 'Waiting for approval evidence before worker resume.' };
  }
  if (scenario === 'failed-operation') {
    return { job_id: `storybook-${operation}-failed`, operation, status: 'failed', error: 'Worker reported a controlled failure for Storybook documentation.' };
  }
  return { job_id: `storybook-${operation}-success`, operation, status: 'succeeded', stdout: 'Typed operation completed through FastAPI mock.', message: 'Completed' };
}

function controlPlaneForScenario(scenario) {
  if (scenario === 'degraded') return controlPlaneNatsDown;
  if (scenario === 'approval-required') return { ...workerDown, ready: true, worker: true, message: 'FastAPI/NATS ready; approval policy requires review.' };
  return controlPlaneHealthy;
}

function makeMockFetch(originalFetch, scenario) {
  return async (input, options = {}) => {
    const url = typeof input === 'string' ? input : input?.url || '';
    const method = String(options?.method || 'GET').toUpperCase();
    const path = url.startsWith('http') ? new URL(url).pathname : url.split('?')[0];

    if (scenario === 'loading' && method === 'GET' && [
      '/api/catalog.json', '/api/release/workflow', '/api/drift/summary', '/api/fleet.json', '/api/health-engine.json'
    ].includes(path)) {
      return delayed({}, 200, 2400);
    }

    if (scenario === 'error' && method === 'GET' && [
      '/api/catalog.json', '/api/release/workflow', '/api/drift/summary', '/api/fleet.json'
    ].includes(path)) {
      return response({ error: 'Storybook controlled API error' }, 500);
    }

    if (path === '/ready') return response(controlPlaneForScenario(scenario), controlPlaneForScenario(scenario).ready ? 200 : 503);
    if (path === '/api') return response({ name: 'Pocket Lab FastAPI/NATS Control API', mode: 'storybook' });
    if (path === '/api/nats/status') {
      const cp = controlPlaneForScenario(scenario);
      return response({ connected: cp.nats, jetstream: cp.jetstream, required: true, mode: 'storybook' }, cp.nats ? 200 : 503);
    }
    if (path === '/api/workers/status') {
      const cp = controlPlaneForScenario(scenario);
      return response({ available: cp.worker, workers: [{ name: 'pocketlab_worker', status: cp.worker ? 'online' : 'offline' }] }, cp.worker ? 200 : 503);
    }

    if (path === '/api/catalog.json') return response(scenario === 'empty' ? emptyCatalog : catalogItems);
    if (path === '/api/catalog/refresh' && method === 'POST') return response({ accepted: true, operation: 'catalog_refresh', updated_at: '2026-06-12T08:30:00Z', count: catalogItems.items.length }, 202);
    if (path === '/api/telemetry.json') return response(scenario === 'degraded' ? telemetryLowDisk : telemetryNormal);
    if (path === '/api/health-engine.json') return response(scenario === 'degraded' ? healthVaultSealed : healthAllGreen);
    if (path === '/api/observability/status') return response(scenario === 'degraded' ? observabilityRuntimeDegraded : observabilityRuntimeHealthy);

    if (path === '/api/logs/query') {
      const now = Date.parse('2026-06-12T08:30:00Z') * 1000000;
      const values = scenario === 'degraded' ? [] : [
        [String(now - 3000000000), 'INFO security_audit policy guardrail passed'],
        [String(now - 2000000000), 'WARN drift review waiting for approval'],
        [String(now - 1000000000), 'INFO Pocket Lab FastAPI log query stream ready'],
      ];
      return response({
        status: 'success',
        data: { result: values.length ? [{ stream: { job: 'pocketlab-fastapi' }, values }] : [] },
        meta: { matched_count: values.length, query_time_ms: 9 }
      });
    }

    if (path === '/api/fleet.json') {
      if (scenario === 'empty') return response({ nodes: [] });
      return response({ nodes: [
        { id: 'android-lab-01', name: 'Android Lab 01', role: 'compute', status: 'online', ip: '100.64.0.11', source: 'tailscale', last_seen_at: '2026-06-12T08:10:00Z' },
        { id: 'edge-storage-01', name: 'Edge Storage 01', role: 'storage', status: 'warning', ip: '100.64.0.12', source: 'tailscale', last_seen_at: '2026-06-12T08:08:00Z' },
      ] });
    }
    if (path === '/api/fleet/agents') return response(scenario === 'empty' ? { agents: [] } : fleetAgents);
    if (path.includes('/api/fleet/agents/') && path.endsWith('/commands')) return response({ commands: [{ id: 'cmd-001', type: 'health.check', status: 'succeeded', at: '2026-06-12T08:11:00Z' }] });
    if (path === '/api/fleet/agents/broadcast' && method === 'POST') return response({ accepted: true, subject: 'pocketlab.commands.fleet.broadcast' }, 202);

    if (path === '/api/drift/summary') return response(driftSummary);
    if (path === '/api/drift/jobs') return response(driftJobs);
    if (path.endsWith('/diff') && path.includes('/api/drift/jobs/')) return response([{ path: 'nats.streams.POCKETLAB_EVENTS.max_age', desired: '7d', actual: '1d' }]);
    if (path.includes('/api/drift/jobs/')) return response(driftJobs[0]);
    if (['/api/drift/approve', '/api/drift/apply', '/api/drift/ignore'].includes(path) && method === 'POST') return response({ accepted: true, job_id: 'storybook-drift-decision', status: scenario === 'approval-required' ? 'pending_approval' : 'succeeded' }, 202);

    if (path === '/api/operations/runs') return response(operationRuns);
    if (path === '/api/operations/preview' && method === 'POST') return response({ accepted: true, status: 'preview_ready', stdout: 'Preview completed. No changes applied.', job_id: 'storybook-preview-001' }, 202);
    if (path === '/api/operations/execute' && method === 'POST') {
      if (scenario === 'degraded') return response({ detail: 'NATS/JetStream worker execution is required; write action paused.' }, 503);
      const body = JSON.parse(options?.body || '{}');
      const operation = body.operation || 'unknown';
      const status = operationStatusForScenario(scenario, operation);
      if (operation === 'fleet_join' && scenario !== 'failed-operation') {
        return response({ accepted: true, job_id: status.job_id, operation, status: status.status, hostname: body?.params?.hostname || 'edge-lab-storybook', invite: 'storybook-device-invite' }, 202);
      }
      return response({ accepted: true, job_id: status.job_id, operation, status: status.status, stdout: status.stdout, detail: status.message || status.error }, 202);
    }
    if (path.startsWith('/api/operations/') && (path.endsWith('/status') || method === 'GET')) {
      const jobId = path.split('/').filter(Boolean)[2] || 'storybook-job';
      const operation = jobId.replace(/^storybook-/, '').replace(/-(success|failed|approval)$/, '') || 'operation';
      return response(operationStatusForScenario(scenario, operation));
    }

    if (path === '/api/release/workflow') return response(scenario === 'empty' ? { stages: [] } : releaseWorkflowRunning);
    if (path === '/api/release/self-update/status') return response(releaseStatus);
    if (path === '/api/release/self-update/check' && method === 'POST') return response({ accepted: true, status: 'queued', command_id: 'storybook-release-check' }, 202);
    if (path === '/api/release/self-update/apply' && method === 'POST') return response({ accepted: true, status: 'queued', command_id: 'storybook-release-apply' }, 202);

    if (path === '/api/settings/governance' && method === 'GET') return response(governanceSettings);
    if (path === '/api/settings/governance' && method === 'PUT') {
      const body = JSON.parse(options?.body || '{}');
      const mode = body.governanceMode === 'enterprise' ? 'enterprise' : 'personal';
      return response({ governanceMode: mode, enterpriseModeEnabled: mode === 'enterprise', source: 'storybook-mock-fastapi' });
    }

    if (path === '/api/opa_evaluations.json') return response({ evaluations: [{ policy: 'runbook.approval', status: 'pass', decision: 'allow' }] });
    if (path === '/api/events/recent') return response(recentEvents);
    if (path === '/api/events/status') return response({ status: 'ok', transport: 'storybook', recent: recentEvents.events.length });
    if (path === '/api/workflows/status') return response({ status: 'ok', workflows: 1 });
    if (path === '/api/reliability/status') return response({ status: 'ok', dlq: 0 });

    return originalFetch(input, options);
  };
}

function installMockWebSocket() {
  class MockWebSocket {
    static CONNECTING = 0;
    static OPEN = 1;
    static CLOSING = 2;
    static CLOSED = 3;

    constructor() {
      this.readyState = MockWebSocket.CONNECTING;
      window.setTimeout(() => {
        this.readyState = MockWebSocket.OPEN;
        this.onopen?.({ type: 'open' });
        this.onmessage?.({ data: JSON.stringify(recentEvents.events[0]) });
      }, 40);
    }

    send() {}

    close() {
      this.readyState = MockWebSocket.CLOSED;
      this.onclose?.({ type: 'close' });
    }
  }
  window.WebSocket = MockWebSocket;
}

export function installPocketLabStoryMocks(scenario = 'normal') {
  if (typeof window === 'undefined') return;
  if (!window[originalFetchKey]) window[originalFetchKey] = window.fetch.bind(window);
  if (!window[originalWebSocketKey]) window[originalWebSocketKey] = window.WebSocket;
  window.localStorage.setItem('POCKETLAB_MOCK_SCENARIO', scenario);
  window.fetch = makeMockFetch(window[originalFetchKey], scenario);
  installMockWebSocket();
}

export function withPocketLabStoryMocks(Story, context) {
  const scenario = context?.parameters?.pocketlab?.scenario || 'normal';
  installPocketLabStoryMocks(scenario);
  return React.createElement(Story);
}

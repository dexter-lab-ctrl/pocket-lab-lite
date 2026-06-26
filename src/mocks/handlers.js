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

const mockLiteSecurityPayload = () => {
  const now = Date.now();
  const baseRun = {
    run_id: 'security-mock-001',
    status: 'succeeded',
    started_at: new Date(now - 3 * 60 * 1000).toISOString(),
    completed_at: new Date(now - 2 * 60 * 1000).toISOString(),
    tools: ['lynis', 'trivy'],
    critical_count: 0,
    high_count: 0,
    medium_count: 0,
    low_count: 0,
    evidence_saved: true,
    sbom_saved: true,
    partial_results: false,
    tool_results: {
      lynis: { status: 'completed' },
      trivy: { status: 'completed', sbom_saved: true },
    },
  };
  const base = {
    status: 'healthy',
    summary: 'No urgent safety issues found.',
    score: 100,
    last_run: baseRun,
    scan_progress: {
      status: 'succeeded',
      stage: 'Safety check complete',
      step: 5,
      steps_total: 5,
      elapsed_seconds: 60,
      estimated_total_seconds: 180,
      estimated_remaining_seconds: 0,
      estimated_remaining_label: 'done',
      percent: 100,
      message: 'Pocket Lab checked host readiness and dependency risks in the backend worker.',
    },
    execution_timeline: [
      { key: 'request_accepted', title: 'Request accepted', detail: 'FastAPI accepted the safety request.', status: 'completed' },
      { key: 'worker_picked_up', title: 'Worker picked it up', detail: 'The backend worker started the check.', status: 'completed' },
      { key: 'lynis_host_check', title: 'Lynis host check', detail: 'Host readiness checks completed.', status: 'completed' },
      { key: 'trivy_dependency_secret_check', title: 'Trivy dependency & secret check', detail: 'Dependency, config, secret-like, and SBOM checks completed.', status: 'completed' },
      { key: 'evidence_saved', title: 'Evidence saved', detail: 'Sanitized evidence files ready.', status: 'completed' }
    ],
    checks_reviewed: 2,
    items_to_review: 0,
    critical_issues: [],
    findings: [],
    evidence_refs: [
      'security/evidence/security-mock-001/summary.json',
      'security/evidence/security-mock-001/lynis-normalized.json',
      'security/evidence/security-mock-001/trivy-normalized.json',
      'security/evidence/security-mock-001/sbom.cdx.json'
    ],
    history: [
      { run_id: 'security-mock-001', status: 'succeeded', score: 100, started_at: new Date(now - 3 * 60 * 1000).toISOString(), completed_at: new Date(now - 2 * 60 * 1000).toISOString(), duration_seconds: 60, items_to_review: 0, evidence_count: 4, sbom_saved: true },
      { run_id: 'security-mock-000', status: 'succeeded', score: 96, started_at: new Date(now - 24 * 60 * 60 * 1000).toISOString(), completed_at: new Date(now - 24 * 60 * 60 * 1000 + 120000).toISOString(), duration_seconds: 120, items_to_review: 1, evidence_count: 4, sbom_saved: true }
    ],
    finding_delta: {
      baseline: 'compared',
      previous_run_id: 'security-mock-000',
      new_count: 0,
      resolved_count: 1,
      unchanged_count: 0,
      summary: 'No new review items.',
      new: [],
      resolved: [{ id: 'mock-resolved-risk', source: 'trivy', category: 'dependency_vulnerability', severity: 'high', summary: 'Old dependency risk resolved.' }],
      unchanged: [],
      still_present: [],
    },
    guidance: [
    ],
    updated_at: new Date(now).toISOString(),
  };

  if (scenario() === 'security-partial') {
    return {
      ...base,
      status: 'degraded',
      summary: 'Partial safety check completed. Recheck recommended.',
      score: 92,
      last_run: { ...baseRun, status: 'partial', partial_results: true, low_count: 1, tool_results: { lynis: { status: 'timed_out' }, trivy: { status: 'completed', sbom_saved: true } } },
      execution_timeline: base.execution_timeline.map((step) => step.key === 'lynis_host_check' ? { ...step, status: 'review', detail: 'Lynis timed out before every host-readiness check finished.' } : step),
      items_to_review: 1,
      findings: [{ id: 'lynis-timeout', source: 'lynis', category: 'host_hardening', severity: 'low', status: 'timed_out', summary: 'Lynis host-readiness check did not finish.', recommendation: 'Run the check again while charging.' }],
      finding_delta: { ...base.finding_delta, new_count: 1, summary: 'One host-readiness item needs recheck.', new: [{ id: 'lynis-timeout', category: 'host_hardening', severity: 'low', status: 'timed_out', summary: 'Lynis host-readiness check did not finish.' }], resolved: [] },
    };
  }

  if (scenario() === 'security-protected-secret') {
    return {
      ...base,
      score: 98,
      items_to_review: 1,
      findings: [{ id: 'protected-runtime-secret', source: 'trivy', category: 'protected_runtime_secret', severity: 'low', summary: 'Protected backend runtime secret found.', recommendation: 'Keep file permissions restricted.' }],
      finding_delta: { ...base.finding_delta, unchanged_count: 1, still_present_count: 1, still_present: [{ id: 'protected-runtime-secret', category: 'protected_runtime_secret', severity: 'low', summary: 'Protected backend runtime secret found.' }] },
    };
  }

  if (scenario() === 'security-action-needed') {
    return {
      ...base,
      status: 'degraded',
      summary: 'Dependency review needed.',
      score: 72,
      last_run: { ...baseRun, high_count: 1, medium_count: 1 },
      items_to_review: 2,
      findings: [
        { id: 'dep-cve', source: 'trivy', category: 'dependency_vulnerability', severity: 'high', summary: 'Dependency has a known vulnerability.', recommendation: 'Update through Pocket Lab’s normal release/bootstrap workflow.' },
        { id: 'secret-like', source: 'trivy', category: 'secret_exposure', severity: 'medium', summary: 'Secret-like value found in a scanned path.', recommendation: 'Rotate through the backend Identity flow if needed.' }
      ],
    };
  }

  if (scenario() === 'security-first-run') {
    return {
      ...base,
      status: 'unknown',
      summary: 'Run your first safety check.',
      score: 0,
      last_run: null,
      scan_progress: null,
      execution_timeline: [],
      evidence_refs: [],
      history: [],
      finding_delta: {},
      items_to_review: 0,
      findings: [],
    };
  }

  if (scenario() === 'security-low') {
    return {
      ...base,
      status: 'unhealthy',
      summary: 'Safety check could not complete.',
      score: 0,
      last_run: { ...baseRun, status: 'failed', critical_count: 0, high_count: 0, evidence_saved: false, sbom_saved: false },
      evidence_refs: [],
      items_to_review: 1,
      findings: [{ id: 'missing-trivy', source: 'trivy', category: 'missing_tool', severity: 'high', summary: 'Trivy was not available on this device.', recommendation: 'Re-run the Lite bootstrap.' }],
    };
  }

  return base;
};
const normalizeLiteDeviceName = (value) => String(value || '')
  .trim()
  .toLowerCase()
  .replace(/[^a-z0-9_.-]+/g, '-')
  .replace(/^[-._]+|[-._]+$/g, '');

const mockLiteDevices = () => [
  {
    id: 'pocket-lab-lite-server',
    name: 'Pocket Lab Lite Server',
    status: 'healthy',
    connection: 'online',
    last_seen: new Date().toISOString(),
    remote_access: true,
    role: 'server_host',
    role_label: 'Server Host',
    is_current: true,
    capabilities: ['Run control plane', 'Serve Lite UI'],
  },
  {
    id: 'test-phone-2',
    name: 'Test-Phone-2',
    status: 'joining',
    connection: 'joining',
    last_seen: new Date(Date.now() - 20 * 60 * 1000).toISOString(),
    remote_access: false,
    role: 'compute',
    role_label: 'App Host',
    capabilities: ['Run apps', 'Report device health'],
  },
  {
    id: 'test-phone-4',
    name: 'Test-Phone-4',
    status: 'healthy',
    connection: 'online',
    last_seen: new Date().toISOString(),
    remote_access: false,
    role: 'compute',
    role_label: 'App Host',
    capabilities: ['Run apps', 'Report device health'],
  }
];

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
    summary: { apps_available: 1, devices_known: 1, security_findings: 0, nats_connected: true, jetstream_enabled: true, live_sampler_running: true },
    telemetry: { status: 'healthy', cpu_temp_c: 42, cpu_usage_percent: 12, free_space_mb: 256000, memory_usage_mb: 512 },
    services: [
      { name: 'Control API', status: 'healthy', summary: 'Pocket Lab Lite API is serving local control-plane requests' },
      { name: 'Command Bus', status: 'healthy', summary: 'NATS / JetStream is ready for worker-owned operations' },
      { name: 'Worker Execution', status: 'healthy', summary: 'Worker heartbeat sampler is active' },
      { name: 'App Catalog', status: 'healthy', summary: 'PhotoPrism is available for the Server Host' },
      { name: 'Identity & Access', status: 'healthy', summary: 'Vault is ready' },
      { name: 'Device Fleet', status: 'healthy', summary: '1 device record known to Pocket Lab Lite' }
    ],
  })),
  http.get('/api/lite/catalog', () => {
    const ready = scenario() === 'catalog-ready';
    const installing = scenario() === 'catalog-installing';
    const app = {
      id: 'photoprism', name: 'PhotoPrism', category: 'Photos',
      summary: 'Private photo library for your self-hosted workspace.',
      status: ready ? 'ready' : installing ? 'installing' : 'not_installed',
      install_state: ready ? 'installed' : installing ? 'installing' : 'available',
      installed: ready,
      target: { default_node_id: 'pocket-lab-lite-server', supported_roles: ['server'], eligible_devices: [{ node_id: 'pocket-lab-lite-server', name: 'Pocket Lab Lite Server', status: 'online', eligible: true, reason: 'Ready to install' }] },
      actions: { install: !ready && !installing, open: ready, details: true, retry: false, remove: false },
      runtime: { route: '/apps/photoprism/', url: ready ? '/apps/photoprism/' : null, health: ready ? 'healthy' : installing ? 'installing' : 'not_installed', version: ready ? 'detected-or-unknown' : null },
      access: { https_ready: true, route_ready: ready, open_url: ready ? '/apps/photoprism/' : null, message: ready ? 'PhotoPrism is ready over secure access.' : 'Install PhotoPrism to enable secure app access.' },
      progress: installing ? { step: 'Preparing PhotoPrism runtime', current: 2, total: 7, message: 'Setting up the app environment.' } : null,
      last_operation: installing ? { operation_id: 'app-photoprism-mock', status: 'running', updated_at: new Date().toISOString(), message: 'PhotoPrism install is running.' } : ready ? { operation_id: 'app-photoprism-mock', status: 'succeeded', updated_at: new Date().toISOString(), message: 'PhotoPrism is ready.' } : null,
      evidence_refs: ready ? ['catalog/evidence/app-photoprism-mock/summary.json'] : [],
    };
    return HttpResponse.json({ status: 'healthy', access: { https_ready: true, secure_origin: 'https://pocket-lab-lite.example.ts.net', route_mode: 'tailscale_caddy', pwa_ready: true, message: 'Secure access is ready.' }, apps: [app], items: [app], count: 1, updated_at: new Date().toISOString() });
  }),
  http.get('/api/lite/identity', () => HttpResponse.json({ status: 'healthy', summary: 'Vault is initialized and unsealed', actions: ['change_password'] })),
  http.get('/api/lite/security', () => HttpResponse.json(mockLiteSecurityPayload())),
  http.get('/api/lite/fleet', () => HttpResponse.json({
    status: 'healthy',
    devices: mockLiteDevices(),
    count: mockLiteDevices().length,
    roles: [
      { role: 'compute', role_label: 'App Host', description: 'Runs apps and services for your Pocket Lab.' },
      { role: 'storage', role_label: 'Storage Node', description: 'Stores backups, files, or app data.' }
    ],
    latest_invite: null,
    updated_at: new Date().toISOString(),
  })),
  http.get('/api/lite/policy', () => HttpResponse.json({ status: 'healthy', summary: 'Protection rules are available in advisory mode', protection_enabled: false, requires_confirmation: true, allowed_actions: ['install_app', 'add_device', 'run_safety_check', 'backup_now'] })),
  http.get('/api/lite/recovery', () => HttpResponse.json({
    status: 'healthy',
    summary: 'Recovery Ready',
    repository: { type: 'local', engine: 'restic', encrypted: true, ready: true, location: '~/pocket-lab-lite-backups' },
    what_will_be_backed_up: ['Lite runtime state', 'Device records and heartbeats', 'Device invite lifecycle records', 'Rules/protection state', 'App catalog/install metadata', 'Backup manifests and receipts'],
    what_will_not_be_backed_up: ['raw API tokens', 'raw invite tokens', 'NATS passwords', 'Vault root token', 'Vault unseal keys', 'private SSH keys'],
    last_backup: { backup_id: 'mock-backup-001', created_at: new Date(Date.now() - 25 * 60 * 1000).toISOString(), engine: 'restic', verification_status: 'not_verified', included_file_count: 6, summary: 'Backup created with 6 safe item(s). Evidence saved.' },
    last_backup_time: new Date(Date.now() - 25 * 60 * 1000).toISOString(),
    last_verification_result: 'not_verified',
    backup_history: [
      { backup_id: 'mock-backup-001', created_at: new Date(Date.now() - 25 * 60 * 1000).toISOString(), engine: 'restic', verification_status: 'not_verified', included_file_count: 6, summary: 'Backup created with 6 safe item(s). Evidence saved.' }
    ],
    available_restore_points: [
      { backup_id: 'mock-backup-001', created_at: new Date(Date.now() - 25 * 60 * 1000).toISOString(), engine: 'restic', verification_status: 'not_verified', included_file_count: 6, summary: 'Backup created with 6 safe item(s). Evidence saved.' }
    ],
    latest_restore_preview: { preview_id: 'mock-preview-001', backup_id: 'mock-backup-001', status: 'ready', change_count: 2 },
    pre_restore_checkpoint: { status: 'not_created', summary: 'A checkpoint will be created automatically before restore changes local state.' },
    last_restore: null,
    actions: ['backup_now', 'verify_backup', 'preview_restore', 'restore_latest'],
    planned_actions: [],
    updated_at: new Date().toISOString(),
  })),
  http.get('/api/lite/recovery/backups', () => HttpResponse.json({
    status: 'healthy',
    count: 1,
    latest_backup: { backup_id: 'mock-backup-001', created_at: new Date(Date.now() - 25 * 60 * 1000).toISOString(), engine: 'restic', verification_status: 'not_verified', included_file_count: 6 },
    backups: [{ backup_id: 'mock-backup-001', created_at: new Date(Date.now() - 25 * 60 * 1000).toISOString(), engine: 'restic', verification_status: 'not_verified', included_file_count: 6 }],
  })),
  http.get('/api/lite/recovery/backups/:backupId', ({ params }) => HttpResponse.json({ backup_id: params.backupId, engine: 'restic', verification_status: 'not_verified', included_file_count: 6 })),
  http.get('/api/lite/recovery/receipts/:backupId', ({ params }) => HttpResponse.json({ backup_id: params.backupId, status: 'succeeded', summary: 'Evidence saved', engine: 'restic', evidence_saved: true })),
  http.get('/api/lite/recovery/restore/previews/:previewId', ({ params }) => HttpResponse.json({
    preview_id: params.previewId,
    backup_id: 'mock-backup-001',
    status: 'ready',
    restore_allowed: true,
    restore_supported: true,
    verification_status: 'verified',
    change_count: 2,
    changes: [
      { relative_path: 'state/fleet_agents.json', action: 'would_overwrite', target: 'Lite state' },
      { relative_path: 'backup-metadata/scope.json', action: 'metadata_only', target: 'Backup metadata' }
    ],
    summary: 'Preview ready. Restore execution remains disabled until Increment 4.',
  })),
  http.post('/api/lite/catalog/install', async ({ request }) => {
    const body = await request.json().catch(() => ({}));
    return HttpResponse.json({ accepted: true, status: 'queued', operation_id: 'app-photoprism-mock', app_id: body.app_id || 'photoprism', target_node_id: body.target_node_id || 'pocket-lab-lite-server', message: 'PhotoPrism install started.' }, { status: 202 });
  }),
  http.post('/api/lite/identity/rotate', () => HttpResponse.json({ accepted: true, status: 'queued', command_id: 'mock-rotate-secret' }, { status: 202 })),
  http.post('/api/lite/security/check', () => HttpResponse.json({ accepted: true, status: 'queued', run_id: 'security-mock-002', command_id: 'security-mock-002', command_subject: 'pocketlab.commands.lite.security.scan', execution_mode: 'worker', summary: 'Safety check queued. Pocket Lab will scan local security posture and dependency risks.' }, { status: 202 })),
  http.post('/api/lite/security/scan', () => HttpResponse.json({ accepted: true, status: 'queued', run_id: 'security-mock-002', command_id: 'security-mock-002', command_subject: 'pocketlab.commands.lite.security.scan' }, { status: 202 })),
  http.get('/api/lite/security/evidence/:runId', ({ params }) => HttpResponse.json({ run: { run_id: params.runId, status: 'succeeded' }, score: 100, status: 'healthy', summary: 'No urgent safety issues found.', findings: [], evidence_refs: ['security/evidence/security-mock-001/summary.json'] })),
  http.post('/api/lite/fleet/devices/:nodeId/restart-agent', ({ params }) => HttpResponse.json({
    accepted: true,
    status: 'queued',
    delivery: 'queued',
    summary: 'Restart requested. If the device is offline, it will run after the agent reconnects.',
    node_id: params.nodeId,
    command_id: 'mock-restart-agent',
  }, { status: 202 })),
  http.post('/api/lite/fleet/remove-device', async ({ request }) => {
    const body = await request.json().catch(() => ({}));
    if (!body.device_id) return HttpResponse.json({ detail: 'Choose a device to remove.' }, { status: 400 });
    if (!body.confirm) return HttpResponse.json({ detail: 'Confirm removal before removing a saved device record.' }, { status: 400 });
    if (body.device_id === 'pocket-lab-lite-server') return HttpResponse.json({ detail: 'Cannot remove the current Pocket Lab Lite server device.' }, { status: 409 });
    if (body.device_id === 'test-phone-4') return HttpResponse.json({ detail: 'Online devices are protected.' }, { status: 409 });
    return HttpResponse.json({
      status: 'removed',
      device_id: body.device_id,
      removed_device_records: 1,
      removed_invite_records: 1,
      message: 'Old device record removed.',
      summary: 'Old device record removed. The phone was not wiped and Pocket Lab was not uninstalled from that device.',
      updated_at: new Date().toISOString(),
    });
  }),
  http.post('/api/lite/fleet/add-device', async ({ request }) => {
    const body = await request.json().catch(() => ({}));
    const role = body.role === 'storage' ? 'storage' : 'compute';
    const roleLabel = role === 'storage' ? 'Storage Node' : 'App Host';
    const hostname = body.hostname || (role === 'storage' ? 'Pocket Lab Storage Node' : 'Pocket Lab App Host');
    const requested = normalizeLiteDeviceName(hostname);
    const conflict = mockLiteDevices().find((device) => [device.id, device.name, device.hostname, device.node_id].map(normalizeLiteDeviceName).includes(requested));
    if (conflict) {
      const connected = conflict.connection === 'online' || ['healthy', 'active', 'online', 'ready'].includes(String(conflict.status || '').toLowerCase());
      return HttpResponse.json({
        detail: {
          status: 'duplicate_device',
          summary: 'A device with this name already exists.',
          message: connected
            ? 'This device is already connected. Use a different name if this is another phone.'
            : 'An old device record already uses this name. Remove the old device record before creating a new invite.',
          existing_device: {
            device_id: conflict.id,
            device_name: conflict.name,
            role: conflict.role,
            status: conflict.status,
            connection: conflict.connection,
            can_remove_old_record: !connected,
          },
          safe_next_actions: ['Use a different device name', 'Refresh the Devices list', 'Remove the old device record if it is no longer used'],
        }
      }, { status: 409 });
    }
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
  http.post('/api/lite/recovery/backup', () => HttpResponse.json({ accepted: true, status: 'queued', job_id: 'mock-backup-now', command_subject: 'pocketlab.commands.lite.backup.create' }, { status: 202 })),
  http.post('/api/lite/recovery/backups/:backupId/verify', ({ params }) => HttpResponse.json({ accepted: true, status: 'queued', job_id: `mock-verify-${params.backupId}`, command_subject: 'pocketlab.commands.lite.backup.verify', summary: 'Backup verification queued.' }, { status: 202 })),
  http.post('/api/lite/recovery/restore/preview', () => HttpResponse.json({ accepted: true, status: 'queued', job_id: 'mock-restore-preview', command_subject: 'pocketlab.commands.lite.restore.preview', summary: 'Restore preview queued.' }, { status: 202 })),
  http.post('/api/lite/recovery/restore', async ({ request }) => {
    const body = await request.json().catch(() => ({}));
    if (!body.confirm) return HttpResponse.json({ detail: { status: 'confirmation_required', summary: 'Confirm restore before running it.' } }, { status: 409 });
    return HttpResponse.json({ accepted: true, status: 'queued', job_id: 'mock-restore-apply', command_subject: 'pocketlab.commands.lite.restore.apply', summary: 'Restore queued. Pocket Lab will create a pre-restore checkpoint before changing Lite state.' }, { status: 202 });
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
  })
];

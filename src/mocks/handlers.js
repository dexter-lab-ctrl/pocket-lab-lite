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


const mockAppLifecycleProfiles = () => [{
  app_id: 'photoprism',
  name: 'PhotoPrism',
  installed: true,
  status: scenario() === 'lifecycle-attention' ? 'review' : 'ready',
  summary: scenario() === 'lifecycle-attention' ? 'PhotoPrism needs attention.' : 'PhotoPrism is ready, protected, and recoverable.',
  host_device: { id: 'pocket-lab-lite-server', name: 'Pocket Lab Lite Server', label: 'Runs on Server Phone', status: 'online' },
  storage: { status: 'connected', summary: 'Media connected', mapping_count: 2, labels: ['Phone photos'] },
  security: { status: 'protected', summary: 'Protected app', evidence_status: 'saved', last_checked_at: new Date(Date.now() - 2 * 60 * 1000).toISOString() },
  backup: { status: 'ready', summary: 'Backup ready', default_mode: 'config_only', media: 'excluded', target_available: true, target_ready: true, target_label: 'Storage Phone' },
  backup_targets: { status: 'healthy', app_id: 'photoprism', targets: [{ device_id: 'storage-phone', name: 'Storage Phone', status: 'ready', ready: true, available: true, label: 'Storage device', summary: 'Storage Phone can save app backups.' }], count: 1, ready_count: 1 },
  app_lifecycle: { status: 'ready', preservation: { media_preserved_by_default: true, backups_preserved_by_default: true, evidence_preserved_by_default: true } },
  recovery: { status: 'review', summary: 'Restore preview not ready', preview_available: false, restore_available: false },
  update: mockAppUpdateState(),
  media: { status: 'ready', summary: 'Import ready', mapping_count: 1, labels: ['Phone photos'], last_imported_at: new Date(Date.now() - 30 * 60 * 1000).toISOString(), evidence: { status: 'saved', count: 1, summary: '1 media record' } },
  attention: scenario() === 'lifecycle-attention' ? [{ id: 'backup_target_missing', area: 'backup', severity: 'review', title: 'Backup target not ready', summary: 'Join a storage device to save app backups elsewhere.' }] : [],
  actions: {
    open: { enabled: true, label: 'Open', url: '/apps/photoprism/' },
    open_full_screen: { enabled: true, label: 'Open full screen', url: '/apps/photoprism/' },
    install_to_phone: { enabled: true, label: 'Install to phone', url: '/apps/photoprism/' },
    connect_photos: { enabled: true, label: 'Connect photos' },
    check_app: { enabled: true, label: 'Check app', category: 'safety', summary: 'Check route, health, storage, and safety proof.', status: 'ready' },
    backup_app: { enabled: true, label: 'Back up app' },
    preview_restore: { enabled: false, label: 'Preview restore', reason: 'No verified app backup yet' },
    import_photos: { enabled: true, label: 'Import photos', summary: 'Import connected photos into PhotoPrism.', status: 'ready' },
    backup_to_storage: { enabled: true, label: 'Back up to storage device', summary: 'Save PhotoPrism backup to Storage Phone.', status: 'ready', target_label: 'Storage Phone', requires_target: true },
    install_app: { enabled: false, label: 'Install', reason: 'PhotoPrism is already installed.' },
    update_app: { enabled: true, label: 'Update', category: 'app_setup', summary: 'Check whether this app is ready for a safe update.', status: 'review', readiness_only: true, apply_supported: false, progress: mockAppUpdateState().pending_check?.progress || null, latest_check: mockAppUpdateState().latest_check, evidence_ref: mockAppUpdateState().latest_check?.evidence_ref },
    repair_app: { enabled: true, label: 'Repair', category: 'recovery', summary: 'Fix route, health, and storage setup safely.', status: 'ready' },
    remove_app: { enabled: true, label: 'Remove app', risk: 'destructive', requires_confirmation: true, summary: 'Your photo files and backups will not be deleted by default.' },
  },
  evidence: { status: 'saved', summary: 'Safety, recovery, and media records saved', security_count: 1, backup_count: 1, media_count: 1 },
  updated_at: new Date().toISOString(),
}];



function mockAppUpdateState() {
  const running = scenario() === 'app-update-running';
  const noCheck = scenario() === 'app-update-empty';
  const now = new Date().toISOString();
  const latest = noCheck ? null : {
    app_id: 'photoprism',
    app_label: 'PhotoPrism',
    action_id: 'update_app',
    action_label: 'Update',
    operation_id: 'app-update-check-photoprism-mock001',
    status: 'succeeded',
    readiness: scenario() === 'app-update-current' ? 'ready' : 'review',
    summary: scenario() === 'app-update-current' ? 'Already current. No update was applied.' : 'Update source not ready. No update was applied.',
    current_version: { status: 'unknown', summary: 'Current version could not be safely verified.', raw_value_hidden: true },
    latest_version: { status: 'unknown', summary: 'Update source not configured yet.' },
    update_available: 'unknown',
    apply_supported: false,
    rollback_ready: false,
    backup_fresh: true,
    restore_preview_ready: false,
    route_healthy: true,
    safety_recent: true,
    evidence_ref: 'apps/photoprism/update/app-update-check-photoprism-mock001.json',
    proof_counts: { passed: 7, review: 4, failed: 0, not_checked: 0, not_applicable: 0 },
    progress: { phase: 'completed', step: 'Update readiness checked. No update was applied.', percent: 100, bounded: true, steps: [
      { id: 'version', label: 'Version', status: 'review' },
      { id: 'backup', label: 'Backup', status: 'completed' },
      { id: 'restore_preview', label: 'Restore Preview', status: 'review' },
      { id: 'route', label: 'Route', status: 'completed' },
      { id: 'rollback', label: 'Rollback', status: 'review' },
      { id: 'evidence', label: 'Evidence', status: 'completed' },
    ] },
    updated_at: now,
    completed_at: now,
  };
  const pending = running ? {
    app_id: 'photoprism',
    app_label: 'PhotoPrism',
    action_id: 'update_app',
    operation_id: 'app-update-check-photoprism-running',
    status: 'running',
    summary: 'Checking PhotoPrism update readiness.',
    progress: { phase: 'running', step: 'Checking version, backup, route, rollback, and safety proof.', percent: 44, indeterminate: true, bounded: true, steps: [
      { id: 'version', label: 'Version', status: 'active' },
      { id: 'backup', label: 'Backup', status: 'waiting' },
      { id: 'restore_preview', label: 'Restore Preview', status: 'waiting' },
      { id: 'route', label: 'Route', status: 'waiting' },
      { id: 'rollback', label: 'Rollback', status: 'waiting' },
      { id: 'evidence', label: 'Evidence', status: 'waiting' },
    ] },
    evidence_ref: 'apps/photoprism/update/app-update-check-photoprism-running.json',
    updated_at: now,
  } : null;
  return {
    status: 'healthy',
    app_id: 'photoprism',
    app_label: 'PhotoPrism',
    summary: 'Update readiness can be checked.',
    update_check_supported: true,
    update_apply_supported: false,
    apply_supported: false,
    latest_check: latest,
    pending_check: pending,
    operation_running: running,
    readiness: { status: latest?.readiness || 'unknown', summary: latest?.summary || 'No update check has run yet.' },
    actions: {
      update_app: { enabled: !running, label: 'Update', summary: 'Check whether this app is ready for a safe update.', disabled_reason: running ? 'Update readiness check is already running.' : null },
      apply_update: { enabled: false, label: 'Apply update', disabled_reason: 'Update apply is not enabled yet.' },
    },
    updated_at: now,
  };
}

function mockAppUpdateReceipt() {
  return ({
  receipt_version: 1,
  receipt_id: 'app-update-check-photoprism-mock001',
  app_id: 'photoprism',
  app_label: 'PhotoPrism',
  action_id: 'update_app',
  action_label: 'Update',
  status: 'succeeded',
  readiness: 'review',
  summary: 'Update source not ready. No update was applied.',
  completed_at: new Date().toISOString(),
  proofs: [
    { id: 'backend_worker_executed', label: 'Backend worker executed', status: 'passed', plain_language: 'The update readiness check ran through the backend worker.' },
    { id: 'frontend_no_shell', label: 'Browser did not run commands', status: 'passed', plain_language: 'The browser only requested Update through FastAPI.' },
    { id: 'no_update_applied', label: 'No update was applied', status: 'passed', plain_language: 'No files were replaced and no services were restarted.' },
    { id: 'backup_freshness_checked', label: 'Backup freshness checked', status: 'passed', plain_language: 'A verified app backup is available.' },
    { id: 'restore_preview_checked', label: 'Restore preview checked', status: 'review', plain_language: 'Prepare a restore preview before updating.' },
    { id: 'rollback_readiness_checked', label: 'Rollback readiness checked', status: 'review', plain_language: 'Rollback is not enabled for app updates yet.' },
    { id: 'secrets_hidden', label: 'Secrets hidden', status: 'passed', plain_language: 'Secret values are hidden.' },
  ],
  proof_counts: { passed: 5, review: 2, failed: 0, not_checked: 0, not_applicable: 0 },
  what_changed: ['Pocket Lab Lite checked whether PhotoPrism is ready for a safe update.'],
  what_did_not_happen: ['No update was installed.', 'No files were replaced.', 'No database was changed.', 'No photos were changed.', 'No services were restarted.', 'No secret values were exposed.'],
  redaction: { status: 'passed', secrets_hidden: true, raw_logs_hidden: true, raw_paths_hidden: true },
  technical_details: { action_id: 'update_app', execution_owner: 'backend worker', apply_supported: false, rollback_ready: false, raw_logs: 'hidden', raw_paths: 'hidden', secret_values: 'hidden' },
  evidence_ref: 'apps/photoprism/update/app-update-check-photoprism-mock001.json',
  updated_at: new Date().toISOString(),
});
}

const mockAppEvidence = () => {
  const completedAt = new Date(Date.now() - 6 * 60 * 1000).toISOString();
  const receipt = {
    receipt_version: 1,
    receipt_id: 'photoprism-media-mock001',
    app_id: 'photoprism',
    app_label: 'PhotoPrism',
    action_id: 'import_photos',
    action_label: 'Import photos',
    status: 'succeeded',
    summary: 'Import photos completed.',
    started_at: new Date(Date.now() - 9 * 60 * 1000).toISOString(),
    completed_at: completedAt,
    proof_counts: { passed: 8, review: 0, failed: 0, not_checked: 0, not_applicable: 1 },
    proof_status: 'passed',
    safety_badges: ['Backend worker executed', 'Storage read-only', 'Secrets hidden', 'Media preserved'],
    proofs: [
      { id: 'backend_worker_executed', label: 'Backend worker executed', status: 'passed', plain_language: 'The action was handled by Pocket Lab Lite backend, not the browser.' },
      { id: 'frontend_no_shell', label: 'Browser did not run commands', status: 'passed', plain_language: 'The browser only requested Import photos through FastAPI.' },
      { id: 'browser_no_file_access', label: 'Browser did not access files', status: 'passed', plain_language: 'The browser did not read files or PhotoPrism output.' },
      { id: 'storage_read_only', label: 'Storage read-only', status: 'passed', plain_language: 'Connected source storage is read-only.' },
      { id: 'raw_paths_hidden', label: 'Raw paths hidden', status: 'passed', plain_language: 'Raw media paths and device-private paths are hidden.' },
      { id: 'secrets_hidden', label: 'Secrets hidden', status: 'passed', plain_language: 'Secret values and raw logs are hidden.' },
      { id: 'media_preserved', label: 'Media preserved', status: 'passed', plain_language: 'The Lite import request does not delete source photos.' },
      { id: 'media_details_owned_by_photoprism', label: 'PhotoPrism owns media details', status: 'passed', plain_language: 'Indexing, thumbnails, metadata, and warnings stay inside PhotoPrism.' },
      { id: 'receipt_saved', label: 'Receipt saved', status: 'passed', plain_language: 'Pocket Lab saved a sanitized import evidence reference.' },
    ],
    what_changed: ['PhotoPrism import was requested using connected phone storage.', 'Pocket Lab saved sanitized import evidence.'],
    what_did_not_happen: ['No source photos were deleted.', 'No secret values were exposed.', 'No frontend shell commands ran.', 'No PhotoPrism indexing was controlled by Pocket Lab Lite.'],
    details_owner: { name: 'PhotoPrism', reason: 'PhotoPrism handles indexing, thumbnails, metadata, and media warnings.' },
    redaction: { status: 'passed', secrets_hidden: true, raw_logs_hidden: true, raw_paths_hidden: true, media_file_names_hidden: true },
    technical_details: {
      action_id: 'import_photos',
      short_command_id: 'photoprism…mock001',
      evidence_ref: 'apps/photoprism/media/photoprism-media-mock001.json',
      execution_owner: 'backend worker',
      control_api: 'FastAPI',
      proof_source: 'PhotoPrism media evidence',
      redaction_status: 'passed',
      storage_mode: 'read_only',
      media_preserved: true,
    },
    evidence_ref: 'apps/photoprism/media/photoprism-media-mock001.json',
    updated_at: completedAt,
  };
  return {
    status: 'healthy',
    app_id: 'photoprism',
    summary: 'Import photos completed.',
    latest: receipt,
    proof_counts: receipt.proof_counts,
    items: [mockAppUpdateReceipt(), receipt],
    count: 2,
    fallback_receipt: null,
    updated_at: completedAt,
  };
};

const mockProtectedApps = () => [{
  app_id: 'photoprism',
  name: 'PhotoPrism',
  status: 'ready',
  summary: 'PhotoPrism is protected.',
  last_checked_at: new Date(Date.now() - 2 * 60 * 1000).toISOString(),
  checks: [
    { id: 'route_safety', label: 'Secure app route', status: 'passed', summary: 'PhotoPrism opens through Pocket Lab.' },
    { id: 'config_redaction', label: 'Config protected', status: 'passed', summary: 'Sensitive values are hidden.' },
    { id: 'media_permissions', label: 'Media folder access', status: 'unknown', summary: 'No media folders connected yet.' },
    { id: 'backup_readiness', label: 'Backup readiness', status: 'passed', summary: 'App config can be backed up.' },
  ],
  evidence: { status: 'saved', count: 1, summary: '1 safety record' },
}];

const mockAppBackups = () => [{
  app_id: 'photoprism',
  name: 'PhotoPrism',
  status: 'ready',
  summary: 'PhotoPrism config and app metadata are ready for backup.',
  default_mode: 'config_only',
  included: ['App config', 'App metadata', 'Storage mappings'],
  excluded: ['Original media', 'Generated cache', 'Raw secrets'],
  media: { default: 'excluded', summary: 'Media excluded. Your photo files can be large. Add media backup when a storage device is ready.' },
  backup_target: { available: true, ready: true, count: 1, label: 'Backup Target available', target_label: 'Storage Phone', summary: 'Backups can be saved to Storage Phone.' },
  backup_target_summary: { available: true, ready: true, count: 1, label: 'Backup Target available', target_label: 'Storage Phone' },
  backup_targets: [{ device_id: 'storage-phone', name: 'Storage Phone', ready: true, label: 'Storage device' }],
  evidence: { status: 'saved', count: 1, summary: '1 recovery record' },
}];

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
    protected_apps: mockProtectedApps(),
    app_security_profiles: { status: 'healthy', apps: mockProtectedApps(), count: mockProtectedApps().length },
    app_lifecycle_profiles: { status: 'healthy', apps: mockAppLifecycleProfiles(), count: mockAppLifecycleProfiles().length },
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
    capabilities: ['app_host', 'compute', 'security_scanner'],
    capability_labels: ['App Host', 'Compute', 'Security Scanner'],
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
    capabilities: ['app_host', 'compute'],
    capability_labels: ['App Host', 'Compute'],
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
    capabilities: ['app_host', 'compute'],
    capability_labels: ['App Host', 'Compute'],
  },
  {
    id: 'storage-phone-1',
    name: 'Storage Phone',
    status: 'healthy',
    connection: 'online',
    last_seen: new Date().toISOString(),
    remote_access: true,
    role: 'storage',
    role_label: 'Storage Node',
    capabilities: ['media_storage', 'backup_target'],
    capability_labels: ['Storage Node', 'Backup Target'],
    storage: { ready: true, status: 'ready', available_gb: 92, media_roots: ['Pictures', 'DCIM'], summary: 'Storage device ready' },
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
      host_device_id: 'pocket-lab-lite-server',
      host_device_name: 'Pocket Lab Lite Server',
      connected_devices: [],
      available_device_capabilities: { app_host: 3, media_storage: 1, backup_target: 1, security_scanner: 1, compute: 3 },
      ready_device_capabilities: { app_host: 2, media_storage: 1, backup_target: 1, security_scanner: 1, compute: 2 },
      device_relationships: { runs_on: 'Pocket Lab Lite Server', media_from: 'No media folders connected', storage_devices_available: 1, storage_devices_ready: 1 },
      storage_devices: [{ id: 'storage-phone-1', name: 'Storage Phone', ready: true, capability_labels: ['Storage Node', 'Backup Target'], storage: { available_gb: 92, media_roots: ['Pictures', 'DCIM'] } }],
      storage: { status: 'not_connected', summary: 'No media folders connected', mappings: [], count: 0, default_target: 'import', safe_modes: ['read_only', 'read_write'] },
      security_profile: { status: 'ready', label: 'Protected app', summary: 'Security profile available.' },
      backup_profile: { status: 'ready', label: 'Backup ready', summary: 'Config protected. Media excluded by default.', media: 'Media excluded' },
      lifecycle: mockAppLifecycleProfiles()[0],
      lifecycle_summary: { status: 'ready', summary: 'PhotoPrism is ready, protected, and recoverable.', host: 'Runs on Server Phone', storage: 'Media connected', security: 'Protected app', backup: 'Backup ready', attention_count: 0 },
    };
    return HttpResponse.json({ status: 'healthy', access: { https_ready: true, secure_origin: 'https://pocket-lab-lite.example.ts.net', route_mode: 'tailscale_caddy', pwa_ready: true, message: 'Secure access is ready.' }, apps: [app], items: [app], count: 1, updated_at: new Date().toISOString() });
  }),
  http.get('/api/lite/apps/lifecycle', () => HttpResponse.json({ status: 'healthy', summary: 'Unified App Lifecycle profiles are available.', apps: mockAppLifecycleProfiles(), items: mockAppLifecycleProfiles(), count: mockAppLifecycleProfiles().length, ready_count: 1, attention_count: 0, updated_at: new Date().toISOString() })),
  http.get('/api/lite/apps/lifecycle/photoprism', () => HttpResponse.json(mockAppLifecycleProfiles()[0])),
  http.get('/api/lite/apps/photoprism/actions', () => HttpResponse.json({ status: 'healthy', app_id: 'photoprism', name: 'PhotoPrism', summary: 'PhotoPrism Action Center is available.', actions: mockAppLifecycleProfiles()[0].actions, media: mockAppLifecycleProfiles()[0].media })),
  http.get('/api/lite/apps/photoprism/evidence', () => HttpResponse.json(mockAppEvidence())),
  http.get('/api/lite/apps/photoprism/update', () => HttpResponse.json(mockAppUpdateState())),
  http.get('/api/lite/apps/photoprism/update/receipts/:operationId', () => HttpResponse.json(mockAppUpdateReceipt())),
  http.post('/api/lite/apps/photoprism/update/apply', () => HttpResponse.json({ status: 'disabled', accepted: false, app_id: 'photoprism', action_id: 'apply_update', summary: 'Update apply is not enabled yet. Run backup and review readiness first.' }, { status: 409 })),
  http.post('/api/lite/apps/photoprism/actions/:actionId', ({ params }) => {
    const actionId = String(params.actionId || '');
    if (actionId === 'import_photos') {
      return HttpResponse.json({ accepted: true, status: 'queued', app_id: 'photoprism', action_id: actionId, summary: 'Import photos queued.', evidence: { status: 'pending', summary: 'Media evidence pending' } }, { status: 202 });
    }
    if (actionId === 'check_app') {
      return HttpResponse.json({ accepted: true, status: 'queued', app_id: 'photoprism', action_id: actionId, command_id: 'app-photoprism-safety-mock001', summary: 'Checking PhotoPrism safety.', progress: { phase: 'queued', step: 'Check queued.', bounded: true, steps: [{ id: 'request_accepted', label: 'Request accepted', status: 'active' }] }, evidence: { status: 'pending', summary: 'Evidence pending.' } }, { status: 202 });
    }
    if (actionId === 'repair_app') {
      return HttpResponse.json({ accepted: true, status: 'queued', app_id: 'photoprism', action_id: actionId, command_id: 'app-photoprism-repair-mock001', summary: 'Repairing PhotoPrism safely.', progress: { phase: 'queued', step: 'Repair queued.', bounded: true, steps: [{ id: 'setup_checked', label: 'Checking setup', status: 'active' }] }, evidence: { status: 'pending', summary: 'Evidence pending.' } }, { status: 202 });
    }
    if (actionId === 'update_app') {
      return HttpResponse.json({ accepted: true, status: 'queued', app_id: 'photoprism', action_id: actionId, operation_id: 'app-update-check-photoprism-mock001', command_id: 'app-update-check-photoprism-mock001', summary: 'Checking PhotoPrism update readiness.', progress: { phase: 'queued', step: 'Update check queued.', bounded: true, steps: [{ id: 'version', label: 'Version', status: 'active' }, { id: 'backup', label: 'Backup', status: 'waiting' }, { id: 'restore_preview', label: 'Restore Preview', status: 'waiting' }, { id: 'route', label: 'Route', status: 'waiting' }, { id: 'rollback', label: 'Rollback', status: 'waiting' }, { id: 'evidence', label: 'Evidence', status: 'waiting' }] }, evidence: { status: 'pending', summary: 'Evidence pending.' } }, { status: 202 });
    }
    if (actionId === 'backup_app') {
      return HttpResponse.json({ accepted: true, status: 'queued', app_id: 'photoprism', action_id: actionId, summary: 'PhotoPrism app backup queued.' }, { status: 202 });
    }
    return HttpResponse.json({ status: 'disabled', app_id: 'photoprism', action_id: actionId, summary: 'This action is not ready yet.' }, { status: 409 });
  }),
  http.get('/api/lite/apps/photoprism/storage-preview', () => HttpResponse.json({
    status: 'ready',
    root: '~/storage',
    root_label: 'Phone storage',
    summary: 'PhotoPrism can look for pictures in this phone’s storage.',
    subfolders: [
      { name: 'shared', path_summary: '~/storage/shared', kind: 'Android shared storage', included: true, photo_likely: true },
      { name: 'dcim', path_summary: '~/storage/dcim', kind: 'Camera photos', included: true, photo_likely: true },
      { name: 'pictures', path_summary: '~/storage/pictures', kind: 'Pictures', included: true, photo_likely: true },
      { name: 'downloads', path_summary: '~/storage/downloads', kind: 'Downloads', included: true, photo_likely: true },
      { name: 'movies', path_summary: '~/storage/movies', kind: 'Videos', included: true, photo_likely: true },
    ],
    connect_payload: { source_type: 'phone_media', label: 'Phone storage', source_path: '~/storage', target: 'import', mode: 'read_only' },
  })),
  http.get('/api/lite/apps/photoprism/storage-mappings', () => HttpResponse.json({ status: 'healthy', app_id: 'photoprism', mappings: [], count: 0, summary: 'No media folders connected yet.' })),
  http.post('/api/lite/apps/photoprism/storage-mappings', async ({ request }) => {
    const body = await request.json().catch(() => ({}));
    return HttpResponse.json({
      status: 'created',
      accepted: true,
      app_id: 'photoprism',
      mapping: {
        mapping_id: 'map-mockmedia001',
        label: body.label || 'Phone photos',
        source_type: body.source_type || 'phone_media',
        source_type_label: 'Phone photos',
        source_path_summary: body.source_path === '~/storage' ? 'Phone storage' : body.source_type === 'storage_device' ? 'Managed media' : 'Camera folder',
        target: body.target || 'import',
        target_label: 'Import folder',
        mode: body.mode || 'read_only',
        mode_label: 'Read-only',
        status: 'pending_apply',
        pending_apply: true,
        requires_restart: true,
      },
      summary: body.source_path === '~/storage' ? 'Phone storage connected. PhotoPrism can now look in ~/storage. Run Import photos to update your library.' : 'Media folder connected. Pocket Lab will apply it safely through the app agent path.',
    }, { status: 201 });
  }),
  http.delete('/api/lite/apps/photoprism/storage-mappings/:mappingId', ({ params }) => HttpResponse.json({ status: 'deleted', accepted: true, app_id: 'photoprism', mapping_id: params.mappingId, summary: 'Media folder disconnected.' })),
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
    capability_summary: {
      host_device_id: 'pocket-lab-lite-server',
      host_device_name: 'Pocket Lab Lite Server',
      available_device_capabilities: { app_host: 3, media_storage: 1, backup_target: 1, security_scanner: 1, compute: 3 },
      ready_device_capabilities: { app_host: 2, media_storage: 1, backup_target: 1, security_scanner: 1, compute: 2 },
      storage_devices_available: 1,
      storage_devices_ready: 1,
    },
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
    app_backups: mockAppBackups(),
    app_backup_profiles: { status: 'healthy', apps: mockAppBackups(), count: mockAppBackups().length },
    app_lifecycle_profiles: { status: 'healthy', apps: mockAppLifecycleProfiles(), count: mockAppLifecycleProfiles().length },
    backup_targets: [{ device_id: 'storage-phone', name: 'Storage Phone', status: 'ready', ready: true, available: true, label: 'Storage device', summary: 'Storage Phone can save app backups.' }],
    backup_target_profiles: { status: 'healthy', count: 1, ready_count: 1 },
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
  http.get('/api/lite/security/apps', () => HttpResponse.json({ status: 'healthy', apps: mockProtectedApps(), items: mockProtectedApps(), count: mockProtectedApps().length })),
  http.get('/api/lite/security/apps/photoprism', () => HttpResponse.json(mockProtectedApps()[0])),
  http.post('/api/lite/security/apps/photoprism/check', () => HttpResponse.json({ status: 'not_implemented', accepted: false, app_id: 'photoprism', summary: 'App-specific safety checks are prepared, but execution is not enabled yet. Use Run Safety Check for the current device-wide scan.' }, { status: 501 })),
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
  http.get('/api/lite/recovery/backup-targets', () => HttpResponse.json({ status: 'healthy', summary: 'Backup targets are available.', targets: [{ device_id: 'storage-phone', name: 'Storage Phone', status: 'ready', ready: true, available: true, label: 'Storage device', summary: 'Storage Phone can save app backups.' }], items: [{ device_id: 'storage-phone', name: 'Storage Phone', status: 'ready', ready: true, available: true, label: 'Storage device', summary: 'Storage Phone can save app backups.' }], count: 1, ready_count: 1 })),
  http.get('/api/lite/recovery/apps/photoprism/backup-targets', () => HttpResponse.json({ status: 'healthy', app_id: 'photoprism', name: 'PhotoPrism', targets: [{ device_id: 'storage-phone', name: 'Storage Phone', status: 'ready', ready: true, available: true, label: 'Storage device', summary: 'Storage Phone can save app backups.' }], count: 1, ready_count: 1 })),
  http.post('/api/lite/recovery/apps/photoprism/backup-to-target', () => HttpResponse.json({ status: 'not_implemented', accepted: false, app_id: 'photoprism', action_id: 'backup_to_storage', summary: 'Backup target transfer is prepared, but the storage-device transfer worker is not enabled yet.' }, { status: 501 })),
  http.get('/api/lite/recovery/apps', () => HttpResponse.json({ status: 'healthy', apps: mockAppBackups(), items: mockAppBackups(), count: mockAppBackups().length })),
  http.get('/api/lite/recovery/apps/photoprism', () => HttpResponse.json(mockAppBackups()[0])),
  http.post('/api/lite/recovery/apps/photoprism/backup', () => HttpResponse.json({ accepted: true, status: 'queued', app_id: 'photoprism', backup_id: 'app-backup-photoprism-mock', mode: 'config_only', summary: 'PhotoPrism app backup queued. Config and app metadata are included; media remains excluded unless a supported media backup mode is enabled.' }, { status: 202 })),
  http.post('/api/lite/recovery/apps/photoprism/restore/preview', () => HttpResponse.json({ status: 'not_implemented', accepted: false, app_id: 'photoprism', summary: 'Restore preview coming soon for app-specific recovery.' }, { status: 501 })),
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

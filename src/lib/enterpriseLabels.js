export const ENTERPRISE_OPERATION_LABELS = {
  git_sync: 'Update Environment',
  deploy_blueprint: 'Install Service',
  fleet_join: 'Add Device to Fleet',
  restore_backup: 'Restore from Backup',
  backup_now: 'Create Backup',
  backup_verify: 'Verify Backup',
  rotate_secret: 'Rotate Credential',
  release_sync: 'Apply Release',
  drift_scan: 'Check Configuration Health',
  policy_deploy: 'Apply Policy Bundle',
  secret_read_dynamic: 'Generate Temporary Access',
};

export const ENTERPRISE_STATUS_LABELS = {
  queued: 'Queued',
  idle: 'Ready',
  running: 'In Progress',
  succeeded: 'Completed Successfully',
  failed: 'Needs Attention',
  error: 'Needs Attention',
  diff_ready: 'Configuration Change Ready',
  drifted: 'Configuration Change Detected',
  pending: 'Waiting for Approval',
  pending_approval: 'Waiting for Approval',
  healthy: 'Healthy',
  degraded: 'Degraded',
  not_required: 'No Action Required',
};

export const ENTERPRISE_ARCHITECTURE_LABELS = {
  FastAPI: 'Control API',
  NATS: 'Event Bus',
  JetStream: 'Durable Event Stream',
  Worker: 'Executor',
  worker: 'executor',
  workers: 'executors',
  'Typed Operation': 'Operation Contract',
  'typed operation': 'operation contract',
  'Desired State': 'Target Configuration',
  'desired state': 'target configuration',
  GitOps: 'Environment Updates',
  Blueprint: 'Service Package',
  blueprint: 'service package',
  Drift: 'Configuration Health',
  drift: 'configuration health',
  Vault: 'Credential Store',
  vault: 'credential store',
};

export const ENTERPRISE_EVENT_SUBJECT_LABELS = [
  [/pocketlab\.events\.operation\.[\w.-]+/gi, 'Operation Activity'],
  [/pocketlab\.events\.workflow[\w.-]*/gi, 'Workflow Activity'],
  [/pocketlab\.events\.health[\w.-]*/gi, 'Health Activity'],
  [/pocketlab\.events\.telemetry[\w.-]*/gi, 'System Status Activity'],
  [/pocketlab\.events\.drift[\w.-]*/gi, 'Configuration Health Activity'],
  [/pocketlab\.events\.fleet[\w.-]*/gi, 'Device Fleet Activity'],
  [/pocketlab\.events\.release[\w.-]*/gi, 'Release Activity'],
  [/pocketlab\.events\.security[\w.-]*/gi, 'Security Activity'],
  [/pocketlab\.events\.catalog[\w.-]*/gi, 'Catalog Activity'],
  [/pocketlab\.events\.blueprint[\w.-]*/gi, 'Service Package Activity'],
  [/pocketlab\.events\.worker[\w.-]*/gi, 'Execution Activity'],
  [/pocketlab\.audit[\w.-]*/gi, 'Audit Activity'],
  [/pocketlab\.dlq\.[\w.-]+/gi, 'Recovery Queue Activity'],
];

export const ENTERPRISE_UI_LEAK_PATTERNS = [
  /\bgit_sync\b/i,
  /\bdeploy_blueprint\b/i,
  /\bfleet_join\b/i,
  /\brestore_backup\b/i,
  /\bbackup_now\b/i,
  /\bbackup_verify\b/i,
  /\brotate_secret\b/i,
  /\brelease_sync\b/i,
  /\bdrift_scan\b/i,
  /\bpolicy_deploy\b/i,
  /\bsecret_read_dynamic\b/i,
  /\/api\/events/i,
  /\/api\/operations/i,
  /\/ws\/events/i,
  /pocketlab\.events/i,
  /pocketlab\.audit/i,
  /\bFastAPI\b/i,
  /\bNATS\b/i,
  /\bJetStream\b/i,
  /\bworker claimed\b/i,
  /\bTyped Operation\b/i,
];

export function enterpriseOperationLabel(operation, fallback = 'Operation') {
  if (!operation) return fallback;
  return ENTERPRISE_OPERATION_LABELS[operation] || String(operation).replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export function enterpriseStatusLabel(status, fallback = 'Ready') {
  if (!status) return fallback;
  return ENTERPRISE_STATUS_LABELS[status] || String(status).replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export function enterpriseSubjectLabel(subject) {
  const value = String(subject || 'Activity Event');
  for (const [pattern, label] of ENTERPRISE_EVENT_SUBJECT_LABELS) {
    pattern.lastIndex = 0;
    if (pattern.test(value)) return label;
  }
  return enterpriseDisplayText(value || 'Activity Event');
}

export function enterpriseDisplayText(value) {
  if (value === null || value === undefined) return '';
  let text = String(value);

  for (const [operation, label] of Object.entries(ENTERPRISE_OPERATION_LABELS)) {
    text = text.replace(new RegExp(`\\b${operation}\\b`, 'g'), label);
  }

  text = text
    .replace(/\/ws\/events/g, 'Live Activity Stream')
    .replace(/\/api\/events\/recent/g, 'Recent Activity')
    .replace(/\/api\/events/g, 'Control Plane Activity')
    .replace(/\/api\/operations\/execute/g, 'Operation Submission')
    .replace(/\/api\/operations\/preview/g, 'Operation Preview')
    .replace(/\/api\/operations/g, 'Operation Records')
    .replace(/operation\.worker_claimed/g, 'execution.started')
    .replace(/worker_claimed/g, 'execution_started')
    .replace(/worker claimed/gi, 'execution started')
    .replace(/command worker/gi, 'command executor')
    .replace(/worker execution/gi, 'executor processing')
    .replace(/worker lifecycle/gi, 'execution lifecycle');

  for (const [pattern, label] of ENTERPRISE_EVENT_SUBJECT_LABELS) {
    pattern.lastIndex = 0;
    text = text.replace(pattern, label);
  }

  for (const [raw, label] of Object.entries(ENTERPRISE_ARCHITECTURE_LABELS)) {
    text = text.replace(new RegExp(`\\b${raw.replace(/\\s+/g, '\\s+')}\\b`, 'g'), label);
  }

  return text;
}

export function hasEnterpriseUiLeak(value) {
  const text = String(value || '');
  return ENTERPRISE_UI_LEAK_PATTERNS.some((pattern) => pattern.test(text));
}

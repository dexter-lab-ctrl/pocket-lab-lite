export const TAB_LABELS = {
  gitops: 'Keep My Environment Updated',
  appstore: 'Apps & Services',
  blueprint: 'Apps & Services',
  drift: 'Health & Issues',
  fleet: 'My Devices',
  vault: 'Passwords & Access',
  security: 'Safety Center',
  telemetry: 'System Status',
  release: 'Updates',
  recovery: 'Backups',
  logs: 'Activity',
  opa: 'Safety Center',
  settings: 'Settings',
  registry: 'Apps & Services',
};

export const ACTION_LABELS = {
  deploy_blueprint: 'Install',
  version: 'Release',
  drift_detected: 'Something Changed',
  join_fleet: 'Add Device',
  fleet_join: 'Add Device',
  desired_state: 'What Should Be Installed',
  rotate_secret: 'Change Password',
  git_sync: 'Update Settings',
  drift_scan: 'Check for Changes',
  release_sync: 'Update Everything',
  backup_now: 'Backup Now',
  restore_backup: 'Restore',
  backup_verify: 'Check Backup',
  policy_deploy: 'Run Safety Check',
  secret_read_dynamic: 'Create Temporary Access',
};

export const STATUS_LABELS = {
  queued: 'Getting ready',
  idle: 'Ready',
  running: 'Working',
  succeeded: 'Done',
  failed: 'Needs attention',
  error: 'Needs attention',
  diff_ready: 'Something Changed',
  drifted: 'Something Changed',
  pending: 'Waiting for review',
  pending_approval: 'Waiting for review',
  healthy: 'Healthy',
  not_required: 'No action needed',
};

export const OPERATION_COPY = {
  deploy_blueprint: {
    title: 'Install',
    description: 'Installs the selected app or service using the approved company setup.',
    success: 'Install request started.',
  },
  fleet_join: {
    title: 'Add Device',
    description: 'Prepares a safe invite so a new device can join your Pocket Lab.',
    success: 'Device invite created.',
  },
  restore_backup: {
    title: 'Restore',
    description: 'Restores your Pocket Lab from the selected backup point.',
    success: 'Restore request started.',
  },
  release_sync: {
    title: 'Update Everything',
    description: 'Checks for approved updates and applies them safely.',
    success: 'Update request started.',
  },
  rotate_secret: {
    title: 'Change Password',
    description: 'Changes the saved app password and stores it securely.',
    success: 'Password change started.',
  },
  git_sync: {
    title: 'Keep Updated',
    description: 'Saves the approved setup so your environment stays current.',
    success: 'Update request started.',
  },
  drift_scan: {
    title: 'Check for Changes',
    description: 'Looks for anything that changed from what should be installed.',
    success: 'Check started.',
  },
  backup_now: {
    title: 'Backup Now',
    description: 'Creates a new safe restore point.',
    success: 'Backup started.',
  },
  backup_verify: {
    title: 'Check Backup',
    description: 'Confirms the selected backup can be trusted.',
    success: 'Backup check started.',
  },
  policy_deploy: {
    title: 'Run Safety Check',
    description: 'Checks your environment against approved safety rules.',
    success: 'Safety check started.',
  },
  secret_read_dynamic: {
    title: 'Create Temporary Access',
    description: 'Creates short-lived access for a service without exposing permanent passwords.',
    success: 'Temporary access created.',
  },
};

export const SIMPLE_PRIMARY_BANNED_TERMS = [
  'GitOps',
  'Blueprint',
  'Drift',
  'NOC',
  'Vault',
  'Runbook',
  'NATS',
  'JetStream',
  'Worker',
  'Typed Operation',
  'Desired State',
  'Reconcile',
  'Policy Guardrails',
];

export function containsSimpleModeJargon(value) {
  if (!value) return false;
  return SIMPLE_PRIMARY_BANNED_TERMS.some((term) => new RegExp(`\\b${term.replace(/\\s+/g, '\\s+')}\\b`, 'i').test(String(value)));
}

export function simpleTabLabel(id, fallback) {
  return TAB_LABELS[id] || fallback;
}

export function simpleActionLabel(key, fallback) {
  return ACTION_LABELS[key] || fallback;
}

export function simpleStatusLabel(status, fallback) {
  return STATUS_LABELS[status] || fallback || status || 'Ready';
}

export function simpleOperationCopy(operation, fallbackTitle = 'Run Action') {
  return OPERATION_COPY[operation] || {
    title: fallbackTitle,
    description: 'Runs this task using approved settings.',
    success: `${fallbackTitle} started.`,
  };
}

export function redactTechnicalText(value) {
  if (!value) return '';
  return String(value)
    .replace(/deploy_blueprint/g, 'install')
    .replace(/fleet_join/g, 'add device')
    .replace(/drift_scan/g, 'check for changes')
    .replace(/rotate_secret/g, 'change password')
    .replace(/release_sync/g, 'update everything')
    .replace(/backup_now/g, 'backup')
    .replace(/restore_backup/g, 'restore')
    .replace(/backup_verify/g, 'check backup')
    .replace(/git_sync/g, 'update settings')
    .replace(/policy_deploy/g, 'safety check')
    .replace(/job_id/g, 'reference')
    .replace(/task id/gi, 'reference')
    .replace(/operation/gi, 'task');
}

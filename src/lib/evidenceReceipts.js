const OPERATION_LABELS = {
  deploy_blueprint: 'Install app or service',
  git_sync: 'Update settings',
  drift_scan: 'Check for changes',
  fleet_join: 'Add device',
  restore_backup: 'Restore backup',
  release_sync: 'Update release',
  rotate_secret: 'Change password',
  policy_deploy: 'Run safety check',
  backup_now: 'Create backup',
};

const EVIDENCE_BY_OPERATION = {
  deploy_blueprint: ['Operation request', 'Execution lifecycle event', 'Service package audit evidence'],
  git_sync: ['Environment update request', 'Repository sync event', 'Audit record'],
  drift_scan: ['Preview operation request', 'Configuration result event', 'Read-only evidence'],
  fleet_join: ['Device onboarding request', 'Device invite event', 'Audit record'],
  restore_backup: ['Restore request', 'Backup reference', 'Recovery audit record'],
  release_sync: ['Release operation request', 'Release validation event', 'Audit record'],
  rotate_secret: ['Secret rotation request', 'Credential store event', 'Audit record'],
  policy_deploy: ['Policy check request', 'Policy decision event', 'Audit record'],
  backup_now: ['Backup request', 'Backup status event', 'Restore point evidence'],
};

export function createEvidenceReceipt({ operation, jobId = '', status = 'succeeded', mode = 'execute', message = '', simpleMode = false } = {}) {
  const now = new Date().toISOString();
  const title = OPERATION_LABELS[operation] || operation || 'Pocket Lab task';
  return {
    id: jobId || `${operation || 'task'}-${Date.now()}`,
    title,
    operation: operation || 'unknown',
    jobId,
    status,
    mode,
    message,
    startedAt: now,
    completedAt: status === 'succeeded' ? now : '',
    evidence: EVIDENCE_BY_OPERATION[operation] || ['Operation request', 'Execution event', 'Audit record'],
  };
}

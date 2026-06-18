const PREVIEWS = {
  deploy_blueprint: {
    risk: 'medium',
    will: ['Install the selected app or service from an approved service package.', 'Queue a governed operation through the control plane.', 'Record lifecycle events and audit evidence.'],
    willNot: ['Run shell commands from the browser.', 'Delete existing data unless the blueprint explicitly requires it.', 'Bypass approval policy.'],
    evidence: ['Operation request', 'Execution lifecycle evidence', 'Audit record'],
  },
  git_sync: {
    risk: 'low',
    will: ['Sync approved repository content.', 'Queue the update through the control API.', 'Record operation status for troubleshooting.'],
    willNot: ['Expose a shell editor.', 'Talk directly to source control or backend messaging from the browser.', 'Apply destructive changes without governed execution.'],
    evidence: ['Operation request', 'GitOps event', 'Audit record'],
  },
  drift_scan: {
    risk: 'low',
    will: ['Check for differences from the target configuration.', 'Show findings before changes are applied.', 'Use a preview-style operation contract.'],
    willNot: ['Change installed services.', 'Delete files or secrets.', 'Require destructive approval.'],
    evidence: ['Drift scan event', 'Preview output'],
  },
  fleet_join: {
    risk: 'low',
    will: ['Prepare a safe device invite.', 'Queue device onboarding through the control plane.', 'Record the join request and status.'],
    willNot: ['Expose raw shell join commands in the UI.', 'Join unknown devices without the worker flow.', 'Bypass governance mode.'],
    evidence: ['Fleet join operation', 'Device lifecycle event'],
  },
  restore_backup: {
    risk: 'high',
    will: ['Prepare a restore request for the selected backup.', 'Require the governed restore path.', 'Record restore evidence and status.'],
    willNot: ['Restore data without confirmation/approval where required.', 'Hide destructive impact.', 'Bypass audit logging.'],
    evidence: ['Restore request', 'Backup reference', 'Audit record'],
  },
  release_sync: {
    risk: 'medium',
    will: ['Check and apply an approved release workflow.', 'Record release status and lifecycle events.', 'Use governed operation execution.'],
    willNot: ['Silently overwrite unmanaged changes.', 'Bypass approval policy.', 'Execute frontend shell commands.'],
    evidence: ['Release operation', 'Validation event', 'Audit record'],
  },
  rotate_secret: {
    risk: 'medium',
    will: ['Request a controlled password or secret rotation.', 'Keep secret handling behind the control plane.', 'Record that the change was requested.'],
    willNot: ['Reveal secret values in the UI.', 'Store raw secrets in browser logs.', 'Bypass credential-store or executor ownership.'],
    evidence: ['Secret rotation request', 'Audit record'],
  },
  policy_deploy: {
    risk: 'low',
    will: ['Run an approved safety check.', 'Apply policy evaluation through the control plane.', 'Show results in the UI.'],
    willNot: ['Bypass policy checks.', 'Run unrestricted commands.', 'Hide blocked outcomes.'],
    evidence: ['Policy decision', 'Audit record'],
  },
  backup_now: {
    risk: 'low',
    will: ['Create a safe restore point.', 'Queue backup through the worker path.', 'Record backup status.'],
    willNot: ['Delete existing backups without policy.', 'Expose storage credentials.', 'Bypass evidence logging.'],
    evidence: ['Backup operation', 'Backup status event'],
  },
};

const DEFAULT_PREVIEW = {
  risk: 'medium',
  will: ['Queue this task through the control plane.', 'Let the backend executor own execution.', 'Record observable lifecycle events.'],
  willNot: ['Run shell commands from the frontend.', 'Talk directly to backend messaging from the browser.', 'Bypass audit evidence.'],
  evidence: ['Operation request', 'Worker event', 'Audit record'],
};

export function safeActionPreview(operation, { simpleMode = false } = {}) {
  const preview = PREVIEWS[operation] || DEFAULT_PREVIEW;
  if (!simpleMode) return preview;
  return {
    ...preview,
    will: preview.will.map((item) => item.replace('control plane', 'Pocket Lab control plane').replace('operation contract', 'safe task')),
    willNot: preview.willNot.map((item) => item.replace('frontend', 'your browser').replace('backend messaging', 'backend messaging')),
    evidence: preview.evidence.map((item) => item.replace('Audit', 'Safety record').replace('Operation', 'Task')),
  };
}

export function riskStatus(risk) {
  if (risk === 'high') return 'blocked';
  if (risk === 'medium') return 'approval_required';
  return 'ready';
}

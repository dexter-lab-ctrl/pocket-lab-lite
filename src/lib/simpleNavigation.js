export const SIMPLE_HOME_TARGET = 'simple-home';
export const SIMPLE_ACTIVITY_TARGET = 'activity';

export const SIMPLE_PRIMARY_NAV_ITEMS = [
  { id: 'simple-home', label: 'Home', description: 'Start here for safe next steps and recent activity.', target: SIMPLE_HOME_TARGET },
  { id: 'simple-apps', label: 'Apps', description: 'Install and manage apps or services.', target: 'appstore' },
  { id: 'simple-health', label: 'Health', description: 'Check what changed or needs attention.', target: 'drift' },
  { id: 'simple-devices', label: 'Devices', description: 'Add and manage connected devices.', target: 'fleet' },
  { id: 'simple-more', label: 'More', description: 'Open the rest of Pocket Lab.', target: 'simple-more', kind: 'more' },
];

export const SIMPLE_MORE_NAV_ITEMS = [
  { id: 'simple-status', label: 'System Status', description: 'See whether Pocket Lab services are working.', target: 'telemetry' },
  { id: 'simple-passwords', label: 'Passwords & Access', description: 'Change saved passwords and access safely.', target: 'vault' },
  { id: 'simple-safety', label: 'Safety Center', description: 'Review safety checks and protection settings.', target: 'security' },
  { id: 'simple-backups', label: 'Backups', description: 'Create or restore from a safe restore point.', target: 'recovery' },
  { id: 'simple-updates', label: 'Updates', description: 'Keep Pocket Lab and installed services current.', target: 'release' },
  { id: 'simple-activity', label: 'Activity', description: 'Review what Pocket Lab has been doing.', target: SIMPLE_ACTIVITY_TARGET },
  { id: 'simple-advanced', label: 'Advanced Details', description: 'Open settings and operator-level details.', target: 'settings' },
];

export const SIMPLE_PRIMARY_TERMS_TO_AVOID = [
  'GitOps', 'Blueprint', 'Drift', 'NOC', 'Vault', 'Runbook', 'NATS', 'JetStream', 'Worker', 'Typed Operation', 'Desired State', 'Reconcile', 'Policy Guardrails',
];

export function simplePrimaryItemForTarget(target) {
  return SIMPLE_PRIMARY_NAV_ITEMS.find((item) => item.target === target);
}

export function simpleMoreItemForTarget(target) {
  return SIMPLE_MORE_NAV_ITEMS.find((item) => item.target === target);
}

export function isSimpleMoreTarget(target) {
  return SIMPLE_MORE_NAV_ITEMS.some((item) => item.target === target);
}

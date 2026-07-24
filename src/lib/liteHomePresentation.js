const READY_STATES = new Set(['healthy', 'ready', 'online', 'success', 'succeeded']);
const REVIEW_STATES = new Set(['degraded', 'warning', 'review', 'partial', 'unknown']);
const DANGER_STATES = new Set(['unavailable', 'unhealthy', 'failed', 'error', 'blocked', 'offline']);

const SERVICE_PRESENTATION = Object.freeze({
  control_api: {
    label: 'Workspace services',
    screen: 'home',
    ready: 'Your workspace services are available.',
    review: 'Pocket Lab is checking the workspace services.',
    danger: 'Workspace services need attention.',
  },
  command_bus: {
    label: 'Task delivery',
    screen: 'home',
    ready: 'Background tasks can be delivered safely.',
    review: 'Task delivery is still getting ready.',
    danger: 'Background tasks cannot be delivered right now.',
  },
  remote_access: {
    label: 'Remote access',
    screen: 'devices',
    ready: 'Private remote access is ready.',
    review: 'Remote access is still being prepared.',
    danger: 'Remote access is not ready.',
  },
  worker_execution: {
    label: 'Background operations',
    screen: 'home',
    ready: 'Pocket Lab can complete background work.',
    review: 'Background operations are being checked.',
    danger: 'Background operations need attention.',
  },
  app_catalog: {
    label: 'Apps',
    screen: 'catalog',
    ready: 'Your self-hosted apps are available.',
    review: 'App availability is being refreshed.',
    danger: 'Apps need attention before they can be used.',
  },
  identity_access: {
    label: 'Account protection',
    screen: 'identity',
    ready: 'Account and access protection is available.',
    review: 'Account protection is still being prepared.',
    danger: 'Account protection needs attention.',
  },
  device_fleet: {
    label: 'Devices',
    screen: 'devices',
    ready: 'Your known devices are connected to this workspace.',
    review: 'Pocket Lab is checking device connections.',
    danger: 'One or more devices need attention.',
  },
  security: {
    label: 'Safety',
    screen: 'security',
    ready: 'No urgent safety issue is reported.',
    review: 'A safety review is recommended.',
    danger: 'Safety needs immediate attention.',
  },
  policy_compliance: {
    label: 'Protection rules',
    screen: 'rules',
    ready: 'Your protection rules are active.',
    review: 'Some protection rules need review.',
    danger: 'Protection rules need attention.',
  },
  recovery: {
    label: 'Backups and recovery',
    screen: 'recovery',
    ready: 'Backup and restore tools are available.',
    review: 'Backup readiness is being checked.',
    danger: 'Backups or recovery need attention.',
  },
  local_source_store: {
    label: 'Workspace storage',
    screen: 'home',
    ready: 'Local workspace storage is available.',
    review: 'Workspace storage is being checked.',
    danger: 'Workspace storage needs attention.',
  },
  database: {
    label: 'Pocket Lab data',
    screen: 'recovery',
    ready: 'Pocket Lab data services are available.',
    review: 'Pocket Lab data services are being checked.',
    danger: 'Pocket Lab data services need attention.',
  },
});

const SERVICE_KEY_ALIASES = Object.freeze({
  identity_and_access: 'identity_access',
  policy_and_compliance: 'policy_compliance',
});

const HOME_SERVICE_PRIORITY = Object.freeze([
  'app_catalog',
  'device_fleet',
  'security',
  'recovery',
  'remote_access',
  'identity_access',
  'control_api',
  'worker_execution',
  'command_bus',
  'policy_compliance',
  'database',
  'local_source_store',
]);

function normalizedKey(value = '') {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/&/g, 'and')
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '');
}

function normalizedStatus(value = '') {
  return normalizedKey(value || 'unknown');
}

export function homeStatusTone(value = '') {
  const status = normalizedStatus(value);
  if (READY_STATES.has(status)) return 'ready';
  if (DANGER_STATES.has(status)) return 'danger';
  if (REVIEW_STATES.has(status)) return 'review';
  return 'review';
}

export function homeServicePresentation(service = {}) {
  const rawKey = normalizedKey(service.name || service.id || 'workspace_area');
  const key = SERVICE_KEY_ALIASES[rawKey] || rawKey;
  const definition = SERVICE_PRESENTATION[key] || {
    label: String(service.name || 'Workspace area').replace(/\s+/g, ' ').trim(),
    screen: 'home',
    ready: 'This area is ready.',
    review: 'Pocket Lab is checking this area.',
    danger: 'This area needs attention.',
  };
  const tone = homeStatusTone(service.status);
  return {
    key,
    label: definition.label,
    screen: definition.screen,
    tone,
    statusLabel: tone === 'ready' ? 'Ready' : tone === 'danger' ? 'Needs attention' : 'Review',
    summary: definition[tone],
  };
}

function boundedCount(value) {
  const parsed = Number(value || 0);
  if (!Number.isFinite(parsed)) return 0;
  return Math.max(0, Math.min(999, Math.round(parsed)));
}

function resourceMetric({ key, label, value, unit = '', thresholds = null, note }) {
  const parsed = Number(value);
  const known = Number.isFinite(parsed);
  let tone = 'neutral';
  if (known && thresholds) {
    if (thresholds.direction === 'high') {
      tone = parsed >= thresholds.danger ? 'danger' : parsed >= thresholds.review ? 'review' : 'ready';
    } else {
      tone = parsed <= thresholds.danger ? 'danger' : parsed <= thresholds.review ? 'review' : 'ready';
    }
  }
  return {
    key,
    label,
    value: known ? `${Math.round(parsed)}${unit}` : 'Not available',
    tone,
    note,
  };
}

export function buildLiteHomeOverview(status = {}, options = {}) {
  const summary = status.summary || {};
  const telemetry = status.telemetry || {};
  const savedStateOnly = Boolean(options.savedStateOnly);
  const backendReachable = options.backendReachable !== false;
  const services = (Array.isArray(status.services) ? status.services : [])
    .map(homeServicePresentation)
    .sort((a, b) => {
      const aIndex = HOME_SERVICE_PRIORITY.indexOf(a.key);
      const bIndex = HOME_SERVICE_PRIORITY.indexOf(b.key);
      return (aIndex < 0 ? 99 : aIndex) - (bIndex < 0 ? 99 : bIndex);
    });

  const readyCount = services.filter((item) => item.tone === 'ready').length;
  const attentionCount = services.filter((item) => item.tone !== 'ready').length;
  const totalCount = services.length;
  const apps = boundedCount(summary.apps_available);
  const devices = boundedCount(summary.devices_known);
  const safetyItems = boundedCount(summary.security_findings);
  const deviceHealthAttention = boundedCount(summary.device_health_attention);
  const remoteReady = summary.remote_access_ready === true;
  const overallTone = savedStateOnly || !backendReachable ? 'review' : homeStatusTone(status.overall);

  let nextAction = {
    screen: 'catalog',
    label: apps ? 'Open Apps' : 'Browse Apps',
    title: apps ? 'Continue with your apps' : 'Add your first self-hosted app',
    detail: apps
      ? `${apps} ${apps === 1 ? 'app is' : 'apps are'} ready to open or manage.`
      : 'Choose a self-hosted app when you are ready to expand this workspace.',
    tone: 'primary',
  };

  if (savedStateOnly || !backendReachable) {
    nextAction = {
      screen: 'home',
      label: 'Refresh status',
      title: 'Reconnect for current information',
      detail: 'Saved information remains visible. Actions stay protected until Pocket Lab reconnects.',
      tone: 'review',
    };
  } else if (safetyItems > 0) {
    nextAction = {
      screen: 'security',
      label: 'Review Safety',
      title: 'Review the latest safety items',
      detail: `${safetyItems} ${safetyItems === 1 ? 'item needs' : 'items need'} your attention.`,
      tone: 'review',
    };
  } else if (deviceHealthAttention > 0) {
    nextAction = {
      screen: 'devices',
      label: 'Review device',
      title: `${deviceHealthAttention} device health ${deviceHealthAttention === 1 ? 'item needs' : 'items need'} attention`,
      detail: 'Open Devices to review the backend-prepared health summary and safest next step.',
      tone: 'review',
    };
  } else if (devices === 0) {
    nextAction = {
      screen: 'devices',
      label: 'Add Device',
      title: 'Connect another device',
      detail: 'Add an app or storage device when you want this workspace to do more.',
      tone: 'primary',
    };
  } else if (!remoteReady) {
    nextAction = {
      screen: 'devices',
      label: 'Review Access',
      title: 'Finish private remote access',
      detail: 'Local use is available, but private remote access is not ready yet.',
      tone: 'review',
    };
  }

  const heroTitle = savedStateOnly || !backendReachable
    ? 'Your workspace is available with saved information'
    : overallTone === 'ready'
      ? 'Your self-hosted workspace is ready'
      : overallTone === 'danger'
        ? 'Your workspace needs attention'
        : 'A few areas need your attention';

  const heroSummary = savedStateOnly || !backendReachable
    ? 'Review the latest saved overview while Pocket Lab reconnects. Protected actions remain unavailable until fresh information returns.'
    : overallTone === 'ready'
      ? 'Open apps, connect devices, review safety, and keep a verified backup from one private workspace.'
      : 'Pocket Lab is still usable. Review the recommended next step before making important changes.';

  return {
    overallTone,
    heroTitle,
    heroSummary,
    readyCount,
    attentionCount,
    totalCount,
    nextAction,
    services: services.slice(0, 8),
    stats: [
      { key: 'apps', label: 'Apps', value: apps, note: apps === 1 ? 'self-hosted app available' : 'self-hosted apps available', screen: 'catalog' },
      { key: 'devices', label: 'Devices', value: devices, note: deviceHealthAttention ? `${deviceHealthAttention} health item${deviceHealthAttention === 1 ? '' : 's'} to review` : devices === 1 ? 'device connected to this workspace' : 'devices connected to this workspace', screen: 'devices' },
      { key: 'safety', label: 'Safety', value: safetyItems, note: safetyItems ? 'items ready for review' : 'no urgent items reported', screen: 'security' },
      { key: 'access', label: 'Remote access', value: remoteReady ? 'Ready' : 'Not ready', note: remoteReady ? 'private access is available' : 'local access remains available', screen: 'devices' },
    ],
    resources: [
      resourceMetric({ key: 'processor', label: 'Processor use', value: telemetry.cpu_usage_percent, unit: '%', thresholds: { direction: 'high', review: 75, danger: 92 }, note: 'Current workspace demand' }),
      resourceMetric({ key: 'temperature', label: 'Device temperature', value: telemetry.cpu_temp_c, unit: '°C', thresholds: { direction: 'high', review: 58, danger: 72 }, note: 'Current device reading' }),
      resourceMetric({ key: 'storage', label: 'Free storage', value: telemetry.free_space_mb, unit: ' MB', thresholds: { direction: 'low', review: 2048, danger: 512 }, note: 'Space available for apps and backups' }),
      resourceMetric({ key: 'memory', label: 'Memory use', value: telemetry.memory_usage_mb, unit: ' MB', note: 'Memory used by Pocket Lab services' }),
    ],
  };
}

export const LITE_HOME_PRESENTATION_IS_UI_ONLY = true;
export const LITE_HOME_PRESENTATION_DOES_NOT_STORE_SERVER_STATE = true;

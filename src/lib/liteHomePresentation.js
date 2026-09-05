import { normalizeDeviceFacts, resourceFactValue } from './liteDeviceFacts.js';
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

function semanticResourceMetric({ key, label, status = 'unknown', summary = '', screen = 'home' }) {
  const normalized = normalizedStatus(status);
  const tone = READY_STATES.has(normalized) || normalized === 'normal' || normalized === 'healthy'
    ? 'ready'
    : DANGER_STATES.has(normalized) || ['critical', 'read_only', 'recovery_required', 'unavailable'].includes(normalized)
      ? 'danger'
      : 'review';
  const value = tone === 'ready'
    ? 'Looks good'
    : tone === 'danger'
      ? 'Needs attention'
      : normalized === 'unknown' || normalized === 'unsupported'
        ? 'Not available'
        : 'Review';
  return { key, label, value, tone, note: String(summary || '').slice(0, 160), screen };
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

function finiteNumber(value) {
  if (value === null || value === undefined || value === '') return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : null;
}

function formatCapacityMb(value) {
  const parsed = finiteNumber(value);
  if (parsed === null) return 'Not available';
  if (parsed >= 1024) {
    const gib = parsed / 1024;
    return `${gib >= 100 ? Math.round(gib) : gib.toFixed(1)} GiB`;
  }
  return `${Math.round(parsed)} MB`;
}

function worstTone(...tones) {
  if (tones.includes('danger')) return 'danger';
  if (tones.includes('review')) return 'review';
  if (tones.includes('ready')) return 'ready';
  return 'neutral';
}

function highUsageTone(value, review, danger) {
  const parsed = finiteNumber(value);
  if (parsed === null) return 'neutral';
  if (parsed >= danger) return 'danger';
  if (parsed >= review) return 'review';
  return 'ready';
}

function lowAvailabilityTone(free, total, reviewPercent, dangerPercent) {
  const freeValue = finiteNumber(free);
  const totalValue = finiteNumber(total);
  if (freeValue === null || totalValue === null || totalValue <= 0) return 'neutral';
  const percent = (freeValue / totalValue) * 100;
  if (percent <= dangerPercent) return 'danger';
  if (percent <= reviewPercent) return 'review';
  return 'ready';
}

export function buildLiteHomeOverview(status = {}, options = {}) {
  const summary = status.summary || {};
  const telemetry = status.telemetry || {};
  const systemCurrentState = status.system_current_state || {};
  const telemetryThresholds = systemCurrentState.telemetry_thresholds || {};
  const storagePressure = systemCurrentState.storage_pressure || {};
  const sqliteHealth = systemCurrentState.sqlite_health || {};
  const activitySummary = systemCurrentState.activity_summary || {};
  const savedStateOnly = Boolean(options.savedStateOnly);
  const backendReachable = options.backendReachable !== false;
  const lastUpdatedLabel = String(options.lastUpdatedLabel || '').trim();
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
  const overallState = normalizedStatus(status.overall);
  const overallKnown = Boolean(status.overall) && overallState !== 'unknown';
  const overallTone = savedStateOnly || !backendReachable ? 'review' : overallKnown ? homeStatusTone(status.overall) : 'unknown';

  let nextAction = null;

  if (savedStateOnly || !backendReachable) {
    nextAction = {
      screen: 'home',
      label: 'Refresh status',
      title: 'Reconnect for current information',
      detail: 'Saved information remains visible. Actions stay protected until Pocket Lab reconnects.',
      tone: 'review',
    };
  } else if (!overallKnown) {
    nextAction = null;
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
  } else if (apps === 0) {
    nextAction = {
      screen: 'catalog',
      label: 'Browse Apps',
      title: 'Add a self-hosted app when you are ready',
      detail: 'No app is currently available from this workspace overview.',
      tone: 'primary',
    };
  } else {
    const attentionService = services.find((item) => item.tone !== 'ready' && item.screen && item.screen !== 'home');
    if (attentionService) {
      nextAction = {
        screen: attentionService.screen,
        label: `Review ${attentionService.label}`,
        title: `${attentionService.label} needs attention`,
        detail: attentionService.summary,
        tone: attentionService.tone,
      };
    }
  }

  const heroTitle = savedStateOnly || !backendReachable
    ? 'Your workspace is available with saved information'
    : !overallKnown
      ? 'Workspace status is not confirmed yet'
    : overallTone === 'ready'
      ? 'Your self-hosted workspace is ready'
      : overallTone === 'danger'
        ? 'Your workspace needs attention'
        : 'A few areas need your attention';

  const heroSummary = savedStateOnly || !backendReachable
    ? 'Review the latest saved overview while Pocket Lab reconnects. Protected actions remain unavailable until fresh information returns.'
    : !overallKnown
      ? 'Pocket Lab has not reported a current workspace state. Check again when current information is available.'
    : overallTone === 'ready'
      ? 'Open apps, connect devices, review safety, and keep a verified backup from one private workspace.'
      : 'Pocket Lab is still usable. Review the recommended next step before making important changes.';

  const hasProjection = (value) => value && typeof value === 'object' && Object.keys(value).length > 0;
  const healthSummary = summary.device_health_summary || {};
  const healthyDevices = boundedCount(healthSummary.by_status?.healthy);
  const healthSummaryCurrent = summary.device_health_attention_current === true;
  const deviceFacts = normalizeDeviceFacts(status.device_facts || {}, { telemetry });

  const memoryTotalMb = resourceFactValue(deviceFacts, 'memory', 'total_mb');
  const memoryFreeMb = resourceFactValue(deviceFacts, 'memory', 'free_mb');
  const memoryUsedMb = resourceFactValue(deviceFacts, 'memory', 'used_mb');
  const derivedMemoryFreeMb = memoryFreeMb ?? (memoryTotalMb !== null && memoryUsedMb !== null
    ? Math.max(0, memoryTotalMb - memoryUsedMb)
    : null);
  const cpuUsage = resourceFactValue(deviceFacts, 'cpu_usage', 'usage_percent');
  const cpuTemp = resourceFactValue(deviceFacts, 'temperature', 'celsius');
  const semanticHealthTone = hasProjection(telemetryThresholds)
    ? semanticResourceMetric({ key: 'device-health', label: 'Device health', status: telemetryThresholds.status }).tone
    : healthSummaryCurrent
      ? deviceHealthAttention > 0 ? 'review' : 'ready'
      : 'neutral';
  const deviceHealthTone = worstTone(
    semanticHealthTone,
    highUsageTone(cpuUsage, 75, 90),
    highUsageTone(cpuTemp, 55, 70),
    lowAvailabilityTone(derivedMemoryFreeMb, memoryTotalMb, 20, 10),
  );
  const memoryKnown = memoryTotalMb !== null && derivedMemoryFreeMb !== null && memoryTotalMb > 0;
  const cpuParts = [
    cpuUsage !== null ? `CPU ${Math.round(cpuUsage)}%` : '',
    cpuTemp !== null ? `${Math.round(cpuTemp)}°C` : '',
  ].filter(Boolean);
  const deviceHealthResource = memoryKnown
    ? {
        key: 'device-health',
        label: 'Memory and CPU',
        value: `${formatCapacityMb(derivedMemoryFreeMb)} free / ${formatCapacityMb(memoryTotalMb)}`,
        tone: deviceHealthTone,
        note: cpuParts.length ? cpuParts.join(' · ') : 'CPU information has not been reported yet.',
        screen: 'devices',
      }
    : hasProjection(telemetryThresholds)
      ? semanticResourceMetric({ key: 'device-health', label: 'Device health', status: telemetryThresholds.status, summary: telemetryThresholds.summary, screen: 'devices' })
      : healthSummaryCurrent
        ? {
            key: 'device-health',
            label: 'Device health',
            value: deviceHealthAttention > 0 ? 'Review' : 'Healthy',
            tone: deviceHealthAttention > 0 ? 'review' : 'ready',
            note: deviceHealthAttention > 0
              ? `${deviceHealthAttention} health ${deviceHealthAttention === 1 ? 'item needs' : 'items need'} attention.`
              : healthyDevices > 0 ? `${healthyDevices} ${healthyDevices === 1 ? 'device is' : 'devices are'} healthy.` : 'No current device health issue is reported.',
            screen: 'devices',
          }
        : resourceMetric({ key: 'device-health', label: 'Device health', value: Number.NaN, note: 'Health information has not been reported yet' });

  const freeSpaceMb = resourceFactValue(deviceFacts, 'storage', 'free_mb');
  const totalSpaceMb = resourceFactValue(deviceFacts, 'storage', 'total_mb');
  const storageKnown = freeSpaceMb !== null && totalSpaceMb !== null && totalSpaceMb > 0;
  const storagePercent = storageKnown ? Math.max(0, Math.min(100, (freeSpaceMb / totalSpaceMb) * 100)) : null;
  const semanticStorageTone = hasProjection(storagePressure)
    ? semanticResourceMetric({ key: 'storage', label: 'Storage', status: storagePressure.status }).tone
    : 'neutral';
  const storageTone = worstTone(semanticStorageTone, lowAvailabilityTone(freeSpaceMb, totalSpaceMb, 15, 5));
  const storageResource = storageKnown
    ? {
        key: 'storage',
        label: 'Storage',
        value: `${formatCapacityMb(freeSpaceMb)} free / ${formatCapacityMb(totalSpaceMb)}`,
        tone: storageTone,
        note: `${Math.round(storagePercent)}% available for apps and backups`,
        screen: 'recovery',
      }
    : hasProjection(storagePressure)
      ? semanticResourceMetric({ key: 'storage', label: 'Storage', status: storagePressure.status, summary: storagePressure.summary, screen: 'recovery' })
      : resourceMetric({ key: 'storage', label: 'Free storage', value: freeSpaceMb, unit: ' MB', thresholds: { direction: 'low', review: 2048, danger: 512 }, note: 'Space available for apps and backups' });

  const databaseResource = hasProjection(sqliteHealth)
    ? semanticResourceMetric({ key: 'database', label: 'Pocket Lab data', status: sqliteHealth.status, summary: sqliteHealth.summary, screen: 'recovery' })
    : semanticResourceMetric({ key: 'database', label: 'Pocket Lab data', status: 'unknown', summary: 'Database health has not been reported yet.', screen: 'recovery' });

  const activityResource = hasProjection(activitySummary)
    ? semanticResourceMetric({ key: 'activity', label: 'Recent activity', status: activitySummary.status, summary: activitySummary.summary, screen: 'home' })
    : semanticResourceMetric({ key: 'activity', label: 'Recent activity', status: 'unknown', summary: 'Activity state has not been reported yet.', screen: 'home' });

  const resources = [deviceHealthResource, storageResource, databaseResource, activityResource];
  const keyAreas = services.filter((item) => ['app_catalog', 'device_fleet', 'security', 'remote_access', 'recovery'].includes(item.key)).slice(0, 5);
  const workspaceStory = savedStateOnly || !backendReachable
    ? {
        state: 'saved',
        tone: 'saved',
        headline: 'Showing saved information',
        summary: heroSummary,
        consequence: 'Current workspace status cannot be confirmed until Pocket Lab reconnects.',
        freshness: lastUpdatedLabel ? { label: 'Saved', detail: lastUpdatedLabel, state: 'stale' } : { label: 'Saved state', state: 'saved' },
      }
    : !overallKnown
      ? {
          state: 'unknown',
          tone: 'unknown',
          headline: heroTitle,
          summary: heroSummary,
          attention: 'No healthy workspace state is assumed while current status is incomplete.',
        }
      : overallTone === 'ready'
        ? {
            state: 'ready',
            tone: 'ready',
            headline: 'Your Pocket Lab is ready',
            summary: 'Apps, devices, and workspace services are available from the latest reported status.',
            consequence: 'No immediate follow-up is required.',
            freshness: lastUpdatedLabel ? { label: 'Current information', detail: lastUpdatedLabel, state: 'live' } : null,
          }
        : {
            state: overallTone === 'danger' ? 'attention' : 'review',
            tone: overallTone === 'danger' ? 'danger' : 'attention',
            headline: heroTitle,
            summary: heroSummary,
            attention: nextAction?.detail || services.find((item) => item.tone !== 'ready')?.summary || 'Review the current workspace areas for more detail.',
            freshness: lastUpdatedLabel ? { label: 'Current information', detail: lastUpdatedLabel, state: 'live' } : null,
          };

  return {
    overallTone,
    heroTitle,
    heroSummary,
    readyCount,
    attentionCount,
    totalCount,
    nextAction,
    workspaceStory,
    keyAreas,
    workspaceDetails: {
      title: 'Workspace details',
      description: 'Capacity, readiness context, and the latest safe workspace information.',
      resources,
      showWorkflow: ['review', 'danger'].includes(overallTone),
      freshness: lastUpdatedLabel || 'Not checked yet',
    },
    services: services.slice(0, 8),
    stats: [
      { key: 'apps', label: 'Apps', value: apps, note: apps === 1 ? 'self-hosted app available' : 'self-hosted apps available', screen: 'catalog' },
      { key: 'devices', label: 'Devices', value: devices, note: deviceHealthAttention ? `${deviceHealthAttention} health item${deviceHealthAttention === 1 ? '' : 's'} to review` : devices === 1 ? 'device connected to this workspace' : 'devices connected to this workspace', screen: 'devices' },
      { key: 'safety', label: 'Safety', value: safetyItems, note: safetyItems ? 'items ready for review' : 'no urgent items reported', screen: 'security' },
      { key: 'access', label: 'Remote access', value: remoteReady ? 'Ready' : 'Not ready', note: remoteReady ? 'private access is available' : 'local access remains available', screen: 'devices' },
    ],
    resources,
  };
}

export const LITE_HOME_PRESENTATION_IS_UI_ONLY = true;
export const LITE_HOME_PRESENTATION_DOES_NOT_STORE_SERVER_STATE = true;

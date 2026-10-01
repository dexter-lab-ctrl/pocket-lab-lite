import {
  deviceResourcePresentation,
  formatDeviceCapacityGb,
  normalizeDeviceFacts,
  resourceFactValue,
} from '../../lib/liteDeviceFacts.js';
import React from 'react';
import { AlertTriangle, Clock3, HeartPulse, Smartphone, X } from 'lucide-react';
import { formatLiteTime, liteApi } from '../../lib/liteApi.js';
import { liteEnterpriseApi } from '../../lib/liteEnterpriseApi.js';
import { liteQueryKeys, liteQueryPaths } from '../../lib/liteQueryClient.js';
import { useLiteQuery } from '../../hooks/useLiteQuery.js';
import { useLiteDeviceHealthReviewFlow } from '../../hooks/useLiteDeviceHealthReviewFlow.js';
import LiteProgressiveDetails from '../components/LiteProgressiveDetails.jsx';
import DevicePhotoBackup from './DevicePhotoBackup.jsx';
import { ResourceMetric, SoftwarePosture } from '../components/DeviceFactsPrimitives.jsx';
import { isLitePerformanceMode } from '../liteNavigationRuntime.js';
import { useLiteUiStore } from '../../stores/liteUiStore.js';
import { triggerLiteTactileFeedback } from '../LiteMotion.jsx';
import { LiteHistoryTimeline } from '../LiteUx.jsx';
import {
  LiteButton,
  backendBadgeStatus,
  deviceCapabilityLabels,
  deviceCapabilitySummary,
  deviceCommandDeliveryLabel,
  deviceRestartAssessment,
  deviceRuntimeServices,
  canonicalDevicePresentation,
  deviceConnectionLabel,
  deviceLinkState,
  deviceStatusLabel,
  normalizeBackendState,
  roleLabel,
  deviceRoleSummary,
  DEVICE_ROLE_OPTIONS,
} from '../LiteUi.jsx';

const DEVICE_DETAILS_USES_PROGRESSIVE_FOUNDATION = true;
const DEVICE_DETAILS_HISTORY_IS_LAZY = true;
const DEVICE_DETAILS_BACKEND_EVIDENCE_BOUNDARY = 'normal Devices details do not fetch backend evidence endpoints';
const DEVICE_DETAILS_TECHNICAL_DETAILS_COLLAPSED = true;
const DEVICE_HEALTH_HISTORY_PROGRESSIVE_DISCLOSURE_D4 = true;
const DEVICE_HEALTH_RECOMMENDATIONS_DO_NOT_EXECUTE_D4 = true;
const DEVICE_DETAILS_NONCRITICAL_DELAY_FRAMES = isLitePerformanceMode() ? 45 : 2;
const DEVICE_AWARENESS_NONCRITICAL_DELAY_FRAMES = isLitePerformanceMode() ? 90 : 2;
void DEVICE_DETAILS_USES_PROGRESSIVE_FOUNDATION;
void DEVICE_DETAILS_HISTORY_IS_LAZY;
void DEVICE_DETAILS_BACKEND_EVIDENCE_BOUNDARY;
void DEVICE_DETAILS_TECHNICAL_DETAILS_COLLAPSED;
void DEVICE_HEALTH_HISTORY_PROGRESSIVE_DISCLOSURE_D4;
void DEVICE_HEALTH_RECOMMENDATIONS_DO_NOT_EXECUTE_D4;

function normalizeStatus(value) {
  return String(value || '').toLowerCase().replace(/[\s-]+/g, '_');
}

function effectiveDeviceStatus(device) {
  return canonicalDevicePresentation(device).state;
}

function formatDeviceTime(value, fallback = 'No report received') {
  return value ? formatLiteTime(value) : fallback;
}

function supervisorStatusLabel(device) {
  const status = normalizeStatus(
    device?.supervisor?.status
      || device?.supervisor_status
      || device?.dependencies?.supervisor_status,
  );

  if (['healthy', 'ready', 'online', 'running'].includes(status)) {
    return 'Running normally';
  }
  if (status === 'repairing') return 'Recovery in progress';
  if (['stopped', 'missing', 'errored', 'error', 'failed'].includes(status)) {
    return 'Needs attention';
  }

  return 'No recovery service status reported';
}

export function capabilityStatusLabel(value, reasonCode = '') {
  const status = normalizeStatus(value);
  const reason = normalizeStatus(reasonCode);

  if (['verified', 'ready'].includes(status)) return 'Verified';
  if (['verification_pending', 'available'].includes(status)) {
    return 'Verification pending';
  }
  if (['unavailable', 'not_ready'].includes(status)) return 'Unavailable';
  if (status === 'unsupported') return 'Unsupported';
  if (status === 'stale') return 'Stale';
  if (status === 'blocked' || status === 'blocked_by_role') return 'Blocked by role';
  if (status === 'not_applicable') return 'Not applicable';
  if (status === 'advertised') return 'Advertised';
  if (
    status === 'not_advertised'
    || reason === 'capability_not_advertised'
  ) return 'Not advertised';
  return 'Unknown';
}

function safeList(items) {
  return (Array.isArray(items) ? items : [])
    .filter(Boolean)
    .map((item) => String(item).trim())
    .filter(Boolean)
    .slice(0, 8);
}

function deviceHistoryItems(device) {
  const candidates = [
    device?.run_history,
    device?.history,
    device?.recent_events,
    device?.events,
    device?.restart_history,
  ].find((items) => Array.isArray(items) && items.length);
  return (Array.isArray(candidates) ? candidates : []).slice(0, 20);
}

function deviceSummary(device) {
  const name = device?.name || device?.hostname || 'This device';
  const connection = deviceConnectionLabel(device);
  if (effectiveDeviceStatus(device) === 'online') return `${name} is online and reporting normally.`;
  if (normalizeStatus(device?.status) === 'repairing' || deviceLinkState(device) === 'repairing') return `${name} is being checked or repaired.`;
  if (normalizeStatus(device?.status) === 'agent_stopped') return `${name} has a device service that needs attention.`;
  if (connection === 'Online') return `${name} is currently online.`;
  if (connection) return `${name} is currently ${connection.toLowerCase()}.`;
  return `${name} details are available.`;
}

function deviceWhatHappened(device) {
  const happened = [
    'Pocket Lab read the latest safe device summary.',
    deviceConnectionLabel(device) === 'Online'
      ? 'The device is currently online and reporting through Pocket Lab.'
      : `The device connection is currently ${deviceConnectionLabel(device).toLowerCase()}.`,
  ];
  const lastSeenAt = (
    device?.last_seen_state?.last_seen_at
    || device?.last_seen_at
    || device?.last_seen
  );
  if (lastSeenAt) {
    happened.push(`The latest device activity was received ${formatLiteTime(lastSeenAt)}.`);
  }

  const supervisorStatus = supervisorStatusLabel(device);
  if (supervisorStatus !== 'No recovery service status reported') {
    happened.push(`Recovery service: ${supervisorStatus}.`);
  }
  return happened;
}

function deviceWhatChanged(device) {
  const changes = safeList(device?.what_changed || device?.changes);
  if (changes.length) return changes;
  return ['Nothing was changed by opening these details.'];
}

function deviceWhatDidNotHappen() {
  return [
    'No action was sent to this device.',
    'No device-service restart was started.',
    'No device record was removed.',
    'No secrets, raw logs, or private paths were loaded into this view.',
  ];
}

function deviceAttention(device) {
  const status = normalizeStatus(device?.status || device?.connection || device?.state);
  const attention = [];
  if (['offline', 'agent_stopped', 'unhealthy', 'failed', 'needs_attention'].includes(status)) {
    attention.push('This device may need a restart or local recovery check.');
  }
  if (deviceLinkState(device) === 'repairing') attention.push('Pocket Lab is still checking the device connection.');
  if (device?.remote_access?.ready === false) attention.push('Remote access is not ready yet.');
  (Array.isArray(device?.proactive_health?.attention_items)
    ? device.proactive_health.attention_items
    : [])
    .slice(0, 4)
    .forEach((item) => {
      const summary = String(item?.summary || '').trim();
      if (summary && !attention.includes(summary)) attention.push(summary);
    });
  return attention;
}

function proactiveHealthLabel(value) {
  const status = normalizeStatus(value || 'unknown');
  return ({
    healthy: 'Healthy',
    watch: 'Watch',
    needs_attention: 'Needs attention',
    degraded: 'Degraded',
    repairing: 'Repairing',
    unreachable: 'Unreachable',
    unknown: 'Health pending',
  })[status] || 'Health pending';
}

function recommendationLabel(value) {
  const action = normalizeStatus(value || 'none');
  return ({
    none: 'No action needed',
    review_device: 'Review device',
    review_storage: 'Review storage',
    wait_for_recovery: 'Wait for recovery',
    update_agent: 'Review software update',
    open_app: 'Open affected app',
    open_backup_restore: 'Open Backup & Restore',
    review_identity: 'Review identity',
  })[action] || titleCase(action, 'Review device');
}

function recommendationScreen(value) {
  const action = normalizeStatus(value || 'none');
  return ({
    open_app: 'catalog',
    open_backup_restore: 'recovery',
    review_identity: 'identity',
    open_remote_access_health: 'devices',
    review_storage: 'devices',
    review_device: 'devices',
    restart_agent: 'devices',
    update_agent: 'devices',
    wait_for_recovery: 'devices',
    remove_old_device: 'devices',
  })[action] || '';
}

function metricTone(percent, { watch = 75, attention = 90 } = {}) {
  if (percent === null || percent === undefined || !Number.isFinite(Number(percent))) return 'unknown';
  const value = Number(percent);
  if (value >= attention) return 'attention';
  if (value >= watch) return 'watch';
  return 'healthy';
}

function temperatureMeter(celsius) {
  const value = Number(celsius);
  if (!Number.isFinite(value)) return { percent: null, tone: 'unknown' };
  const percent = Math.max(0, Math.min(100, (value / 80) * 100));
  const tone = value >= 60 ? 'attention' : value >= 45 ? 'watch' : 'healthy';
  return { percent, tone };
}

function resourceHealthLabel(status, hasMeasurement) {
  const normalized = normalizeStatus(status || '');
  if (['healthy', 'normal', 'ok', 'ready'].includes(normalized)) return 'Healthy';
  if (['watch', 'warning', 'degraded'].includes(normalized)) return 'Watch';
  if (['needs_attention', 'critical', 'failed', 'unhealthy'].includes(normalized)) return 'Needs attention';
  if (['unsupported', 'not_applicable'].includes(normalized)) return titleCase(normalized);
  if (['stale'].includes(normalized)) return 'Stale';
  return hasMeasurement ? 'Measured' : 'Not reported';
}

function healthResourceRows(health = {}, device = {}) {
  const facts = normalizeDeviceFacts(
    device?.device_facts || health?.device_facts || device,
    { health },
  );
  const resources = health?.resources || {};
  const factValue = (metric, key, fallback = null) => {
    const value = resourceFactValue(facts, metric, key);
    if (value !== null) return value;
    if (fallback === null || fallback === undefined || fallback === '') return null;
    const parsedFallback = Number(fallback);
    return Number.isFinite(parsedFallback) ? parsedFallback : null;
  };
  const boundedPercent = (value) => {
    const parsed = Number(value);
    return Number.isFinite(parsed) && parsed >= 0 && parsed <= 100 ? parsed : null;
  };

  const storageFree = factValue('storage', 'free_mb');
  const storageTotal = factValue('storage', 'total_mb');
  const storageUsedPercent = storageFree !== null && storageTotal > 0 && storageFree <= storageTotal
    ? ((storageTotal - storageFree) / storageTotal) * 100
    : null;

  const memoryFree = factValue('memory', 'free_mb');
  const memoryTotal = factValue('memory', 'total_mb');
  const memoryUsedPercent = memoryFree !== null && memoryTotal > 0 && memoryFree <= memoryTotal
    ? ((memoryTotal - memoryFree) / memoryTotal) * 100
    : null;

  const cpuPercent = boundedPercent(
    factValue(
      'pocketlab_workload_cpu',
      'usage_percent',
      factValue('cpu_usage', 'usage_percent', resources.load?.usage_percent),
    ),
  );
  const processCount = factValue('pocketlab_workload_cpu', 'process_count', resources.load?.process_count);
  const temperature = factValue('temperature', 'celsius', resources.temperature?.celsius);
  const temperatureVisual = temperatureMeter(temperature);

  const definitions = [
    {
      label: 'Storage',
      metric: 'storage',
      healthValue: resources.storage,
      primaryValue: storageFree !== null ? `${formatDeviceCapacityGb(storageFree)} free` : null,
      secondaryValue: storageTotal !== null ? `${formatDeviceCapacityGb(storageTotal)} total` : '',
      meterPercent: storageUsedPercent,
      meterTone: metricTone(storageUsedPercent, { watch: 75, attention: 90 }),
      meterLabel: 'Storage used',
    },
    {
      label: 'Memory',
      metric: 'memory',
      healthValue: resources.memory,
      primaryValue: memoryFree !== null ? `${formatDeviceCapacityGb(memoryFree)} free` : null,
      secondaryValue: memoryTotal !== null ? `${formatDeviceCapacityGb(memoryTotal)} total` : '',
      meterPercent: memoryUsedPercent,
      meterTone: metricTone(memoryUsedPercent, { watch: 75, attention: 90 }),
      meterLabel: 'Memory used',
    },
    {
      label: 'Pocket Lab CPU',
      metric: 'pocketlab_workload_cpu',
      healthValue: resources.load,
      primaryValue: cpuPercent !== null ? `${Math.round(cpuPercent)}%` : null,
      secondaryValue: processCount !== null
        ? `${Math.round(processCount)} Pocket Lab service process${Math.round(processCount) === 1 ? '' : 'es'}`
        : '',
      meterPercent: cpuPercent,
      meterTone: metricTone(cpuPercent, { watch: 60, attention: 80 }),
      meterLabel: 'Pocket Lab CPU usage',
    },
    {
      label: 'Temperature',
      metric: 'temperature',
      healthValue: resources.temperature,
      primaryValue: temperature !== null ? `${Math.round(temperature)} °C` : null,
      secondaryValue: temperature !== null ? 'Current thermal reading' : '',
      meterPercent: temperatureVisual.percent,
      meterTone: temperatureVisual.tone,
      meterLabel: 'Temperature on a 0 to 80 °C display scale',
    },
  ];

  return definitions.map((definition) => {
    const presentation = deviceResourcePresentation(facts, definition.metric, definition.healthValue);
    const hasMeasurement = Boolean(definition.primaryValue);
    const statusLabel = resourceHealthLabel(presentation.healthStatus, hasMeasurement);
    return {
      label: definition.label,
      status: normalizeStatus(presentation.healthStatus || definition.meterTone || presentation.observationStatus || 'unknown'),
      statusLabel,
      primaryValue: definition.primaryValue || presentation.availabilityLabel,
      secondaryValue: definition.secondaryValue,
      metric: definition.primaryValue || presentation.availabilityLabel,
      summary: presentation.healthSummary || '',
      observationStatus: presentation.observationStatus,
      freshness: presentation.freshness,
      source: presentation.source,
      reasonCode: presentation.reasonCode,
      observedAt: presentation.observedAt,
      meterPercent: definition.meterPercent,
      meterTone: definition.meterTone,
      meterLabel: definition.meterLabel,
    };
  });
}

function healthHistoryItems(payload = {}) {
  return (Array.isArray(payload?.items) ? payload.items : []).slice(0, 20).map((item) => ({
    id: item.event_id,
    title: normalizeStatus(item.previous_state) === normalizeStatus(item.new_state)
      ? `${proactiveHealthLabel(item.new_state)} updated`
      : `${proactiveHealthLabel(item.previous_state)} → ${proactiveHealthLabel(item.new_state)}`,
    summary: item.summary || (item.reason_code ? titleCase(item.reason_code) : 'Device health changed.'),
    status: item.new_state || 'recorded',
    created_at: item.occurred_at,
    reason_code: item.reason_code || '',
  }));
}

function deviceHistoryTimelineItems(items = []) {
  const eventTitles = {
    device_online: 'Device returned online',
    online: 'Device returned online',
    device_offline: 'Device connection was lost',
    offline: 'Device connection was lost',
    connection_lost: 'Device connection was lost',
    connection_restored: 'Device returned online',
    agent_stopped: 'Device service stopped',
    restart_requested: 'Device service restart requested',
    restart_completed: 'Device service restart completed',
    repairing: 'Device recovery started',
    repair_started: 'Device recovery started',
    repair_completed: 'Device recovery completed',
    supervisor_recovery: 'Recovery service restored the device service',
    invite_accepted: 'Device invite accepted',
    device_joined: 'Device joined Pocket Lab',
    remote_access_ready: 'Remote access became ready',
    remote_access_not_ready: 'Remote access needs attention',
  };
  return (Array.isArray(items) ? items : []).slice(0, 20).map((item, index) => {
    const type = normalizeStatus(item?.event_type || item?.type || item?.event || item?.status || item?.reason_code || 'recorded');
    const rawTitle = String(item?.title || item?.label || '').trim();
    const rawSummary = String(item?.summary || item?.message || item?.detail || '').trim();
    const title = rawTitle || eventTitles[type] || titleCase(type, 'Device activity');
    const summary = rawSummary && rawSummary !== title
      ? rawSummary
      : item?.reason_code && normalizeStatus(item.reason_code) !== type
        ? titleCase(item.reason_code)
        : '';
    const createdAt = item?.occurred_at || item?.created_at || item?.updated_at || item?.timestamp || item?.completed_at || item?.started_at || '';
    return {
      id: item?.event_id || item?.id || `${createdAt || 'event'}:${type}:${index}`,
      title,
      summary,
      time: createdAt ? formatLiteTime(createdAt) : '',
      state: type,
    };
  });
}

function technicalRows(device) {
  const facts = normalizeDeviceFacts(device?.device_facts || device);
  const agentSoftware = facts.software?.node_agent || {};
  const supervisorSoftware = facts.software?.supervisor || {};
  return [
    { label: 'Device id', value: device?.id },
    { label: 'Roles', value: deviceRoleSummary(device) },
    { label: 'Status', value: deviceStatusLabel(effectiveDeviceStatus(device)) },
    { label: 'Connection', value: deviceConnectionLabel(device) },
    {
      label: 'Badge state',
      value: titleCase(
        device?.proactive_health?.status
          || device?.health_status
          || backendBadgeStatus(effectiveDeviceStatus(device)),
        'Status pending',
      ),
    },
    {
      label: 'Last seen',
      value: formatDeviceTime(
        device?.last_seen_state?.last_seen_at
          || device?.last_seen_at
          || device?.last_seen,
      ),
    },
    { label: 'Recovery service', value: supervisorStatusLabel(device) },
    { label: 'Capabilities', value: deviceCapabilityLabels(device).join(', ') },
    { label: 'OS family', value: device?.system_profile?.os_family },
    { label: 'Operating system', value: [device?.system_profile?.os_name, device?.system_profile?.os_version].filter(Boolean).join(' ') },
    { label: 'Android API', value: device?.system_profile?.android_api_level },
    { label: 'Security patch', value: device?.system_profile?.security_patch },
    { label: 'Manufacturer', value: titleCase(device?.system_profile?.manufacturer, '') },
    { label: 'Technical model', value: device?.system_profile?.technical_model },
    { label: 'Friendly model', value: device?.system_profile?.consumer_model_name || 'Using detected technical model' },
    { label: 'Internal codename', value: device?.system_profile?.device_codename },
    { label: 'Architecture', value: device?.system_profile?.architecture },
    { label: 'Android ABI', value: device?.system_profile?.android_abi },
    { label: 'Kernel', value: device?.system_profile?.kernel },
    { label: 'Runtime', value: device?.system_profile?.runtime_type },
    { label: 'Termux', value: device?.system_profile?.termux_version },
    { label: 'Python', value: device?.system_profile?.python_version },
    { label: 'Device service version', value: agentSoftware.version || device?.system_profile?.agent_version },
    { label: 'Device service version freshness', value: agentSoftware.version ? titleCase(agentSoftware.freshness, 'Unknown') : '' },
    { label: 'Recovery service version', value: supervisorSoftware.version || device?.system_profile?.supervisor_version },
    { label: 'Recovery service version freshness', value: supervisorSoftware.version ? titleCase(supervisorSoftware.freshness, 'Unknown') : '' },
    { label: 'Uptime', value: device?.system_health?.uptime_label },
    { label: 'System load', value: device?.system_health?.load_status ? device.system_health.load_status.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase()) : '' },
    { label: 'Load average', value: Array.isArray(device?.system_health?.load_average) ? device.system_health.load_average.filter((value) => value !== null).join(' / ') : '' },
    { label: 'Profile status', value: device?.system_profile?.collection_status },
    { label: 'Profile freshness', value: device?.system_profile?.freshness },
    { label: 'Profile checked', value: formatLiteTime(device?.system_profile?.collected_at) },
    device?.storage ? { label: 'Storage', value: device.storage.ready ? 'Ready' : 'Not ready' } : null,
  ].filter((row) => row && row.value);
}

function titleCase(value, fallback = 'Unknown') {
  const valueText = String(value || '').replace(/_/g, ' ').trim();
  return valueText ? valueText.replace(/\b\w/g, (letter) => letter.toUpperCase()) : fallback;
}

function capabilityRows(device) {
  const source = Array.isArray(device?.capability_states) ? device.capability_states : device?.capabilities;
  return (Array.isArray(source) ? source : []).slice(0, 16).map((item) => {
    if (item && typeof item === 'object') return item;
    return { id: String(item || ''), label: titleCase(item), status: 'unknown' };
  }).filter((item) => item.id);
}

function trustSummary(device) {
  const identity = device?.identity || {};
  const enrollment = device?.enrollment || {};
  return [
    { label: 'Identity', value: titleCase(identity.status || device?.identity_status, 'Identity check pending') },
    { label: 'Joined', value: formatLiteTime(enrollment.enrolled_at || enrollment.first_heartbeat_at) },
    { label: 'Invite accepted', value: formatLiteTime(enrollment.invite_accepted_at) },
    { label: 'Blocked joins', value: String(identity.blocked_join_count || 0) },
  ];
}

function DeviceRoleManager({ device, onChanged }) {
  const initialRoles = React.useMemo(() => {
    const preferred = Array.isArray(device?.desired_device_roles) && device.desired_device_roles.length
      ? device.desired_device_roles
      : Array.isArray(device?.device_role_ids) && device.device_role_ids.length
        ? device.device_role_ids
        : device?.role && device.role !== 'server_host' ? [device.role] : [];
    return preferred.filter((role) => ['compute', 'storage'].includes(role)).slice(0, 2);
  }, [device?.desired_device_roles, device?.device_role_ids, device?.role]);
  const [draftRoles, setDraftRoles] = React.useState(initialRoles);
  const [confirming, setConfirming] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  const [result, setResult] = React.useState(null);
  const [access, setAccess] = React.useState(null);

  React.useEffect(() => {
    setDraftRoles(initialRoles);
    setConfirming(false);
  }, [initialRoles.join(',')]);
  React.useEffect(() => {
    let active = true;
    liteEnterpriseApi.access().then((payload) => { if (active) setAccess(payload); }).catch(() => { if (active) setAccess(null); });
    return () => { active = false; };
  }, []);

  const currentHumanRole = access?.current_membership?.role || access?.current_role || access?.role?.id || '';
  const storagePresenceChanges = initialRoles.includes('storage') !== draftRoles.includes('storage');
  const matrixAction = storagePresenceChanges ? 'device.roles.assign.storage' : 'device.roles.assign.compute';
  const matrixRow = (access?.action_matrix || []).find((row) => row.action_id === matrixAction);
  const authorityMode = currentHumanRole && matrixRow?.roles ? matrixRow.roles[currentHumanRole] : '';
  const authorityLabel = authorityMode === 'approval'
    ? 'Review required'
    : authorityMode === 'deny'
      ? 'Not allowed'
      : authorityMode === 'step_up'
        ? 'Passkey confirmation'
        : authorityMode === 'allow'
          ? 'Direct'
          : 'Server will check';
  const changed = initialRoles.join(',') !== draftRoles.join(',');

  function toggleRole(role) {
    const checked = draftRoles.includes(role);
    const next = checked
      ? draftRoles.filter((item) => item !== role)
      : [...draftRoles, role].sort((left, right) => (left === 'compute' ? -1 : right === 'compute' ? 1 : left.localeCompare(right)));
    if (!next.length) return;
    setDraftRoles(next);
    setConfirming(false);
    setResult(null);
  }

  async function applyRoles() {
    if (!changed || authorityMode === 'deny') return;
    if (!confirming) {
      setConfirming(true);
      return;
    }
    setBusy(true);
    setResult(null);
    try {
      const payload = await liteApi.changeDeviceRoles(device?.id || device?.node_id, {
        device_roles: draftRoles,
        confirm: true,
        expected_generation: Number(device?.device_role_generation || 0),
      });
      setResult({ tone: 'ready', message: payload?.summary || 'Role change sent for verification.' });
      setConfirming(false);
      onChanged?.();
    } catch (error) {
      const detail = error?.payload?.detail || {};
      setResult({
        tone: detail?.reason_code === 'device_role_change_requires_approval' || detail?.reason_code === 'approval_required' ? 'review' : 'critical',
        message: detail?.message || detail?.summary || error?.message || 'Pocket Lab could not change these roles.',
      });
      setConfirming(false);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="lite-device-awareness-section" aria-label="Device roles">
      <span>Responsibilities</span>
      <strong>{deviceRoleSummary(device)}</strong>
      <p>Roles authorize what this device may do. Capabilities below still have to be reported, verified, fresh, and allowed by current Safety Rules.</p>
      <div className="lite-role-selector" role="group" aria-label="Change device roles">
        {DEVICE_ROLE_OPTIONS.map((role) => {
          const checked = draftRoles.includes(role.value);
          return (
            <label key={role.value} className={`lite-role-card ${checked ? 'lite-role-card-selected' : ''}`}>
              <input type="checkbox" checked={checked} onChange={() => toggleRole(role.value)} disabled={busy} />
              <span><strong>{role.label}</strong><span>{role.description}</span></span>
            </label>
          );
        })}
      </div>
      <p role="note"><strong>Access check: {authorityLabel}.</strong> Pocket Lab re-checks this on the server before applying any role change.</p>
      <p role="note">Photo Backup source is a separate device capability. Sending photos to Pocket Lab does not make this device a Storage node.</p>
      {confirming ? <p role="alert">Confirm the exact role set: {draftRoles.map((role) => roleLabel(role)).join(' + ')}. Storage changes may affect backups or recovery and will be blocked if dependencies are still in use.</p> : null}
      {result ? <p className={`is-${result.tone}`} role="status">{result.message}</p> : null}
      <LiteButton tone={confirming ? 'primary' : 'secondary'} onClick={applyRoles} disabled={!changed || busy || authorityMode === 'deny'}>
        {busy ? 'Applying…' : confirming ? 'Confirm role change' : authorityMode === 'approval' ? 'Request role change' : 'Change roles'}
      </LiteButton>
    </section>
  );
}

function LiteDeferredDetails({ render, delayFrames = 1 }) {
  const [ready, setReady] = React.useState(false);

  React.useEffect(() => {
    let active = true;
    let frame = null;
    let remaining = Math.max(1, Number(delayFrames) || 1);
    const schedule = () => {
      frame = window.requestAnimationFrame(() => {
        if (!active) return;
        remaining -= 1;
        if (remaining <= 0) setReady(true);
        else schedule();
      });
    };
    schedule();
    return () => {
      active = false;
      if (frame !== null) window.cancelAnimationFrame(frame);
    };
  }, [delayFrames]);

  if (!ready) {
    return <div className="lite-device-details-progressive-placeholder" aria-busy="true" aria-label="Loading device awareness details" />;
  }
  return render();
}

const DEVICE_AWARENESS_INITIAL_SECTION_COUNT = 1;
const DEVICE_AWARENESS_SECTION_BATCH_SIZE = 2;

function DeviceAwarenessDetails({ device }) {
  const sections = React.useMemo(() => {
    const capabilities = capabilityRows(device);
    const capabilitySummary = deviceCapabilitySummary(device);
    const runtimeServices = deviceRuntimeServices(device);
    const restartAssessment = deviceRestartAssessment(device) || {};
    const dependencies = device?.dependencies || {};
    const removal = device?.removal_assessment || {};
    return [
      <section key="connection" className="lite-device-awareness-section" aria-label="Connection status">
        <span>Connection</span>
        <strong>{deviceConnectionLabel(device)}</strong>
        <p>
          Latest activity {formatDeviceTime(
            device?.last_seen_state?.last_seen_at
              || device?.last_seen_at
              || device?.last_seen,
          )} from {titleCase(
            device?.last_seen_state?.last_seen_source,
            'device activity',
          )}.
        </p>
        <dl>
          <div>
            <dt>Device check-in</dt>
            <dd>{formatDeviceTime(
              device?.last_seen_state?.last_heartbeat_at,
              'No heartbeat reported',
            )}</dd>
          </div>
          <div>
            <dt>Recovery service</dt>
            <dd>{formatDeviceTime(
              device?.last_seen_state?.last_supervisor_heartbeat_at
                || device?.last_supervisor_at,
              'No recovery-service check-in reported',
            )}</dd>
          </div>
          <div>
            <dt>Private connection</dt>
            <dd>{formatDeviceTime(
              device?.last_seen_state?.last_nats_connected_at,
              'No private connection report',
            )}</dd>
          </div>
        </dl>
      </section>,

      <section key="trust" className="lite-device-awareness-section" aria-label="Device trust">
        <span>Trust</span>
        <strong>{titleCase(device?.identity?.status || device?.identity_status, 'Identity check pending')}</strong>
        <dl>
          {trustSummary(device).map((item) => <div key={item.label}><dt>{item.label}</dt><dd>{item.value || 'Not reported'}</dd></div>)}
        </dl>
        {device?.identity?.repair_required ? <p className="is-review">Repair or rejoin must be started explicitly.</p> : null}
      </section>,

      <section key="role-boundary" className="lite-device-awareness-section" aria-label="Device role boundary">
        <span>Assigned roles</span>
        <strong>{deviceRoleSummary(device)}</strong>
        <p>Assigned roles are server-owned responsibilities. A reported capability is effective only when the assigned role authorizes it and Pocket Lab verifies fresh runtime evidence.</p>
        <p>Photo Backup source remains independent from the Storage role.</p>
      </section>,

      <section key="capabilities" className="lite-device-awareness-section" aria-label="Device capabilities">
        <span>Capabilities</span>
        <strong>{capabilitySummary.label}</strong>
        <ul className="lite-device-capability-list">
          {capabilities.map((item) => (
            <li key={item.id}>
              <span>{item.label || titleCase(item.id)}</span>
              <strong className={`is-${String(item.status || 'unknown').toLowerCase()}`}>
                {capabilityStatusLabel(item.status, item.reason_code)}
              </strong>
            </li>
          ))}
        </ul>
      </section>,

      <section key="services" className="lite-device-awareness-section" aria-label="Device services">
        <span>Services</span>
        <strong>{runtimeServices.length ? `${runtimeServices.length} reported` : 'Not reported'}</strong>
        {runtimeServices.length ? (
          <ul className="lite-device-capability-list">
            {runtimeServices.map((service) => (
              <li key={service.service_id}>
                <span>{service.label || titleCase(service.service_id)}</span>
                <strong className={`is-${String(service.freshness || 'unknown').toLowerCase()}`}>
                  {String(service.freshness || '').toLowerCase() === 'stale' ? `Last reported ${titleCase(service.state)}` : titleCase(service.state)}
                </strong>
              </li>
            ))}
          </ul>
        ) : <p>Service status will appear after the device reports again.</p>}
        {!restartAssessment.allowed ? <p>{restartAssessment.summary || 'Restart actions are unavailable until the device reports a safe recovery state.'}</p> : null}
      </section>,

      <section key="responsibilities" className="lite-device-awareness-section" aria-label="Device responsibilities">
        <span>Responsibilities</span>
        <strong>{Number(dependencies.hosted_app_count || 0) + Number(dependencies.backup_set_count || 0)} responsibilities</strong>
        {Array.isArray(dependencies.hosted_apps) && dependencies.hosted_apps.length ? (
          <ul>{dependencies.hosted_apps.map((app) => <li key={app.app_id}><strong>{app.label}</strong> · {titleCase(app.status)}</li>)}</ul>
        ) : <p>No hosted apps reported.</p>}
        {Number(dependencies.backup_set_count || 0) > 0 ? <p>Stores {dependencies.backup_set_count} verified backup set{Number(dependencies.backup_set_count) === 1 ? '' : 's'}.</p> : null}
        <p>Action delivery: {deviceCommandDeliveryLabel(device)}</p>
      </section>,

      <section key="removal" className="lite-device-awareness-section lite-device-awareness-removal" aria-label="Removal impact">
        <span>Removal</span>
        <strong>{removal.protected ? 'Protected server host' : (removal.allowed ?? removal.safe_to_remove) ? 'Remove after confirmation' : 'Removal blocked'}</strong>
        {Array.isArray(removal.blockers) && removal.blockers.length ? (
          <ul>{removal.blockers.map((item) => <li key={item.code}>{item.summary}</li>)}</ul>
        ) : <p>{removal.protected ? 'This control device cannot be removed.' : 'No dependency blockers are currently reported.'}</p>}
      </section>,
    ];
  }, [device]);
  const initialSectionCount = Math.min(DEVICE_AWARENESS_INITIAL_SECTION_COUNT, sections.length);
  const [visibleSectionCount, setVisibleSectionCount] = React.useState(initialSectionCount);

  React.useEffect(() => {
    setVisibleSectionCount(initialSectionCount);
    if (sections.length <= initialSectionCount) return undefined;

    let active = true;
    let frame = null;
    let nextCount = initialSectionCount;
    const revealNextBatch = () => {
      frame = window.requestAnimationFrame(() => {
        if (!active) return;
        nextCount = Math.min(sections.length, nextCount + DEVICE_AWARENESS_SECTION_BATCH_SIZE);
        setVisibleSectionCount(nextCount);
        if (nextCount < sections.length) revealNextBatch();
      });
    };
    revealNextBatch();
    return () => {
      active = false;
      if (frame !== null) window.cancelAnimationFrame(frame);
    };
  }, [initialSectionCount, sections.length]);

  return <div className="lite-device-awareness-grid">{sections.slice(0, visibleSectionCount)}</div>;
}

function DeviceHealthHistory({ deviceId }) {
  const healthHistoryOpenId = useLiteUiStore((state) => state.deviceHealthHistoryOpenId);
  const setDeviceHealthHistoryOpenId = useLiteUiStore((state) => state.setDeviceHealthHistoryOpenId);
  const healthHistoryOpen = healthHistoryOpenId === deviceId;
  const healthHistoryQuery = useLiteQuery({
    queryKey: liteQueryKeys.deviceHealthHistory(deviceId, 20, ''),
    path: liteQueryPaths.deviceHealthHistory(deviceId, 20, ''),
    queryFn: () => liteApi.deviceHealthHistory(deviceId, 20, ''),
    enabled: Boolean(deviceId && healthHistoryOpen),
    staleTime: 60_000,
    refetchInterval: false,
    refetchOnWindowFocus: false,
  });
  const healthTransitions = healthHistoryItems(healthHistoryQuery.data || {});

  return (
    <section className={`lite-device-health-history-shell ${healthHistoryOpen ? 'is-open' : ''}`.trim()} aria-label="Health timeline">
      <div className="lite-device-health-history-head">
        <div className="lite-device-health-history-title">
          <span className="lite-device-health-history-icon" aria-hidden="true"><Clock3 className="h-4 w-4" /></span>
          <div>
            <strong>Health timeline</strong>
            <small>Review meaningful health changes in time order.</small>
          </div>
        </div>
        <LiteButton
          tone="secondary"
          onClick={() => setDeviceHealthHistoryOpenId(healthHistoryOpen ? '' : deviceId)}
          aria-expanded={healthHistoryOpen}
        >
          {healthHistoryOpen ? 'Hide health history' : 'Show health history'}
        </LiteButton>
      </div>
      {healthHistoryOpen ? (
        <div className="lite-device-health-history" role="region" aria-label="Device health history">
          {healthHistoryQuery.loading ? <p className="lite-device-timeline-loading">Loading health history…</p> : null}
          {!healthHistoryQuery.loading ? (
            <LiteHistoryTimeline
              className="lite-device-timeline is-health"
              items={healthTransitions.map((item) => ({ id: item.id, title: item.title, summary: item.summary, time: item.created_at ? formatLiteTime(item.created_at) : '', state: item.status }))}
              emptyTitle="No health changes yet"
              emptyDescription="Health changes will appear here when Pocket Lab observes a meaningful transition."
            />
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

export default function DeviceDetailsLazy({ device, onClose, onChooseModel }) {
  if (!device) return null;
  const initialDeviceId = device?.id || '';
  const [deviceHistoryOpen, setDeviceHistoryOpen] = React.useState(false);
  const setActiveTab = useLiteUiStore((state) => state.setActiveTab);
  const detailsQuery = useLiteQuery({
    queryKey: liteQueryKeys.device(initialDeviceId),
    path: liteQueryPaths.device(initialDeviceId),
    queryFn: () => liteApi.device(initialDeviceId),
    enabled: Boolean(initialDeviceId),
    staleTime: 30_000,
    refetchInterval: false,
    refetchOnWindowFocus: false,
  });
  device = detailsQuery.data?.device || device;
  const healthQuery = useLiteQuery({
    queryKey: liteQueryKeys.deviceHealth(initialDeviceId),
    path: liteQueryPaths.deviceHealth(initialDeviceId),
    queryFn: () => liteApi.deviceHealth(initialDeviceId),
    enabled: Boolean(initialDeviceId),
    staleTime: 30_000,
    refetchInterval: false,
    refetchOnWindowFocus: false,
  });
  const healthSnapshot = healthQuery.data?.__liteSnapshot || null;
  const healthAttentionCurrent = !healthSnapshot || !(
    healthSnapshot.stale || healthSnapshot.expired || healthSnapshot.isExpired
    || healthSnapshot.source === 'cache' || healthSnapshot.source === 'saved'
  );
  const proactiveHealth = healthQuery.data?.health || device?.proactive_health || null;
  device = proactiveHealth ? { ...device, proactive_health: proactiveHealth } : device;
  const title = device?.name || device?.hostname || 'Device details';
  const effectiveStatus = effectiveDeviceStatus(device);
  const status = effectiveStatus === 'online'
    ? 'ready'
    : deviceAttention(device).length
      ? 'review'
      : 'neutral';
  const historyQuery = useLiteQuery({
    queryKey: liteQueryKeys.deviceHistory(device?.id || '', 20, ''),
    path: liteQueryPaths.deviceHistory(device?.id || '', 20, ''),
    queryFn: () => liteApi.deviceHistory(device?.id || '', 20, ''),
    enabled: Boolean(device?.id),
    staleTime: 60_000,
    refetchInterval: false,
    refetchOnWindowFocus: false,
  });
  const isProtectedServer = String(device?.role || '').toLowerCase() === 'server_host' || device?.is_current || device?.isCurrent;
  const healthReviewFlow = useLiteDeviceHealthReviewFlow({
    nodeId: initialDeviceId,
    healthRevision: proactiveHealth?.health_revision || '',
    recommendation: proactiveHealth?.recommended_action || 'review_device',
    backendReachable: healthQuery.backendReachable,
    savedStateOnly: !healthAttentionCurrent,
  });
  React.useEffect(() => {
    if (!proactiveHealth?.health_revision) return;
    healthReviewFlow.confirmBackend(proactiveHealth);
  }, [healthReviewFlow.confirmBackend, proactiveHealth?.attention_count, proactiveHealth?.health_revision, proactiveHealth?.status]);

  return (
    <section className={`lite-device-details-panel is-${status}`} role="region" aria-label={`${title} details`}>
      <div className="lite-device-details-panel-head">
        <div>
          <span>Details</span>
          <h3>{title}</h3>
          <p>{deviceSummary(device)}</p>
        </div>
        <button type="button" className="lite-device-remove-close" onClick={onClose} aria-label="Close device details">
          <X className="h-4 w-4" />
        </button>
      </div>

      <section className="lite-device-system-summary" aria-label="System identity and health">
        <div>
          <span>System</span>
          <strong>{device?.system_profile?.display_model || device?.system_profile?.technical_model || 'System details unavailable'}</strong>
          <p>{[device?.system_profile?.manufacturer, device?.system_profile?.technical_model, device?.system_profile?.device_codename].filter(Boolean).join(' · ')}</p>
        </div>
        <div className="lite-device-system-facts">
          <span>{[device?.system_profile?.os_name, device?.system_profile?.os_version].filter(Boolean).join(' ') || 'OS unavailable'}</span>
          <span>{device?.system_profile?.android_abi || device?.system_profile?.architecture || 'Architecture unavailable'}</span>
          <span>{device?.system_health?.uptime_label || 'Uptime unavailable'}</span>
        </div>
        {isProtectedServer ? (
          <p className="lite-device-model-boundary" role="note">
            Choosing a friendly model changes display metadata only. Server identity, technical model, and internal codename remain reported by the device.
          </p>
        ) : null}
        {onChooseModel ? (
          <LiteButton tone="secondary" onClick={onChooseModel}>
            <Smartphone className="h-4 w-4" />
            Choose model
          </LiteButton>
        ) : null}
      </section>

      {!isProtectedServer ? (
        <>
          <DeviceRoleManager device={device} onChanged={() => detailsQuery.refetch?.()} />
          <DevicePhotoBackup deviceId={initialDeviceId} />
        </>
      ) : null}

      <LiteDeferredDetails delayFrames={DEVICE_DETAILS_NONCRITICAL_DELAY_FRAMES} render={() => {
        const healthResources = proactiveHealth ? healthResourceRows(proactiveHealth, device) : [];
        const deviceFacts = normalizeDeviceFacts(
          device?.device_facts || proactiveHealth?.device_facts || device,
          { health: proactiveHealth },
        );
        const healthAttention = healthAttentionCurrent && Array.isArray(proactiveHealth?.attention_items)
          ? proactiveHealth.attention_items.slice(0, 12)
          : [];
        const recommendationTargetScreen = recommendationScreen(proactiveHealth?.recommended_action);
        return (<section className={`lite-device-proactive-health is-${normalizeStatus(proactiveHealth?.status || 'unknown')}`} aria-label="Proactive device health">
        <div className="lite-device-proactive-health-head">
          <span className="lite-device-proactive-health-icon">
            {healthAttention.length ? <AlertTriangle className="h-5 w-5" /> : <HeartPulse className="h-5 w-5" />}
          </span>
          <div>
            <span>Overall health</span>
            <strong>{proactiveHealthLabel(proactiveHealth?.status)}</strong>
            <p>{proactiveHealth?.summary || 'Device health is not available yet.'}</p>
          </div>
          <small>{titleCase(proactiveHealth?.severity, 'No severity')}</small>
        </div>

        {proactiveHealth ? (
          <>
            <div className="lite-device-health-resource-grid" aria-label="Resource health">
              {healthResources.map((item) => (
                <ResourceMetric
                  key={item.label}
                  item={{ ...item, key: item.label, value: item.metric, note: item.summary }}
                  variant="detailed"
                />
              ))}
            </div>

            <div className="lite-device-health-posture-grid">
              <article>
                <span>Connection</span>
                <strong>{titleCase(proactiveHealth.connection?.status)}</strong>
                <p>{proactiveHealth.connection?.summary || 'Connection quality is not available yet.'}</p>
              </article>
              <article>
                <span>Recovery</span>
                <strong>{titleCase(proactiveHealth.recovery?.status)}</strong>
                <p>{proactiveHealth.recovery?.summary || 'Recovery posture is not available yet.'}</p>
              </article>
              <article>
                <span>Software</span>
                <SoftwarePosture
                  facts={deviceFacts}
                  posture={proactiveHealth.software_posture || proactiveHealth.versions || {}}
                />
              </article>
              <article>
                <span>Responsibility impact</span>
                <strong>{titleCase(proactiveHealth.dependency_impact?.status)}</strong>
                <p>{proactiveHealth.dependency_impact?.impact_summary || 'Responsibility impact is not available yet.'}</p>
              </article>
            </div>

            <div className="lite-device-health-recommendation" role="note">
              <div>
                <span>Recommended next step</span>
                <strong>{recommendationLabel(proactiveHealth.recommended_action)}</strong>
                <p>Recommendations are guidance only. Pocket Lab will not run an action without the normal guarded flow.</p>
              </div>
              {recommendationTargetScreen && healthAttentionCurrent ? (
                <LiteButton
                  tone="secondary"
                  onClick={() => {
                    triggerLiteTactileFeedback('selection');
                    healthReviewFlow.routeTo(recommendationTargetScreen, (screenId) => {
                      setActiveTab(screenId);
                      if (screenId === 'devices') onClose?.();
                    });
                  }}
                  disabled={healthReviewFlow.blocked}
                >
                  {recommendationTargetScreen === 'devices'
                    ? 'Return to device actions'
                    : `Open ${recommendationTargetScreen === 'catalog' ? 'Apps' : recommendationTargetScreen === 'recovery' ? 'Backup & Restore' : 'Access Center'}`}
                </LiteButton>
              ) : null}
            </div>

            {healthAttention.length ? (
              <div className="lite-device-health-attention-list" aria-label="Current health attention">
                <span>Needs attention</span>
                {healthAttention.map((item) => (
                  <article key={item.id || item.reason_code}>
                    <div>
                      <strong>{item.summary}</strong>
                      <small>{titleCase(item.category)} · {titleCase(item.severity)}</small>
                    </div>
                    <p>{item.recommendation}</p>
                  </article>
                ))}
              </div>
            ) : healthAttentionCurrent ? (
              <p className="lite-device-health-clear">No immediate health action is needed.</p>
            ) : (
              <p className="lite-device-health-saved-note">Saved health is visible. Reconnect before treating attention as current.</p>
            )}

            <DeviceHealthHistory deviceId={initialDeviceId} />
          </>
        ) : <p>Health will appear after the device reports again.</p>}
      </section>);
      }} />

      <LiteDeferredDetails delayFrames={DEVICE_AWARENESS_NONCRITICAL_DELAY_FRAMES} render={() => <DeviceAwarenessDetails device={device} />} />

      <details className="lite-device-advanced-details">
        <summary>
          <span>Connection, health and history</span>
          <small>Safe operational facts, recent health changes, and troubleshooting context</small>
        </summary>
        <LiteDeferredDetails delayFrames={DEVICE_DETAILS_NONCRITICAL_DELAY_FRAMES} render={() => {
          const historyItems = Array.isArray(historyQuery.data?.items) && historyQuery.data.items.length
            ? historyQuery.data.items
            : deviceHistoryItems({ ...device, recent_events: device?.recent_lifecycle });
          const restartAssessment = deviceRestartAssessment(device) || {};
          const attention = deviceAttention(device);
          const timelineItems = deviceHistoryTimelineItems(historyItems);
          const latestActivity = device?.last_seen_state?.last_seen_at || device?.last_seen_at || device?.last_seen;
          return (
            <div className="lite-device-connection-health-story">
              <section className="lite-device-operational-now" aria-label="Current connection and health">
                <div>
                  <span>Connection now</span>
                  <strong>{deviceConnectionLabel(device)}</strong>
                  <small>{latestActivity ? `Last activity ${formatLiteTime(latestActivity)}` : 'No recent activity timestamp reported'}</small>
                </div>
                <div>
                  <span>Health now</span>
                  <strong>{proactiveHealthLabel(proactiveHealth?.status)}</strong>
                  <small>{proactiveHealth?.summary || 'Current health summary is not available yet.'}</small>
                </div>
              </section>

              <section className={`lite-device-history-timeline-card ${deviceHistoryOpen ? 'is-open' : 'is-collapsed'}`} aria-label="Device history timeline">
                <div className="lite-device-history-timeline-head">
                  <div>
                    <span>Recent changes</span>
                    <strong>Device history</strong>
                    <p>{historyQuery.loading ? 'Loading recent device activity…' : timelineItems.length ? `${timelineItems.length} recent event${timelineItems.length === 1 ? '' : 's'}` : 'No device history has been reported yet.'}</p>
                  </div>
                  <div className="lite-device-history-timeline-actions">
                    {timelineItems[0]?.time ? <time>{timelineItems[0].time}</time> : null}
                    <LiteButton
                      tone="secondary"
                      onClick={() => setDeviceHistoryOpen((open) => !open)}
                      aria-expanded={deviceHistoryOpen}
                      aria-controls={`device-history-timeline-${initialDeviceId}`}
                    >
                      {deviceHistoryOpen ? 'Collapse history' : 'Show history'}
                    </LiteButton>
                  </div>
                </div>
                {deviceHistoryOpen ? (
                  <div id={`device-history-timeline-${initialDeviceId}`} className="lite-device-history-timeline-body">
                    {historyQuery.loading ? <p className="lite-device-timeline-loading">Loading recent device activity…</p> : (
                      <LiteHistoryTimeline
                        className="lite-device-timeline is-device-history"
                        items={timelineItems}
                        emptyTitle="No device history yet"
                        emptyDescription="Connection, recovery, and lifecycle changes will appear here when Pocket Lab reports them."
                      />
                    )}
                  </div>
                ) : null}
              </section>

              <LiteProgressiveDetails
              title={title}
              status={status}
              statusLabel={deviceStatusLabel(effectiveStatus)}
              summary={deviceSummary(device)}
              what_happened={deviceWhatHappened(device)}
              what_changed={deviceWhatChanged(device)}
              what_needs_attention={attention}
              what_did_not_happen={deviceWhatDidNotHappen()}
              saved_for_troubleshooting={{
                saved: Boolean(device?.last_seen || device?.id),
                backend_only: true,
                summary: 'Device events and troubleshooting records stay protected by Pocket Lab.',
              }}
              next_step={attention.length ? (restartAssessment.allowed ? 'Restart the device service through Pocket Lab.' : restartAssessment.summary || 'Check power, private network access, and the device recovery service.') : 'No action is needed right now.'}
              technicalDetails={technicalRows(device)}
            />
            </div>
          );
        }} />
      </details>
    </section>
  );
}

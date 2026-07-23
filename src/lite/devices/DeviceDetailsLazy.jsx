import React from 'react';
import { Smartphone, X } from 'lucide-react';
import { formatLiteTime, liteApi } from '../../lib/liteApi.js';
import { liteQueryKeys, liteQueryPaths } from '../../lib/liteQueryClient.js';
import { useLiteQuery } from '../../hooks/useLiteQuery.js';
import LiteProgressiveDetails from '../components/LiteProgressiveDetails.jsx';
import {
  LiteButton,
  backendBadgeStatus,
  deviceCapabilityLabels,
  deviceConnectionLabel,
  deviceLinkState,
  deviceStatusLabel,
  normalizeBackendState,
  roleLabel,
} from '../LiteUi.jsx';

const DEVICE_DETAILS_USES_PROGRESSIVE_FOUNDATION = true;
const DEVICE_DETAILS_HISTORY_IS_LAZY = true;
const DEVICE_DETAILS_BACKEND_EVIDENCE_BOUNDARY = 'normal Devices details do not fetch backend evidence endpoints';
const DEVICE_DETAILS_TECHNICAL_DETAILS_COLLAPSED = true;
void DEVICE_DETAILS_USES_PROGRESSIVE_FOUNDATION;
void DEVICE_DETAILS_HISTORY_IS_LAZY;
void DEVICE_DETAILS_BACKEND_EVIDENCE_BOUNDARY;
void DEVICE_DETAILS_TECHNICAL_DETAILS_COLLAPSED;

function normalizeStatus(value) {
  return String(value || '').toLowerCase().replace(/[\s-]+/g, '_');
}

function effectiveDeviceStatus(device) {
  const status = normalizeStatus(device?.status);
  const connection = normalizeStatus(device?.connection);
  const role = normalizeStatus(device?.role);

  if (['ready', 'healthy', 'active', 'online'].includes(status)) return 'online';
  if (
    ['repairing', 'supervisor_repairing'].includes(status)
    || connection === 'repairing'
  ) return 'repairing';
  if (
    ['agent_stopped', 'stopped'].includes(status)
    || connection === 'stopped'
  ) return 'agent_stopped';
  if (
    ['offline', 'failed', 'unhealthy', 'degraded', 'stale'].includes(status)
    || connection === 'offline'
  ) return 'offline';

  if (
    connection === 'online'
    || role === 'server_host'
    || device?.is_current
    || device?.isCurrent
  ) return 'online';

  if (connection === 'joining') return 'joining';
  if (connection === 'waiting') return 'waiting';

  return status || connection || 'status_pending';
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

  return 'No supervisor status reported';
}

function capabilityStatusLabel(value) {
  const status = normalizeStatus(value);
  if (status === 'ready') return 'Ready';
  if (status === 'available') return 'Advertised';
  if (status === 'not_ready') return 'Not ready';
  return 'Verification pending';
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
  if (normalizeStatus(device?.status) === 'agent_stopped') return `${name} has an agent that needs attention.`;
  if (connection === 'Online') return `${name} is currently online.`;
  if (connection) return `${name} is currently ${connection.toLowerCase()}.`;
  return `${name} details are available.`;
}

function deviceWhatHappened(device) {
  const happened = [
    'Pocket Lab read the latest safe device summary from the Lite API.',
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
  if (supervisorStatus !== 'No supervisor status reported') {
    happened.push(`Supervisor: ${supervisorStatus}.`);
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
    'No command was sent to this device.',
    'No agent restart was started.',
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
  return attention;
}

function technicalRows(device) {
  return [
    { label: 'Device id', value: device?.id },
    { label: 'Role', value: device?.role_label || roleLabel(device?.role) },
    { label: 'Status', value: deviceStatusLabel(effectiveDeviceStatus(device)) },
    { label: 'Connection', value: deviceConnectionLabel(device) },
    {
      label: 'Badge state',
      value: titleCase(
        backendBadgeStatus(effectiveDeviceStatus(device)),
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
    { label: 'Supervisor', value: supervisorStatusLabel(device) },
    { label: 'Capabilities', value: deviceCapabilityLabels(device).join(', ') },
    { label: 'OS family', value: device?.system_profile?.os_family },
    { label: 'Operating system', value: [device?.system_profile?.os_name, device?.system_profile?.os_version].filter(Boolean).join(' ') },
    { label: 'Android API', value: device?.system_profile?.android_api_level },
    { label: 'Security patch', value: device?.system_profile?.security_patch },
    { label: 'Manufacturer', value: device?.system_profile?.manufacturer },
    { label: 'Technical model', value: device?.system_profile?.technical_model },
    { label: 'Friendly model', value: device?.system_profile?.consumer_model_name || 'Using detected technical model' },
    { label: 'Internal codename', value: device?.system_profile?.device_codename },
    { label: 'Architecture', value: device?.system_profile?.architecture },
    { label: 'Android ABI', value: device?.system_profile?.android_abi },
    { label: 'Kernel', value: device?.system_profile?.kernel },
    { label: 'Runtime', value: device?.system_profile?.runtime_type },
    { label: 'Termux', value: device?.system_profile?.termux_version },
    { label: 'Python', value: device?.system_profile?.python_version },
    { label: 'Agent', value: device?.system_profile?.agent_version },
    { label: 'Supervisor version', value: device?.system_profile?.supervisor_version },
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
  const text = String(value || '').replace(/_/g, ' ').trim();
  return text ? text.replace(/\b\w/g, (letter) => letter.toUpperCase()) : fallback;
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

export default function DeviceDetailsLazy({ device, onClose, onChooseModel }) {
  if (!device) return null;
  const initialDeviceId = device?.id || '';
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
  const historyItems = Array.isArray(historyQuery.data?.items) && historyQuery.data.items.length
    ? historyQuery.data.items
    : deviceHistoryItems({ ...device, recent_events: device?.recent_lifecycle });
  const capabilities = capabilityRows(device);
  const dependencies = device?.dependencies || {};
  const removal = device?.removal_assessment || {};
  const isProtectedServer = String(device?.role || '').toLowerCase() === 'server_host' || device?.is_current || device?.isCurrent;

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
            Choosing a friendly model changes display metadata only. Server identity, technical model, and internal codename remain agent-owned.
          </p>
        ) : null}
        {onChooseModel ? (
          <LiteButton tone="secondary" onClick={onChooseModel}>
            <Smartphone className="h-4 w-4" />
            Choose model
          </LiteButton>
        ) : null}
      </section>

      <div className="lite-device-awareness-grid">
        <section className="lite-device-awareness-section" aria-label="Connection lifecycle">
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
              <dt>Heartbeat</dt>
              <dd>{formatDeviceTime(
                device?.last_seen_state?.last_heartbeat_at,
                'No heartbeat reported',
              )}</dd>
            </div>
            <div>
              <dt>Supervisor</dt>
              <dd>{formatDeviceTime(
                device?.last_seen_state?.last_supervisor_heartbeat_at
                  || device?.last_supervisor_at,
                'No supervisor heartbeat reported',
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
        </section>

        <section className="lite-device-awareness-section" aria-label="Device trust">
          <span>Trust</span>
          <strong>{titleCase(device?.identity?.status || device?.identity_status, 'Identity check pending')}</strong>
          <dl>
            {trustSummary(device).map((item) => <div key={item.label}><dt>{item.label}</dt><dd>{item.value || 'Not reported'}</dd></div>)}
          </dl>
          {device?.identity?.repair_required ? <p className="is-review">Repair or rejoin must be started explicitly.</p> : null}
        </section>

        <section className="lite-device-awareness-section" aria-label="Device capabilities">
          <span>Capabilities</span>
          <strong>{capabilities.filter((item) => ['ready', 'available'].includes(String(item.status).toLowerCase())).length} available</strong>
          <ul className="lite-device-capability-list">
            {capabilities.map((item) => (
              <li key={item.id}>
                <span>{item.label || titleCase(item.id)}</span>
                <strong className={`is-${String(item.status || 'unknown').toLowerCase()}`}>
                  {capabilityStatusLabel(item.status)}
                </strong>
              </li>
            ))}
          </ul>
        </section>

        <section className="lite-device-awareness-section" aria-label="Device dependencies">
          <span>Dependencies</span>
          <strong>{Number(dependencies.hosted_app_count || 0) + Number(dependencies.backup_set_count || 0)} responsibilities</strong>
          {Array.isArray(dependencies.hosted_apps) && dependencies.hosted_apps.length ? (
            <ul>{dependencies.hosted_apps.map((app) => <li key={app.app_id}><strong>{app.label}</strong> · {titleCase(app.status)}</li>)}</ul>
          ) : <p>No hosted apps reported.</p>}
          {Number(dependencies.backup_set_count || 0) > 0 ? <p>Stores {dependencies.backup_set_count} verified backup set{Number(dependencies.backup_set_count) === 1 ? '' : 's'}.</p> : null}
          <p>Command delivery: {titleCase(dependencies.command_delivery_status)}</p>
        </section>

        <section className="lite-device-awareness-section lite-device-awareness-removal" aria-label="Removal impact">
          <span>Removal</span>
          <strong>{removal.safe_to_remove ? 'Safe to remove after confirmation' : 'Not safe to remove'}</strong>
          {Array.isArray(removal.blockers) && removal.blockers.length ? (
            <ul>{removal.blockers.map((item) => <li key={item.code}>{item.summary}</li>)}</ul>
          ) : <p>No dependency blockers are currently reported.</p>}
        </section>
      </div>

      <details className="lite-device-advanced-details">
        <summary>
          <span>Diagnostics and history</span>
          <small>Technical details, safe activity summary, and troubleshooting records</small>
        </summary>
        <LiteProgressiveDetails
          title={title}
          status={status}
          statusLabel={deviceStatusLabel(effectiveStatus)}
          summary={deviceSummary(device)}
          what_happened={deviceWhatHappened(device)}
          what_changed={deviceWhatChanged(device)}
          what_needs_attention={deviceAttention(device)}
          what_did_not_happen={deviceWhatDidNotHappen()}
          saved_for_troubleshooting={{
            saved: Boolean(device?.last_seen || device?.id),
            backend_only: true,
            summary: 'Device events and troubleshooting records stay backend-owned and protected.',
          }}
          next_step={deviceAttention(device).length ? 'Use Restart agent only when Pocket Lab shows it is safe, or check the device locally.' : 'No action is needed right now.'}
          technicalDetails={technicalRows(device)}
          history={{
            title: 'Device history',
            domain: 'default',
            datasetKey: `device:${device?.id || device?.name || device?.hostname || 'unknown'}`,
            summary: historyQuery.loading ? 'Loading recent device activity…' : historyItems.length ? `${historyItems.length} safe event${historyItems.length === 1 ? '' : 's'} available.` : 'No device history has been reported yet.',
            items: historyItems,
            enabled: true,
            emptyMessage: 'No device history has been reported yet.',
          }}
        />
      </details>
    </section>
  );
}

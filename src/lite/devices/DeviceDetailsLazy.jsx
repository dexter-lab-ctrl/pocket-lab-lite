import React from 'react';
import { Smartphone, X } from 'lucide-react';
import { formatLiteTime } from '../../lib/liteApi.js';
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
  if (normalizeBackendState(device?.status) === 'ready') return `${name} is online and reporting to Pocket Lab.`;
  if (normalizeStatus(device?.status) === 'repairing' || deviceLinkState(device) === 'repairing') return `${name} is being checked or repaired.`;
  if (normalizeStatus(device?.status) === 'agent_stopped') return `${name} has an agent that needs attention.`;
  if (connection) return `${name} is shown as ${connection}.`;
  return `${name} details are available.`;
}

function deviceWhatHappened(device) {
  const happened = [
    'Pocket Lab read the latest safe device summary from the Lite API.',
    `Connection is shown as ${deviceConnectionLabel(device)}.`,
  ];
  if (device?.last_seen) happened.push(`Last seen ${formatLiteTime(device.last_seen)}.`);
  if (device?.supervisor?.status) happened.push(`Supervisor status is ${device.supervisor.status}.`);
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
    { label: 'Status', value: deviceStatusLabel(device?.status) },
    { label: 'Connection', value: deviceConnectionLabel(device) },
    { label: 'Badge state', value: backendBadgeStatus(device?.status) },
    { label: 'Last seen', value: formatLiteTime(device?.last_seen) },
    { label: 'Supervisor', value: device?.supervisor?.status || device?.supervisor_status },
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

export default function DeviceDetailsLazy({ device, onClose, onChooseModel }) {
  if (!device) return null;
  const title = device?.name || device?.hostname || 'Device details';
  const status = normalizeBackendState(device?.status) === 'ready' ? 'ready' : deviceAttention(device).length ? 'review' : 'neutral';
  const historyItems = deviceHistoryItems(device);
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

      <details className="lite-device-advanced-details">
        <summary>
          <span>Diagnostics and history</span>
          <small>Technical details, safe activity summary, and troubleshooting records</small>
        </summary>
        <LiteProgressiveDetails
          title={title}
          status={status}
          statusLabel={deviceStatusLabel(device?.status)}
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
            summary: historyItems.length ? `${historyItems.length} safe event${historyItems.length === 1 ? '' : 's'} available.` : 'No device history has been reported yet.',
            items: historyItems,
            enabled: true,
            emptyMessage: 'No device history has been reported yet.',
          }}
        />
      </details>
    </section>
  );
}

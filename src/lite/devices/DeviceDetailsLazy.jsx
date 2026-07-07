import React from 'react';
import { X } from 'lucide-react';
import { formatLiteTime } from '../../lib/liteApi.js';
import LiteProgressiveDetails from '../components/LiteProgressiveDetails.jsx';
import {
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
    device?.storage ? { label: 'Storage', value: device.storage.ready ? 'Ready' : 'Not ready' } : null,
  ].filter((row) => row && row.value);
}

export default function DeviceDetailsLazy({ device, onClose }) {
  if (!device) return null;
  const title = device?.name || device?.hostname || 'Device details';
  const status = normalizeBackendState(device?.status) === 'ready' ? 'ready' : deviceAttention(device).length ? 'review' : 'neutral';
  const historyItems = deviceHistoryItems(device);

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
          summary: historyItems.length ? `${historyItems.length} safe event${historyItems.length === 1 ? '' : 's'} available.` : 'History will appear here after the device reports more events.',
          items: historyItems,
          enabled: true,
          emptyMessage: 'History will appear here after the device reports more events.',
        }}
      />
    </section>
  );
}

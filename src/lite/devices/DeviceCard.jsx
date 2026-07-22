import React from 'react';
import { Network, RefreshCw, Trash2 } from 'lucide-react';
import {
  GlassCard,
  StatusBadge,
  LiteButton,
  backendBadgeStatus,
  normalizeBackendState,
  roleLabel,
  deviceConnectionLabel,
  deviceStatusLabel,
  deviceCapabilityLabels,
  deviceLinkState,
  canRestartDeviceAgent,
  canRemoveDevice,
} from '../LiteUi.jsx';
import { formatLiteTime } from '../../lib/liteApi.js';

const DEVICES_CARD_RENDER_REDUCTION_M1 = true;
const DEVICES_CARD_ACTIONS_OWN_CLICKS = true;
void DEVICES_CARD_RENDER_REDUCTION_M1;
void DEVICES_CARD_ACTIONS_OWN_CLICKS;

function DeviceCard({
  device,
  restartBusy = '',
  removeBusy = false,
  detailsOpen = false,
  onRestartAgent,
  onRemoveDevice,
  onOpenDetails,
  detailsButtonRef = null,
}) {
  const online = normalizeBackendState(device?.status) === 'ready';
  const linkState = deviceLinkState(device);
  const role = String(device?.role || '').toLowerCase();
  const isServerCard = role === 'server_host' || device?.is_current || device?.isCurrent;
  const connectionClass = isServerCard
    ? 'lite-device-card-server'
    : `lite-device-card-linked lite-device-card-linked-${linkState}`;
  const deviceName = device?.name || 'Unnamed device';
  const capabilities = deviceCapabilityLabels(device);
  const canRestart = canRestartDeviceAgent(device);
  const canRemove = canRemoveDevice(device);

  return (
    <GlassCard className={`lite-device-card ${connectionClass}`}>
      <div className="lite-device-card-top">
        <div className="lite-device-icon">
          <span className={online ? 'lite-device-pulse' : 'lite-device-pulse lite-device-pulse-muted'} />
          <Network className="h-5 w-5" />
        </div>
        <StatusBadge status={backendBadgeStatus(device?.status)}>
          {deviceStatusLabel(device?.status)}
        </StatusBadge>
      </div>

      <h2>{deviceName}</h2>

      <div className="lite-device-connection-copy">
        {isServerCard
          ? 'Connection anchor for this Pocket Lab.'
          : linkState === 'joined'
            ? 'Connected to the Pocket Lab Lite server.'
            : linkState === 'repairing'
              ? 'Connection is being repaired.'
              : 'Disconnected from the Pocket Lab Lite server.'}
      </div>

      <div className="lite-device-details">
        <div>
          <span>Role</span>
          <strong>{device?.role_label || roleLabel(device?.role)}</strong>
        </div>
        <div>
          <span>Last seen</span>
          <strong>{formatLiteTime(device?.last_seen)}</strong>
        </div>
        <div>
          <span>Connection</span>
          <strong>{deviceConnectionLabel(device)}</strong>
        </div>
        {device?.tailnet_ip ? (
          <div>
            <span>Tailscale IP</span>
            <strong>{device.tailnet_ip}</strong>
          </div>
        ) : null}
      </div>

      {capabilities.length ? (
        <div className="lite-device-capability-chips" aria-label="Device capabilities">
          {capabilities.map((label) => (
            <span key={label}>{label}</span>
          ))}
        </div>
      ) : null}

      {device?.storage ? (
        <div className="lite-device-storage-summary">
          <strong>{device.storage.ready ? 'Storage ready' : 'Storage not ready'}</strong>
          <span>{device.storage.available_gb ? `${device.storage.available_gb} GB available` : device.storage.summary || 'Storage status will appear after the device reports it.'}</span>
        </div>
      ) : null}

      <div className="lite-device-actions">
        <LiteButton tone="secondary" onClick={onOpenDetails} aria-expanded={detailsOpen} buttonRef={detailsButtonRef}>
          {detailsOpen ? 'Hide Details' : 'Details'}
        </LiteButton>
        {canRestart ? (
          <LiteButton
            tone="secondary"
            onClick={onRestartAgent}
            disabled={restartBusy === device?.id}
          >
            <RefreshCw className="h-4 w-4" />
            {restartBusy === device?.id ? 'Checking progress...' : 'Restart agent'}
          </LiteButton>
        ) : null}
        {canRemove ? (
          <LiteButton
            tone="danger"
            onClick={onRemoveDevice}
            disabled={removeBusy}
          >
            <Trash2 className="h-4 w-4" />
            Remove old device
          </LiteButton>
        ) : null}
      </div>
    </GlassCard>
  );
}

function areEqual(previous, next) {
  return previous.device === next.device
    && previous.restartBusy === next.restartBusy
    && previous.removeBusy === next.removeBusy
    && previous.detailsOpen === next.detailsOpen;
}

export default React.memo(DeviceCard, areEqual);

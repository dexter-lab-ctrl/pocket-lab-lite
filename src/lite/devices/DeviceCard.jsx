import React from 'react';
import { ChevronRight, LockKeyhole, Monitor, Server, Smartphone } from 'lucide-react';
import { GlassCard, canonicalDevicePresentation, deviceLinkState, deviceRoleSummary } from '../LiteUi.jsx';
import { triggerLiteHaptic } from '../../lib/liteNativeFeedback.js';
import { deviceLibraryEntry } from './deviceLibraryPresentation.js';
import './deviceActionFocus.css';

// Public connection helpers are retained for existing source consumers.
export function deviceConnectionFlowState({ isServerCard, linkState, presentation }) {
  if (isServerCard) return 'server';
  if (linkState === 'repairing' || presentation?.state === 'repairing') return 'repairing';
  if (linkState === 'joined' || presentation?.state === 'online') return 'connected';
  return 'disconnected';
}

export function deviceConnectionFlowLabel(state, deviceName, isServerCard, connectionView = null) {
  if (isServerCard) return `Pocket Lab Server. ${deviceName} is the protected server host.`;
  if (connectionView?.kind === 'joining') return `Pocket Lab Server is joining ${deviceName}.`;
  if (connectionView?.kind === 'waiting') return `Pocket Lab Server is waiting for ${deviceName}.`;
  if (connectionView?.kind === 'stopped') return `Pocket Lab Server reports the agent stopped on ${deviceName}.`;
  if (connectionView?.kind === 'blocked') return `Pocket Lab Server blocked the identity for ${deviceName}.`;
  if (connectionView?.kind === 'stale') return `Pocket Lab Server has saved status for ${deviceName}, but no current connection is confirmed.`;
  if (state === 'connected') return `Pocket Lab Server connected to ${deviceName}.`;
  if (state === 'repairing') return `Pocket Lab Server is restoring the connection to ${deviceName}.`;
  return `Pocket Lab Server is disconnected from ${deviceName}.`;
}

function DeviceTypeIcon({ device, server }) {
  if (server) return <Server aria-hidden="true" size={21} />;
  const details = [device?.system_profile?.os_name, device?.system_profile?.device_type,
    device?.system_profile?.display_model, device?.device_type, device?.role]
    .filter(Boolean).join(' ').toLowerCase();
  if (/desktop|laptop|windows|workstation|computer|macos|pc/.test(details)) return <Monitor aria-hidden="true" size={21} />;
  return <Smartphone aria-hidden="true" size={21} />;
}

function DeviceCard({
  device, detailsOpen = false, onOpenDetails, onPreloadDetails,
  detailsButtonRef = null, savedStateOnly = false,
}) {
  const presentation = canonicalDevicePresentation(device);
  const linkState = deviceLinkState(device);
  const entry = deviceLibraryEntry(device, { saved: savedStateOnly, presentation, linkState });
  const server = entry.connection.kind === 'server';
  const name = device?.name || device?.hostname || 'Unnamed device';
  const statusText = savedStateOnly ? 'Saved · connection not confirmed'
    : entry.healthAttention ? 'Health needs review'
      : entry.connection.label;
  const state = savedStateOnly ? 'stale' : entry.healthAttention ? 'attention' : entry.connection.kind;
  const roleText = server ? 'Protected server host'
    : device?.system_profile?.os_name
      ? `${deviceRoleSummary(device)} · ${device.system_profile.os_name}`
      : deviceRoleSummary(device) || 'Managed device';
  const handleManage = () => {
    triggerLiteHaptic('tap');
    onOpenDetails?.();
  };

  return (
    <GlassCard className={`lite-device-card lite-device-library-card ${server ? 'lite-device-card-server' : 'lite-device-card-peer'}`}>
      <div className="lite-device-library-identity">
        <span className={`lite-device-library-icon is-${server ? 'server' : 'peer'}`} aria-hidden="true">
          <DeviceTypeIcon device={device} server={server} />
        </span>
        <div className="lite-device-library-name">
          <h3 title={name}>{name}</h3>
          <p>{roleText}</p>
        </div>
        {server ? <LockKeyhole size={15} className="lite-device-library-lock" aria-label="Protected server host" /> : null}
      </div>
      <div className="lite-device-library-footer">
        <span className={`lite-device-library-status is-${state}`} data-connection-state={state}>
          <i aria-hidden="true" />
          <span>{statusText}</span>
        </span>
        <button type="button" ref={detailsButtonRef} className="lite-device-library-manage"
          aria-label={`Manage ${name}`} aria-expanded={detailsOpen}
          onPointerEnter={onPreloadDetails} onFocus={onPreloadDetails} onTouchStart={onPreloadDetails}
          onClick={handleManage}>
          <span>Manage</span><ChevronRight size={17} aria-hidden="true" />
        </button>
      </div>
    </GlassCard>
  );
}

function areEqual(previous, next) {
  return previous.device === next.device
    && previous.detailsOpen === next.detailsOpen
    && previous.savedStateOnly === next.savedStateOnly
    && previous.onPreloadDetails === next.onPreloadDetails;
}

export default React.memo(DeviceCard, areEqual);

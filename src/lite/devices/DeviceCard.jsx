import React from 'react';
import { Clock3, Cpu, Network, RefreshCw, Server, ShieldCheck, Trash2 } from 'lucide-react';
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

function hasMeaningfulStorage(device) {
  const storage = device?.storage;
  if (!storage || typeof storage !== 'object') return false;
  return storage.ready === true
    || Number.isFinite(Number(storage.available_gb))
    || Boolean(String(storage.summary || '').trim())
    || (Array.isArray(storage.media_roots) && storage.media_roots.length > 0)
    || ['storage', 'backup_target'].includes(String(device?.role || '').toLowerCase());
}

function storageSummary(device) {
  const storage = device?.storage || {};
  if (Number.isFinite(Number(storage.available_gb))) return `${Number(storage.available_gb)} GB available`;
  if (String(storage.summary || '').trim()) return String(storage.summary).trim();
  return storage.ready ? 'Ready for app data and backups.' : 'Storage telemetry needs attention.';
}

function identityLabel(device) {
  const status = String(device?.identity?.status || device?.identity_status || '').toLowerCase();
  if (status === 'protected_server_host') return 'Protected server host';
  if (status === 'verified') return 'Identity verified';
  if (status === 'join_blocked') return 'Join blocked';
  if (device?.identity?.repair_required) return 'Repair required';
  return 'Identity check pending';
}

function stalenessLabel(device) {
  const state = String(device?.staleness_state || device?.last_seen_state?.staleness_state || '').toLowerCase();
  if (state === 'review_recommended') return 'Review recommended';
  if (state === 'stale') return 'Stale';
  if (state === 'recently_offline') return 'Recently offline';
  return deviceConnectionLabel(device);
}

function responsibilitySummary(device) {
  const dependencies = device?.dependencies || {};
  const parts = [];
  if (Number(dependencies.hosted_app_count || 0) > 0) parts.push(`${dependencies.hosted_app_count} hosted app${Number(dependencies.hosted_app_count) === 1 ? '' : 's'}`);
  if (Number(dependencies.backup_set_count || 0) > 0) parts.push(`${dependencies.backup_set_count} backup set${Number(dependencies.backup_set_count) === 1 ? '' : 's'}`);
  if (dependencies.command_delivery_status === 'deliverable') parts.push('Receives recovery commands');
  return parts.slice(0, 2).join(' · ');
}

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
  const runtimeLabel = String(device?.system_profile?.runtime_type || '').replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
  const capabilities = deviceCapabilityLabels(device);
  const canRestart = canRestartDeviceAgent(device);
  const canRemove = canRemoveDevice(device);
  const showStorage = hasMeaningfulStorage(device);

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

      <div className="lite-device-card-heading">
        <span className="lite-device-card-kicker">
          {isServerCard ? <Server className="h-3.5 w-3.5" /> : <Network className="h-3.5 w-3.5" />}
          {isServerCard ? 'Pocket Lab server' : device?.role_label || roleLabel(device?.role)}
        </span>
        <h2>{deviceName}</h2>
        <p>
          {isServerCard
            ? 'Protected control device for this self-hosted workspace.'
            : linkState === 'joined'
              ? 'Connected and reporting through the private device channel.'
              : linkState === 'repairing'
                ? 'Pocket Lab is repairing this device connection.'
                : 'This device is not currently reporting.'}
        </p>
      </div>

      <div className="lite-device-system-strip" aria-label="Device system summary">
        <div>
          <span>System</span>
          <strong>{device?.system_profile?.display_model || device?.system_profile?.technical_model || 'Not reported'}</strong>
          <small>{[[device?.system_profile?.os_name, device?.system_profile?.os_version].filter(Boolean).join(' '), runtimeLabel].filter(Boolean).join(' · ') || 'System profile pending'}</small>
        </div>
        <div>
          <Cpu className="h-4 w-4" />
          <span>Architecture</span>
          <strong>{device?.system_profile?.android_abi || device?.system_profile?.architecture || 'Pending'}</strong>
        </div>
        <div>
          <Clock3 className="h-4 w-4" />
          <span>Uptime</span>
          <strong>{device?.system_health?.uptime_label || 'Pending'}</strong>
        </div>
      </div>

      <div className="lite-device-card-meta">
        <span><strong>{stalenessLabel(device)}</strong></span>
        <span>Last seen <strong>{formatLiteTime(device?.last_seen_state?.last_seen_at || device?.last_seen)}</strong></span>
        {capabilities.length ? <span><strong>{capabilities.length}</strong> verified capabilities</span> : null}
      </div>

      <div className="lite-device-trust-strip" aria-label="Device trust and responsibilities">
        <span><ShieldCheck className="h-4 w-4" /> <strong>{identityLabel(device)}</strong></span>
        {responsibilitySummary(device) ? <small>{responsibilitySummary(device)}</small> : <small>No active dependencies reported.</small>}
        {device?.removal_assessment ? (
          <small className={device.removal_assessment.safe_to_remove ? 'is-ready' : 'is-review'}>
            {device.removal_assessment.safe_to_remove ? 'Safe to remove after confirmation' : 'Not safe to remove'}
          </small>
        ) : null}
      </div>

      {showStorage ? (
        <div className={`lite-device-storage-summary ${device.storage.ready ? 'is-ready' : 'is-review'}`}>
          <strong>{device.storage.ready ? 'Storage ready' : 'Storage needs attention'}</strong>
          <span>{storageSummary(device)}</span>
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
            {device?.removal_assessment?.safe_to_remove ? 'Remove old device' : 'Review'}
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

import React from 'react';
import { AlertTriangle, HeartPulse, Network, RefreshCw, Server, ShieldCheck, Trash2 } from 'lucide-react';
import {
  GlassCard,
  StatusBadge,
  LiteButton,
  backendBadgeStatus,
  normalizeBackendState,
  roleLabel,
  deviceConnectionLabel,
  deviceStatusLabel,
  deviceCapabilitySummary,
  canonicalDevicePresentation,
  deviceLinkState,
  canRestartDeviceAgent,
  canRemoveDevice,
} from '../LiteUi.jsx';
import { formatLiteTime } from '../../lib/liteApi.js';

const DEVICES_CARD_RENDER_REDUCTION_M1 = true;
const DEVICES_CARD_ACTIONS_OWN_CLICKS = true;
void DEVICES_CARD_RENDER_REDUCTION_M1;
void DEVICES_CARD_ACTIONS_OWN_CLICKS;

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

function healthLabel(value) {
  const status = String(value || 'unknown').toLowerCase().replace(/[\s-]+/g, '_');
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

function healthTone(value) {
  const status = String(value || '').toLowerCase();
  if (['degraded', 'unreachable'].includes(status)) return 'is-critical';
  if (['watch', 'needs_attention'].includes(status)) return 'is-review';
  if (status === 'repairing') return 'is-repairing';
  if (status === 'healthy') return 'is-ready';
  return 'is-unknown';
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
  const presentation = canonicalDevicePresentation(device);
  const online = presentation.state === 'online';
  const linkState = deviceLinkState(device);
  const role = String(device?.role || '').toLowerCase();
  const isServerCard = role === 'server_host' || device?.is_current || device?.isCurrent;
  const connectionClass = isServerCard
    ? 'lite-device-card-server'
    : `lite-device-card-linked lite-device-card-linked-${linkState}`;
  const deviceName = device?.name || 'Unnamed device';
  const capabilitySummary = deviceCapabilitySummary(device);
  const canRestart = canRestartDeviceAgent(device);
  const canRemove = canRemoveDevice(device);
  const proactiveHealth = device?.proactive_health || null;
  const healthAttentionCurrent = Boolean(proactiveHealth?.attention_current !== false);
  const healthAttentionCount = healthAttentionCurrent ? Number(proactiveHealth?.attention_count || 0) : 0;

  return (
    <GlassCard className={`lite-device-card ${connectionClass}`}>
      <div className="lite-device-card-top">
        <div className="lite-device-icon">
          <span className={online ? 'lite-device-pulse' : 'lite-device-pulse lite-device-pulse-muted'} />
          <Network className="h-5 w-5" />
        </div>
        <StatusBadge status={backendBadgeStatus(presentation.state)}>
          {presentation.label}
        </StatusBadge>
      </div>

      <div className="lite-device-card-heading">
        <span className="lite-device-card-kicker">
          {isServerCard ? <Server className="h-3.5 w-3.5" /> : <Network className="h-3.5 w-3.5" />}
          {isServerCard ? 'Server host' : device?.role_label || roleLabel(device?.role)}
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

      <div className="lite-device-card-meta">
        <span><strong>{stalenessLabel(device)}</strong></span>
        <span>Last seen <strong>{formatLiteTime(device?.last_seen_state?.last_seen_at || device?.last_seen)}</strong></span>
        <span><strong>{capabilitySummary.label}</strong></span>
      </div>

      {proactiveHealth ? (
        <div className={`lite-device-health-strip ${healthTone(proactiveHealth.status)}`} aria-label="Proactive device health">
          <span className="lite-device-health-strip-icon">
            {healthAttentionCount > 0 ? <AlertTriangle className="h-4 w-4" /> : <HeartPulse className="h-4 w-4" />}
          </span>
          <span>
            <strong>{healthLabel(proactiveHealth.status)}</strong>
            <small>{proactiveHealth.summary || 'Device health is not available yet.'}</small>
          </span>
          {healthAttentionCount > 0 ? <em>{healthAttentionCount} item{healthAttentionCount === 1 ? '' : 's'}</em> : null}
        </div>
      ) : null}

      <div className="lite-device-trust-strip" aria-label="Device trust and responsibilities">
        <span><ShieldCheck className="h-4 w-4" /> <strong>{identityLabel(device)}</strong></span>
        {responsibilitySummary(device) ? <small>{responsibilitySummary(device)}</small> : <small>No active dependencies reported.</small>}
        {device?.removal_assessment ? (
          <small className={device.removal_assessment.safe_to_remove ? 'is-ready' : 'is-review'}>
            {device.removal_assessment.protected ? 'Protected server host' : (device.removal_assessment.allowed ?? device.removal_assessment.safe_to_remove) ? 'Remove after confirmation' : 'Removal blocked'}
          </small>
        ) : null}
      </div>

      <div className="lite-device-actions">
        <LiteButton
          tone="secondary"
          onClick={() => {
            onOpenDetails?.();
          }}
          aria-expanded={detailsOpen}
          buttonRef={detailsButtonRef}
        >
          {detailsOpen ? 'Hide Details' : healthAttentionCount > 0 ? 'Review health' : 'Details'}
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
            {(device?.removal_assessment?.allowed ?? device?.removal_assessment?.safe_to_remove) ? 'Remove device' : 'Review'}
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

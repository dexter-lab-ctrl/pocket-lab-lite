import React from 'react';
import { AlertTriangle, ChevronDown, HeartPulse, Lock, Network, RefreshCw, Server, ShieldCheck, Trash2 } from 'lucide-react';
import {
  GlassCard,
  LiteButton,
  roleLabel,
  deviceCapabilitySummary,
  canonicalDevicePresentation,
  deviceLinkState,
  canRestartDeviceAgent,
  canRemoveDevice,
  LiteActionRow,
  LiteOperationalStory,
} from '../LiteUi.jsx';
import { formatLiteTime } from '../../lib/liteApi.js';
import { selectDeviceOperationalStory } from '../../lib/liteViewModels.js';

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

export function deviceConnectionFlowState({ isServerCard, linkState, presentation }) {
  if (isServerCard) return 'server';
  if (linkState === 'repairing' || presentation.state === 'repairing') return 'repairing';
  if (linkState === 'joined' || presentation.state === 'online') return 'connected';
  return 'disconnected';
}

export function deviceConnectionFlowLabel(state, deviceName, isServerCard) {
  if (isServerCard) return `Pocket Lab Server. ${deviceName} is the protected server host.`;
  if (state === 'connected') return `Pocket Lab Server connected to ${deviceName}.`;
  if (state === 'repairing') return `Pocket Lab Server is restoring the connection to ${deviceName}.`;
  return `Pocket Lab Server is disconnected from ${deviceName}.`;
}

function deviceConnectionSummary(state) {
  if (state === 'connected') return 'Connected privately';
  if (state === 'repairing') return 'Repairing connection';
  if (state === 'server') return 'Protected control plane';
  return 'Connection interrupted';
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
  savedStateOnly = false,
}) {
  const presentation = canonicalDevicePresentation(device);
  const online = !savedStateOnly && presentation.state === 'online';
  const linkState = deviceLinkState(device);
  const role = String(device?.role || '').toLowerCase();
  const isServerCard = Boolean(device?.protected_server_host || role === 'server_host' || device?.is_current || device?.isCurrent);
  const effectiveLinkState = savedStateOnly && !isServerCard ? 'disconnected' : linkState;
  const connectionClass = isServerCard
    ? 'lite-device-card-server'
    : `lite-device-card-linked lite-device-card-linked-${effectiveLinkState}`;
  const deviceName = device?.name || 'Unnamed device';
  const capabilitySummary = deviceCapabilitySummary(device);
  const canRestart = !savedStateOnly && canRestartDeviceAgent(device);
  const canRemove = !savedStateOnly && canRemoveDevice(device);
  const proactiveHealth = device?.proactive_health || null;
  const healthAttentionCurrent = Boolean(proactiveHealth?.attention_current !== false);
  const healthAttentionCount = healthAttentionCurrent ? Number(proactiveHealth?.attention_count || 0) : 0;
  const flowState = savedStateOnly && !isServerCard
    ? 'disconnected'
    : deviceConnectionFlowState({ isServerCard, linkState: effectiveLinkState, presentation });
  const showHealthAttention = Boolean(proactiveHealth && (healthAttentionCount > 0 || !['healthy', 'unknown'].includes(String(proactiveHealth.status || '').toLowerCase())));
  const lastSeen = device?.last_seen_state?.last_seen_at || device?.last_seen;
  const story = selectDeviceOperationalStory(device, { savedStateOnly });

  return (
    <GlassCard className={`lite-device-card ${connectionClass}`}>
      <div className="lite-device-card-top">
        <div className="lite-device-icon">
          <span className={online ? 'lite-device-pulse' : 'lite-device-pulse lite-device-pulse-muted'} />
          <Network className="h-5 w-5" />
        </div>
      </div>

      <div className="lite-device-card-heading">
        <span className="lite-device-card-kicker">
          {isServerCard ? <Server className="h-3.5 w-3.5" /> : <Network className="h-3.5 w-3.5" />}
          {isServerCard ? 'Server host' : device?.role_label || roleLabel(device?.role)}
        </span>
        <h2>{deviceName}</h2>
        {isServerCard ? <p>Protected control device for this self-hosted workspace.</p> : null}
      </div>

      <div className={`lite-device-connection-flow is-${flowState}`} data-connection-state={flowState} role="img" aria-label={deviceConnectionFlowLabel(flowState, deviceName, isServerCard)}>
        <div className="lite-device-connection-copy">
          <span>Connection</span>
          <strong>{deviceConnectionSummary(flowState)}</strong>
        </div>
        {isServerCard ? (
          <div className="lite-device-protected-host" aria-hidden="true">
            <span className="lite-device-flow-node lite-device-flow-server"><Server className="h-4 w-4" /><small>Pocket Lab Server</small></span>
            <span className="lite-device-protected-lock"><Lock className="h-3.5 w-3.5" /> Protected</span>
          </div>
        ) : (
          <div className="lite-device-flow-topology" aria-hidden="true">
            <span className="lite-device-flow-node lite-device-flow-server"><Server className="h-4 w-4" /><small>Server</small></span>
            <span className="lite-device-flow-track"><span className="lite-device-flow-signal" /><span className="lite-device-flow-break">×</span></span>
            <span className="lite-device-flow-node lite-device-flow-device"><Network className="h-4 w-4" /><small title={deviceName}>{deviceName}</small></span>
          </div>
        )}
      </div>

      <LiteOperationalStory
        className="lite-device-operational-story"
        story={{
          ...story,
          freshness: lastSeen ? { label: savedStateOnly ? 'Saved status' : 'Last seen', detail: formatLiteTime(lastSeen), state: savedStateOnly ? 'stale' : 'live' } : null,
        }}
        primaryAction={story.next_action?.kind === 'restart' ? { label: story.next_action.label, onClick: onRestartAgent, tone: 'primary' } : null}
        manageAction={{
          label: detailsOpen ? 'Hide details' : 'Manage',
          onClick: onOpenDetails,
          ariaLabel: `${detailsOpen ? 'Hide' : 'Manage'} ${deviceName}`,
          ariaExpanded: detailsOpen,
          buttonRef: detailsButtonRef,
        }}
      />

      {story.remote_access === 'not_ready' ? (
        <LiteActionRow
          className="lite-device-remote-access-row"
          label="Remote access"
          value="Not ready"
          summary="This is separate from the local Pocket Lab connection."
          attention
        />
      ) : null}

      {showHealthAttention ? (
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

      <div className="lite-device-actions">
        <details className="lite-device-card-disclosure">
          <summary aria-label={`More details and actions for ${deviceName}`}>
            <span>Technical and safety</span><ChevronDown className="h-4 w-4" />
          </summary>
          <div className="lite-device-card-disclosure-content">
            <div className="lite-device-trust-strip" aria-label="Device trust and responsibilities">
              <span><ShieldCheck className="h-4 w-4" /> <strong>{identityLabel(device)}</strong></span>
              {responsibilitySummary(device) ? <small>{responsibilitySummary(device)}</small> : <small>No active dependencies reported.</small>}
              {device?.removal_assessment ? (
                <small className={device.removal_assessment.safe_to_remove ? 'is-ready' : 'is-review'}>
                  {device.removal_assessment.protected ? 'Protected server host' : (device.removal_assessment.allowed ?? device.removal_assessment.safe_to_remove) ? 'Remove after confirmation' : 'Removal blocked'}
                </small>
              ) : null}
              <small>Capabilities: {capabilitySummary.label}</small>
            </div>
            {(canRestart || canRemove) ? <div className="lite-device-secondary-actions">
              {canRestart && story.next_action?.kind !== 'restart' ? <LiteButton tone="secondary" onClick={onRestartAgent} disabled={restartBusy === device?.id}>
                <RefreshCw className="h-4 w-4" />{restartBusy === device?.id ? 'Checking progress...' : 'Restart agent'}
              </LiteButton> : null}
              {canRemove ? <LiteButton tone="danger" onClick={onRemoveDevice} disabled={removeBusy}>
                <Trash2 className="h-4 w-4" />{(device?.removal_assessment?.allowed ?? device?.removal_assessment?.safe_to_remove) ? 'Remove device' : 'Review removal'}
              </LiteButton> : null}
            </div> : null}
          </div>
        </details>
      </div>
    </GlassCard>
  );
}

function areEqual(previous, next) {
  return previous.device === next.device
    && previous.restartBusy === next.restartBusy
    && previous.removeBusy === next.removeBusy
    && previous.detailsOpen === next.detailsOpen
    && previous.savedStateOnly === next.savedStateOnly;
}

export default React.memo(DeviceCard, areEqual);

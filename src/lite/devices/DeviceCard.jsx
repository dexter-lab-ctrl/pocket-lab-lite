import React from 'react';
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
import './deviceActionFocus.css';

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
  onPreloadDetails,
  detailsButtonRef = null,
  removeButtonRef = null,
  savedStateOnly = false,
}) {
  const [technicalDetailsOpen, setTechnicalDetailsOpen] = React.useState(false);
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
  const capabilitySummary = technicalDetailsOpen ? deviceCapabilitySummary(device) : null;
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
  function openRemovalReview() {
    onRemoveDevice?.();
  }

  return (
    <GlassCard className={`lite-device-card ${connectionClass}`}>
        <div className="lite-device-card-top">
          <div className="lite-device-icon">
            <span className={online ? 'lite-device-pulse' : 'lite-device-pulse lite-device-pulse-muted'} />
          </div>
        </div>

        <div className="lite-device-card-heading">
          <span className="lite-device-card-kicker">
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
              <span className="lite-device-flow-node lite-device-flow-server"><span className="lite-device-static-glyph" aria-hidden="true" /><small>Pocket Lab Server</small></span>
              <span className="lite-device-protected-lock"><span className="lite-device-static-glyph" aria-hidden="true" /> Protected</span>
            </div>
          ) : (
            <div className="lite-device-flow-topology" aria-hidden="true">
              <span className="lite-device-flow-node lite-device-flow-server"><span className="lite-device-flow-glyph" aria-hidden="true" /><small>Server</small></span>
              <span className="lite-device-flow-track"><span className="lite-device-flow-signal" /><span className="lite-device-flow-break">×</span></span>
              <span className="lite-device-flow-node lite-device-flow-device"><span className="lite-device-flow-glyph" aria-hidden="true" /><small title={deviceName}>{deviceName}</small></span>
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
            onPointerEnter: onPreloadDetails,
            onFocus: onPreloadDetails,
            onTouchStart: onPreloadDetails,
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
              <span className="lite-device-health-static-glyph" aria-hidden="true" />
            </span>
            <span>
              <strong>{healthLabel(proactiveHealth.status)}</strong>
              <small>{proactiveHealth.summary || 'Device health is not available yet.'}</small>
            </span>
            {healthAttentionCount > 0 ? <em>{healthAttentionCount} item{healthAttentionCount === 1 ? '' : 's'}</em> : null}
          </div>
        ) : null}

        <div className="lite-device-actions">
          <details className="lite-device-card-disclosure" onToggle={(event) => setTechnicalDetailsOpen(event.currentTarget.open)}>
            <summary aria-label={`More details and actions for ${deviceName}`}>
              <span>Technical and safety</span><span className="lite-device-card-chevron" aria-hidden="true" />
            </summary>
            {technicalDetailsOpen ? (
              <div className="lite-device-card-disclosure-content">
                <div className="lite-device-trust-strip" aria-label="Device trust and responsibilities">
                  <span><span className="lite-device-card-static-glyph" aria-hidden="true" /> <strong>{identityLabel(device)}</strong></span>
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
                    <span className="lite-device-card-action-glyph" aria-hidden="true" />{restartBusy === device?.id ? 'Checking progress...' : 'Restart agent'}
                  </LiteButton> : null}
                  {canRemove ? <LiteButton tone="danger" onClick={openRemovalReview} disabled={removeBusy} buttonRef={removeButtonRef}>
                    <span className="lite-device-card-action-glyph is-danger" aria-hidden="true" />{(device?.removal_assessment?.allowed ?? device?.removal_assessment?.safe_to_remove) ? 'Remove device' : 'Review removal'}
                  </LiteButton> : null}
                </div> : null}
              </div>
            ) : null}
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
    && previous.onPreloadDetails === next.onPreloadDetails
    && previous.savedStateOnly === next.savedStateOnly;
}

export default React.memo(DeviceCard, areEqual);

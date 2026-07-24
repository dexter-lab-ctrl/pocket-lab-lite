import React, { Suspense, useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity,
  Copy,
  Database,
  Download,
  EyeOff,
  FileCheck,
  Fingerprint,
  LayoutGrid,
  Lock,
  Menu,
  Network,
  RefreshCw,
  Server,
  ShieldCheck,
  Trash2,
  WifiOff,
  X,
} from 'lucide-react';
import { useLiteResource } from '../hooks/useLiteStatus.js';
import { hasLiteLiveOperation, isLiteLiveStatus } from '../lib/litePollingPolicy.js';
import { isLiteDevicesViewLive, selectDevicesScreenView } from '../lib/liteViewModels.js';
import { useLiteAddDeviceFlow } from '../hooks/useLiteAddDeviceFlow.js';
import { useLiteDeviceRemovalFlow } from '../hooks/useLiteDeviceRemovalFlow.js';
import { useLiteServiceWorkerUpdateBlocker } from '../hooks/useLiteServiceWorkerUpdateBlocker.js';
import { formatLiteTime, liteApi } from '../lib/liteApi.js';
import {
  GlassCard,
  StatusBadge,
  StateSurface,
  DEVICE_ROLE_OPTIONS,
  NAV_ITEMS,
  roleLabel,
  deviceConnectionLabel,
  canRestartDeviceAgent,
  canRemoveDevice,
  normalizeDeviceName,
  findDeviceNameConflict,
  deviceDuplicateMessage,
  deviceStatusLabel,
  deviceCapabilityLabels,
  copyTextToClipboard,
  serviceTone,
  normalizeBackendState,
  backendBadgeStatus,
  backendLabel,
  backendHeroTitle,
  securityFindingTone,
  securityFindingLabel,
  clampSecurityProgress,
  parseSecurityTimestamp,
  formatSecurityRemainingSeconds,
  liveSecurityProgress,
  securityProgressStage,
  scanInProgressValue,
  triggerHapticFeedback,
  shortRunId,
  formatSecurityDuration,
  securityTrendLabel,
  securityTrendView,
  securityDeltaTone,
  isSecurityTimeoutFinding,
  securityDeltaBadge,
  securityDeltaTitle,
  securityDeltaDescription,
  securityDeltaAction,
  securityDeltaSummary,
  securityExecutionStateTone,
  securityExecutionStepGlyph,
  securityToolStatusLabel,
  securityExecutionStateFromBackend,
  securityExecutionStepLabel,
  normalizeSecurityExecutionSteps,
  securityExecutionTimeline,
  PageHeader,
  LiteButton,
  LiteRefreshButton,
  ResultNotice,
  LoadingCard,
  LiteFlowStatusPanel,
  friendlyOverallLabel,
  deviceLinkState,
  restartProgressTitle,
  restartStepStateLabel,
  safeRestartSteps
} from './LiteUi.jsx';
import DeviceCard from './devices/DeviceCard.jsx';
import LiteVirtualList from './components/LiteVirtualList.jsx';
import { useLiteDeviceDetailsState, useLiteUiStore } from '../stores/liteUiStore.js';

const DeviceDetailsLazy = React.lazy(() => import('./devices/DeviceDetailsLazy.jsx'));
const DeviceModelPickerLazy = React.lazy(() => import('./devices/DeviceModelPickerLazy.jsx'));

const DEVICES_PROGRESSIVE_DETAILS_MILESTONE_2 = true;
const DEVICES_DETAILS_ARE_LAZY = true;
const DEVICES_ACTION_ROWS_OWN_CLICKS = true;
const DEVICES_LINKED_CARD_CLASS_MARKER = 'lite-device-card-linked';
const DEVICES_CONNECTION_COPY_MARKER = 'Disconnected from the Pocket Lab Lite server.';
void DEVICES_PROGRESSIVE_DETAILS_MILESTONE_2;
void DEVICES_DETAILS_ARE_LAZY;
void DEVICES_ACTION_ROWS_OWN_CLICKS;
void DEVICES_LINKED_CARD_CLASS_MARKER;
void DEVICES_CONNECTION_COPY_MARKER;

const DEVICES_POLLING_POLICY_PHASE4 = 'DEVICES_POLLING_POLICY_PHASE4';

function devicePollingValue(value) {
  return String(value || '').toLowerCase().replace(/[\s-]+/g, '_');
}

function deviceInviteIsLive(invite) {
  if (!invite || typeof invite !== 'object') return false;
  const status = devicePollingValue(invite.status || invite.state || invite.phase || invite.lifecycle);
  if (!status) return Boolean(invite.token || invite.bootstrap_url || invite.bootstrap_command || invite.copy_text);
  return !['completed', 'expired', 'cancelled', 'canceled', 'failed', 'removed', 'revoked'].includes(status);
}

function deviceRestartProgressIsLive(progress) {
  if (!progress || typeof progress !== 'object') return false;
  const status = devicePollingValue(progress.status || progress.state || progress.phase);
  return Boolean(status && !['completed', 'failed', 'cancelled', 'canceled', 'done'].includes(status));
}

export function hasLiveDeviceFleetOperation(payload) {
  if (!payload || typeof payload !== 'object') return false;
  if (hasLiteLiveOperation(payload?.current_action) || hasLiteLiveOperation(payload?.latest_operation)) return true;
  if (deviceInviteIsLive(payload?.latest_invite)) return true;

  const devices = Array.isArray(payload?.devices) ? payload.devices : [];
  return devices.some((device) => {
    const status = devicePollingValue(device?.status || device?.connection || device?.state || device?.phase);
    if (['joining', 'waiting', 'repairing', 'restarting', 'restart_pending', 'command_pending', 'command_running'].includes(status)) return true;
    if (isLiteLiveStatus(status)) return true;
    return hasLiteLiveOperation(device?.restart_progress)
      || hasLiteLiveOperation(device?.command_progress)
      || hasLiteLiveOperation(device?.latest_command)
      || hasLiteLiveOperation(device?.supervisor);
  });
}

export default function DevicesScreen() {
  const [hostname, setHostname] = useState('');
  const [selectedRole, setSelectedRole] = useState('compute');
  const [result, setResult] = useState(null);
  const [invite, setInvite] = useState(null);
  const [copied, setCopied] = useState(false);
  const [actionError, setActionError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [restartBusy, setRestartBusy] = useState('');
  const [restartProgress, setRestartProgress] = useState(null);
  const [removeCandidate, setRemoveCandidate] = useState(null);
  const [removeAssessment, setRemoveAssessment] = useState(null);
  const [removeBusy, setRemoveBusy] = useState(false);
  const [removeAssessmentLoading, setRemoveAssessmentLoading] = useState(false);
  const [serverConflict, setServerConflict] = useState(null);
  const { activeDeviceDetailsId: detailsDeviceId, deviceModelPickerId } = useLiteDeviceDetailsState();
  const setDetailsDeviceId = useLiteUiStore((state) => state.setActiveDeviceDetailsId);
  const setDeviceModelPickerId = useLiteUiStore((state) => state.setDeviceModelPickerId);
  const detailsButtonRefs = useRef(new Map());
  const detailsPanelRef = useRef(null);
  const fleetPollingIsLive = useMemo(() => (fleetPayload) => (
    busy
    || Boolean(restartBusy)
    || removeBusy
    || deviceRestartProgressIsLive(restartProgress)
    || ['queued', 'accepted', 'running', 'working', 'joining', 'waiting', 'repairing'].includes(devicePollingValue(result?.status || result?.state))
    || isLiteDevicesViewLive(fleetPayload)
    || hasLiveDeviceFleetOperation(fleetPayload)
  ), [busy, restartBusy, removeBusy, restartProgress, result]);
  const { data, loading, error, refresh, cacheStatus, refreshing, backendReachable, savedStateOnly } = useLiteResource(liteApi.fleet, [], {
    pollingMode: 'slow',
    isLive: fleetPollingIsLive,
    staleTime: 15_000,
    select: selectDevicesScreenView,
    snapshotSelect: selectDevicesScreenView,
  });
  const removalFlow = useLiteDeviceRemovalFlow({ backendReachable, savedStateOnly });
  const devices = data?.devices || [];
  const activeDetailsDevice = devices.find((device) => String(device?.id || device?.name || '') === detailsDeviceId) || null;
  const modelPickerDevice = devices.find((device) => String(device?.id || device?.name || '') === deviceModelPickerId) || null;
  const remoteAccess = data?.remote_access || {};
  const remoteAccessReady = remoteAccess?.status === 'healthy' || remoteAccess?.ready;
  const latestInvite = invite || data?.latest_invite || null;
  useLiteServiceWorkerUpdateBlocker('devices-workflow', Boolean(
    hostname.trim()
    || busy
    || restartBusy
    || removeBusy
    || removeCandidate
    || deviceInviteIsLive(latestInvite)
    || deviceRestartProgressIsLive(restartProgress)
  ));
  const onlineDevices = devices.filter((device) => normalizeBackendState(device.status) === 'ready').length;
  const healthAttentionCurrent = Boolean(data?.health_summary?.attention_current);
  const healthAttentionCount = healthAttentionCurrent ? Number(data?.health_summary?.attention_count || 0) : 0;
  const selectedRoleLabel = roleLabel(selectedRole);
  const candidateDeviceName = hostname.trim() || `Pocket Lab ${selectedRoleLabel}`;
  const localNameConflict = findDeviceNameConflict(candidateDeviceName, devices);
  const activeNameConflict = localNameConflict || serverConflict;
  const addDeviceFlow = useLiteAddDeviceFlow({ devices, latestInvite, backendReachable, savedStateOnly, remoteAccessReady });
  const addDeviceDisabled = busy || addDeviceFlow.writeBlocked || Boolean(activeNameConflict);
  useEffect(() => {
    if (!activeDetailsDevice || !detailsPanelRef.current) return undefined;
    const frame = window.requestAnimationFrame(() => {
      const panel = detailsPanelRef.current;
      const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches;
      panel?.scrollIntoView?.({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'nearest' });
      panel?.focus?.({ preventScroll: true });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [activeDetailsDevice?.id]);
  const closeDeviceDetails = () => {
    const trigger = detailsButtonRefs.current.get(detailsDeviceId);
    trigger?.focus?.({ preventScroll: true });
    setDetailsDeviceId('');
  };


  async function addDevice() {
    const validation = addDeviceFlow.validateName(candidateDeviceName, selectedRole);
    if (!validation.ok) { setActionError(validation.reason); return; }
    addDeviceFlow.createInvite();
    setBusy(true);
    setResult({ status: 'queued', summary: 'Preparing invite...' });
    setInvite(null);
    setCopied(false);
    setActionError(null);
    setServerConflict(null);
    try {
      const payload = await liteApi.addDevice({ role: selectedRole, hostname: hostname || undefined });
      setResult(payload);
      if (payload?.status === 'invite_ready' && payload?.invite) {
        setInvite(payload.invite);
        addDeviceFlow.inviteReady(payload);
      } else if (payload?.status === 'queued') {
        addDeviceFlow.queued(payload);
      }
      refresh();
    } catch (err) {
      const detail = err?.payload?.detail || {};
      setResult(null);
      if (detail?.status === 'duplicate_device') {
        setServerConflict(detail.existing_device || null);
        addDeviceFlow.block(detail.message || detail.summary || 'This name is already used.');
        setActionError(detail.message || detail.summary || 'A device with this name already exists.');
      } else {
        addDeviceFlow.fail(err);
        setActionError(err.message);
      }
    } finally {
      setBusy(false);
    }
  }

  function inviteCommand(inviteDetails) {
    if (!inviteDetails) return '';
    if (inviteDetails.copy_text) return inviteDetails.copy_text;
    if (inviteDetails.bootstrap_command) return inviteDetails.bootstrap_command;
    if (inviteDetails.bootstrap_url) return `curl -fsSL '${inviteDetails.bootstrap_url}' | bash`;
    return inviteDetails.url || '';
  }

  async function copyInvite() {
    const copyValue = inviteCommand(latestInvite);
    const didCopy = await copyTextToClipboard(copyValue);
    if (didCopy) {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    }
  }

  async function restartAgent(device) {
    const nodeId = device?.id;
    if (!nodeId) return;
    setRestartBusy(nodeId);
    setActionError(null);
    setResult(null);
    setRestartProgress({
      node_id: nodeId,
      device_name: device?.name || device?.hostname || nodeId,
      status: 'starting',
      summary: 'Pocket Lab is preparing a safe restart request.',
      steps: [
        { id: 'request_saved', label: 'Preparing request', detail: 'Pocket Lab is recording the restart request.', state: 'active' },
        { id: 'private_channel', label: 'Private channel', detail: 'The request will be sent through the device command channel.', state: 'waiting' },
        { id: 'device_ack', label: 'Device agent', detail: 'Waiting for the device agent to receive the request.', state: 'waiting' },
        { id: 'heartbeat', label: 'Back online', detail: 'The device will show Online after a fresh heartbeat arrives.', state: 'waiting' },
      ],
    });
    try {
      const response = await liteApi.restartDeviceAgent(nodeId, {
        reason: 'Lite Devices restart requested',
      });
      setResult(response);
      setRestartProgress({
        ...response.progress,
        node_id: nodeId,
        device_name: device?.name || device?.hostname || nodeId,
      });
      refresh();

      const commandId = response?.command_id;
      if (commandId) {
        for (let attempt = 0; attempt < 12; attempt += 1) {
          await sleep(2500);
          const statusPayload = await liteApi.restartDeviceAgentStatus(nodeId, commandId);
          const nextProgress = statusPayload?.progress || statusPayload;
          setRestartProgress({
            ...nextProgress,
            node_id: nodeId,
            device_name: device?.name || device?.hostname || nodeId,
          });
          if (['completed', 'failed'].includes(nextProgress?.status)) {
            refresh();
            break;
          }
        }
      }
    } catch (err) {
      setActionError(err.message);
      setRestartProgress((current) => ({
        ...(current || {}),
        node_id: nodeId,
        device_name: device?.name || device?.hostname || nodeId,
        status: 'failed',
        summary: err.message || 'Pocket Lab could not confirm the restart.',
      }));
    } finally {
      setRestartBusy('');
    }
  }

  async function loadRemovalAssessment(device) {
    const nodeId = device?.id;
    if (!nodeId) return;
    setRemoveCandidate(device);
    setRemoveAssessment(device?.removal_assessment || null);
    setRemoveAssessmentLoading(true);
    setActionError(null);
    removalFlow.review(nodeId);
    try {
      const response = await liteApi.deviceRemovalAssessment(nodeId);
      setRemoveAssessment(response);
      removalFlow.assessmentReady(response);
    } catch (err) {
      removalFlow.fail(err);
      setActionError(err.message);
    } finally {
      setRemoveAssessmentLoading(false);
    }
  }

  function closeRemovalReview() {
    if (removeBusy) return;
    removalFlow.cancel();
    setRemoveCandidate(null);
    setRemoveAssessment(null);
  }

  async function removeOldDevice() {
    const nodeId = removeCandidate?.id;
    if (!nodeId || !removeAssessment?.safe_to_remove) return;
    removalFlow.submit();
    setRemoveBusy(true);
    setActionError(null);
    setResult(null);
    try {
      const response = await liteApi.removeDevice(nodeId, {
        reason: 'Old device cleanup from Lite Devices tab',
        assessment_revision: removeAssessment.assessment_revision || '',
        expected_awareness_revision: Number(removeAssessment.awareness_revision || 0),
      });
      removalFlow.accepted();
      removalFlow.verify();
      removalFlow.complete();
      setResult(response);
      setRemoveCandidate(null);
      setRemoveAssessment(null);
      setInvite(null);
      refresh();
    } catch (err) {
      const currentAssessment = err?.payload?.detail?.assessment;
      if (err?.status === 409 && currentAssessment) {
        setRemoveAssessment(currentAssessment);
        removalFlow.stale(err.message);
        removalFlow.assessmentReady(currentAssessment);
      } else {
        removalFlow.fail(err);
      }
      setActionError(err.message);
    } finally {
      setRemoveBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Devices"
        title="My Devices"
        description="See this device and any others connected to your Pocket Lab. Add a new device when you are ready to expand."
        actions={<LiteRefreshButton scope="devices" refresh={refresh} cacheStatus={cacheStatus} error={error} refreshing={refreshing} />}
      />

      <section className="lite-devices-hero">
        <div className="lite-devices-hero-copy">
          <div className="lite-home-pill">
            <span className="lite-ready-dot" />
            {remoteAccessReady ? (onlineDevices > 0 ? 'Devices online' : 'Remote access ready') : 'Remote access not ready'}
          </div>
          <h2>Keep your devices easy to find and easy to trust.</h2>
          <p>
            Check which devices are available, when they were last seen, and add another device without handling setup details manually.
          </p>
        </div>

        <div className="lite-devices-count-card">
          <div className="lite-devices-orbit">
            <Network className="h-7 w-7" />
          </div>
          <span>Connected now</span>
          <strong>{onlineDevices}</strong>
          <p>{healthAttentionCount > 0 ? `${healthAttentionCount} health item${healthAttentionCount === 1 ? '' : 's'} to review` : `${devices.length} total device${devices.length === 1 ? '' : 's'} known`}</p>
        </div>
      </section>

      <section className={`lite-remote-access-panel ${remoteAccessReady ? 'lite-remote-access-ready' : 'lite-remote-access-not-ready'}`} aria-live="polite">
        <div className="lite-remote-access-icon">
          <Network className="h-5 w-5" />
        </div>
        <div className="lite-remote-access-copy">
          <span>Remote access</span>
          <strong>{remoteAccessReady ? 'Remote access ready' : 'Remote access not ready'}</strong>
          <p>{remoteAccess?.summary || 'Pocket Lab is checking whether private-network device access is available.'}</p>
        </div>
        {remoteAccessReady && remoteAccess?.ip ? (
          <div className="lite-remote-access-ip">
            <span>Tailscale IP</span>
            <code>{remoteAccess.ip}</code>
          </div>
        ) : null}
      </section>

      <div className="lite-devices-layout">
        <details className="lite-devices-add-disclosure">
          <summary>
            <span>Expand your workspace</span>
            <strong>Add a device</strong>
            <small>Create a protected invite only when you need one.</small>
          </summary>
          <GlassCard className="lite-devices-add-card">
          <div className="lite-devices-card-head">
            <div className="lite-devices-mini-icon">
              <Network className="h-5 w-5" />
            </div>
            <span className="lite-devices-soft-badge">Add safely</span>
          </div>

          <h2>Add a device</h2>
          <p>
            Create a simple invite for another phone, tablet, or small server you want to connect.
          </p>

          <label className="lite-devices-field-label" htmlFor="device-name">
            Device name
          </label>
          <input
            id="device-name"
            className="pocket-input lite-devices-input"
            value={hostname}
            onChange={(event) => {
              setHostname(event.target.value);
              setServerConflict(null);
              addDeviceFlow.enterDevice(event.target.value, selectedRole);
            }}
            placeholder="Optional, for example: Kitchen tablet"
            aria-label="Device name"
          />

          {activeNameConflict ? (
            <div className="lite-devices-name-conflict" role="alert">
              <strong>A device with this name already exists.</strong>
              <span>{deviceDuplicateMessage(activeNameConflict)}</span>
            </div>
          ) : null}

          <div className="lite-devices-field-label">Select a role</div>
          <div className="lite-role-selector" role="radiogroup" aria-label="Device role">
            {DEVICE_ROLE_OPTIONS.map((role) => (
              <button
                key={role.value}
                type="button"
                className={`lite-role-card ${selectedRole === role.value ? 'lite-role-card-selected' : ''}`}
                onClick={() => {
                  setSelectedRole(role.value);
                  setServerConflict(null);
                  addDeviceFlow.enterDevice(candidateDeviceName, role.value);
                }}
                role="radio"
                aria-checked={selectedRole === role.value}
              >
                <strong>{role.label}</strong>
                <span>{role.description}</span>
              </button>
            ))}
          </div>

          <div className="lite-devices-safe-note">
            <strong>What happens next</strong>
            <span>Pocket Lab prepares an invite. Open it on the new device while it is connected to the same Pocket Lab private network.</span>
          </div>

          <LiteFlowStatusPanel
            title="Add Device"
            label={addDeviceFlow.label}
            steps={addDeviceFlow.steps}
            note={addDeviceFlow.writeBlocked ? addDeviceFlow.blockedReason : 'Invite creation stays backend-owned.'}
            className="mt-4"
          />

          <div className="mt-5">
            <LiteButton onClick={addDevice} disabled={addDeviceDisabled}>
              {busy ? 'Preparing invite...' : (addDeviceFlow.writeBlocked ? 'Reconnect to continue' : activeNameConflict ? 'Device already added' : 'Add Device')}
            </LiteButton>
          </div>

          {result?.status === 'queued' && !latestInvite ? (
            <StateSurface
              tone="empty"
              title="Preparing invite..."
              description="Pocket Lab is getting the invite ready. The device list will refresh automatically."
              className="mt-4"
            />
          ) : null}

          {latestInvite ? (
            <div className="lite-invite-card" aria-live="polite">
              <div className="lite-invite-card-header">
                <div>
                  <span>Invite ready</span>
                  <strong>{latestInvite.hostname || hostname || 'New device'}</strong>
                </div>
                <StatusBadge status="healthy">Ready</StatusBadge>
              </div>

              <div className="lite-invite-card-body">
                <div>
                  <span>Role</span>
                  <strong>{latestInvite.role_label || selectedRoleLabel}</strong>
                </div>
                <div>
                  <span>Expires at</span>
                  <strong>{formatLiteTime(latestInvite.expires_at)}</strong>
                </div>
              </div>

              <p>Run this in Termux on the new phone. Pocket Lab will set up the secure connection and start the device agent automatically.</p>

              {inviteCommand(latestInvite) ? (
                <>
                  <div className="lite-invite-command" aria-label="Connect this device command">
                    <span>Connect this device</span>
                    <code>{inviteCommand(latestInvite)}</code>
                  </div>
                  <div className="lite-invite-actions">
                    <LiteButton onClick={copyInvite} tone="secondary">
                      <Copy className="h-4 w-4" /> {copied ? 'Copied' : 'Copy command'}
                    </LiteButton>
                    <LiteRefreshButton scope="devices" refresh={refresh} cacheStatus={cacheStatus} error={error} refreshing={refreshing} label="Refresh devices" tone="secondary" />
                  </div>

                  <details className="lite-invite-details">
                    <summary>What this does</summary>
                    <ul>
                      <li>Installs only the small required tools.</li>
                      <li>Saves this device’s connection file.</li>
                      <li>Checks the secure Pocket Lab connection.</li>
                      <li>Downloads Pocket Lab Lite if needed.</li>
                      <li>Starts the small device agent.</li>
                      <li>The device appears Online when heartbeats arrive.</li>
                    </ul>
                  </details>

                  <details className="lite-invite-details">
                    <summary>Troubleshooting</summary>
                    <ol>
                      <li>Check that Tailscale is connected.</li>
                      <li>Run: <code>source ~/.pocketlab-lite-agent.env && echo $POCKETLAB_NATS_URL</code></li>
                      <li>The value should not be <code>nats://127.0.0.1:4222</code> on a secondary phone.</li>
                      <li>Run: <code>tail -n 80 ~/pocketlab-agent-*.log</code></li>
                    </ol>
                  </details>
                </>
              ) : (
                <span className="lite-invite-muted">Invite details were created earlier. Create a new invite if you need to copy the command again.</span>
              )}
            </div>
          ) : null}
          </GlassCard>
        </details>

        <section className="lite-devices-list-area">
          <div className="lite-devices-section-title">
            <div>
              <p>Fleet</p>
              <h2>Devices</h2>
              <small>Current connection, system identity, and health at a glance.</small>
            </div>
            <div className="lite-devices-section-metrics" aria-label="Device totals">
              <span><strong>{onlineDevices}</strong> online</span>
              <span><strong>{devices.length}</strong> total</span>
              {healthAttentionCurrent ? <span><strong>{healthAttentionCount}</strong> health attention</span> : null}
            </div>
          </div>

          {error ? (
            <StateSurface
              tone="degraded"
              title="Device list needs a moment"
              description={error}
              className="mb-4"
            />
          ) : null}

          {restartProgress ? (
            <GlassCard className="lite-device-restart-panel" aria-live="polite">
              <div className="lite-device-restart-panel-head">
                <div>
                  <span>Restart agent</span>
                  <h3>{restartProgressTitle(restartProgress)}</h3>
                </div>
                <button
                  type="button"
                  className="lite-device-remove-close"
                  onClick={() => setRestartProgress(null)}
                  aria-label="Close restart progress"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
              <p className="lite-device-restart-copy">
                {restartProgress.summary || 'Pocket Lab is checking whether the device reports back after the restart request.'}
              </p>
              <div className="lite-device-restart-device">
                <span>Device</span>
                <strong>{restartProgress.device_name || restartProgress.node_id}</strong>
              </div>
              <ol className="lite-device-restart-steps">
                {safeRestartSteps(restartProgress).map((step) => (
                  <li key={step.id || step.label} className={`lite-device-restart-step lite-device-restart-step-${step.state || 'waiting'}`}>
                    <span className="lite-device-restart-step-dot" aria-hidden="true" />
                    <div>
                      <strong>{step.label}</strong>
                      <p>{step.detail}</p>
                    </div>
                    <em>{restartStepStateLabel(step.state)}</em>
                  </li>
                ))}
              </ol>
              {['waiting', 'agent_stopped', 'repairing'].includes(String(restartProgress.status || '').toLowerCase()) ? (
                <p className="lite-device-restart-hint">
                  If the device agent is stopped, the local supervisor should start it. If this phone does not have the supervisor yet, open Termux on that phone and start it once.
                </p>
              ) : null}
            </GlassCard>
          ) : null}

          {removeCandidate ? (
            <GlassCard className="lite-device-remove-panel">
              <div className="lite-device-remove-panel-head">
                <div>
                  <span>Remove old device</span>
                  <h3>{removeCandidate.name || 'Selected device'}</h3>
                </div>
                <button
                  type="button"
                  className="lite-device-remove-close"
                  onClick={closeRemovalReview}
                  aria-label="Close remove old device review"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              <p className="lite-device-remove-copy">
                Pocket Lab checks hosted apps, backups, command delivery, recovery, and protected server responsibilities before removal.
              </p>

              <div className="lite-device-remove-facts">
                <div><span>Status</span><strong>{deviceStatusLabel(removeCandidate.status)}</strong></div>
                <div><span>Connection</span><strong>{deviceConnectionLabel(removeCandidate)}</strong></div>
                <div><span>Role</span><strong>{removeCandidate.role_label || roleLabel(removeCandidate.role)}</strong></div>
                <div><span>Last seen</span><strong>{formatLiteTime(removeCandidate.last_seen)}</strong></div>
              </div>

              <ul className="lite-device-remove-safety">
                <li>This removes the saved record from this Pocket Lab server.</li>
                <li>It does not wipe the phone.</li>
                <li>It does not uninstall Pocket Lab.</li>
                <li>It does not stop a running agent on that device.</li>
              </ul>

              {removeAssessmentLoading ? <p className="lite-device-remove-assessment-state">Checking device responsibilities…</p> : null}

              {Array.isArray(removeAssessment?.blockers) && removeAssessment.blockers.length ? (
                <div className="lite-device-removal-impact is-blocked">
                  <strong>Removal blocked</strong>
                  <ul>{removeAssessment.blockers.map((item) => <li key={item.code || item.summary}>{item.summary}</li>)}</ul>
                </div>
              ) : null}

              {Array.isArray(removeAssessment?.warnings) && removeAssessment.warnings.length ? (
                <div className="lite-device-removal-impact is-warning">
                  <strong>Review before removal</strong>
                  <ul>{removeAssessment.warnings.map((item) => <li key={item.code || item.summary}>{item.summary}</li>)}</ul>
                </div>
              ) : null}

              {removalFlow.isConfirming ? (
                <p className="lite-device-remove-final-warning" role="alert">
                  Confirm that you want to remove this saved device record. The remote agent is not stopped or uninstalled.
                </p>
              ) : null}

              <div className="lite-device-remove-actions">
                {removalFlow.isConfirming ? (
                  <LiteButton tone="danger" onClick={removeOldDevice} disabled={removeBusy || !removeAssessment?.safe_to_remove}>
                    {removeBusy ? 'Removing...' : 'Confirm removal'}
                  </LiteButton>
                ) : (
                  <LiteButton
                    tone="danger"
                    onClick={removalFlow.confirm}
                    disabled={removeAssessmentLoading || !removeAssessment?.safe_to_remove || removeBusy || savedStateOnly || backendReachable === false}
                  >
                    Continue to confirmation
                  </LiteButton>
                )}
                <LiteButton tone="secondary" onClick={closeRemovalReview} disabled={removeBusy}>
                  Keep device
                </LiteButton>
              </div>
            </GlassCard>
          ) : null}

          {loading ? <LoadingCard label="Loading devices..." /> : null}

          {activeDetailsDevice ? (
            <div ref={detailsPanelRef} tabIndex={-1} className="lite-device-details-focus-anchor">
              <Suspense fallback={<GlassCard className="lite-device-details-panel"><p>Loading device details…</p></GlassCard>}>
                <DeviceDetailsLazy
                  device={activeDetailsDevice}
                  onClose={closeDeviceDetails}
                  onChooseModel={() => { triggerHapticFeedback(12); setDeviceModelPickerId(activeDetailsDevice?.id); }}
                />
              </Suspense>
            </div>
          ) : null}

          {modelPickerDevice ? (
            <Suspense fallback={null}>
              <DeviceModelPickerLazy
                device={modelPickerDevice}
                open={Boolean(modelPickerDevice)}
                onClose={() => setDeviceModelPickerId('')}
                backendReachable={backendReachable}
                savedStateOnly={savedStateOnly}
              />
            </Suspense>
          ) : null}

          <LiteVirtualList
            items={devices}
            domain="devices"
            datasetKey="fleet:all"
            getItemKey={(device) => device?.id || device?.name}
            estimateSize={312}
            overscan={4}
            viewportHeight={720}
            lanes={2}
            compactLanes={1}
            laneGap={16}
            ariaLabel="Pocket Lab devices"
            className="lite-devices-list-shell"
            normalClassName="lite-devices-grid lite-devices-linked-grid lite-render-containment lite-render-containment--devices"
            virtualClassName="lite-devices-virtual-list"
            savedState={savedStateOnly}
            pinnedItemKeys={[detailsDeviceId, restartBusy].filter(Boolean)}
            emptyState={null}
            testId="devices-fleet-list"
            renderItem={(device) => {
              const key = String(device.id || device.name);
              return (
                <DeviceCard
                  device={device}
                  restartBusy={restartBusy}
                  removeBusy={removeBusy}
                  detailsOpen={detailsDeviceId === key}
                  onOpenDetails={() => { triggerHapticFeedback(10); setDetailsDeviceId(detailsDeviceId === key ? '' : key); }}
                  detailsButtonRef={(node) => {
                    if (node) detailsButtonRefs.current.set(key, node);
                    else detailsButtonRefs.current.delete(key);
                  }}
                  onRestartAgent={() => restartAgent(device)}
                  onRemoveDevice={() => loadRemovalAssessment(device)}
                />
              );
            }}
          />

          {!loading && devices.length === 0 ? (
            <StateSurface
              tone="empty"
              title="No devices yet"
              description="Add a device to create your first invite."
            />
          ) : null}
        </section>
      </div>

      <ResultNotice result={result?.status === 'removed' ? result : (latestInvite ? null : result)} error={actionError} />
    </>
  );
}

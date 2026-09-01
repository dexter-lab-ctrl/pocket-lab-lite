import React from 'react';
import { RefreshCw } from 'lucide-react';
import { NAV_ITEMS } from './liteNavigationConfig.js';
import { GlassCard, StatusBadge, StateSurface } from '../components/ui.jsx';
import { actionReference } from '../lib/liteApi.js';
import { useLiteUiStore, useLiteRefreshFeedback } from '../stores/liteUiStore.js';
import { triggerLiteHaptic } from '../lib/liteNativeFeedback.js';

export { GlassCard, StatusBadge, StateSurface };

function refreshStatusCopy(cacheStatus, error, refreshing = false, refreshFeedback = null) {
  const stale = Boolean(cacheStatus?.stale || error || ['saved', 'stale', 'expired', 'unreachable', 'failed'].includes(refreshFeedback?.result));
  return {
    stale,
    title: refreshFeedback?.title || cacheStatus?.title || (refreshing ? 'Refreshing…' : stale ? 'Showing saved state' : 'Fresh state'),
    summary: refreshFeedback?.summary || cacheStatus?.summary || error || (refreshing
      ? 'Pocket Lab is checking for fresh state.'
      : stale
        ? 'Pocket Lab is not reachable. Saved state only.'
        : 'Pocket Lab is showing the latest saved status.'),
    detail: refreshFeedback?.detail || cacheStatus?.detail || '',
  };
}

function refreshResultFromMeta(cacheStatus, error) {
  if (error) return 'unreachable';
  if (cacheStatus?.expired) return 'expired';
  if (cacheStatus?.stale) return 'saved';
  return 'fresh';
}

export function LiteSavedStateBanner() {
  return null;
}

export function LiteRefreshButton({
  refresh,
  cacheStatus,
  error,
  refreshing = false,
  label = 'Refresh',
  tone = 'secondary',
  className = '',
  scope = 'global',
}) {
  const [open, setOpen] = React.useState(false);
  const closeTimerRef = React.useRef(null);
  const beginRefresh = useLiteUiStore((state) => state.beginRefresh);
  const finishRefresh = useLiteUiStore((state) => state.finishRefresh);
  const refreshFeedback = useLiteRefreshFeedback(scope);
  const copy = refreshStatusCopy(cacheStatus, error, refreshing, refreshFeedback);

  React.useEffect(() => () => {
    if (closeTimerRef.current) window.clearTimeout(closeTimerRef.current);
  }, []);

  function showStatus() {
    setOpen(true);
    if (closeTimerRef.current) window.clearTimeout(closeTimerRef.current);
    closeTimerRef.current = window.setTimeout(() => setOpen(false), 4200);
  }

  async function handleClick(event) {
    event?.stopPropagation?.();
    beginRefresh(scope);
    showStatus();
    try {
      const maybeResult = refresh?.({ force: true });
      if (maybeResult && typeof maybeResult.then === 'function') {
        await maybeResult;
      }
      finishRefresh(scope, refreshResultFromMeta(cacheStatus, error));
    } catch (_error) {
      finishRefresh(scope, 'failed');
      // The owning screen already renders the safe error state.
    } finally {
      showStatus();
    }
  }

  return (
    <div className={`lite-refresh-control ${copy.stale ? 'is-stale' : 'is-live'} ${open ? 'is-open' : ''} ${className}`.trim()}>
      <LiteButton onClick={handleClick} tone={tone}>
        <RefreshCw className={`h-4 w-4 lite-refresh-icon ${refreshing ? 'is-refreshing' : ''}`} />
        {refreshing ? 'Refreshing…' : label}
      </LiteButton>
      {open ? (
        <div className="lite-refresh-status-popover" role="status" aria-live="polite">
          <span className="lite-refresh-status-dot" aria-hidden="true" />
          <div>
            <strong>{copy.title}</strong>
            <p>{copy.summary}</p>
            {copy.detail ? <small>{copy.detail}</small> : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}


export const DEVICE_ROLE_OPTIONS = [
  {
    value: 'compute',
    label: 'App Host',
    description: 'Runs apps and services for your Pocket Lab.',
  },
  {
    value: 'storage',
    label: 'Storage Node',
    description: 'Stores backups, files, or app data.',
  },
];

export { NAV_ITEMS };



export function resolveSafeAppOpenPath(itemOrUrl) {
  const raw = typeof itemOrUrl === 'string'
    ? itemOrUrl
    : itemOrUrl?.access?.open_url || itemOrUrl?.runtime?.url || itemOrUrl?.runtime?.route || '';
  const trimmed = String(raw || '').trim();

  if (!trimmed || trimmed.startsWith('//') || /^[a-z][a-z0-9+.-]*:/i.test(trimmed)) {
    return '';
  }

  if (!trimmed.startsWith('/apps/')) {
    return '';
  }

  try {
    const url = new URL(trimmed, window.location.origin);
    if (url.origin !== window.location.origin || !url.pathname.startsWith('/apps/')) {
      return '';
    }
    return `${url.pathname}${url.search}${url.hash}`;
  } catch (_error) {
    return '';
  }
}

export function appWorkspaceEmbedAllowed(item) {
  const access = item?.access || {};
  const workspace = item?.workspace || {};
  const runtime = item?.runtime || {};
  const embedOrigin = String(access.embed_origin || workspace.embed_origin || runtime.embed_origin || '').trim();

  if (embedOrigin) {
    if (typeof window === 'undefined') return false;
    if (window.location.origin !== embedOrigin) return false;
  }

  return Boolean(
    item?.embedAllowed === true ||
    access.embed_allowed === true ||
    access.workspace_embed === true ||
    access.workspace_embeddable === true ||
    access.frame_allowed === true ||
    workspace.embed_allowed === true ||
    workspace.embeddable === true ||
    workspace.mode === 'embed' ||
    runtime.embed_allowed === true
  );
}

export function roleLabel(value) {
  if (String(value || '').toLowerCase() === 'server_host') return 'Server host';
  return DEVICE_ROLE_OPTIONS.find((role) => role.value === value)?.label || 'App Host';
}

export const DEVICE_CAPABILITY_LABELS = {
  app_host: 'App Host',
  media_storage: 'Storage Node',
  backup_target: 'Backup Target',
  security_scanner: 'Security Scanner',
  compute: 'Compute',
};

export function deviceCapabilityLabels(device) {
  const explicit = Array.isArray(device?.capability_labels) ? device.capability_labels : [];
  const capabilitySource = Array.isArray(device?.capability_states) ? device.capability_states : device?.capabilities;
  const fromIds = Array.isArray(capabilitySource)
    ? capabilitySource.map((item) => {
      if (item && typeof item === 'object') {
        const status = String(item.status || 'unknown').toLowerCase();
        if (!['verified', 'ready'].includes(status)) return '';
        return item.label || DEVICE_CAPABILITY_LABELS[item.id] || String(item.id || '').replace(/_/g, ' ');
      }
      return DEVICE_CAPABILITY_LABELS[item] || String(item || '').replace(/_/g, ' ');
    }).filter(Boolean)
    : [];
  const labels = [...explicit, ...fromIds]
    .map((item) => String(item || '').trim())
    .filter(Boolean);
  return [...new Set(labels)].slice(0, 5);
}


export function normalizeDeviceCapabilityStatus(value, reasonCode = '') {
  const status = String(value || 'unknown').trim().toLowerCase();
  const reason = String(reasonCode || '').trim().toLowerCase();
  if (['verified', 'ready'].includes(status)) return 'verified';
  if (['verification_pending', 'available'].includes(status)) return 'pending';
  if (['unavailable', 'not_ready'].includes(status)) return 'unavailable';
  if (status === 'not_advertised' || reason === 'capability_not_advertised') return 'not_advertised';
  return 'unknown';
}

export function deviceCapabilitySummary(device) {
  const source = Array.isArray(device?.capability_states)
    ? device.capability_states
    : Array.isArray(device?.capabilities)
      ? device.capabilities
      : [];
  const counts = { verified: 0, pending: 0, unavailable: 0, notAdvertised: 0, unknown: 0, total: source.length };
  source.forEach((item) => {
    const state = item && typeof item === 'object'
      ? normalizeDeviceCapabilityStatus(item.status, item.reason_code)
      : 'unknown';
    if (state === 'verified') counts.verified += 1;
    else if (state === 'pending') counts.pending += 1;
    else if (state === 'unavailable') counts.unavailable += 1;
    else if (state === 'not_advertised') counts.notAdvertised += 1;
    else counts.unknown += 1;
  });
  const parts = [];
  if (counts.verified) parts.push(`${counts.verified} verified`);
  if (counts.pending) parts.push(`${counts.pending} pending`);
  if (counts.unavailable) parts.push(`${counts.unavailable} unavailable`);
  return { ...counts, label: parts.join(' · ') || 'No verified capabilities yet' };
}

export function deviceRuntimeServices(device) {
  return Array.isArray(device?.runtime_services) ? device.runtime_services : [];
}

export function deviceRestartAssessment(device) {
  return device?.restart_agent_assessment && typeof device.restart_agent_assessment === 'object'
    ? device.restart_agent_assessment
    : null;
}

export function deviceCommandDeliveryLabel(device) {
  const assessment = deviceRestartAssessment(device);
  if (assessment && typeof assessment.command_deliverable === 'boolean') {
    return assessment.command_deliverable ? 'Deliverable' : 'Temporarily unreachable';
  }
  const status = String(
    device?.dependencies?.command_delivery_status
      || device?.command_delivery_status
      || '',
  ).trim().toLowerCase();
  if (['deliverable', 'available', 'ready', 'online'].includes(status)) return 'Deliverable';
  if (['temporarily_unreachable', 'unreachable', 'offline', 'blocked'].includes(status)) return 'Temporarily unreachable';
  return 'Unknown';
}

export function canonicalDevicePresentation(device) {
  const connection = String(device?.connection_truth?.state || device?.connection || '').toLowerCase();
  const status = String(device?.status || '').toLowerCase();
  if (connection === 'repairing' || ['repairing', 'supervisor_repairing'].includes(status)) return { state: 'repairing', label: 'Repairing' };
  if (connection === 'stopped' || ['agent_stopped', 'stopped'].includes(status)) return { state: 'agent_stopped', label: 'Agent stopped' };
  if (connection === 'offline' || ['offline', 'failed', 'unhealthy', 'degraded', 'stale'].includes(status)) return { state: 'offline', label: 'Offline' };
  if (connection === 'online') return { state: 'online', label: 'Online' };
  if (connection === 'joining' || ['joining', 'accepted', 'setup_started'].includes(status)) return { state: 'joining', label: 'Joining' };
  if (connection === 'waiting' || ['pending', 'invited', 'invite_sent'].includes(status)) return { state: 'waiting', label: 'Waiting' };
  return { state: 'unknown', label: 'Checking' };
}

export function deviceConnectionLabel(device) {
  return canonicalDevicePresentation(device).label;
}

export function canRestartDeviceAgent(device) {
  const assessment = device?.restart_agent_assessment;
  if (assessment && typeof assessment === 'object') return assessment.allowed === true;
  const role = String(device?.role || '').toLowerCase();
  const connection = String(device?.connection_truth?.state || device?.connection || '').toLowerCase();
  const supervisorFreshness = String(device?.supervisor_status_freshness || '').toLowerCase();
  const agentState = String(device?.agent_process_status || device?.agent_status || '').toLowerCase();
  if (!device?.id || role === 'server_host' || device?.is_current || device?.isCurrent) return false;
  if (connection !== 'online' || supervisorFreshness !== 'fresh') return false;
  return ['stopped', 'offline', 'errored', 'error', 'failed', 'unhealthy', 'unknown'].includes(agentState);
}

export function canRemoveDevice(device) {
  const role = String(device?.role || '').toLowerCase();
  const connection = String(device?.connection || '').toLowerCase();
  const status = String(device?.status || '').toLowerCase();

  if (!device?.id || device?.is_current || device?.isCurrent) return false;
  if (role === 'server_host') return false;

  const assessment = device?.removal_assessment;
  const staleness = String(device?.staleness_state || device?.last_seen_state?.staleness_state || '').toLowerCase();
  if (assessment && typeof assessment === 'object' && (assessment.allowed ?? assessment.safe_to_remove)) return true;
  return ['joining', 'waiting', 'offline', 'stale'].includes(connection)
    || ['joining', 'pending', 'invited', 'offline', 'stale', 'agent_stopped'].includes(status)
    || ['stale', 'review_recommended'].includes(staleness);
}

export function normalizeDeviceName(value) {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_.-]+/g, '-')
    .replace(/^[-._]+|[-._]+$/g, '');
}

export function findDeviceNameConflict(name, devices = []) {
  const wanted = normalizeDeviceName(name);
  if (!wanted) return null;

  return devices.find((device) => {
    const identities = [device?.id, device?.node_id, device?.hostname, device?.name]
      .map(normalizeDeviceName)
      .filter(Boolean);
    return identities.includes(wanted);
  }) || null;
}

export function deviceDuplicateMessage(device) {
  if (!device) return '';
  const connection = String(device?.connection || '').toLowerCase();
  const status = String(device?.status || '').toLowerCase();

  if (connection === 'online' || ['healthy', 'active', 'online', 'ready'].includes(status)) {
    return 'This device is already connected. Use a different name if this is another phone.';
  }
  if (connection === 'joining' || ['joining', 'accepted', 'setup_started'].includes(status)) {
    return 'This device is already joining. Use the existing invite or wait for the device to connect.';
  }
  if (connection === 'waiting' || ['pending', 'invited', 'invite_sent'].includes(status)) {
    return 'An invite for this device is already in progress. Use the existing invite or wait for the device to connect.';
  }
  return 'An old device record already uses this name. Remove the old device record before creating a new invite.';
}

export function deviceStatusLabel(status) {
  const value = String(status || '').toLowerCase().replace(/[\s-]+/g, '_');
  if (['pending', 'invited', 'invite_sent'].includes(value)) return 'Invite sent';
  if (['joining', 'accepted', 'setup_started'].includes(value)) return 'Joining';
  if (['agent_stopped', 'stopped'].includes(value)) return 'Agent stopped';
  if (['repairing', 'supervisor_repairing'].includes(value)) return 'Repairing';
  return backendLabel(status, {
    ready: 'Online',
    healthy: 'Online',
    review: 'Review',
    danger: 'Offline',
    checking: 'Checking',
  });
}

export async function copyTextToClipboard(text) {
  if (!text) return false;
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch (_error) {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.setAttribute('readonly', '');
    textarea.style.position = 'fixed';
    textarea.style.left = '-9999px';
    document.body.appendChild(textarea);
    textarea.select();
    const copied = document.execCommand('copy');
    document.body.removeChild(textarea);
    return copied;
  }
}

export function serviceTone(status) {
  const value = String(status || 'unknown').toLowerCase();
  if (['healthy', 'ready', 'online', 'success'].includes(value)) return 'healthy';
  if (['degraded', 'warning', 'needs_attention'].includes(value)) return 'degraded';
  if (['unhealthy', 'failed', 'error'].includes(value)) return 'unhealthy';
  return value || 'unknown';
}

export function normalizeBackendState(status) {
  const value = String(status || 'unknown').toLowerCase().replace(/[\s-]+/g, '_');

  if (['healthy', 'ready', 'online', 'success', 'succeeded', 'auto_approved'].includes(value)) {
    return 'ready';
  }

  if (['review', 'degraded', 'warning', 'needs_attention', 'pending', 'invited', 'invite_sent', 'pending_approval', 'approval_required', 'waiting_for_approval', 'paused', 'repairing', 'supervisor_repairing'].includes(value)) {
    return 'review';
  }

  if (['danger', 'unhealthy', 'failed', 'failure', 'error', 'blocked', 'unavailable', 'agent_stopped', 'stopped'].includes(value)) {
    return 'danger';
  }

  return 'checking';
}

export function backendBadgeStatus(status) {
  const state = normalizeBackendState(status);
  if (state === 'ready') return 'healthy';
  if (state === 'review') return 'degraded';
  if (state === 'danger') return 'unhealthy';
  return 'unknown';
}

export function backendLabel(status, labels = {}) {
  const state = normalizeBackendState(status);
  const defaults = {
    ready: 'Ready',
    review: 'Review recommended',
    danger: 'Needs attention',
    checking: 'Checking',
  };
  return labels[state] || defaults[state];
}

export function backendHeroTitle(status, labels = {}) {
  return backendLabel(status, {
    ready: labels.ready || 'Everything looks good',
    review: labels.review || 'Review recommended',
    danger: labels.danger || 'Needs attention',
    checking: labels.checking || 'Checking status',
  });
}

export function securityFindingTone(severity) {
  const value = String(severity || '').toLowerCase();
  if (value === 'critical' || value === 'high') return 'danger';
  if (value === 'medium') return 'warning';
  return 'safe';
}

export function securityFindingLabel(finding) {
  if (!finding) return 'Review item';
  if (finding.category === 'protected_runtime_secret') return 'Protected runtime secret';
  if (finding.category === 'secret_exposure') return 'Secret-like value';
  if (finding.category === 'host_hardening') return 'Host readiness';
  if (finding.category === 'dependency_vulnerability') return 'Dependency risk';
  if (finding.category === 'missing_tool') return 'Tool needed';
  return finding.summary || 'Review item';
}

export function clampSecurityProgress(value, fallback = 8) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.max(0, Math.min(100, Math.round(parsed)));
}

export function parseSecurityTimestamp(value) {
  if (!value) return null;
  const parsed = new Date(value).getTime();
  return Number.isFinite(parsed) ? parsed : null;
}

export function formatSecurityRemainingSeconds(seconds, runStatus = 'running') {
  if (!Number.isFinite(seconds)) return 'calculating';
  const safeSeconds = Math.max(0, Math.round(seconds));
  if (runStatus === 'running' && safeSeconds <= 0) return 'finalizing';
  if (safeSeconds < 60) return `${Math.max(1, safeSeconds)} sec`;
  const minutes = Math.floor(safeSeconds / 60);
  const remainder = safeSeconds % 60;
  return remainder ? `${minutes}m ${String(remainder).padStart(2, '0')}s` : `${minutes} min`;
}

export function liveSecurityProgress(progress, runStatus, busy, nowMs) {
  const status = String(progress?.status || runStatus || '').toLowerCase();
  const estimatedTotal = Math.max(60, Number(progress?.estimated_total_seconds || 900));
  const startedAt = parseSecurityTimestamp(progress?.started_at);
  const serverElapsed = Number(progress?.elapsed_seconds || 0);
  const liveElapsed = startedAt ? Math.max(0, Math.round((nowMs - startedAt) / 1000)) : serverElapsed;
  const elapsed = Math.max(serverElapsed, liveElapsed);

  if (status === 'queued') {
    return {
      percent: 5,
      eta: 'working',
      elapsed,
      remaining: estimatedTotal,
    };
  }

  if (status === 'accepted' || status === 'working' || status === 'in_progress' || status === 'running' || busy) {
    const percentFromElapsed = Math.round((elapsed / estimatedTotal) * 100);
    const serverPercent = Number(progress?.percent || 0);
    const percent = Math.max(8, Math.min(95, Math.max(serverPercent, percentFromElapsed)));
    const remaining = Math.max(0, estimatedTotal - elapsed);
    return {
      percent,
      eta: 'working',
      elapsed,
      remaining,
    };
  }

  if (['succeeded', 'degraded', 'failed'].includes(status)) {
    return { percent: 100, eta: 'complete', elapsed, remaining: 0 };
  }

  return {
    percent: scanInProgressValue(runStatus, busy, progress),
    eta: progress?.estimated_remaining_label || 'calculating',
    elapsed,
    remaining: Number(progress?.estimated_remaining_seconds || estimatedTotal),
  };
}

export function securityProgressStage(progress, runStatus) {
  if (progress?.stage) return progress.stage;
  if (runStatus === 'queued') return 'Waiting for the backend worker';
  if (runStatus === 'running') return 'Running Lynis and Trivy';
  return 'Preparing safety check';
}

export function scanInProgressValue(runStatus, busy, progress) {
  if (progress?.percent !== undefined) return clampSecurityProgress(progress.percent, busy ? 8 : 0);
  if (runStatus === 'queued') return 5;
  if (runStatus === 'running') return 16;
  return busy ? 8 : 0;
}

export function triggerHapticFeedback(_pattern = 12) {
  // Compatibility bridge for existing Lite callers. New code should use the
  // semantic helper directly rather than choosing hardware patterns.
  return triggerLiteHaptic('accepted');
}

export function shortRunId(value) {
  const text = String(value || '');
  if (!text) return 'Not available yet';
  return text.length > 18 ? `${text.slice(0, 12)}…${text.slice(-6)}` : text;
}

export function formatSecurityDuration(seconds) {
  const value = Number(seconds);
  if (!Number.isFinite(value)) return 'duration unknown';
  const safe = Math.max(0, Math.round(value));
  if (safe < 60) return `${safe}s`;
  const minutes = Math.floor(safe / 60);
  const remainder = safe % 60;
  return remainder ? `${minutes}m ${String(remainder).padStart(2, '0')}s` : `${minutes} min`;
}

export function securityTrendLabel(value) {
  const delta = Number(value || 0);
  if (delta > 0) return `Up ${delta} pts`;
  if (delta < 0) return `Down ${Math.abs(delta)} pts`;
  return 'Stable';
}

export function securityTrendView(latest, previous) {
  if (!latest || !previous) {
    return { label: 'Baseline', detail: 'Future checks will show movement.', tone: 'neutral' };
  }
  const latestScore = Number(latest.score || 0);
  const previousScore = Number(previous.score || 0);
  const delta = latestScore - previousScore;
  if (delta > 0) {
    return {
      label: `Up ${delta} pts`,
      detail: `Latest ${latestScore} vs previous ${previousScore}.`,
      tone: 'safe',
    };
  }
  if (delta < 0) {
    return {
      label: `Down ${Math.abs(delta)} pts`,
      detail: `Latest ${latestScore} vs previous ${previousScore}. Usually caused by a new review item or partial check.`,
      tone: 'warning',
    };
  }
  return {
    label: 'Stable',
    detail: `Latest ${latestScore} matches the previous check.`,
    tone: 'neutral',
  };
}

export function securityDeltaTone(type, finding) {
  if (isSecurityTimeoutFinding(finding)) return 'warning';
  if (type === 'new') return 'warning';
  if (type === 'resolved') return 'safe';
  return 'neutral';
}

export function isSecurityTimeoutFinding(finding) {
  const summary = `${finding?.summary || ''} ${finding?.recommendation || ''}`.toLowerCase();
  return finding?.category === 'host_hardening' && summary.includes('timed out');
}

export function securityDeltaBadge(finding) {
  if (isSecurityTimeoutFinding(finding)) return 'recheck';
  if (finding?.delta_type === 'resolved') return 'resolved';
  if (finding?.delta_type === 'unchanged') return 'ongoing';
  return 'new';
}

export function securityDeltaTitle(finding) {
  if (isSecurityTimeoutFinding(finding)) return 'Host readiness partially checked';
  return securityFindingLabel(finding);
}

export function securityDeltaDescription(finding) {
  if (isSecurityTimeoutFinding(finding)) {
    return 'Lynis did not finish every host-readiness check before the timeout. This is usually a device speed, battery, or timeout condition, not evidence of compromise.';
  }
  return finding?.summary || finding?.recommendation || 'Security item recorded.';
}

export function securityDeltaAction(finding) {
  if (isSecurityTimeoutFinding(finding)) {
    return 'Run the check again while the device is charging, or increase the Lynis timeout for slower devices.';
  }
  return finding?.recommendation || '';
}

export function securityDeltaSummary(delta, previewItems = []) {
  const newCount = Number(delta?.new_count || 0);
  const resolvedCount = Number(delta?.resolved_count || 0);
  const unchangedCount = Number(delta?.unchanged_count || 0);
  const timeoutCount = previewItems.filter(isSecurityTimeoutFinding).length;
  if (timeoutCount && newCount === timeoutCount) {
    return `${timeoutCount} host-readiness check needs a re-run. No critical issue was found, but the latest check was partial.`;
  }
  if (newCount || resolvedCount || unchangedCount) {
    const parts = [];
    if (newCount) parts.push(`${newCount} new review item${newCount === 1 ? '' : 's'}`);
    if (resolvedCount) parts.push(`${resolvedCount} resolved`);
    if (unchangedCount) parts.push(`${unchangedCount} ongoing`);
    return `${parts.join(' · ')} since the previous completed check.`;
  }
  return delta?.summary || 'Future checks will show new, resolved, and ongoing items.';
}

export function securityExecutionStateTone(state) {
  if (state === 'done') return 'ready';
  if (state === 'active') return 'checking';
  if (state === 'review') return 'review';
  if (state === 'failed') return 'danger';
  return 'waiting';
}

export function securityExecutionStepGlyph(step, index) {
  if (step?.state === 'done') return '✓';
  if (step?.state === 'review') return '!';
  if (step?.state === 'failed') return '×';
  return index + 1;
}

export function securityToolStatusLabel(toolResult = {}) {
  const status = String(toolResult?.status || '').toLowerCase();
  if (status === 'completed') return 'Completed';
  if (status === 'timed_out') return 'Timed out';
  if (status === 'missing_tool') return 'Tool missing';
  if (status === 'partial') return 'Partial';
  if (status) return status.replace(/_/g, ' ');
  return 'Pending';
}

export function securityExecutionStateFromBackend(status) {
  const normalized = String(status || '').toLowerCase();
  if (normalized === 'completed' || normalized === 'succeeded') return 'done';
  if (normalized === 'running' || normalized === 'in_progress') return 'active';
  if (normalized === 'review' || normalized === 'partial' || normalized === 'timed_out' || normalized === 'missing_tool' || normalized === 'degraded') return 'review';
  if (normalized === 'failed' || normalized === 'error') return 'failed';
  return 'waiting';
}

export function securityExecutionStepLabel(state) {
  if (state === 'done') return 'Completed';
  if (state === 'active') return 'Running';
  if (state === 'review') return 'Needs review';
  if (state === 'failed') return 'Failed';
  return 'Waiting';
}

export function normalizeSecurityExecutionSteps(steps = []) {
  const normalized = steps.map((step) => ({ ...step }));
  const terminalStates = ['done', 'review', 'failed'];

  let activeIndex = normalized.findIndex((step) => step.state === 'active');
  let lastResolvedIndex = -1;

  normalized.forEach((step, index) => {
    if (terminalStates.includes(step.state)) {
      lastResolvedIndex = index;
    }
  });

  if (activeIndex >= 0) {
    normalized.forEach((step, index) => {
      if (index < activeIndex && (step.state === 'waiting' || step.state === 'active')) {
        step.state = 'done';
      }
      if (index > activeIndex && step.state === 'active') {
        step.state = 'waiting';
      }
    });
  }

  if (lastResolvedIndex >= 0) {
    normalized.forEach((step, index) => {
      if (index < lastResolvedIndex && step.state === 'waiting') {
        step.state = 'done';
      }
    });
  }

  const allTerminal = normalized.length > 0 && normalized.every((step) => terminalStates.includes(step.state));
  if (allTerminal) {
    normalized.forEach((step) => {
      if (step.state === 'waiting' || step.state === 'active') {
        step.state = 'done';
      }
    });
  }

  return normalized;
}

export function securityExecutionTimeline({ executionTimeline, currentRunId, runStatus, scanProgress, evidenceRun, toolResults, evidenceRefs, sbomSaved }) {
  const backendTimeline = Array.isArray(executionTimeline) ? executionTimeline : [];

  if (backendTimeline.length) {
    const keyTitleMap = {
      request_accepted: 'Request accepted',
      worker_picked_up: 'Worker picked it up',
      lynis_host_check: 'Lynis host check',
      trivy_dependency_secret_check: 'Trivy dependency & secret check',
      evidence_saved: 'Evidence saved',
    };

    const normalizedBackendSteps = backendTimeline.map((step, index) => {
      const key = String(step?.key || `step_${index + 1}`);
      return {
        key,
        title: step?.title || keyTitleMap[key] || `Step ${index + 1}`,
        detail: step?.detail || step?.summary || step?.message || 'Security step update.',
        state: securityExecutionStateFromBackend(step?.status),
      };
    });

    return normalizeSecurityExecutionSteps(normalizedBackendSteps);
  }

  const status = String(evidenceRun?.status || runStatus || '').toLowerCase();
  const terminal = ['succeeded', 'degraded', 'failed'].includes(status);
  const running = status === 'running';
  const queued = status === 'queued';
  const lynis = toolResults?.lynis || {};
  const trivy = toolResults?.trivy || {};
  const sameRunEvidence = Boolean(
    evidenceRun?.run_id &&
    currentRunId &&
    String(evidenceRun.run_id) === String(currentRunId)
  );
  const hasCurrentRunEvidence = terminal && Boolean(
    (sameRunEvidence && evidenceRun?.evidence_refs?.length) ||
    evidenceRefs?.length ||
    sbomSaved
  );

  const fallbackSteps = [
    {
      key: 'request_accepted',
      title: 'Request accepted',
      detail: queued ? 'FastAPI queued the check.' : 'FastAPI accepted the safety request.',
      state: queued ? 'active' : status ? 'done' : 'waiting',
    },
    {
      key: 'worker_picked_up',
      title: 'Worker picked it up',
      detail: running ? 'The backend worker is running local tools.' : terminal ? 'The backend worker finished the check.' : 'Waiting for the backend worker.',
      state: running || terminal ? 'done' : 'waiting',
    },
    {
      key: 'lynis_host_check',
      title: 'Lynis host check',
      detail: lynis.status ? securityToolStatusLabel(lynis) : 'Checks host readiness.',
      state:
        lynis.status === 'completed'
          ? 'done'
          : lynis.status === 'timed_out' || lynis.status === 'missing_tool'
            ? 'review'
            : running
              ? 'active'
              : terminal
                ? 'done'
                : 'waiting',
    },
    {
      key: 'trivy_dependency_secret_check',
      title: 'Trivy dependency & secret check',
      detail: trivy.status ? `${securityToolStatusLabel(trivy)}${trivy.sbom_saved ? ' · SBOM saved' : ''}` : 'Checks dependencies, config, secret-like values, and SBOM evidence.',
      state:
        trivy.status === 'completed'
          ? 'done'
          : trivy.status === 'partial' || trivy.status === 'missing_tool'
            ? 'review'
            : running && (lynis.status === 'completed' || lynis.status === 'timed_out' || lynis.status === 'missing_tool')
              ? 'active'
              : terminal
                ? 'done'
                : 'waiting',
    },
    {
      key: 'evidence_saved',
      title: 'Evidence saved',
      detail: hasCurrentRunEvidence ? `${evidenceRefs?.length || evidenceRun?.evidence_refs?.length || (sbomSaved ? 1 : 0)} sanitized file(s) ready.` : 'Sanitized evidence appears after completion.',
      state: hasCurrentRunEvidence || terminal ? 'done' : 'waiting',
    },
  ];

  return normalizeSecurityExecutionSteps(fallbackSteps);
}

export function PageHeader({ eyebrow = 'Pocket Lab Lite', title, description, actions }) {
  return (
    <div className="mb-5 flex flex-col gap-4 rounded-[2rem] border border-white/10 bg-slate-900/65 p-5 shadow-2xl shadow-black/20 backdrop-blur-xl sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        <p className="text-xs font-black uppercase tracking-[0.22em] text-cyan-200">{eyebrow}</p>
        <h1 className="mt-2 text-3xl font-black tracking-tight text-white sm:text-4xl">{title}</h1>
        {description ? <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-300">{description}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  );
}

export function LiteButton({ children, onClick, disabled = false, tone = 'primary', type = 'button', haptic = false, ariaLabel, title, className = '', buttonRef = null, ...buttonProps }) {
  const toneClass = {
    primary: 'pocket-button-primary',
    secondary: 'pocket-button-secondary',
    success: 'pocket-button-success',
    danger: 'pocket-button-danger',
  }[tone] || 'pocket-button-secondary';

  function handleClick(event) {
    if (disabled) return;
    if (haptic) triggerLiteHaptic('accepted');
    if (onClick) onClick(event);
  }

  return (
    <button
      {...buttonProps}
      ref={buttonRef}
      type={type}
      onClick={handleClick}
      disabled={disabled}
      aria-label={ariaLabel}
      title={title || ariaLabel}
      className={`pocket-button ${toneClass} ${className}`.trim()}
    >
      {children}
    </button>
  );
}

export function ResultNotice({ result, error }) {
  if (!result && !error) return null;
  if (error) {
    return <StateSurface tone="degraded" title="Needs attention" description={error} className="mt-4" />;
  }
  const reference = actionReference(result);
  return (
    <StateSurface
      tone="empty"
      title={result?.accepted ? 'Request sent safely' : 'Action recorded'}
      description={reference ? `Pocket Lab queued this through the control plane. Reference: ${reference}` : (result?.summary || 'Pocket Lab accepted the request.')}
      className="mt-4"
    />
  );
}

const LITE_OPERATIONAL_TONES = new Set(['ready', 'info', 'review', 'attention', 'blocked', 'danger', 'unknown', 'saved', 'stale', 'live', 'refreshing', 'completed', 'failed', 'running', 'waiting']);

export function operationalStoryPresentation(story = {}) {
  const state = String(story?.state || 'unknown').toLowerCase();
  const requestedTone = String(story?.tone || state || 'unknown').toLowerCase();
  let tone = LITE_OPERATIONAL_TONES.has(requestedTone) ? requestedTone : 'unknown';
  if (state === 'unknown') tone = 'unknown';
  if (state === 'saved' && ['ready', 'live'].includes(tone)) tone = 'saved';
  if (state === 'stale' && ['ready', 'live'].includes(tone)) tone = 'stale';
  const headline = String(story?.headline || '').trim() || 'Status not available';
  const summary = String(story?.summary || '').trim();
  const consequence = String(story?.consequence || '').trim();
  const attention = String(story?.attention || '').trim();
  const freshness = story?.freshness && typeof story.freshness === 'object'
    ? {
        label: String(story.freshness.label || '').trim(),
        detail: String(story.freshness.detail || '').trim(),
        state: String(story.freshness.state || '').trim().toLowerCase(),
      }
    : null;

  const stateLabel = state
    ? state.replaceAll('_', ' ').replace(/\b\w/g, (character) => character.toUpperCase())
    : 'Unknown';

  return { state, stateLabel, tone, headline, summary, consequence, attention, freshness };
}

function StoryAction({ action, fallbackTone = 'secondary' }) {
  if (!action?.label) return null;
  return (
    <div className="lite-operational-story-action">
      <LiteButton
        onClick={action.onClick}
        disabled={Boolean(action.disabled)}
        tone={action.tone || fallbackTone}
        ariaLabel={action.ariaLabel || action.label}
        aria-expanded={typeof action.ariaExpanded === 'boolean' ? action.ariaExpanded : undefined}
        buttonRef={action.buttonRef}
      >
        {action.label}
      </LiteButton>
      {action.disabled && action.disabledReason ? <small>{action.disabledReason}</small> : null}
    </div>
  );
}

export function LiteOperationalStory({ story, primaryAction, manageAction, className = '' }) {
  const presentation = operationalStoryPresentation(story);
  const hasActions = Boolean(primaryAction?.label || manageAction?.label);

  return (
    <section className={`lite-operational-story is-${presentation.tone} ${className}`.trim()} aria-live="polite">
      <div className="lite-operational-story-copy">
        <span>{presentation.stateLabel}</span>
        <strong>{presentation.headline}</strong>
        {presentation.summary ? <p>{presentation.summary}</p> : null}
        {presentation.consequence ? <p className="lite-operational-story-consequence">{presentation.consequence}</p> : null}
        {presentation.attention ? <p className="lite-operational-story-attention">{presentation.attention}</p> : null}
        {presentation.freshness?.label ? <small className={`lite-operational-story-freshness is-${presentation.freshness.state || 'unknown'}`.trim()}>{presentation.freshness.label}{presentation.freshness.detail ? ` · ${presentation.freshness.detail}` : ''}</small> : null}
      </div>
      {hasActions ? (
        <div className="lite-operational-story-actions">
          <StoryAction action={primaryAction} fallbackTone="primary" />
          <StoryAction action={manageAction} />
        </div>
      ) : null}
    </section>
  );
}

export function LiteActionRow({ label, value = '', summary = '', action, disabledReason = '', attention = false, className = '' }) {
  return (
    <div className={`lite-action-row ${attention ? 'is-attention' : ''} ${className}`.trim()}>
      <div>
        <strong>{label}</strong>
        {summary ? <p>{summary}</p> : null}
        {disabledReason ? <small>{disabledReason}</small> : null}
      </div>
      <div className="lite-action-row-trailing">
        {value ? <span>{value}</span> : null}
        {action?.label ? <LiteButton onClick={action.onClick} disabled={Boolean(action.disabled)} tone={action.tone || 'secondary'} ariaLabel={action.ariaLabel || action.label}>{action.label}</LiteButton> : null}
      </div>
    </div>
  );
}

export function LiteOutcomeNotice({ outcome, className = '' }) {
  if (!outcome?.headline && !outcome?.summary) return null;
  const tone = LITE_OPERATIONAL_TONES.has(String(outcome?.tone || '').toLowerCase())
    ? String(outcome.tone).toLowerCase()
    : 'unknown';
  return (
    <section className={`lite-outcome-notice is-${tone} ${className}`.trim()} aria-live="polite">
      <strong>{outcome.headline || 'Outcome not reported'}</strong>
      {outcome.summary ? <p>{outcome.summary}</p> : null}
      {outcome.consequence ? <p>{outcome.consequence}</p> : null}
      {outcome.nextAction ? <small>{outcome.nextAction}</small> : null}
    </section>
  );
}

export function LiteTechnicalDetails({ summary = 'Technical details', children, className = '' }) {
  if (!children) return null;
  return <details className={`lite-technical-details ${className}`.trim()}><summary>{summary}</summary><div>{children}</div></details>;
}

export function LoadingCard({ label = 'Loading Pocket Lab Lite...' }) {
  return (
    <GlassCard>
      <div className="h-3 w-40 animate-pulse rounded-full bg-white/10" />
      <div className="mt-4 h-20 animate-pulse rounded-3xl bg-white/5" />
      <p className="mt-4 text-sm text-slate-400">{label}</p>
    </GlassCard>
  );
}


export function LiteFlowStatusPanel({ title = 'Guided step', label = 'Getting ready', steps = [], note = '', tone = 'info', className = '' }) {
  const safeSteps = Array.isArray(steps) ? steps.filter(Boolean) : [];
  if (!safeSteps.length && !label && !note) return null;

  return (
    <div className={`lite-flow-status-panel lite-flow-status-${tone} ${className}`.trim()} aria-live="polite">
      <div className="lite-flow-status-head">
        <span>{title}</span>
        <strong>{label}</strong>
      </div>
      {note ? <p>{note}</p> : null}
      {safeSteps.length ? (
        <ol className="lite-flow-status-steps">
          {safeSteps.map((step) => (
            <li key={step.id || step.label} className={`lite-flow-status-step is-${step.state || 'waiting'}`}>
              <span aria-hidden="true" />
              <em>{step.label}</em>
            </li>
          ))}
        </ol>
      ) : null}
    </div>
  );
}

export function friendlyOverallLabel(overall) {
  return backendLabel(overall, {
    ready: 'Everything looks good',
    review: 'A few things need attention',
    danger: 'Needs attention',
    checking: 'Checking your setup',
  });
}

export function deviceLinkState(device) {
  const role = String(device?.role || '').toLowerCase();
  if (role === 'server_host' || device?.is_current || device?.isCurrent) return 'server';
  const state = canonicalDevicePresentation(device).state;
  if (state === 'online') return 'joined';
  if (state === 'repairing') return 'repairing';
  return 'disconnected';
}

export function restartProgressTitle(progress = {}) {
  const status = String(progress?.status || '').toLowerCase();
  if (status === 'completed') return 'Device is back online';
  if (status === 'agent_stopped') return 'Device agent is stopped';
  if (status === 'repairing') return 'Supervisor is repairing the agent';
  if (status === 'failed') return 'Restart needs attention';
  if (status === 'starting') return 'Preparing restart';
  return 'Restart in progress';
}

export function restartStepStateLabel(state) {
  const value = String(state || 'waiting').toLowerCase();
  if (value === 'complete') return 'Done';
  if (value === 'active') return 'Working';
  if (value === 'failed') return 'Needs help';
  return 'Waiting';
}

export function safeRestartSteps(progress = {}) {
  return Array.isArray(progress?.steps) ? progress.steps.filter(Boolean) : [];
}

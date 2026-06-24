import React from 'react';
import {
  Activity,
  Database,
  FileCheck,
  Fingerprint,
  LayoutGrid,
  Network,
  ShieldCheck,
} from 'lucide-react';
import { GlassCard, StatusBadge, StateSurface } from '../components/ui.jsx';
import { actionReference } from '../lib/liteApi.js';

export { GlassCard, StatusBadge, StateSurface };

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

export const NAV_ITEMS = [
  { id: 'home', label: 'Home', icon: Activity },
  { id: 'catalog', label: 'App Catalog', icon: LayoutGrid },
  { id: 'identity', label: 'Identity & Access', icon: Fingerprint },
  { id: 'security', label: 'Security', icon: ShieldCheck },
  { id: 'devices', label: 'Devices', icon: Network },
  { id: 'rules', label: 'Rules', icon: FileCheck },
  { id: 'recovery', label: 'Recovery', icon: Database },
];

export function roleLabel(value) {
  return DEVICE_ROLE_OPTIONS.find((role) => role.value === value)?.label || 'App Host';
}

export function deviceConnectionLabel(device) {
  const connection = String(device?.connection || '').toLowerCase();
  const role = String(device?.role || '').toLowerCase();
  const status = String(device?.status || '').toLowerCase();

  if (role === 'server_host') return 'Online';
  if (connection === 'stopped' || ['agent_stopped', 'stopped'].includes(status)) return 'Stopped';
  if (connection === 'repairing' || ['repairing', 'supervisor_repairing'].includes(status)) return 'Repairing';
  if (connection === 'online' || ['healthy', 'active', 'online', 'ready'].includes(status)) return 'Online';
  if (connection === 'joining' || ['joining', 'accepted', 'setup_started'].includes(status)) return 'Joining';
  if (connection === 'waiting' || ['pending', 'invited', 'invite_sent'].includes(status)) return 'Waiting';
  if (connection === 'offline' || ['offline', 'failed', 'unhealthy', 'degraded', 'stale'].includes(status)) return 'Offline';
  if (connection === 'unknown' && (device?.last_seen || device?.last_seen_at)) return 'Offline';

  return device?.remote_access ? 'Online' : 'Not setup yet';
}

export function canRestartDeviceAgent(device) {
  const role = String(device?.role || '').toLowerCase();
  if (!device?.id || role === 'server_host' || device?.is_current || device?.isCurrent) return false;
  const connection = String(device?.connection || '').toLowerCase();
  const status = String(device?.status || '').toLowerCase();
  return ['offline', 'unknown', 'stopped', 'repairing'].includes(connection) || ['offline', 'degraded', 'stale', 'unhealthy', 'failed', 'agent_stopped', 'repairing', 'supervisor_repairing'].includes(status);
}

export function canRemoveDevice(device) {
  const role = String(device?.role || '').toLowerCase();
  const connection = String(device?.connection || '').toLowerCase();
  const status = String(device?.status || '').toLowerCase();

  if (!device?.id || device?.is_current || device?.isCurrent) return false;
  if (role === 'server_host') return false;

  return ['joining', 'waiting', 'offline', 'stale'].includes(connection)
    || ['joining', 'pending', 'invited', 'offline', 'stale'].includes(status);
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
  const estimatedTotal = Math.max(60, Number(progress?.estimated_total_seconds || 180));
  const startedAt = parseSecurityTimestamp(progress?.started_at);
  const serverElapsed = Number(progress?.elapsed_seconds || 0);
  const liveElapsed = startedAt ? Math.max(0, Math.round((nowMs - startedAt) / 1000)) : serverElapsed;
  const elapsed = Math.max(serverElapsed, liveElapsed);

  if (status === 'queued') {
    return {
      percent: 5,
      eta: formatSecurityRemainingSeconds(estimatedTotal, status),
      elapsed,
      remaining: estimatedTotal,
    };
  }

  if (status === 'running' || busy) {
    const percentFromElapsed = Math.round((elapsed / estimatedTotal) * 100);
    const serverPercent = Number(progress?.percent || 0);
    const percent = Math.max(8, Math.min(95, Math.max(serverPercent, percentFromElapsed)));
    const remaining = Math.max(0, estimatedTotal - elapsed);
    return {
      percent,
      eta: formatSecurityRemainingSeconds(remaining, 'running'),
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

export function triggerHapticFeedback(pattern = 12) {
  try {
    if (typeof navigator !== 'undefined' && typeof navigator.vibrate === 'function') {
      navigator.vibrate(pattern);
    }
  } catch (_error) {
    // Haptics are optional and must never block a Lite action.
  }
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

export function LiteButton({ children, onClick, disabled = false, tone = 'primary', type = 'button', haptic = false }) {
  const toneClass = {
    primary: 'pocket-button-primary',
    secondary: 'pocket-button-secondary',
    success: 'pocket-button-success',
    danger: 'pocket-button-danger',
  }[tone] || 'pocket-button-secondary';

  function handleClick(event) {
    if (disabled) return;
    if (haptic) triggerHapticFeedback();
    if (onClick) onClick(event);
  }

  return (
    <button type={type} onClick={handleClick} disabled={disabled} className={`pocket-button ${toneClass}`}>
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

export function LoadingCard({ label = 'Loading Pocket Lab Lite...' }) {
  return (
    <GlassCard>
      <div className="h-3 w-40 animate-pulse rounded-full bg-white/10" />
      <div className="mt-4 h-20 animate-pulse rounded-3xl bg-white/5" />
      <p className="mt-4 text-sm text-slate-400">{label}</p>
    </GlassCard>
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
  const status = String(device?.status || '').toLowerCase();
  const connection = String(device?.connection || '').toLowerCase();

  if (role === 'server_host' || device?.is_current || device?.isCurrent) return 'server';
  if (connection === 'online' || ['healthy', 'active', 'online', 'ready'].includes(status)) return 'joined';
  if (connection === 'repairing' || ['repairing', 'supervisor_repairing'].includes(status)) return 'repairing';
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

import React, { useMemo, useState } from 'react';
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
import { GlassCard, StatusBadge, StateSurface } from '../components/ui.jsx';
import { useOnlineStatus } from '../hooks/useOnlineStatus.js';
import { useLiteResource, useLiteStatus } from '../hooks/useLiteStatus.js';
import { actionReference, formatLiteTime, liteApi } from '../lib/liteApi.js';


const DEVICE_ROLE_OPTIONS = [
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

function roleLabel(value) {
  return DEVICE_ROLE_OPTIONS.find((role) => role.value === value)?.label || 'App Host';
}

function deviceConnectionLabel(device) {
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

function canRestartDeviceAgent(device) {
  const role = String(device?.role || '').toLowerCase();
  if (!device?.id || role === 'server_host' || device?.is_current || device?.isCurrent) return false;
  const connection = String(device?.connection || '').toLowerCase();
  const status = String(device?.status || '').toLowerCase();
  return ['offline', 'unknown', 'stopped', 'repairing'].includes(connection) || ['offline', 'degraded', 'stale', 'unhealthy', 'failed', 'agent_stopped', 'repairing', 'supervisor_repairing'].includes(status);
}

function canRemoveDevice(device) {
  const role = String(device?.role || '').toLowerCase();
  const connection = String(device?.connection || '').toLowerCase();
  const status = String(device?.status || '').toLowerCase();

  if (!device?.id || device?.is_current || device?.isCurrent) return false;
  if (role === 'server_host') return false;

  return ['joining', 'waiting', 'offline', 'stale'].includes(connection)
    || ['joining', 'pending', 'invited', 'offline', 'stale'].includes(status);
}

function normalizeDeviceName(value) {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_.-]+/g, '-')
    .replace(/^[-._]+|[-._]+$/g, '');
}

function findDeviceNameConflict(name, devices = []) {
  const wanted = normalizeDeviceName(name);
  if (!wanted) return null;

  return devices.find((device) => {
    const identities = [device?.id, device?.node_id, device?.hostname, device?.name]
      .map(normalizeDeviceName)
      .filter(Boolean);
    return identities.includes(wanted);
  }) || null;
}

function deviceDuplicateMessage(device) {
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


function deviceStatusLabel(status) {
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

async function copyTextToClipboard(text) {
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

const NAV_ITEMS = [
  { id: 'home', label: 'Home', icon: Activity },
  { id: 'catalog', label: 'App Catalog', icon: LayoutGrid },
  { id: 'identity', label: 'Identity & Access', icon: Fingerprint },
  { id: 'security', label: 'Security', icon: ShieldCheck },
  { id: 'devices', label: 'Devices', icon: Network },
  { id: 'rules', label: 'Rules', icon: FileCheck },
  { id: 'recovery', label: 'Recovery', icon: Database },
];

function serviceTone(status) {
  const value = String(status || 'unknown').toLowerCase();
  if (['healthy', 'ready', 'online', 'success'].includes(value)) return 'healthy';
  if (['degraded', 'warning', 'needs_attention'].includes(value)) return 'degraded';
  if (['unhealthy', 'failed', 'error'].includes(value)) return 'unhealthy';
  return value || 'unknown';
}

function normalizeBackendState(status) {
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

function backendBadgeStatus(status) {
  const state = normalizeBackendState(status);
  if (state === 'ready') return 'healthy';
  if (state === 'review') return 'degraded';
  if (state === 'danger') return 'unhealthy';
  return 'unknown';
}

function backendLabel(status, labels = {}) {
  const state = normalizeBackendState(status);
  const defaults = {
    ready: 'Ready',
    review: 'Review recommended',
    danger: 'Needs attention',
    checking: 'Checking',
  };
  return labels[state] || defaults[state];
}

function backendHeroTitle(status, labels = {}) {
  return backendLabel(status, {
    ready: labels.ready || 'Everything looks good',
    review: labels.review || 'Review recommended',
    danger: labels.danger || 'Needs attention',
    checking: labels.checking || 'Checking status',
  });
}

function securityFindingTone(severity) {
  const value = String(severity || '').toLowerCase();
  if (value === 'critical' || value === 'high') return 'danger';
  if (value === 'medium') return 'warning';
  return 'safe';
}

function securityFindingLabel(finding) {
  if (!finding) return 'Review item';
  if (finding.category === 'protected_runtime_secret') return 'Protected runtime secret';
  if (finding.category === 'secret_exposure') return 'Secret-like value';
  if (finding.category === 'host_hardening') return 'Host readiness';
  if (finding.category === 'dependency_vulnerability') return 'Dependency risk';
  if (finding.category === 'missing_tool') return 'Tool needed';
  return finding.summary || 'Review item';
}

function clampSecurityProgress(value, fallback = 8) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.max(0, Math.min(100, Math.round(parsed)));
}

function parseSecurityTimestamp(value) {
  if (!value) return null;
  const parsed = new Date(value).getTime();
  return Number.isFinite(parsed) ? parsed : null;
}

function formatSecurityRemainingSeconds(seconds, runStatus = 'running') {
  if (!Number.isFinite(seconds)) return 'calculating';
  const safeSeconds = Math.max(0, Math.round(seconds));
  if (runStatus === 'running' && safeSeconds <= 0) return 'finalizing';
  if (safeSeconds < 60) return `${Math.max(1, safeSeconds)} sec`;
  const minutes = Math.floor(safeSeconds / 60);
  const remainder = safeSeconds % 60;
  return remainder ? `${minutes}m ${String(remainder).padStart(2, '0')}s` : `${minutes} min`;
}

function liveSecurityProgress(progress, runStatus, busy, nowMs) {
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

function securityProgressStage(progress, runStatus) {
  if (progress?.stage) return progress.stage;
  if (runStatus === 'queued') return 'Waiting for the backend worker';
  if (runStatus === 'running') return 'Running Lynis and Trivy';
  return 'Preparing safety check';
}

function scanInProgressValue(runStatus, busy, progress) {
  if (progress?.percent !== undefined) return clampSecurityProgress(progress.percent, busy ? 8 : 0);
  if (runStatus === 'queued') return 5;
  if (runStatus === 'running') return 16;
  return busy ? 8 : 0;
}

function triggerHapticFeedback(pattern = 12) {
  try {
    if (typeof navigator !== 'undefined' && typeof navigator.vibrate === 'function') {
      navigator.vibrate(pattern);
    }
  } catch (_error) {
    // Haptics are optional and must never block a Lite action.
  }
}

function shortRunId(value) {
  const text = String(value || '');
  if (!text) return 'Not available yet';
  return text.length > 18 ? `${text.slice(0, 12)}…${text.slice(-6)}` : text;
}


function PageHeader({ eyebrow = 'Pocket Lab Lite', title, description, actions }) {
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

function LiteButton({ children, onClick, disabled = false, tone = 'primary', type = 'button', haptic = false }) {
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

function ResultNotice({ result, error }) {
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

function LoadingCard({ label = 'Loading Pocket Lab Lite...' }) {
  return (
    <GlassCard>
      <div className="h-3 w-40 animate-pulse rounded-full bg-white/10" />
      <div className="mt-4 h-20 animate-pulse rounded-3xl bg-white/5" />
      <p className="mt-4 text-sm text-slate-400">{label}</p>
    </GlassCard>
  );
}

function friendlyOverallLabel(overall) {
  return backendLabel(overall, {
    ready: 'Everything looks good',
    review: 'A few things need attention',
    danger: 'Needs attention',
    checking: 'Checking your setup',
  });
}

function HomeScreen({ status, loading, error, refresh, onNavigate }) {
  const primaryServices = useMemo(() => status.services?.slice(0, 6) || [], [status.services]);
  const stats = status.summary || {};
  const readyServices = primaryServices.filter((service) => serviceTone(service.status) === 'healthy').length;
  const totalServices = primaryServices.length || 0;

  return (
    <>
      <PageHeader
        eyebrow="Home"
        title={backendHeroTitle(status.overall, { ready: 'Your Pocket Lab is ready', review: 'Your Pocket Lab needs review', danger: 'Your Pocket Lab needs attention', checking: 'Checking your Pocket Lab' })}
        description="A calm overview of your apps, devices, safety, and backups. Start common tasks from here without digging through settings."
        actions={<LiteButton onClick={refresh} tone="secondary">Refresh</LiteButton>}
      />

      {error ? (
        <StateSurface
          tone="degraded"
          title="Pocket Lab needs a moment"
          description={error}
          className="mb-5"
        />
      ) : null}

      <section className="lite-home-hero">
        <div className="lite-home-hero-copy">
          <div className="lite-home-pill">
            <span className="lite-ready-dot" />
            {friendlyOverallLabel(status.overall)}
          </div>
          <h2>Manage your private apps and devices from one simple place.</h2>
          <p>
            Pocket Lab Lite keeps the essentials close: apps, access, safety checks,
            devices, rules, and recovery.
          </p>
          <div className="lite-home-actions">
            <LiteButton onClick={() => onNavigate('catalog')}>Browse Apps</LiteButton>
            <LiteButton onClick={() => onNavigate('devices')} tone="secondary">Add Device</LiteButton>
            <LiteButton onClick={() => onNavigate('security')} tone="secondary">Safety Check</LiteButton>
            <LiteButton onClick={() => onNavigate('recovery')} tone="secondary">Backup</LiteButton>
          </div>
        </div>

        <div className="lite-home-readiness-card">
          <p className="lite-home-card-label">Today’s status</p>
          <strong>{readyServices}/{totalServices || '—'}</strong>
          <span>key areas ready</span>
          <StatusBadge status={status.overall}>
            {status.overall === 'healthy' ? 'Ready' : 'Needs attention'}
          </StatusBadge>
        </div>
      </section>

      <div className="lite-home-stats">
        <div className="lite-home-stat-card">
          <span>Apps</span>
          <strong>{stats.apps_available ?? 0}</strong>
          <p>available to install or manage</p>
        </div>
        <div className="lite-home-stat-card">
          <span>Devices</span>
          <strong>{stats.devices_known ?? 0}</strong>
          <p>known to this Pocket Lab</p>
        </div>
        <div className="lite-home-stat-card">
          <span>Safety</span>
          <strong>{stats.security_findings ?? 0}</strong>
          <p>items that need review</p>
        </div>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
        <GlassCard>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-xs font-black uppercase tracking-[0.18em] text-indigo-200">This device</p>
              <h2 className="mt-2 text-2xl font-black text-white">{status.device?.name || 'Pocket Lab'}</h2>
              <p className="mt-2 text-sm leading-6 text-slate-300">
                Set up for a small, private environment with the essentials enabled.
              </p>
            </div>
            <StatusBadge status={status.overall}>
              {status.overall === 'healthy' ? 'Ready' : 'Needs attention'}
            </StatusBadge>
          </div>

          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            <div className="lite-home-device-metric">
              <span>Device load</span>
              <strong>{status.telemetry?.cpu_usage_percent ?? '—'}%</strong>
            </div>
            <div className="lite-home-device-metric">
              <span>Device warmth</span>
              <strong>{status.telemetry?.cpu_temp_c ?? '—'}°C</strong>
            </div>
            <div className="lite-home-device-metric">
              <span>Storage available</span>
              <strong>{status.telemetry?.free_space_mb ?? '—'} MB</strong>
            </div>
            <div className="lite-home-device-metric">
              <span>Memory in use</span>
              <strong>{status.telemetry?.memory_usage_mb ?? '—'} MB</strong>
            </div>
          </div>

          <p className="mt-4 text-xs text-slate-500">Last checked: {formatLiteTime(status.checked_at)}</p>
        </GlassCard>

        <GlassCard>
          <p className="text-xs font-black uppercase tracking-[0.18em] text-cyan-200">Needs attention</p>
          <h2 className="mt-2 text-2xl font-black text-white">
            {(stats.security_findings ?? 0) === 0 ? 'Nothing urgent right now' : 'Review recommended'}
          </h2>
          <p className="mt-2 text-sm leading-6 text-slate-300">
            Pocket Lab will highlight problems here when apps, devices, safety checks,
            or backups need your attention.
          </p>
          <div className="mt-5">
            <LiteButton onClick={() => onNavigate('security')} tone="secondary">Review Safety</LiteButton>
          </div>
        </GlassCard>
      </div>

      <section className="mt-4">
        <div className="mb-3 flex items-end justify-between gap-3">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.18em] text-indigo-200">Key areas</p>
            <h2 className="text-xl font-black text-white">What is ready</h2>
          </div>
          {loading ? <span className="text-sm text-slate-400">Checking...</span> : null}
        </div>

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {loading ? <LoadingCard /> : primaryServices.map((service) => (
            <GlassCard key={service.name} className="lite-home-service-card">
              <div className="flex items-start justify-between gap-3">
                <h3 className="text-base font-black text-white">{service.name}</h3>
                <StatusBadge status={serviceTone(service.status)}>
                  {serviceTone(service.status) === 'healthy' ? 'Ready' : 'Check'}
                </StatusBadge>
              </div>
              <p className="mt-3 text-sm leading-6 text-slate-300">{service.summary}</p>
            </GlassCard>
          ))}
        </div>
      </section>
    </>
  );
}

function CatalogScreen() {
  const { data, loading, error, refresh } = useLiteResource(liteApi.catalog, []);
  const [query, setQuery] = useState('');
  const [result, setResult] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const items = data?.items || [];

  const filteredItems = useMemo(() => {
    const value = query.trim().toLowerCase();
    if (!value) return items;
    return items.filter((item) => {
      return `${item.name || ''} ${item.summary || ''}`.toLowerCase().includes(value);
    });
  }, [items, query]);

  const installedCount = items.filter((item) => item.installed).length;
  const attentionCount = items.filter((item) => String(item.status || '').toLowerCase().includes('attention')).length;

  async function install(item) {
    setBusyId(item.id);
    setResult(null);
    setActionError(null);
    try {
      setResult(await liteApi.installApp(item.id));
      refresh();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Apps"
        title="App Catalog"
        description="Choose useful apps for this Pocket Lab. Installed apps stay easy to see, and new installs are prepared safely for you."
        actions={<LiteButton onClick={refresh} tone="secondary">Refresh</LiteButton>}
      />

      <section className="lite-catalog-hero">
        <div className="lite-catalog-hero-copy">
          <div className="lite-home-pill">
            <span className="lite-ready-dot" />
            Ready to browse
          </div>
          <h2>Pick what you want this device to run.</h2>
          <p>
            Start with the essentials, add services when you need them, and keep the experience focused on what matters.
          </p>
        </div>

        <div className="lite-catalog-counts">
          <div>
            <span>Available</span>
            <strong>{items.length}</strong>
          </div>
          <div>
            <span>Installed</span>
            <strong>{installedCount}</strong>
          </div>
          <div>
            <span>Review</span>
            <strong>{attentionCount}</strong>
          </div>
        </div>
      </section>

      <div className="lite-catalog-toolbar">
        <div className="lite-catalog-search-wrap">
          <LayoutGrid className="h-5 w-5" />
          <input
            className="lite-catalog-search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search apps"
            aria-label="Search apps"
          />
        </div>
        <p>{filteredItems.length} shown</p>
      </div>

      {error ? (
        <StateSurface
          tone="degraded"
          title="Catalog needs a moment"
          description={error}
          className="mb-5"
        />
      ) : null}

      {loading ? <LoadingCard label="Loading apps..." /> : null}

      <div className="lite-catalog-grid">
        {filteredItems.map((item) => {
          const installed = Boolean(item.installed);
          const needsAttention = String(item.status || '').toLowerCase().includes('attention');

          return (
            <GlassCard key={item.id} className="lite-catalog-card">
              <div className="lite-catalog-card-top">
                <div className="lite-catalog-icon">
                  <LayoutGrid className="h-5 w-5" />
                </div>
                <StatusBadge status={needsAttention ? 'degraded' : installed ? 'healthy' : 'ready'}>
                  {needsAttention ? 'Check' : installed ? 'Installed' : 'Available'}
                </StatusBadge>
              </div>

              <h2>{item.name}</h2>
              <p>{item.summary}</p>

              <div className="lite-catalog-meta">
                <span>{installed ? 'Already on this device' : 'Ready when you are'}</span>
              </div>

              <div className="lite-catalog-actions">
                <LiteButton
                  onClick={() => install(item)}
                  disabled={busyId === item.id || installed}
                  tone={installed ? 'secondary' : 'primary'}
                >
                  {busyId === item.id ? 'Starting...' : installed ? 'Installed' : 'Install'}
                </LiteButton>
              </div>
            </GlassCard>
          );
        })}
      </div>

      {!loading && filteredItems.length === 0 ? (
        <StateSurface
          tone="empty"
          title={query ? 'No matching apps' : 'No apps yet'}
          description={query ? 'Try a different search term.' : 'Refresh the catalog after setup or add app entries to your catalog source.'}
        />
      ) : null}

      <ResultNotice result={result} error={actionError} />
    </>
  );
}

function IdentityScreen() {
  const { data, loading, error, refresh } = useLiteResource(liteApi.identity, []);
  const [target, setTarget] = useState('local-admin');
  const [result, setResult] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function rotate() {
    setBusy(true);
    setResult(null);
    setActionError(null);
    try {
      setResult(await liteApi.rotateIdentity(target));
      refresh();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Access"
        title="Identity & Access"
        description="Keep passwords and local access in a safe state. Change access only when you need to, with a clear record of the request."
        actions={<LiteButton onClick={refresh} tone="secondary">Refresh</LiteButton>}
      />

      <section className="lite-identity-hero">
        <div className="lite-identity-hero-copy">
          <div className="lite-home-pill">
            <span className="lite-ready-dot" />
            {backendLabel(data?.status, {
              ready: 'Access protected',
              review: 'Access needs review',
              danger: 'Access needs attention',
              checking: 'Checking access',
            })}
          </div>
          <h2>{backendHeroTitle(data?.status, {
            ready: 'Your passwords and access are kept in one safe place.',
            review: 'Access protection may need your review.',
            danger: 'Access needs attention.',
            checking: 'Checking access protection.',
          })}</h2>
          <p>
            Review access readiness, change a password safely, and keep your Pocket Lab protected without handling sensitive details yourself.
          </p>
        </div>

        <div className="lite-identity-status-card">
          <div className="lite-identity-icon">
            <Fingerprint className="h-7 w-7" />
          </div>
          <span>Current state</span>
          <strong>{backendLabel(data?.status, {
            ready: 'Protected',
            review: 'Review',
            danger: 'Attention',
            checking: 'Checking',
          })}</strong>
          <StatusBadge status={backendBadgeStatus(data?.status)}>
            {backendLabel(data?.status, {
              ready: 'Ready',
              review: 'Review',
              danger: 'Attention',
              checking: 'Checking',
            })}
          </StatusBadge>
        </div>
      </section>

      {loading ? <LoadingCard label="Checking access..." /> : null}

      {error ? (
        <StateSurface
          tone="degraded"
          title="Access summary needs a moment"
          description={error}
          className="mb-5"
        />
      ) : null}

      <div className="lite-identity-grid">
        <GlassCard className="lite-identity-card">
          <div className="lite-identity-card-head">
            <div className="lite-identity-mini-icon">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <StatusBadge status={backendBadgeStatus(data?.status)}>
              {backendLabel(data?.status, {
                ready: 'Ready',
                review: 'Review',
                danger: 'Attention',
                checking: 'Checking',
              })}
            </StatusBadge>
          </div>

          <h2>Access readiness</h2>
          <p>
            {data?.summary || 'Pocket Lab is checking whether access protection is ready.'}
          </p>

          <div className="lite-identity-checklist">
            <div>
              <span className="lite-check-dot" />
              Password changes are requested safely
            </div>
            <div>
              <span className="lite-check-dot" />
              Sensitive values stay hidden
            </div>
            <div>
              <span className="lite-check-dot" />
              Changes are recorded for review
            </div>
          </div>
        </GlassCard>

        <GlassCard className="lite-identity-card lite-identity-action-card">
          <div className="lite-identity-card-head">
            <div className="lite-identity-mini-icon">
              <Fingerprint className="h-5 w-5" />
            </div>
            <span className="lite-identity-soft-badge">Safe change</span>
          </div>

          <h2>Change a password</h2>
          <p>
            Choose what you want to update. Pocket Lab will prepare the change and keep the sensitive value hidden.
          </p>

          <label className="lite-identity-field-label" htmlFor="identity-target">
            What should be updated?
          </label>
          <select
            id="identity-target"
            className="pocket-input lite-identity-select"
            value={target}
            onChange={(event) => setTarget(event.target.value)}
          >
            <option value="local-admin">Main admin access</option>
            <option value="app-access">App access password</option>
            <option value="device-access">Device access password</option>
          </select>

          <div className="lite-identity-safe-note">
            <strong>Before it runs</strong>
            <span>You will see a clear request result. The password itself will not be shown here.</span>
          </div>

          <div className="mt-5">
            <LiteButton onClick={rotate} disabled={busy}>
              {busy ? 'Preparing...' : 'Change Password'}
            </LiteButton>
          </div>
        </GlassCard>
      </div>

      <ResultNotice result={result} error={actionError} />
    </>
  );
}

function SecurityScreen() {
  const { data, loading, error, refresh } = useLiteResource(liteApi.security, []);
  const [result, setResult] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [evidence, setEvidence] = useState(null);
  const [evidenceError, setEvidenceError] = useState(null);
  const [evidenceLoading, setEvidenceLoading] = useState(false);
  const [progressNow, setProgressNow] = useState(() => Date.now());

  const lastRun = data?.last_run || null;
  const findings = Number(data?.items_to_review ?? data?.findings_count ?? 0);
  const checks = Number(data?.checks_reviewed ?? data?.checks_count ?? 0);
  const criticalIssues = Array.isArray(data?.critical_issues) ? data.critical_issues : [];
  const reviewItems = Array.isArray(data?.findings) ? data.findings : [];
  const evidenceRefs = Array.isArray(data?.evidence_refs) ? data.evidence_refs : [];
  const componentPosture = Array.isArray(data?.component_posture) ? data.component_posture : [];
  const healthyComponents = componentPosture.filter((item) => normalizeBackendState(item?.status) === 'ready').length;
  const guidance = Array.isArray(data?.guidance) && data.guidance.length ? data.guidance : [
    { step: 1, title: 'Check local readiness', summary: 'Pocket Lab reviews local security and dependency posture.' },
    { step: 2, title: 'Summarize what changed', summary: 'New issues are compared against the last safety check.' },
    { step: 3, title: 'Show clear next steps', summary: 'Only actionable items are shown.' },
  ];
  const evidenceFindings = Array.isArray(evidence?.findings) ? evidence.findings : [];
  const evidenceRun = evidence?.run || null;
  const toolResults = evidenceRun?.tool_results || {};
  const protectedFileNames = new Set([
    ...reviewItems.map((item) => item?.file).filter(Boolean),
    ...evidenceFindings.map((item) => item?.file).filter(Boolean),
  ]);
  const protectedFileCount = protectedFileNames.size;
  const toolNames = Array.isArray(lastRun?.tools) && lastRun.tools.length ? lastRun.tools : ['lynis', 'trivy'];
  const sbomSaved = evidenceRefs.some((ref) => String(ref).includes('sbom.cdx.json')) || Boolean(toolResults?.trivy?.sbom_saved);
  const evidenceFileCount = evidenceRefs.length || (Array.isArray(evidence?.evidence_refs) ? evidence.evidence_refs.length : 0);
  const postureDashboard = [
    { label: 'Tools active', value: toolNames.length, detail: toolNames.join(' + ') },
    { label: 'Protected files', value: protectedFileCount || '—', detail: protectedFileCount ? 'with sanitized findings' : 'no file findings' },
    { label: 'Evidence files', value: evidenceFileCount, detail: sbomSaved ? 'SBOM saved' : 'saved after check' },
    { label: 'Protected areas', value: healthyComponents || componentPosture.length || 0, detail: 'components watched' },
  ];
  const runStatus = String(lastRun?.status || result?.status || '').toLowerCase();
  const scanProgress = data?.scan_progress || result?.scan_progress || null;
  const scanInProgress = busy || ['queued', 'running'].includes(runStatus);
  const liveProgress = liveSecurityProgress(scanProgress, runStatus, busy, progressNow);
  const scanProgressPercent = liveProgress.percent;
  const scanProgressEta = liveProgress.eta;
  const scanProgressLabel = securityProgressStage(scanProgress, runStatus);
  const scanProgressStep = Number(scanProgress?.step || (runStatus === 'queued' ? 1 : 2));
  const scanProgressStepsTotal = Number(scanProgress?.steps_total || 3);
  const safetyStatus = data?.status || (findings === 0 ? 'healthy' : 'degraded');
  const safetyState = ['queued', 'running'].includes(runStatus) ? 'checking' : normalizeBackendState(safetyStatus);
  const safetyIsReady = safetyState === 'ready' && findings === 0;
  const scoreValue = Number(data?.score ?? (safetyIsReady ? 100 : Math.max(55, 100 - Math.max(findings, 1) * 12)));
  const safetyScore = Number.isFinite(scoreValue) ? Math.max(0, Math.min(100, Math.round(scoreValue))) : 0;
  const safetyLabel = runStatus === 'queued'
    ? 'Safety check queued'
    : runStatus === 'running'
      ? 'Safety check running'
      : backendLabel(safetyStatus, {
        ready: findings === 0 ? 'Protected' : 'Protected · review item',
        review: 'Needs review',
        danger: 'Needs attention',
        checking: 'Checking safety',
      });
  const safetyScoreSummary = lastRun?.partial_results
    ? 'Partial check completed. Available evidence was saved.'
    : data?.summary || 'Pocket Lab is checking the current safety state.';
  const trustSignals = [
    {
      icon: Server,
      title: 'Backend-run checks',
      summary: 'Security tools run on this device, not in your browser.',
    },
    {
      icon: EyeOff,
      title: 'Secrets stay hidden',
      summary: 'Findings are redacted before they appear in the app.',
    },
    {
      icon: FileCheck,
      title: 'Evidence saved',
      summary: evidenceRefs.length ? `${evidenceRefs.length} sanitized evidence files` : 'Evidence appears after a completed check.',
    },
  ];

  React.useEffect(() => {
    if (!scanInProgress) return undefined;
    setProgressNow(Date.now());
    const timer = window.setInterval(() => setProgressNow(Date.now()), 1000);
    const refreshTimer = window.setInterval(() => refresh(), 8000);
    return () => {
      window.clearInterval(timer);
      window.clearInterval(refreshTimer);
    };
  }, [scanInProgress, refresh]);

  React.useEffect(() => {
    const panelOpen = evidence || evidenceError || evidenceLoading;
    if (!panelOpen) return undefined;
    function handleKeyDown(event) {
      if (event.key === 'Escape') {
        setEvidence(null);
        setEvidenceError(null);
        setEvidenceLoading(false);
      }
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [evidence, evidenceError, evidenceLoading]);

  function scheduleSecurityRefresh() {
    refresh();
    [700, 1800, 4000].forEach((delay) => window.setTimeout(() => refresh(), delay));
  }

  async function scan() {
    setBusy(true);
    setResult({ status: 'queued', summary: 'Safety check queued.' });
    setActionError(null);
    setEvidence(null);
    setEvidenceError(null);
    setEvidenceLoading(false);
    try {
      const payload = await liteApi.runSecurityScan('local', { reason: 'manual safety check' });
      setResult(payload);
      scheduleSecurityRefresh();
    } catch (err) {
      setResult(null);
      setActionError(err.message);
    } finally {
      setBusy(false);
    }
  }

  function closeEvidencePanel() {
    setEvidence(null);
    setEvidenceError(null);
    setEvidenceLoading(false);
  }

  async function showEvidence() {
    triggerHapticFeedback(8);
    if (evidence) {
      closeEvidencePanel();
      return;
    }
    const runId = lastRun?.run_id || result?.run_id;
    if (!runId) {
      setEvidenceError('Run a safety check before opening evidence.');
      return;
    }
    setEvidenceError(null);
    setEvidenceLoading(true);
    try {
      setEvidence(await liteApi.securityEvidence(runId));
    } catch (err) {
      setEvidence(null);
      setEvidenceError(err.message);
    } finally {
      setEvidenceLoading(false);
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Safety"
        title="Security"
        description="Check whether your Pocket Lab needs attention. The results are summarized clearly so you know what to do next."
        actions={<LiteButton onClick={scan} disabled={scanInProgress} haptic>{scanInProgress ? 'Checking...' : 'Run Safety Check'}</LiteButton>}
      />

      <section className="lite-security-hero">
        <div className="lite-security-hero-copy">
          <div className="lite-home-pill">
            <span className="lite-ready-dot" />
            {safetyLabel}
          </div>
          <h2>{runStatus === 'queued'
            ? 'Safety check queued.'
            : runStatus === 'running'
              ? 'Safety check running.'
              : backendHeroTitle(safetyStatus, {
                ready: safetyIsReady ? 'No urgent safety issues found.' : 'A few items may need your review.',
                review: 'A few items may need your review.',
                danger: 'Safety needs attention.',
                checking: 'Checking your safety status.',
              })}</h2>
          <p>
            Pocket Lab checks host readiness, dependency risks, configuration concerns, and secret-like findings through the backend worker. Sensitive values stay hidden and evidence is saved for review.
          </p>
          <div className="lite-security-trust-strip" aria-label="Security assurances">
            {trustSignals.map((item) => {
              const Icon = item.icon;
              return (
                <div key={item.title}>
                  <Icon className="h-4 w-4" />
                  <span>{item.title}</span>
                </div>
              );
            })}
          </div>
          {scanInProgress ? (
            <div className="lite-security-progress-card" aria-live="polite">
              <div className="lite-security-progress-head">
                <div>
                  <strong>{scanProgressLabel}</strong>
                  <span>Step {scanProgressStep} of {scanProgressStepsTotal}</span>
                </div>
                <span>{scanProgressEta} remaining</span>
              </div>
              <div className="lite-security-progress-track" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow={scanProgressPercent} aria-label="Safety check progress">
                <span style={{ width: `${scanProgressPercent}%` }} />
              </div>
              <p>{scanProgress?.message || 'Pocket Lab is checking host readiness and dependency risks in the backend worker.'}</p>
            </div>
          ) : null}
          <div className="lite-security-actions">
            <LiteButton onClick={scan} disabled={scanInProgress} haptic>{scanInProgress ? 'Checking...' : 'Run Safety Check'}</LiteButton>
            <LiteButton onClick={showEvidence} tone="secondary">{evidence ? 'Hide Evidence' : evidenceLoading ? 'Opening...' : 'Evidence'}</LiteButton>
          </div>
        </div>

        <div className="lite-security-score-card">
          <div className="lite-security-score-ring" style={{ '--score': `${safetyScore}%` }}>
            <span>{safetyScore}</span>
          </div>
          <strong>Safety score</strong>
          <p>{safetyScoreSummary}</p>
          <StatusBadge status={backendBadgeStatus(safetyStatus)}>
            {safetyLabel}
          </StatusBadge>
          <div className="lite-security-score-meta">
            <span>{scanInProgress ? `${scanProgressPercent}% complete · ${scanProgressEta} remaining` : lastRun?.completed_at ? `Last check ${formatLiteTime(lastRun.completed_at)}` : 'Run a check to refresh posture'}</span>
            <span>{healthyComponents || componentPosture.length || 0} protected areas healthy</span>
          </div>
        </div>
      </section>

      <section className="lite-security-assurance-grid" aria-label="Security assurances">
        {trustSignals.map((item) => {
          const Icon = item.icon;
          return (
            <div key={item.title} className="lite-security-assurance-card">
              <span><Icon className="h-4 w-4" /></span>
              <strong>{item.title}</strong>
              <p>{item.summary}</p>
            </div>
          );
        })}
      </section>

      {loading ? <LoadingCard label="Loading safety summary..." /> : null}

      {error ? (
        <StateSurface
          tone="degraded"
          title="Safety summary needs a moment"
          description={error}
          className="mb-5"
        />
      ) : null}

      <div className="lite-security-grid">
        <GlassCard className="lite-security-card">
          <div className="lite-security-card-head">
            <div className="lite-security-icon">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <StatusBadge status={backendBadgeStatus(safetyStatus)}>
              {safetyLabel}
            </StatusBadge>
          </div>

          <h2>{criticalIssues.length ? 'Critical issues found' : 'No critical issues'}</h2>
          <p>{criticalIssues.length ? 'Review the items below before making more changes.' : 'No urgent safety issues were found in the latest summary.'}</p>

          <div className="lite-security-summary-list">
            <div>
              <span className="lite-security-dot" />
              <strong>{checks || '—'}</strong>
              <p>checks reviewed</p>
            </div>
            <div>
              <span className={findings === 0 ? 'lite-security-dot' : 'lite-security-dot lite-security-dot-warning'} />
              <strong>{findings}</strong>
              <p>items to review</p>
            </div>
          </div>

          {criticalIssues.length ? (
            <div className="lite-security-issue-list">
              {criticalIssues.slice(0, 4).map((issue) => (
                <div key={issue.id || issue.summary} className="lite-security-issue">
                  <strong>{issue.summary || 'Critical issue found'}</strong>
                  <p>{issue.recommendation || 'Review this item and apply the recommended fix.'}</p>
                </div>
              ))}
            </div>
          ) : null}

          {reviewItems.length ? (
            <div className="lite-security-review-list">
              {reviewItems.slice(0, 4).map((item) => (
                <div key={item.id || item.summary} className="lite-security-review-item">
                  <span className={`lite-security-severity lite-security-severity-${securityFindingTone(item.severity)}`}>
                    {item.severity || 'review'}
                  </span>
                  <div>
                    <strong>{securityFindingLabel(item)}</strong>
                    <p>{item.recommendation || item.summary || 'Review this item and keep the workspace protected.'}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="lite-security-safe-panel">
              <Lock className="h-4 w-4" />
              <span>No urgent issues. Pocket Lab will keep evidence ready after each check.</span>
            </div>
          )}
        </GlassCard>

        <GlassCard className="lite-security-card lite-security-dashboard-card">
          <div className="lite-security-card-head">
            <div className="lite-security-icon">
              <FileCheck className="h-5 w-5" />
            </div>
            <span className="lite-security-soft-badge">Protection dashboard</span>
          </div>

          <h2>Local protection summary</h2>
          <p>
            Lynis checks host readiness. Trivy checks dependency, config, secret-like findings, and saves SBOM evidence.
          </p>

          <div className="lite-security-mini-dashboard" aria-label="Security protection dashboard">
            {postureDashboard.map((item) => (
              <div key={item.label}>
                <strong>{item.value}</strong>
                <span>{item.label}</span>
                <p>{item.detail}</p>
              </div>
            ))}
          </div>

          <div className="lite-security-steps lite-security-compact-steps">
            {guidance.slice(0, 3).map((item, index) => (
              <div key={item.step || item.title || index}>
                <span>{item.step || index + 1}</span>
                <p>{item.title || item.summary}</p>
              </div>
            ))}
          </div>
        </GlassCard>
      </div>

      {(evidence || evidenceError || evidenceLoading) ? (
        <div className="lite-security-evidence-modal-backdrop" role="presentation" onClick={closeEvidencePanel}>
          <GlassCard className="lite-security-card lite-security-evidence-panel" role="dialog" aria-modal="true" aria-label="Sanitized security evidence" onClick={(event) => event.stopPropagation()}>
            <div className="lite-security-card-head">
              <div className="lite-security-icon">
                <FileCheck className="h-5 w-5" />
              </div>
              <span className="lite-security-soft-badge">Sanitized evidence</span>
              <button type="button" className="lite-security-evidence-close" onClick={closeEvidencePanel} aria-label="Close evidence details">
                <X className="h-4 w-4" />
              </button>
            </div>

            <h2>{evidenceError ? 'Evidence not ready' : evidenceLoading ? 'Opening evidence...' : 'Evidence details'}</h2>
            {evidenceError ? <p>{evidenceError}</p> : null}
            {evidenceLoading ? <p>Pocket Lab is opening the sanitized evidence summary for the latest safety check.</p> : null}
            {evidence ? (
              <>
              <div className="lite-security-evidence-summary">
                <div>
                  <span>Run</span>
                  <strong>{shortRunId(evidence?.run?.run_id || lastRun?.run_id)}</strong>
                </div>
                <div>
                  <span>Status</span>
                  <strong>{evidence?.run?.status || 'unknown'}</strong>
                </div>
                <div>
                  <span>Score</span>
                  <strong>{evidence?.score ?? safetyScore}</strong>
                </div>
                <div>
                  <span>Findings</span>
                  <strong>{evidenceFindings.length}</strong>
                </div>
              </div>

              <div className="lite-security-evidence-tools">
                {['lynis', 'trivy'].map((tool) => {
                  const item = toolResults?.[tool] || {};
                  return (
                    <div key={tool}>
                      <strong>{tool}</strong>
                      <span>{item.status || 'recorded'}</span>
                      <p>{tool === 'trivy' && item.sbom_saved ? 'SBOM saved and findings normalized.' : 'Output normalized before display.'}</p>
                    </div>
                  );
                })}
              </div>

              <div className="lite-security-evidence-files">
                {(evidence.evidence_refs || evidenceRefs).slice(0, 6).map((ref) => (
                  <code key={ref}>{String(ref).split('/').slice(-1)[0]}</code>
                ))}
              </div>
              <p className="lite-security-evidence-note">Raw scanner output and sensitive values stay hidden. This panel shows only sanitized evidence metadata.</p>
            </>
          ) : null}
          </GlassCard>
        </div>
      ) : null}

      <ResultNotice result={result} error={actionError} />
    </>
  );
}

function deviceLinkState(device) {
  const role = String(device?.role || '').toLowerCase();
  const status = String(device?.status || '').toLowerCase();
  const connection = String(device?.connection || '').toLowerCase();

  if (role === 'server_host' || device?.is_current || device?.isCurrent) return 'server';
  if (connection === 'online' || ['healthy', 'active', 'online', 'ready'].includes(status)) return 'joined';
  if (connection === 'repairing' || ['repairing', 'supervisor_repairing'].includes(status)) return 'repairing';
  return 'disconnected';
}

function DevicesScreen() {
  const { data, loading, error, refresh } = useLiteResource(liteApi.fleet, []);
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
  const [removeBusy, setRemoveBusy] = useState(false);
  const [serverConflict, setServerConflict] = useState(null);
  const devices = data?.devices || [];
  const remoteAccess = data?.remote_access || {};
  const remoteAccessReady = remoteAccess?.status === 'healthy' || remoteAccess?.ready;
  const latestInvite = invite || data?.latest_invite || null;
  const onlineDevices = devices.filter((device) => normalizeBackendState(device.status) === 'ready').length;
  const selectedRoleLabel = roleLabel(selectedRole);
  const candidateDeviceName = hostname.trim() || `Pocket Lab ${selectedRoleLabel}`;
  const localNameConflict = findDeviceNameConflict(candidateDeviceName, devices);
  const activeNameConflict = localNameConflict || serverConflict;
  const addDeviceDisabled = busy || Boolean(activeNameConflict);

  async function addDevice() {
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
      } else if (payload?.status === 'queued') {
        window.setTimeout(() => refresh(), 1800);
      }
      refresh();
    } catch (err) {
      const detail = err?.payload?.detail || {};
      setResult(null);
      if (detail?.status === 'duplicate_device') {
        setServerConflict(detail.existing_device || null);
        setActionError(detail.message || detail.summary || 'A device with this name already exists.');
      } else {
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
    refresh();
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
          refresh();
          if (['completed', 'failed'].includes(nextProgress?.status)) break;
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

  async function removeOldDevice() {
    const nodeId = removeCandidate?.id;
    if (!nodeId) return;
    setRemoveBusy(true);
    setActionError(null);
    setResult(null);
    try {
      const response = await liteApi.removeDevice(nodeId, {
        reason: 'Old device cleanup from Lite Devices tab',
      });
      setResult(response);
      setRemoveCandidate(null);
      setInvite(null);
      refresh();
    } catch (err) {
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
        actions={<LiteButton onClick={refresh} tone="secondary">Refresh</LiteButton>}
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
          <p>{devices.length} total device{devices.length === 1 ? '' : 's'} known</p>
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

          <div className="mt-5">
            <LiteButton onClick={addDevice} disabled={addDeviceDisabled}>
              {busy ? 'Preparing invite...' : (activeNameConflict ? 'Device already added' : 'Add Device')}
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
                    <LiteButton onClick={refresh} tone="ghost">Refresh devices</LiteButton>
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

        <section className="lite-devices-list-area">
          <div className="lite-devices-section-title">
            <div>
              <p>Device list</p>
              <h2>Available devices</h2>
            </div>
            <span>{devices.length} shown</span>
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
                  onClick={() => setRemoveCandidate(null)}
                  aria-label="Close remove old device confirmation"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              <p className="lite-device-remove-copy">
                This only removes the saved device record. It does not wipe the phone or uninstall Pocket Lab from that device.
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

              <div className="lite-device-remove-actions">
                <LiteButton tone="danger" onClick={removeOldDevice} disabled={removeBusy}>
                  {removeBusy ? 'Removing...' : 'Confirm removal'}
                </LiteButton>
                <LiteButton tone="secondary" onClick={() => setRemoveCandidate(null)} disabled={removeBusy}>
                  Keep device
                </LiteButton>
              </div>
            </GlassCard>
          ) : null}

          {loading ? <LoadingCard label="Loading devices..." /> : null}

          <div className="lite-devices-grid lite-devices-linked-grid">
            {devices.map((device) => {
              const online = normalizeBackendState(device.status) === 'ready';
              const linkState = deviceLinkState(device);
              const role = String(device?.role || '').toLowerCase();
              const isServerCard = role === 'server_host' || device?.is_current || device?.isCurrent;
              const connectionClass = isServerCard
                ? 'lite-device-card-server'
                : `lite-device-card-linked lite-device-card-linked-${linkState}`;

              return (
                <GlassCard key={device.id || device.name} className={`lite-device-card ${connectionClass}`}>
                  <div className="lite-device-card-top">
                    <div className="lite-device-icon">
                      <span className={online ? 'lite-device-pulse' : 'lite-device-pulse lite-device-pulse-muted'} />
                      <Network className="h-5 w-5" />
                    </div>
                    <StatusBadge status={backendBadgeStatus(device.status)}>
                      {deviceStatusLabel(device.status)}
                    </StatusBadge>
                  </div>

                  <h2>{device.name || 'Unnamed device'}</h2>

                  <div className="lite-device-connection-copy">
                    {isServerCard ? 'Connection anchor for this Pocket Lab.' : linkState === 'joined' ? 'Connected to the Pocket Lab Lite server.' : linkState === 'repairing' ? 'Connection is being repaired.' : 'Disconnected from the Pocket Lab Lite server.'}
                  </div>

                  <div className="lite-device-details">
                    <div>
                      <span>Role</span>
                      <strong>{device.role_label || roleLabel(device.role)}</strong>
                    </div>
                    <div>
                      <span>Last seen</span>
                      <strong>{formatLiteTime(device.last_seen)}</strong>
                    </div>
                    <div>
                      <span>Connection</span>
                      <strong>{deviceConnectionLabel(device)}</strong>
                    </div>
                    {device.tailnet_ip ? (
                      <div>
                        <span>Tailscale IP</span>
                        <strong>{device.tailnet_ip}</strong>
                      </div>
                    ) : null}
                  </div>

                  {canRestartDeviceAgent(device) || canRemoveDevice(device) ? (
                    <div className="lite-device-actions">
                      {canRestartDeviceAgent(device) ? (
                        <LiteButton
                          tone="secondary"
                          onClick={() => restartAgent(device)}
                          disabled={restartBusy === device.id}
                        >
                          <RefreshCw className="h-4 w-4" />
                          {restartBusy === device.id ? 'Checking progress...' : 'Restart agent'}
                        </LiteButton>
                      ) : null}
                      {canRemoveDevice(device) ? (
                        <LiteButton
                          tone="danger"
                          onClick={() => setRemoveCandidate(device)}
                          disabled={removeBusy}
                        >
                          <Trash2 className="h-4 w-4" />
                          Remove old device
                        </LiteButton>
                      ) : null}
                    </div>
                  ) : null}

                </GlassCard>
              );
            })}
          </div>

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

function RulesScreen() {
  const { data, loading, error, refresh } = useLiteResource(liteApi.policy, []);
  const [enabled, setEnabled] = useState(false);
  const [result, setResult] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [busy, setBusy] = useState(false);

  React.useEffect(() => {
    if (data) setEnabled(Boolean(data.protection_enabled));
  }, [data]);

  const rulesStatus = data ? (enabled ? 'healthy' : 'degraded') : 'unknown';

  async function apply() {
    setBusy(true);
    setResult(null);
    setActionError(null);
    try {
      setResult(await liteApi.applyPolicy({ protection_enabled: enabled, reason: 'Pocket Lab Lite rules update' }));
      refresh();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Rules"
        title="Safety Rules"
        description="Choose how careful Pocket Lab should be before making changes. Keep protection on for everyday use."
        actions={<LiteButton onClick={refresh} tone="secondary">Refresh</LiteButton>}
      />

      <section className="lite-rules-hero">
        <div className="lite-rules-hero-copy">
          <div className="lite-home-pill">
            <span className="lite-ready-dot" />
            {backendLabel(rulesStatus, {
              ready: 'Protection on',
              review: 'Ready to enable',
              danger: 'Needs attention',
              checking: 'Checking rules',
            })}
          </div>
          <h2>Simple rules help prevent unwanted changes.</h2>
          <p>
            Pocket Lab can pause sensitive actions, ask for confirmation, and keep a clear record of important changes.
          </p>
        </div>

        <div className="lite-rules-status-card">
          <div className="lite-rules-icon">
            <FileCheck className="h-7 w-7" />
          </div>
          <span>Protection</span>
          <strong>{enabled ? 'On' : 'Off'}</strong>
          <StatusBadge status={backendBadgeStatus(rulesStatus)}>
            {backendLabel(rulesStatus, {
              ready: 'Enabled',
              review: 'Review',
              danger: 'Attention',
              checking: 'Checking',
            })}
          </StatusBadge>
        </div>
      </section>

      {loading ? <LoadingCard label="Loading rules..." /> : null}

      {error ? (
        <StateSurface
          tone="degraded"
          title="Rules need a moment"
          description={error}
          className="mb-5"
        />
      ) : null}

      <div className="lite-rules-grid">
        <GlassCard className="lite-rules-card lite-rules-toggle-card">
          <div className="lite-rules-card-head">
            <div className="lite-rules-mini-icon">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <StatusBadge status={backendBadgeStatus(rulesStatus)}>
              {backendLabel(rulesStatus, {
                ready: 'Protected',
                review: 'Not enabled',
                danger: 'Attention',
                checking: 'Checking',
              })}
            </StatusBadge>
          </div>

          <h2>Protection mode</h2>
          <p>
            {data?.summary || 'Pocket Lab is checking whether protection is enabled.'}
          </p>

          <button
            type="button"
            className={`lite-rules-toggle ${enabled ? 'lite-rules-toggle-on' : ''}`}
            onClick={() => setEnabled((value) => !value)}
            aria-pressed={enabled}
          >
            <span className="lite-rules-toggle-track">
              <span className="lite-rules-toggle-thumb" />
            </span>
            <span>
              <strong>{enabled ? 'Protection is on' : 'Protection is off'}</strong>
              <small>{enabled ? 'Recommended for everyday use' : 'Turn on to add an extra safety step'}</small>
            </span>
          </button>

          <div className="mt-5">
            <LiteButton onClick={apply} disabled={busy}>
              {busy ? 'Saving...' : 'Save Rules'}
            </LiteButton>
          </div>
        </GlassCard>

        <GlassCard className="lite-rules-card lite-rules-guide-card">
          <div className="lite-rules-card-head">
            <div className="lite-rules-mini-icon">
              <FileCheck className="h-5 w-5" />
            </div>
            <span className="lite-rules-soft-badge">Recommended</span>
          </div>

          <h2>What these rules do</h2>
          <p>
            Rules keep important actions intentional without making the app hard to use.
          </p>

          <div className="lite-rules-list">
            <div>
              <span>1</span>
              <p>Ask before sensitive changes</p>
            </div>
            <div>
              <span>2</span>
              <p>Keep a clear record</p>
            </div>
            <div>
              <span>3</span>
              <p>Let safe everyday actions stay simple</p>
            </div>
          </div>
        </GlassCard>
      </div>

      <ResultNotice result={result} error={actionError} />
    </>
  );
}

function restartProgressTitle(progress = {}) {
  const status = String(progress?.status || '').toLowerCase();
  if (status === 'completed') return 'Device is back online';
  if (status === 'agent_stopped') return 'Device agent is stopped';
  if (status === 'repairing') return 'Supervisor is repairing the agent';
  if (status === 'failed') return 'Restart needs attention';
  if (status === 'starting') return 'Preparing restart';
  return 'Restart in progress';
}

function restartStepStateLabel(state) {
  const value = String(state || 'waiting').toLowerCase();
  if (value === 'complete') return 'Done';
  if (value === 'active') return 'Working';
  if (value === 'failed') return 'Needs help';
  return 'Waiting';
}

function safeRestartSteps(progress = {}) {
  return Array.isArray(progress?.steps) ? progress.steps.filter(Boolean) : [];
}

function RecoveryScreen() {
  const { data, loading, error, refresh } = useLiteResource(liteApi.recovery, []);
  const [backupResult, setBackupResult] = useState(null);
  const [verifyResult, setVerifyResult] = useState(null);
  const [previewResult, setPreviewResult] = useState(null);
  const [restoreResult, setRestoreResult] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [busy, setBusy] = useState('');
  const lastRecoveryActionRef = React.useRef('');

  React.useEffect(() => {
    if (busy) {
      lastRecoveryActionRef.current = busy;
      return undefined;
    }

    if (!lastRecoveryActionRef.current) {
      return undefined;
    }

    lastRecoveryActionRef.current = '';
    refresh();

    const timers = [
      window.setTimeout(refresh, 700),
      window.setTimeout(refresh, 1800),
    ];

    return () => timers.forEach((timer) => window.clearTimeout(timer));
  }, [busy, refresh]);
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [copiedEvidence, setCopiedEvidence] = useState('');
  const [activeActionPanel, setActiveActionPanel] = useState('');
  const [highlightedAction, setHighlightedAction] = useState('');

  const latestBackup = data?.last_backup || data?.latest_backup || null;
  const history = data?.backup_history || data?.available_restore_points || [];
  const repository = data?.repository || {};
  const latestBackupVerified = latestBackup?.verification_status === 'verified';
  const latestPreview = data?.latest_restore_preview || null;
  const latestPreviewReady = latestPreview?.status === 'ready';
  const lastRestore = data?.last_restore || null;
  const checkpoint = data?.pre_restore_checkpoint || null;
  const serviceRestart = lastRestore?.service_restart || {};
  const healthValidation = lastRestore?.health_validation || {};
  const restoreSucceeded = ['succeeded', 'succeeded_with_warnings'].includes(String(lastRestore?.status || '').toLowerCase());

  const shortId = (value) => {
    const text = String(value || '');
    if (!text) return 'Not available';
    if (text.length <= 18) return text;
    return `${text.slice(0, 10)}…${text.slice(-6)}`;
  };

  const restoreSteps = [
    { key: 'backup', label: 'Backup', detail: latestBackup ? 'Safe copy saved' : 'Create backup', complete: Boolean(latestBackup) },
    { key: 'verified', label: 'Verified', detail: latestBackupVerified ? 'Evidence checked' : 'Verify backup', complete: latestBackupVerified },
    { key: 'preview', label: 'Preview', detail: latestPreviewReady ? `${latestPreview?.change_count || 0} item(s)` : 'Preview changes', complete: latestPreviewReady },
    { key: 'checkpoint', label: 'Checkpoint', detail: checkpoint?.checkpoint_id ? 'Saved before restore' : 'Created on restore', complete: checkpoint?.status === 'created' },
    { key: 'restored', label: 'Restored', detail: restoreSucceeded ? `${lastRestore?.restored_file_count || 0} file(s)` : 'Confirm restore', complete: restoreSucceeded },
  ];

  const confidencePills = [
    { label: repository?.encrypted ? 'Encrypted backup' : 'Local backup', state: repository?.ready ? 'ready' : 'waiting' },
    { label: latestBackupVerified ? 'Verified' : 'Needs verification', state: latestBackupVerified ? 'ready' : 'waiting' },
    { label: latestPreviewReady ? 'Preview ready' : 'Preview needed', state: latestPreviewReady ? 'ready' : 'waiting' },
    { label: healthValidation?.status === 'passed' ? 'Health passed' : 'Health pending', state: healthValidation?.status === 'passed' ? 'ready' : 'waiting' },
  ];

  const previewStats = [
    { label: 'Will restore', value: latestPreview?.change_count ?? lastRestore?.restored_file_count ?? '—' },
    { label: 'Skipped', value: lastRestore?.skipped_change_count ?? 0 },
    { label: 'Secrets', value: 'Excluded' },
  ];

  const evidenceItems = [
    { label: 'Backup ID', value: latestBackup?.backup_id },
    { label: 'Snapshot ID', value: latestBackup?.snapshot_id },
    { label: 'Manifest checksum', value: latestBackup?.manifest_checksum },
    { label: 'Preview ID', value: latestPreview?.preview_id },
    { label: 'Checkpoint ID', value: checkpoint?.checkpoint_id || lastRestore?.checkpoint_id },
    { label: 'Restore ID', value: lastRestore?.restore_id },
  ].filter((item) => item.value);

  const actionPanelMeta = {
    verify: {
      title: 'Verify Backup',
      subtitle: latestBackupVerified ? 'Evidence checked and backup is ready.' : 'Pocket Lab is checking the backup evidence.',
      next: 'Preview Restore',
      logs: [
        'Verification runs through the Lite control API.',
        latestBackupVerified ? 'Manifest checksum passed.' : 'Manifest checksum will be checked.',
        latestBackupVerified ? 'Restic snapshot lookup passed.' : 'Restic snapshot lookup will be checked.',
        latestBackupVerified ? 'Repository metadata check passed.' : 'Repository metadata will be checked.',
      ],
    },
    preview: {
      title: 'Preview Restore',
      subtitle: latestPreviewReady ? `${latestPreview?.change_count || 0} item(s) checked without changing local state.` : 'Pocket Lab will inspect the restore point safely.',
      next: 'Restore Latest',
      logs: [
        'Preview runs through the worker and does not restore files.',
        latestPreviewReady ? `${latestPreview?.change_count || 0} item(s) would be restored.` : 'Restore changes will be counted before restore is enabled.',
        latestPreviewReady ? `${latestPreview?.restic_item_count || 0} restic item(s) inspected.` : 'Encrypted repository contents will be inspected.',
        'Raw secrets remain excluded from this restore point.',
      ],
    },
    restore: {
      title: 'Restore Latest',
      subtitle: restoreSucceeded ? `${lastRestore?.restored_file_count || 0} file(s) restored after checkpoint creation.` : 'Restore creates a checkpoint before changing Lite state.',
      next: 'Evidence',
      logs: [
        checkpoint?.checkpoint_id ? `Checkpoint saved: ${shortId(checkpoint.checkpoint_id)}` : 'Checkpoint will be saved before restore.',
        restoreSucceeded ? `${lastRestore?.restored_file_count || 0} Lite state file(s) restored.` : 'Restore is waiting for confirmation.',
        serviceRestart?.status ? `Service restart: ${serviceRestart.status}` : 'Service restart will be checked after restore.',
        healthValidation?.status ? `Lite API health: ${healthValidation.status}` : 'Lite API health will be checked after restore.',
      ],
    },
    evidence: {
      title: 'Evidence',
      subtitle: evidenceItems.length ? 'Recovery IDs are ready to copy or inspect.' : 'Evidence will appear after backup activity.',
      next: 'Verify Backup',
      logs: evidenceItems.length
        ? evidenceItems.slice(0, 6).map((item) => `${item.label}: ${shortId(item.value)}`)
        : ['No evidence IDs are available yet. Create a backup first.'],
    },
  };

  const activePanel = actionPanelMeta[activeActionPanel] || null;

  function openActionPanel(action) {
    setActiveActionPanel(action);
    setHighlightedAction('');
  }

  function closeActionPanel() {
    setActiveActionPanel('');
  }

  async function copyEvidence(value, label) {
    const copied = await copyTextToClipboard(value);
    if (copied) {
      setCopiedEvidence(label);
      window.setTimeout(() => setCopiedEvidence(''), 1600);
    }
  }

  async function backup() {
    setBusy('backup');
    setBackupResult(null);
    setActionError(null);
    try {
      setBackupResult(await liteApi.backupNow({ include_app_data: false, reason: 'manual backup' }));
      refresh();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setBusy('');
    }
  }

  async function verifyLatestBackup() {
    if (!latestBackup?.backup_id) return;
    openActionPanel('verify');
    setBusy('verify');
    setVerifyResult(null);
    setActionError(null);
    try {
      setVerifyResult(await liteApi.verifyBackup(latestBackup.backup_id, { reason: 'manual verification' }));
      setHighlightedAction('preview');
      refresh();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setBusy('');
    }
  }

  async function previewLatestRestore() {
    if (!latestBackup?.backup_id) return;
    openActionPanel('preview');
    setBusy('preview');
    setPreviewResult(null);
    setActionError(null);
    try {
      setPreviewResult(await liteApi.previewRestore({ backup_id: latestBackup.backup_id, reason: 'manual restore preview' }));
      setHighlightedAction('restore');
      refresh();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setBusy('');
    }
  }

  async function restoreLatestBackup() {
    if (!latestBackup?.backup_id || !latestPreview?.preview_id) return;
    openActionPanel('restore');
    const confirmed = window.confirm('Restore will change local Lite state. Pocket Lab will create a checkpoint first. Continue?');
    if (!confirmed) return;
    setBusy('restore');
    setRestoreResult(null);
    setActionError(null);
    try {
      setRestoreResult(await liteApi.restoreBackup({
        backup_id: latestBackup.backup_id,
        preview_id: latestPreview.preview_id,
        confirm: true,
      }));
      setHighlightedAction('evidence');
      refresh();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setBusy('');
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Recovery"
        title="Backup & Restore"
        description="Create a safety copy before changes. Restore stays protected until backup checks and preview are ready."
        actions={<LiteButton onClick={refresh} tone="secondary">Refresh</LiteButton>}
      />

      <section className="lite-recovery-hero lite-recovery-hero-premium">
        <div className="lite-recovery-hero-copy">
          <div className="lite-home-pill">
            <span className="lite-ready-dot" />
            {backendLabel(data?.status, {
              ready: 'Recovery Ready',
              review: 'Needs Attention',
              danger: 'Needs Attention',
              checking: 'Checking recovery',
            })}
          </div>
          <h2>{latestBackup ? 'You have a safe restore point.' : 'Create your first safe copy.'}</h2>
          <p>
            Pocket Lab backs up local Lite state into an encrypted restic repository and saves a clear evidence receipt.
          </p>
          <div className="lite-recovery-confidence-strip" aria-label="Recovery confidence">
            {confidencePills.map((pill) => (
              <span key={pill.label} className={`lite-recovery-confidence-pill lite-recovery-confidence-${pill.state}`}>
                {pill.label}
              </span>
            ))}
          </div>
          <div className="lite-recovery-actions">
            <LiteButton onClick={backup} disabled={busy === 'backup'}>
              {busy === 'backup' ? 'Starting backup...' : 'Backup Now'}
            </LiteButton>
            <LiteButton onClick={refresh} tone="secondary">Refresh</LiteButton>
          </div>
        </div>

        <div className="lite-recovery-status-card lite-recovery-confidence-card">
          <div className="lite-recovery-icon">
            <Database className="h-7 w-7" />
          </div>
          <span>Last backup</span>
          <strong>{latestBackup?.created_at ? formatLiteTime(latestBackup.created_at) : 'None yet'}</strong>
          <StatusBadge status={backendBadgeStatus(data?.status)}>
            {latestBackup ? 'Safe restore point' : backendLabel(data?.status, {
              ready: 'Recovery Ready',
              review: 'Needs Attention',
              danger: 'Needs Attention',
              checking: 'Checking',
            })}
          </StatusBadge>
          <div className="lite-recovery-confidence-meter" aria-hidden="true">
            <span style={{ width: `${restoreSteps.filter((step) => step.complete).length * 20}%` }} />
          </div>
        </div>
      </section>

      <GlassCard className="lite-recovery-card lite-recovery-timeline-card">
        <div className="lite-recovery-card-head">
          <div>
            <h2>Restore readiness</h2>
            <p>Follow each safety step before restoring local state.</p>
          </div>
          <StatusBadge status={restoreSucceeded ? 'healthy' : latestPreviewReady ? 'degraded' : 'unknown'}>
            {restoreSucceeded ? 'Restored' : latestPreviewReady ? 'Ready to restore' : 'In progress'}
          </StatusBadge>
        </div>
        <div className="lite-recovery-timeline">
          {restoreSteps.map((step, index) => (
            <div key={step.key} className={`lite-recovery-step ${step.complete ? 'lite-recovery-step-complete' : ''}`}>
              <div className="lite-recovery-step-dot">{step.complete ? '✓' : index + 1}</div>
              <strong>{step.label}</strong>
              <span>{step.detail}</span>
            </div>
          ))}
        </div>
      </GlassCard>

      {loading ? <LoadingCard label="Loading recovery..." /> : null}

      {error ? (
        <StateSurface
          tone="degraded"
          title="Recovery needs a moment"
          description={error}
          className="mb-5"
        />
      ) : null}

      {actionError ? (
        <StateSurface
          tone="degraded"
          title="Recovery action needs attention"
          description={actionError}
          className="mb-5"
        />
      ) : null}

      {verifyResult ? (
        <StateSurface
          tone="healthy"
          title="Backup verification queued"
          description={verifyResult.summary || 'Pocket Lab is checking the backup evidence and repository metadata.'}
          className="mb-5"
        />
      ) : null}

      {previewResult ? (
        <StateSurface
          tone="healthy"
          title="Restore preview queued"
          description={previewResult.summary || 'Pocket Lab is preparing a restore preview without changing local state.'}
          className="mb-5"
        />
      ) : null}

      {restoreResult ? (
        <StateSurface
          tone="healthy"
          title="Restore queued"
          description={restoreResult.summary || 'Pocket Lab will create a checkpoint before applying the restore.'}
          className="mb-5"
        />
      ) : null}

      <div className="lite-recovery-grid">
        <GlassCard className="lite-recovery-card lite-recovery-backup-card">
          <div className="lite-recovery-card-head">
            <div className="lite-recovery-mini-icon">
              <Database className="h-5 w-5" />
            </div>
            <StatusBadge status={repository?.ready ? 'healthy' : backendBadgeStatus(data?.status)}>
              {repository?.ready ? 'Repository ready' : 'Needs Attention'}
            </StatusBadge>
          </div>

          <h2>Backup status</h2>
          <p>{data?.summary || 'Pocket Lab is checking whether backups are ready.'}</p>

          <div className="lite-recovery-facts">
            <div>
              <span>Stored in</span>
              <strong>{repository?.location || 'Local backup folder'}</strong>
            </div>
            <div>
              <span>Engine</span>
              <strong>{repository?.engine || 'restic'}</strong>
            </div>
            <div>
              <span>Last check</span>
              <strong>{data?.updated_at ? formatLiteTime(data.updated_at) : 'Not available yet'}</strong>
            </div>
            <div>
              <span>Last verification</span>
              <strong>{data?.last_verification_result || 'Not verified yet'}</strong>
            </div>
          </div>

          <div className="mt-5">
            <LiteButton onClick={backup} disabled={busy === 'backup'}>
              {busy === 'backup' ? 'Starting backup...' : 'Backup Now'}
            </LiteButton>
          </div>
        </GlassCard>

        <GlassCard className="lite-recovery-card">
          <div className="lite-recovery-card-head">
            <div className="lite-recovery-mini-icon">
              <FileCheck className="h-5 w-5" />
            </div>
            <span className="lite-recovery-warning-badge">Evidence saved</span>
          </div>

          <h2>What is protected</h2>
          <p>Pocket Lab saves the Lite state needed to recover devices, app metadata, rules, and evidence.</p>

          <div className="lite-recovery-checklist">
            {(data?.what_will_be_backed_up || []).slice(0, 6).map((item) => (
              <div key={item}>
                <span className="lite-recovery-dot" />
                {item}
              </div>
            ))}
          </div>
        </GlassCard>
      </div>

      <div className="lite-recovery-grid mt-4">
        <GlassCard className="lite-recovery-card">
          <div className="lite-recovery-card-head">
            <div className="lite-recovery-mini-icon lite-recovery-mini-icon-warning">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <span className="lite-recovery-warning-badge">Secrets excluded</span>
          </div>
          <h2>What is not backed up</h2>
          <p>Raw secrets are not saved by default. A separate encrypted secret recovery bundle can be added later only with clear confirmation.</p>
          <div className="lite-recovery-checklist">
            {(data?.what_will_not_be_backed_up || []).slice(0, 6).map((item) => (
              <div key={item}>
                <span className="lite-recovery-dot lite-recovery-dot-warning" />
                {item}
              </div>
            ))}
          </div>
        </GlassCard>

        <GlassCard className="lite-recovery-card lite-recovery-restore-card lite-recovery-restore-cockpit">
          <div className="lite-recovery-card-head">
            <div className="lite-recovery-mini-icon lite-recovery-mini-icon-warning">
              <FileCheck className="h-5 w-5" />
            </div>
            <span className="lite-recovery-warning-badge">Protected</span>
          </div>

          <h2>Restore Latest</h2>
          <p>
            Verify the backup, preview what would change, then restore only after clear confirmation.
          </p>

          <div className={`lite-recovery-flip-shell ${activePanel ? 'is-flipped' : ''}`}>
            <div className="lite-recovery-flip-inner">
              <div className="lite-recovery-flip-face lite-recovery-flip-front" aria-hidden={Boolean(activePanel)}>
                <div className="lite-recovery-restore-chips">
                  <span className={latestBackupVerified ? 'is-ready' : ''}>Verified</span>
                  <span className={latestPreviewReady ? 'is-ready' : ''}>Preview ready</span>
                  <span className={checkpoint?.checkpoint_id ? 'is-ready' : ''}>Checkpoint saved</span>
                  <span className={healthValidation?.status === 'passed' ? 'is-ready' : ''}>Health passed</span>
                </div>

                <div className="lite-recovery-preview-stats">
                  {previewStats.map((stat) => (
                    <div key={stat.label}>
                      <span>{stat.label}</span>
                      <strong>{stat.value}</strong>
                    </div>
                  ))}
                </div>

                <div className="lite-recovery-warning-note lite-recovery-safety-panel">
                  <strong>{latestBackupVerified ? 'Backup verified' : 'Verification required'}</strong>
                  <span>{latestPreview ? `Latest preview checks ${latestPreview.change_count || 0} item(s).` : 'Pocket Lab will check the backup and show what changes before restoring.'}</span>
                  {checkpoint?.checkpoint_id ? <span>Checkpoint: {shortId(checkpoint.checkpoint_id)}</span> : null}
                  {lastRestore?.status ? <span>Last restore: {lastRestore.status}</span> : null}
                  {serviceRestart?.status ? <span>Service restart: {serviceRestart.status}</span> : null}
                  {healthValidation?.status ? <span>Health: {healthValidation.status}</span> : null}
                </div>

                {lastRestore?.restore_id ? (
                  <div className="lite-recovery-last-restore-card">
                    <span>Last restore</span>
                    <strong>{lastRestore.status || 'Unknown'}</strong>
                    <p>{lastRestore.summary || `${lastRestore.restored_file_count || 0} file(s) restored.`}</p>
                  </div>
                ) : null}
              </div>

              <div className="lite-recovery-flip-face lite-recovery-flip-back" aria-hidden={!activePanel}>
                <button type="button" className="lite-recovery-flip-close" onClick={closeActionPanel} aria-label="Show restore controls">
                  <X className="h-4 w-4" />
                </button>
                <div className="lite-recovery-flip-head">
                  <span>{activePanel?.title || 'Restore readiness'}</span>
                  <h3>{activePanel?.subtitle || 'Pocket Lab is preparing the restore path.'}</h3>
                  {activePanel?.next ? <p>Next suggested action: <strong>{activePanel.next}</strong></p> : null}
                </div>
                <div className="lite-recovery-flip-readiness">
                  {restoreSteps.map((step) => (
                    <div key={step.key} className={step.complete ? 'is-complete' : ''}>
                      <span>{step.complete ? '✓' : '•'}</span>
                      <strong>{step.label}</strong>
                      <small>{step.detail}</small>
                    </div>
                  ))}
                </div>
                <div className="lite-recovery-action-log">
                  <strong>Friendly log</strong>
                  {(activePanel?.logs || []).map((line) => (
                    <p key={line}>{line}</p>
                  ))}
                </div>
                {activeActionPanel === 'evidence' ? (
                  <LiteButton disabled={!evidenceItems.length} tone="secondary" onClick={() => setEvidenceOpen(true)}>
                    Open evidence details
                  </LiteButton>
                ) : null}
              </div>
            </div>
          </div>

          <div className="lite-recovery-action-buttons">
            <span className={highlightedAction === 'verify' ? 'lite-recovery-next-action' : ''}>
              <LiteButton disabled={!latestBackup || busy === 'verify'} tone="secondary" onClick={verifyLatestBackup}>
                {busy === 'verify' ? 'Verifying evidence...' : 'Verify Backup'}
              </LiteButton>
            </span>
            <span className={highlightedAction === 'preview' ? 'lite-recovery-next-action' : ''}>
              <LiteButton disabled={!latestBackup || busy === 'preview'} tone="secondary" onClick={previewLatestRestore}>
                {busy === 'preview' ? 'Preparing preview...' : 'Preview Restore'}
              </LiteButton>
            </span>
            <span className={highlightedAction === 'restore' ? 'lite-recovery-next-action' : ''}>
              <LiteButton disabled={!latestBackupVerified || !latestPreviewReady || busy === 'restore'} tone="danger" onClick={restoreLatestBackup}>
                {busy === 'restore' ? 'Creating checkpoint...' : 'Restore Latest'}
              </LiteButton>
            </span>
            <span className={highlightedAction === 'evidence' ? 'lite-recovery-next-action' : ''}>
              <LiteButton disabled={!evidenceItems.length} tone="secondary" onClick={() => openActionPanel('evidence')}>
                Evidence
              </LiteButton>
            </span>
          </div>
        </GlassCard>
      </div>

      <GlassCard className="lite-recovery-card mt-4 lite-recovery-history-card">
        <div className="lite-recovery-card-head">
          <div>
            <h2>Backup history</h2>
            <p>Available restore points and evidence receipts appear here.</p>
          </div>
          <StatusBadge status={history.length ? 'healthy' : 'unknown'}>{history.length} saved</StatusBadge>
        </div>
        {history.length ? (
          <div className="lite-recovery-history">
            {history.slice(0, 6).map((backup) => (
              <div key={backup.backup_id} className="lite-recovery-history-row lite-recovery-history-row-premium">
                <div>
                  <strong>{backup.verification_status === 'verified' ? 'Backup verified and ready' : backup.summary || 'Backup created'}</strong>
                  <span>{formatLiteTime(backup.created_at)} · {backup.engine || 'restic'} · {backup.included_file_count || 0} item(s)</span>
                  <div className="lite-recovery-history-tags">
                    <em>Encrypted</em>
                    <em>{backup.verification_status === 'verified' ? 'Verified' : 'Needs verification'}</em>
                    {latestPreviewReady ? <em>Preview ready</em> : null}
                  </div>
                </div>
                <div className="lite-recovery-history-actions">
                  <StatusBadge status={backup.verification_status === 'verified' ? 'healthy' : 'degraded'}>
                    {backup.verification_status === 'verified' ? 'Verified' : 'Not verified'}
                  </StatusBadge>
                  <button type="button" onClick={() => setEvidenceOpen(true)}>Evidence</button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <StateSurface
            tone="empty"
            title="No backups yet"
            description="Use Backup Now to create your first encrypted local backup."
          />
        )}
      </GlassCard>

      {evidenceOpen ? (
        <div className="lite-recovery-evidence-backdrop" role="presentation" onClick={() => setEvidenceOpen(false)}>
          <aside className="lite-recovery-evidence-drawer" role="dialog" aria-label="Recovery evidence" onClick={(event) => event.stopPropagation()}>
            <div className="lite-recovery-evidence-head">
              <div>
                <span>Evidence</span>
                <h2>Recovery details</h2>
                <p>IDs are shortened here. Copy a value to inspect logs or evidence.</p>
              </div>
              <button type="button" onClick={() => setEvidenceOpen(false)} aria-label="Close evidence details">×</button>
            </div>
            <div className="lite-recovery-evidence-list">
              {evidenceItems.map((item) => (
                <div key={item.label} className="lite-recovery-evidence-item">
                  <span>{item.label}</span>
                  <strong>{shortId(item.value)}</strong>
                  <button type="button" onClick={() => copyEvidence(item.value, item.label)}>
                    <Copy className="h-4 w-4" />
                    {copiedEvidence === item.label ? 'Copied' : 'Copy'}
                  </button>
                </div>
              ))}
            </div>
          </aside>
        </div>
      ) : null}

      <ResultNotice result={backupResult} error={actionError} />
    </>
  );
}

class LiteErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="pocket-app-shell theme-pocket-lite-daylight lite-motion-system">
          <main className="pocket-main lite-error-boundary-wrap">
            <GlassCard className="lite-error-boundary-card">
              <div className="lite-devices-mini-icon">
                <WifiOff className="h-5 w-5" />
              </div>
              <h1>Pocket Lab needs a moment</h1>
              <p>Refresh the Devices tab. Your services are still running, and Pocket Lab kept the action safely contained.</p>
              <LiteButton onClick={() => window.location.reload()} tone="secondary">Refresh app</LiteButton>
            </GlassCard>
          </main>
        </div>
      );
    }
    return this.props.children;
  }
}

function LiteAppShell() {
  const [active, setActive] = useState('home');
  const [menuOpen, setMenuOpen] = useState(false);
  const online = useOnlineStatus();
  const { status, loading, error, refresh } = useLiteStatus();

  const content = {
    home: <HomeScreen status={status} loading={loading} error={error} refresh={refresh} onNavigate={setActive} />,
    catalog: <CatalogScreen />,
    identity: <IdentityScreen />,
    security: <SecurityScreen />,
    devices: <DevicesScreen />,
    rules: <RulesScreen />,
    recovery: <RecoveryScreen />,
  }[active];

  return (
    <div className="pocket-app-shell theme-pocket-lite-daylight lite-motion-system">
      <a href="#pocket-lite-main" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[80] focus:rounded-xl focus:bg-indigo-500 focus:px-4 focus:py-2 focus:text-sm focus:font-black focus:text-white">Skip to Pocket Lab Lite content</a>
      <div className="pocket-app-backdrop" aria-hidden="true" />

      {!online && (
        <div className="fixed left-1/2 top-4 z-[90] w-[calc(100vw-2rem)] max-w-2xl -translate-x-1/2 rounded-3xl border border-slate-300/20 bg-slate-950/95 px-4 py-3 text-slate-100 shadow-2xl shadow-black/40 backdrop-blur-xl" role="status">
          <div className="flex items-start gap-3">
            <div className="rounded-2xl border border-slate-300/20 bg-slate-500/10 p-2 text-slate-200"><WifiOff className="h-5 w-5" /></div>
            <div className="min-w-0">
              <p className="text-sm font-black text-white">You are offline</p>
              <p className="mt-1 text-sm text-slate-300">Pocket Lab Lite will show cached information where possible. Changes are paused until your connection returns.</p>
            </div>
          </div>
        </div>
      )}

      <header className="relative z-20 border-b border-white/10 bg-slate-950/70 backdrop-blur-xl">
        <div className="mx-auto flex w-full max-w-[1500px] items-center justify-between gap-3 px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3">
            <div className="rounded-2xl border border-indigo-300/25 bg-indigo-500/15 p-2 text-indigo-100"><Download className="h-5 w-5" /></div>
            <div>
              <p className="text-xs font-black uppercase tracking-[0.18em] text-indigo-200">Pocket Lab Lite</p>
              <p className="text-sm text-slate-400">Self-hosted workspace</p>
            </div>
          </div>
          <button type="button" onClick={() => setMenuOpen(true)} className="rounded-2xl border border-white/10 bg-white/5 p-3 text-slate-100 md:hidden" aria-label="Open navigation"><Menu className="h-5 w-5" /></button>
        </div>
      </header>

      <nav className="pocket-nav-dock scrollbar-none" aria-label="Pocket Lab Lite sections">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = active === item.id;
          return (
            <button key={item.id} type="button" onClick={() => setActive(item.id)} aria-current={isActive ? 'page' : undefined} className={`pocket-nav-button nav-active-rail-item ${isActive ? 'pocket-nav-button-active' : ''}`}>
              <Icon className="nav-active-rail-icon relative z-10 h-5 w-5" />
              <span className="relative z-10 mt-1 text-[0.68rem] font-bold tracking-wide">{item.label.split(' ')[0]}</span>
            </button>
          );
        })}
      </nav>

      <nav className="pocket-side-rail" aria-label="Pocket Lab Lite primary sections">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = active === item.id;
          return (
            <button key={item.id} type="button" onClick={() => setActive(item.id)} title={item.label} aria-label={item.label} aria-current={isActive ? 'page' : undefined} className={`pocket-side-button nav-active-rail-item ${isActive ? 'pocket-side-button-active' : ''}`}>
              <Icon className="nav-active-rail-icon h-5 w-5" />
            </button>
          );
        })}
      </nav>

      {menuOpen && <div className="mobile-more-backdrop" onClick={() => setMenuOpen(false)} aria-hidden="true" />}
      <aside className={`mobile-more-sheet ${menuOpen ? 'mobile-more-sheet-open' : ''}`} aria-hidden={!menuOpen} aria-label="Pocket Lab Lite sections">
        <div className="flex items-center justify-between gap-3 border-b border-white/10 p-4">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.18em] text-indigo-200">Sections</p>
            <h2 className="text-lg font-black text-white">Open Pocket Lab Lite</h2>
          </div>
          <button type="button" onClick={() => setMenuOpen(false)} className="rounded-2xl border border-white/10 bg-white/5 p-2 text-slate-200 hover:bg-white/10" aria-label="Close navigation"><X className="h-5 w-5" /></button>
        </div>
        <div className="grid gap-2 p-4">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            return (
              <button key={item.id} type="button" onClick={() => { setActive(item.id); setMenuOpen(false); }} className="mobile-more-item nav-active-rail-item">
                <Icon className="nav-active-rail-icon h-5 w-5" />
                <span>{item.label}</span>
              </button>
            );
          })}
        </div>
      </aside>

      <main id="pocket-lite-main" key={active} className="pocket-main nav-page-fade lg:pl-24 xl:pl-28">
        {content}
      </main>
    </div>
  );
}

export default function LiteApp() {
  return (
    <LiteErrorBoundary>
      <LiteAppShell />
    </LiteErrorBoundary>
  );
}

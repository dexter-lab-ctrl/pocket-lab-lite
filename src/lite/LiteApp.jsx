import React, { useMemo, useState } from 'react';
import {
  Activity,
  Copy,
  Database,
  Download,
  FileCheck,
  Fingerprint,
  LayoutGrid,
  Menu,
  Network,
  ShieldCheck,
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

function deviceStatusLabel(status) {
  const value = String(status || '').toLowerCase().replace(/[\s-]+/g, '_');
  if (['pending', 'invited', 'invite_sent'].includes(value)) return 'Invite sent';
  if (['joining', 'accepted', 'setup_started'].includes(value)) return 'Joining';
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

  if (['degraded', 'warning', 'needs_attention', 'pending', 'invited', 'invite_sent', 'pending_approval', 'approval_required', 'waiting_for_approval', 'paused'].includes(value)) {
    return 'review';
  }

  if (['unhealthy', 'failed', 'failure', 'error', 'blocked', 'unavailable'].includes(value)) {
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

function LiteButton({ children, onClick, disabled = false, tone = 'primary', type = 'button' }) {
  const toneClass = {
    primary: 'pocket-button-primary',
    secondary: 'pocket-button-secondary',
    success: 'pocket-button-success',
    danger: 'pocket-button-danger',
  }[tone] || 'pocket-button-secondary';
  return (
    <button type={type} onClick={onClick} disabled={disabled} className={`pocket-button ${toneClass}`}>
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

  const findings = Number(data?.findings_count ?? 0);
  const checks = Number(data?.checks_count ?? 0);
  const safetyStatus = data?.status || (findings === 0 ? 'healthy' : 'degraded');
  const safetyState = normalizeBackendState(safetyStatus);
  const safetyIsReady = safetyState === 'ready' && findings === 0;
  const safetyLabel = backendLabel(safetyStatus, {
    ready: findings === 0 ? 'Looks safe' : 'Review recommended',
    review: 'Review recommended',
    danger: 'Needs attention',
    checking: 'Checking safety',
  });
  const safetyScore = safetyIsReady ? 100 : Math.max(55, 100 - Math.max(findings, 1) * 12);

  async function scan() {
    setBusy(true);
    setResult(null);
    setActionError(null);
    try {
      setResult(await liteApi.runSecurityScan('local'));
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
        eyebrow="Safety"
        title="Security"
        description="Check whether your Pocket Lab needs attention. The results are summarized clearly so you know what to do next."
        actions={<LiteButton onClick={scan} disabled={busy}>{busy ? 'Checking...' : 'Run Safety Check'}</LiteButton>}
      />

      <section className="lite-security-hero">
        <div className="lite-security-hero-copy">
          <div className="lite-home-pill">
            <span className="lite-ready-dot" />
            {safetyLabel}
          </div>
          <h2>{backendHeroTitle(safetyStatus, {
            ready: safetyIsReady ? 'No urgent safety issues found.' : 'A few items may need your review.',
            review: 'A few items may need your review.',
            danger: 'Safety needs attention.',
            checking: 'Checking your safety status.',
          })}</h2>
          <p>
            Run a quick safety check anytime. Pocket Lab keeps the result simple and helps you focus on what matters.
          </p>
          <div className="lite-security-actions">
            <LiteButton onClick={scan} disabled={busy}>{busy ? 'Checking...' : 'Run Safety Check'}</LiteButton>
            <LiteButton onClick={refresh} tone="secondary">Refresh</LiteButton>
          </div>
        </div>

        <div className="lite-security-score-card">
          <div className="lite-security-score-ring" style={{ '--score': `${safetyScore}%` }}>
            <span>{safetyScore}</span>
          </div>
          <strong>Safety score</strong>
          <p>{backendLabel(safetyStatus, {
            ready: safetyIsReady ? 'Everything important looks okay.' : 'Review the recommended items.',
            review: 'Review the recommended items.',
            danger: 'Take a look before making more changes.',
            checking: 'Pocket Lab is checking the current result.',
          })}</p>
          <StatusBadge status={backendBadgeStatus(safetyStatus)}>
            {backendLabel(safetyStatus, {
              ready: safetyIsReady ? 'Ready' : 'Review',
              review: 'Review',
              danger: 'Attention',
              checking: 'Checking',
            })}
          </StatusBadge>
        </div>
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
              {backendLabel(safetyStatus, {
                ready: safetyIsReady ? 'Ready' : 'Review',
                review: 'Review',
                danger: 'Attention',
                checking: 'Checking',
              })}
            </StatusBadge>
          </div>

          <h2>{backendHeroTitle(safetyStatus, {
            ready: safetyIsReady ? 'No critical issues' : 'Review recommended',
            review: 'Review recommended',
            danger: 'Needs attention',
            checking: 'Checking safety',
          })}</h2>
          <p>{data?.summary || 'Pocket Lab is checking the current safety state.'}</p>

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
        </GlassCard>

        <GlassCard className="lite-security-card lite-security-guide-card">
          <div className="lite-security-card-head">
            <div className="lite-security-icon">
              <FileCheck className="h-5 w-5" />
            </div>
            <span className="lite-security-soft-badge">Simple guidance</span>
          </div>

          <h2>What happens during a check?</h2>
          <p>
            Pocket Lab reviews the local setup and reports only the outcome you need to act on.
          </p>

          <div className="lite-security-steps">
            <div>
              <span>1</span>
              <p>Check local readiness</p>
            </div>
            <div>
              <span>2</span>
              <p>Summarize what changed</p>
            </div>
            <div>
              <span>3</span>
              <p>Show clear next steps</p>
            </div>
          </div>
        </GlassCard>
      </div>

      <ResultNotice result={result} error={actionError} />
    </>
  );
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
  const devices = data?.devices || [];
  const latestInvite = invite || data?.latest_invite || null;
  const onlineDevices = devices.filter((device) => normalizeBackendState(device.status) === 'ready').length;
  const selectedRoleLabel = roleLabel(selectedRole);

  async function addDevice() {
    setBusy(true);
    setResult({ status: 'queued', summary: 'Preparing invite...' });
    setInvite(null);
    setCopied(false);
    setActionError(null);
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
      setResult(null);
      setActionError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function copyInvite() {
    const copyValue = latestInvite?.copy_text || latestInvite?.url;
    const didCopy = await copyTextToClipboard(copyValue);
    if (didCopy) {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    }
    refresh();
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
            {onlineDevices > 0 ? 'Devices online' : 'Ready to add devices'}
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
            onChange={(event) => setHostname(event.target.value)}
            placeholder="Optional, for example: Kitchen tablet"
            aria-label="Device name"
          />

          <div className="lite-devices-field-label">Select a role</div>
          <div className="lite-role-selector" role="radiogroup" aria-label="Device role">
            {DEVICE_ROLE_OPTIONS.map((role) => (
              <button
                key={role.value}
                type="button"
                className={`lite-role-card ${selectedRole === role.value ? 'lite-role-card-selected' : ''}`}
                onClick={() => setSelectedRole(role.value)}
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
            <LiteButton onClick={addDevice} disabled={busy}>
              {busy ? 'Preparing invite...' : 'Add Device'}
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

              <p>{latestInvite.instructions || 'Open this invite on the new device while it is connected to the same Pocket Lab private network.'}</p>

              {latestInvite.url || latestInvite.copy_text ? (
                <LiteButton onClick={copyInvite} tone="secondary">
                  <Copy className="h-4 w-4" /> {copied ? 'Copied' : 'Copy Invite Link'}
                </LiteButton>
              ) : (
                <span className="lite-invite-muted">Invite link was created earlier. Create a new invite if you need to copy it again.</span>
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

          {loading ? <LoadingCard label="Loading devices..." /> : null}

          <div className="lite-devices-grid">
            {devices.map((device) => {
              const online = normalizeBackendState(device.status) === 'ready';

              return (
                <GlassCard key={device.id || device.name} className="lite-device-card">
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
                      <strong>{device.remote_access ? 'Ready' : (['pending', 'invited'].includes(String(device.status || '').toLowerCase()) ? 'Waiting' : 'Not set up yet')}</strong>
                    </div>
                  </div>
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

      <ResultNotice result={latestInvite ? null : result} error={actionError} />
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

function RecoveryScreen() {
  const { data, loading, error, refresh } = useLiteResource(liteApi.recovery, []);
  const [backupResult, setBackupResult] = useState(null);
  const [restoreResult, setRestoreResult] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [confirmRestore, setConfirmRestore] = useState(false);
  const [busy, setBusy] = useState('');

  async function backup() {
    setBusy('backup');
    setBackupResult(null);
    setRestoreResult(null);
    setActionError(null);
    try {
      setBackupResult(await liteApi.backupNow({ include_event_journal: true }));
      refresh();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setBusy('');
    }
  }

  async function restore() {
    setBusy('restore');
    setRestoreResult(null);
    setBackupResult(null);
    setActionError(null);
    try {
      setRestoreResult(await liteApi.restoreBackup({ backup_ref: 'latest', confirm: confirmRestore }));
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
        description="Create a safety copy before changes and restore only when you clearly choose to continue."
        actions={<LiteButton onClick={refresh} tone="secondary">Refresh</LiteButton>}
      />

      <section className="lite-recovery-hero">
        <div className="lite-recovery-hero-copy">
          <div className="lite-home-pill">
            <span className="lite-ready-dot" />
            {backendLabel(data?.status, {
              ready: 'Recovery ready',
              review: 'Recovery needs review',
              danger: 'Recovery needs attention',
              checking: 'Checking recovery',
            })}
          </div>
          <h2>{backendHeroTitle(data?.status, {
            ready: 'Keep a safe way back.',
            review: 'Review your recovery setup.',
            danger: 'Recovery needs attention.',
            checking: 'Checking recovery readiness.',
          })}</h2>
          <p>
            Back up your Pocket Lab before important changes. Restore is intentionally protected so it cannot happen by accident.
          </p>
          <div className="lite-recovery-actions">
            <LiteButton onClick={backup} disabled={busy === 'backup'}>
              {busy === 'backup' ? 'Starting backup...' : 'Backup Now'}
            </LiteButton>
            <LiteButton onClick={refresh} tone="secondary">Refresh</LiteButton>
          </div>
        </div>

        <div className="lite-recovery-status-card">
          <div className="lite-recovery-icon">
            <Database className="h-7 w-7" />
          </div>
          <span>Recovery state</span>
          <strong>{backendLabel(data?.status, {
            ready: 'Ready',
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

      {loading ? <LoadingCard label="Loading recovery..." /> : null}

      {error ? (
        <StateSurface
          tone="degraded"
          title="Recovery needs a moment"
          description={error}
          className="mb-5"
        />
      ) : null}

      <div className="lite-recovery-grid">
        <GlassCard className="lite-recovery-card lite-recovery-backup-card">
          <div className="lite-recovery-card-head">
            <div className="lite-recovery-mini-icon">
              <Database className="h-5 w-5" />
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

          <h2>Backup</h2>
          <p>
            {data?.summary || 'Pocket Lab is checking whether backup and restore are ready.'}
          </p>

          <div className="lite-recovery-checklist">
            <div>
              <span className="lite-recovery-dot" />
              Save a recovery point before important changes
            </div>
            <div>
              <span className="lite-recovery-dot" />
              Keep restore separate from everyday actions
            </div>
            <div>
              <span className="lite-recovery-dot" />
              Show a clear result after every request
            </div>
          </div>

          <div className="mt-5">
            <LiteButton onClick={backup} disabled={busy === 'backup'}>
              {busy === 'backup' ? 'Starting backup...' : 'Backup Now'}
            </LiteButton>
          </div>
        </GlassCard>

        <GlassCard className="lite-recovery-card lite-recovery-restore-card">
          <div className="lite-recovery-card-head">
            <div className="lite-recovery-mini-icon lite-recovery-mini-icon-warning">
              <FileCheck className="h-5 w-5" />
            </div>
            <span className="lite-recovery-warning-badge">Confirm first</span>
          </div>

          <h2>Restore</h2>
          <p>
            Restore can replace the current setup with the latest saved backup. Use it only when you are sure.
          </p>

          <button
            type="button"
            className={`lite-recovery-confirm ${confirmRestore ? 'lite-recovery-confirm-on' : ''}`}
            onClick={() => setConfirmRestore((value) => !value)}
            aria-pressed={confirmRestore}
          >
            <span className="lite-recovery-confirm-box">
              {confirmRestore ? '✓' : ''}
            </span>
            <span>
              <strong>I understand what restore does</strong>
              <small>{confirmRestore ? 'Restore is now unlocked.' : 'Turn this on before restoring.'}</small>
            </span>
          </button>

          <div className="lite-recovery-warning-note">
            <strong>Restore is protected</strong>
            <span>You must confirm before Pocket Lab starts a restore request.</span>
          </div>

          <div className="mt-5">
            <LiteButton
              onClick={restore}
              disabled={busy === 'restore' || !confirmRestore}
              tone="danger"
            >
              {busy === 'restore' ? 'Starting restore...' : 'Restore Latest'}
            </LiteButton>
          </div>
        </GlassCard>
      </div>

      <ResultNotice result={backupResult || restoreResult} error={actionError} />
    </>
  );
}

export default function LiteApp() {
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
              <p className="text-sm text-slate-400">Simple self-hosted workspace</p>
            </div>
          </div>
          <div className="hidden items-center gap-2 md:flex">
            <StatusBadge status={status.overall}>{status.overall === 'healthy' ? 'Ready' : 'Needs attention'}</StatusBadge>
            <button type="button" onClick={refresh} className="pocket-button pocket-button-secondary">Refresh</button>
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

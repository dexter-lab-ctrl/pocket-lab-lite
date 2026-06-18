import React, { useMemo, useState } from 'react';
import {
  Activity,
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

function HomeScreen({ status, loading, error, refresh, onNavigate }) {
  const primaryServices = useMemo(() => status.services?.slice(0, 6) || [], [status.services]);
  const stats = status.summary || {};
  return (
    <>
      <PageHeader
        title="Home"
        description="A simple overview of this Pocket Lab Lite device, what needs attention, and the safest next actions."
        actions={<LiteButton onClick={refresh} tone="secondary">Refresh</LiteButton>}
      />
      {error ? <StateSurface tone="degraded" title="Pocket Lab Lite is not reachable" description={error} className="mb-5" /> : null}
      <div className="grid gap-4 lg:grid-cols-[1.4fr_0.8fr]">
        <GlassCard>
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-xs font-black uppercase tracking-[0.18em] text-indigo-200">Device status</p>
              <h2 className="mt-2 text-2xl font-black text-white">{status.device?.name || 'pocket-lab'}</h2>
              <p className="mt-2 text-sm leading-6 text-slate-300">Mode: Lite · Resource profile: {status.device?.resource_profile || 'low-power'}</p>
            </div>
            <StatusBadge status={status.overall}>{status.overall === 'healthy' ? 'Ready' : 'Needs attention'}</StatusBadge>
          </div>
          <div className="mt-5 grid gap-3 sm:grid-cols-3">
            <div className="rounded-3xl border border-white/10 bg-white/5 p-4">
              <p className="text-2xl font-black text-white">{stats.apps_available ?? 0}</p>
              <p className="mt-1 text-xs font-bold uppercase tracking-[0.14em] text-slate-400">Apps available</p>
            </div>
            <div className="rounded-3xl border border-white/10 bg-white/5 p-4">
              <p className="text-2xl font-black text-white">{stats.devices_known ?? 0}</p>
              <p className="mt-1 text-xs font-bold uppercase tracking-[0.14em] text-slate-400">Devices known</p>
            </div>
            <div className="rounded-3xl border border-white/10 bg-white/5 p-4">
              <p className="text-2xl font-black text-white">{stats.security_findings ?? 0}</p>
              <p className="mt-1 text-xs font-bold uppercase tracking-[0.14em] text-slate-400">Items to review</p>
            </div>
          </div>
          <div className="mt-5 flex flex-wrap gap-2">
            <LiteButton onClick={() => onNavigate('catalog')}>Install App</LiteButton>
            <LiteButton onClick={() => onNavigate('devices')} tone="secondary">Add Device</LiteButton>
            <LiteButton onClick={() => onNavigate('security')} tone="secondary">Run Safety Check</LiteButton>
            <LiteButton onClick={() => onNavigate('recovery')} tone="secondary">Backup Now</LiteButton>
          </div>
        </GlassCard>
        <GlassCard>
          <p className="text-xs font-black uppercase tracking-[0.18em] text-cyan-200">Telemetry</p>
          <div className="mt-4 grid gap-3 text-sm text-slate-300">
            <div className="flex justify-between gap-3"><span>CPU usage</span><strong className="text-white">{status.telemetry?.cpu_usage_percent ?? '—'}%</strong></div>
            <div className="flex justify-between gap-3"><span>CPU temperature</span><strong className="text-white">{status.telemetry?.cpu_temp_c ?? '—'}°C</strong></div>
            <div className="flex justify-between gap-3"><span>Free space</span><strong className="text-white">{status.telemetry?.free_space_mb ?? '—'} MB</strong></div>
            <div className="flex justify-between gap-3"><span>Memory used</span><strong className="text-white">{status.telemetry?.memory_usage_mb ?? '—'} MB</strong></div>
          </div>
          <p className="mt-4 text-xs text-slate-500">Last checked: {formatLiteTime(status.checked_at)}</p>
        </GlassCard>
      </div>
      <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {loading ? <LoadingCard /> : primaryServices.map((service) => (
          <GlassCard key={service.name}>
            <div className="flex items-start justify-between gap-3">
              <h3 className="text-base font-black text-white">{service.name}</h3>
              <StatusBadge status={serviceTone(service.status)} />
            </div>
            <p className="mt-3 text-sm leading-6 text-slate-300">{service.summary}</p>
          </GlassCard>
        ))}
      </div>
    </>
  );
}

function CatalogScreen() {
  const { data, loading, error, refresh } = useLiteResource(liteApi.catalog, []);
  const [result, setResult] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const items = data?.items || [];

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
      <PageHeader title="App Catalog" description="Install and manage simple app/service packages without showing backend package details." actions={<LiteButton onClick={refresh} tone="secondary">Refresh</LiteButton>} />
      {error ? <StateSurface tone="degraded" title="Catalog unavailable" description={error} className="mb-5" /> : null}
      {loading ? <LoadingCard label="Loading app catalog..." /> : null}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {items.map((item) => (
          <GlassCard key={item.id}>
            <div className="flex items-start justify-between gap-3">
              <h2 className="text-lg font-black text-white">{item.name}</h2>
              <StatusBadge status={item.installed ? 'healthy' : 'ready'}>{item.installed ? 'Installed' : 'Available'}</StatusBadge>
            </div>
            <p className="mt-3 text-sm leading-6 text-slate-300">{item.summary}</p>
            <div className="mt-5 flex flex-wrap gap-2">
              <LiteButton onClick={() => install(item)} disabled={busyId === item.id}>{busyId === item.id ? 'Starting...' : 'Install'}</LiteButton>
            </div>
          </GlassCard>
        ))}
      </div>
      {!loading && items.length === 0 ? <StateSurface tone="empty" title="No apps yet" description="Refresh the catalog after bootstrap or add app metadata to the catalog source." /> : null}
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
      <PageHeader title="Identity & Access" description="Manage passwords and access readiness without exposing raw Vault paths, tokens, or policies." actions={<LiteButton onClick={refresh} tone="secondary">Refresh</LiteButton>} />
      <GlassCard>
        {loading ? <p className="text-sm text-slate-400">Checking access readiness...</p> : null}
        {error ? <StateSurface tone="degraded" title="Access summary unavailable" description={error} /> : null}
        {data ? (
          <>
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs font-black uppercase tracking-[0.18em] text-indigo-200">Passwords & Access</p>
                <h2 className="mt-2 text-2xl font-black text-white">Access is protected</h2>
                <p className="mt-2 text-sm leading-6 text-slate-300">{data.summary}</p>
              </div>
              <StatusBadge status={data.status} />
            </div>
            <div className="mt-5 grid gap-3 sm:grid-cols-[1fr_auto]">
              <input className="pocket-input" value={target} onChange={(event) => setTarget(event.target.value)} aria-label="Password or access target" />
              <LiteButton onClick={rotate} disabled={busy}>{busy ? 'Changing...' : 'Change Password'}</LiteButton>
            </div>
          </>
        ) : null}
      </GlassCard>
      <ResultNotice result={result} error={actionError} />
    </>
  );
}

function SecurityScreen() {
  const { data, loading, error, refresh } = useLiteResource(liteApi.security, []);
  const [result, setResult] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [busy, setBusy] = useState(false);

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
      <PageHeader title="Security" description="Run lightweight local safety checks and review simple findings." actions={<LiteButton onClick={scan} disabled={busy}>{busy ? 'Checking...' : 'Run Safety Check'}</LiteButton>} />
      <GlassCard>
        {loading ? <p className="text-sm text-slate-400">Loading safety summary...</p> : null}
        {error ? <StateSurface tone="degraded" title="Safety summary unavailable" description={error} /> : null}
        {data ? (
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-xs font-black uppercase tracking-[0.18em] text-emerald-200">Safety Center</p>
              <h2 className="mt-2 text-2xl font-black text-white">{data.findings_count ? 'Review recommended fixes' : 'No critical issues'}</h2>
              <p className="mt-2 text-sm leading-6 text-slate-300">{data.summary}</p>
            </div>
            <StatusBadge status={data.status === 'needs_attention' ? 'degraded' : data.status} />
          </div>
        ) : null}
      </GlassCard>
      <ResultNotice result={result} error={actionError} />
    </>
  );
}

function DevicesScreen() {
  const { data, loading, error, refresh } = useLiteResource(liteApi.fleet, []);
  const [hostname, setHostname] = useState('');
  const [result, setResult] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [busy, setBusy] = useState(false);
  const devices = data?.devices || [];

  async function addDevice() {
    setBusy(true);
    setResult(null);
    setActionError(null);
    try {
      setResult(await liteApi.addDevice({ role: 'compute', hostname: hostname || undefined }));
      refresh();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader title="Devices" description="Show this device and connected devices with simple online/offline status." />
      <GlassCard className="mb-4">
        <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
          <input className="pocket-input" value={hostname} onChange={(event) => setHostname(event.target.value)} placeholder="Optional device name" aria-label="Device name" />
          <LiteButton onClick={addDevice} disabled={busy}>{busy ? 'Creating invite...' : 'Add Device'}</LiteButton>
        </div>
      </GlassCard>
      {error ? <StateSurface tone="degraded" title="Device list unavailable" description={error} className="mb-4" /> : null}
      {loading ? <LoadingCard label="Loading devices..." /> : null}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {devices.map((device) => (
          <GlassCard key={device.id || device.name}>
            <div className="flex items-start justify-between gap-3">
              <h2 className="text-lg font-black text-white">{device.name}</h2>
              <StatusBadge status={device.status} />
            </div>
            <p className="mt-3 text-sm text-slate-300">Last seen: {formatLiteTime(device.last_seen)}</p>
            <p className="mt-2 text-sm text-slate-400">Remote access {device.remote_access ? 'ready' : 'not configured yet'}</p>
          </GlassCard>
        ))}
      </div>
      {!loading && devices.length === 0 ? <StateSurface tone="empty" title="No devices yet" description="Add a device to create an invite through the control plane." /> : null}
      <ResultNotice result={result} error={actionError} />
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
      <PageHeader title="Rules" description="Show whether basic safety rules are enabled without exposing policy internals." />
      <GlassCard>
        {loading ? <p className="text-sm text-slate-400">Loading rules...</p> : null}
        {error ? <StateSurface tone="degraded" title="Rules unavailable" description={error} /> : null}
        {data ? (
          <>
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-xs font-black uppercase tracking-[0.18em] text-cyan-200">Protection</p>
                <h2 className="mt-2 text-2xl font-black text-white">{data.protection_enabled ? 'Protection enabled' : 'Rules available'}</h2>
                <p className="mt-2 text-sm leading-6 text-slate-300">{data.summary}</p>
              </div>
              <StatusBadge status={data.status === 'needs_attention' ? 'degraded' : data.status} />
            </div>
            <label className="mt-5 flex items-center gap-3 rounded-3xl border border-white/10 bg-white/5 p-4 text-sm text-slate-200">
              <input type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} />
              Protection enabled
            </label>
            <div className="mt-4"><LiteButton onClick={apply} disabled={busy}>{busy ? 'Applying...' : 'Apply Rules'}</LiteButton></div>
          </>
        ) : null}
      </GlassCard>
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
      <PageHeader title="Recovery" description="Create backups and restore only after clear confirmation." actions={<LiteButton onClick={backup} disabled={busy === 'backup'}>{busy === 'backup' ? 'Starting...' : 'Backup Now'}</LiteButton>} />
      <GlassCard>
        {loading ? <p className="text-sm text-slate-400">Loading recovery summary...</p> : null}
        {error ? <StateSurface tone="degraded" title="Recovery summary unavailable" description={error} /> : null}
        {data ? (
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-xs font-black uppercase tracking-[0.18em] text-indigo-200">Backup & Restore</p>
              <h2 className="mt-2 text-2xl font-black text-white">Recovery ready</h2>
              <p className="mt-2 text-sm leading-6 text-slate-300">{data.summary}</p>
            </div>
            <StatusBadge status={data.status} />
          </div>
        ) : null}
      </GlassCard>
      <GlassCard className="mt-4 border-amber-300/20 bg-amber-500/10">
        <h2 className="text-lg font-black text-white">Restore</h2>
        <p className="mt-2 text-sm leading-6 text-amber-100">Restore can change local state. Confirm before continuing.</p>
        <label className="mt-4 flex items-center gap-3 text-sm text-amber-50">
          <input type="checkbox" checked={confirmRestore} onChange={(event) => setConfirmRestore(event.target.checked)} />
          I understand restore can change this device.
        </label>
        <div className="mt-4"><LiteButton onClick={restore} disabled={busy === 'restore'} tone="danger">{busy === 'restore' ? 'Starting restore...' : 'Restore Latest'}</LiteButton></div>
      </GlassCard>
      <ResultNotice result={backupResult || restoreResult} error={actionError} />
    </>
  );
}

export default function LiteApp() {
  const [active, setActive] = useState('home');
  const [menuOpen, setMenuOpen] = useState(false);
  const online = useOnlineStatus();
  const { status, loading, error, refresh } = useLiteStatus();
  const activeItem = NAV_ITEMS.find((item) => item.id === active) || NAV_ITEMS[0];

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
    <div className="pocket-app-shell theme-control-plane-graphite theme-midnight-saas-simple">
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
              <p className="text-sm text-slate-400">Low-power local control plane</p>
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
        <div className="mb-4 rounded-3xl border border-cyan-300/15 bg-cyan-500/10 p-4 text-sm text-cyan-50">
          <strong>{activeItem.label}</strong> · Simple appliance view. Actions are sent through the local control plane with safety checks.
        </div>
        {content}
      </main>
    </div>
  );
}

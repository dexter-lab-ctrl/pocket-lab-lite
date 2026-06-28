from pathlib import Path

ROOT = Path.cwd()
CATALOG = ROOT / "src/lite/LiteCatalog.jsx"
CSS = ROOT / "src/index.css"

catalog_source = r'''import React, { useMemo, useState } from 'react';
import {
  CheckCircle2,
  Clock3,
  ExternalLink,
  Image as ImageIcon,
  Info,
  RefreshCw,
  Search,
  Server,
  Sparkles,
  X,
} from 'lucide-react';
import { useLiteResource } from '../hooks/useLiteStatus.js';
import { formatLiteTime, liteApi } from '../lib/liteApi.js';
import { GlassCard, StatusBadge, StateSurface, PageHeader, LiteButton, ResultNotice, LoadingCard } from './LiteUi.jsx';

const PHOTOPRISM_ICON_URL = 'https://dl.photoprism.app/icons/app.svg';

const APP_FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'installed', label: 'Installed' },
  { id: 'available', label: 'Available' },
  { id: 'attention', label: 'Needs attention' },
];

function safeHaptic(duration = 8) {
  try {
    navigator.vibrate?.(duration);
  } catch {
    // Optional browser feedback only.
  }
}

function appTone(status) {
  const value = String(status || '').toLowerCase();
  if (['ready', 'installed', 'healthy'].includes(value)) return 'healthy';
  if (['installing', 'queued', 'running'].includes(value)) return 'working';
  if (['needs_attention', 'unavailable', 'failed'].includes(value)) return 'degraded';
  return 'ready';
}

function appLabel(app) {
  const value = String(app?.status || '').toLowerCase();
  if (value === 'ready' && app?.actions?.open) return 'Ready to open';
  if (value === 'ready' || app?.installed) return 'Installed';
  if (value === 'installing') return 'Installing';
  if (value === 'needs_attention') return 'Needs attention';
  if (value === 'unavailable') return 'Unavailable';
  return 'Available';
}

function appFilterState(app) {
  const value = String(app?.status || '').toLowerCase();
  if (['needs_attention', 'unavailable', 'failed'].includes(value)) return 'attention';
  if (value === 'ready' || app?.installed) return 'installed';
  return 'available';
}

function lastOperationText(app) {
  const op = app?.last_operation;
  if (!op) return 'No install has run yet.';
  const when = op.updated_at ? ` · ${formatLiteTime(op.updated_at)}` : '';
  return `${op.message || 'Latest install status is available.'}${when}`;
}

function resolveAppOpenUrl(item) {
  const raw =
    item?.access?.open_url ||
    item?.runtime?.url ||
    item?.runtime?.route ||
    '';

  if (!raw) return '';

  try {
    const url = new URL(raw, window.location.origin);
    if (!url.pathname.startsWith('/apps/')) {
      return '';
    }
    return url.toString();
  } catch {
    return '';
  }
}

function AppIcon({ app }) {
  const isPhotoPrism = String(app?.id || '').toLowerCase() === 'photoprism' || String(app?.name || '').toLowerCase().includes('photoprism');
  if (isPhotoPrism) {
    return <img src={PHOTOPRISM_ICON_URL} alt="" loading="lazy" decoding="async" />;
  }
  return <ImageIcon className="h-6 w-6" />;
}

function CatalogSkeletons() {
  return (
    <div className="lite-catalog-grid lite-catalog-skeleton-grid" aria-label="Loading App Catalog">
      {[0, 1, 2].map((item) => (
        <GlassCard key={item} className="lite-catalog-card lite-catalog-app-card lite-catalog-skeleton-card">
          <div className="lite-catalog-skeleton-icon" />
          <div className="lite-catalog-skeleton-line is-title" />
          <div className="lite-catalog-skeleton-line" />
          <div className="lite-catalog-skeleton-line is-short" />
          <div className="lite-catalog-skeleton-button" />
        </GlassCard>
      ))}
    </div>
  );
}

function DetailRow({ label, value }) {
  if (!value) return null;
  return (
    <div className="lite-catalog-detail-row">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function AppDetailsDrawer({ app, openUrl, opening, installing, canOpen, canInstall, onClose, onOpen, onInstall }) {
  if (!app) return null;
  const targetName = app?.target?.eligible_devices?.[0]?.name || 'Server Host';
  const health = app?.runtime?.health || (app?.installed ? 'healthy' : 'not installed');
  const evidenceCount = Array.isArray(app?.evidence_refs) ? app.evidence_refs.length : 0;

  return (
    <div className="lite-catalog-drawer-shell" role="dialog" aria-modal="true" aria-label={`${app.name} details`}>
      <button className="lite-catalog-drawer-backdrop" type="button" onClick={onClose} aria-label="Close app details" />
      <GlassCard className="lite-catalog-drawer">
        <div className="lite-catalog-drawer-grip" aria-hidden="true" />
        <div className="lite-catalog-drawer-head">
          <div className="lite-catalog-icon lite-catalog-icon-large"><AppIcon app={app} /></div>
          <div>
            <p className="lite-catalog-category">{app.category || 'Local app'}</p>
            <h2>{app.name}</h2>
            <p>{app.summary}</p>
          </div>
          <button className="lite-catalog-drawer-close" type="button" onClick={onClose} aria-label="Close app details"><X className="h-5 w-5" /></button>
        </div>
        <div className="lite-catalog-detail-grid">
          <DetailRow label="Status" value={appLabel(app)} />
          <DetailRow label="Runs on" value={targetName} />
          <DetailRow label="Health" value={health} />
          <DetailRow label="Address" value={openUrl ? '/apps/photoprism/' : app?.runtime?.route || app?.access?.open_url || 'Available after install'} />
          <DetailRow label="Evidence" value={evidenceCount ? `${evidenceCount} file(s)` : 'Saved after install'} />
        </div>
        <div className="lite-catalog-detail-note"><Info className="h-4 w-4" />Open uses the current Pocket Lab address and stays inside the private app route.</div>
        <div className="lite-catalog-drawer-actions">
          <LiteButton onClick={onInstall} disabled={!canInstall} tone={canInstall ? 'primary' : 'secondary'}>{installing ? 'Installing...' : app?.actions?.retry ? 'Retry' : app?.installed || app?.status === 'ready' ? 'Installed' : 'Install'}</LiteButton>
          <LiteButton onClick={onOpen} disabled={!canOpen} tone={canOpen ? 'primary' : 'ghost'}><ExternalLink className="h-4 w-4" />{opening ? 'Opening...' : 'Open'}</LiteButton>
        </div>
      </GlassCard>
    </div>
  );
}

export default function CatalogScreen() {
  const { data, loading, error, refresh } = useLiteResource(liteApi.catalog, []);
  const [query, setQuery] = useState('');
  const [activeFilter, setActiveFilter] = useState('all');
  const [selectedApp, setSelectedApp] = useState(null);
  const [result, setResult] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const [openingId, setOpeningId] = useState(null);

  const apps = data?.apps || data?.items || [];
  const access = data?.access || {};
  const featuredApp = apps.find((app) => String(app?.id || '').toLowerCase() === 'photoprism') || apps[0];

  const filteredApps = useMemo(() => {
    const value = query.trim().toLowerCase();
    return apps.filter((app) => {
      const matchesQuery = !value || `${app.name || ''} ${app.summary || ''} ${app.category || ''}`.toLowerCase().includes(value);
      const matchesFilter = activeFilter === 'all' || appFilterState(app) === activeFilter;
      return matchesQuery && matchesFilter;
    });
  }, [apps, activeFilter, query]);

  const readyCount = apps.filter((app) => app.status === 'ready' || app.installed).length;
  const installingCount = apps.filter((app) => app.status === 'installing').length;
  const attentionCount = apps.filter((app) => ['needs_attention', 'unavailable'].includes(String(app.status || ''))).length;

  async function install(app, event) {
    event?.stopPropagation?.();
    if (!app) return;
    safeHaptic(8);
    setBusyId(app.id);
    setResult({ status: 'queued', message: `${app.name || 'App'} install started.` });
    setActionError(null);
    try {
      const targetNodeId = app?.target?.default_node_id || 'pocket-lab-lite-server';
      setResult(await liteApi.installApp(app.id, { target_node_id: targetNodeId }));
      refresh();
      window.setTimeout(refresh, 700);
      window.setTimeout(refresh, 1800);
    } catch (err) {
      setActionError(err.message);
    } finally {
      setBusyId(null);
    }
  }

  function openApp(app, event) {
    event?.stopPropagation?.();
    const target = resolveAppOpenUrl(app);
    if (!target) return;
    safeHaptic(6);
    setOpeningId(app.id);
    window.setTimeout(() => window.location.assign(target), 160);
  }

  function renderAppCard(app, featured = false) {
    const status = String(app.status || 'not_installed').toLowerCase();
    const installing = status === 'installing' || busyId === app.id;
    const opening = openingId === app.id;
    const canInstall = Boolean(app?.actions?.install) && !installing;
    const canOpen = Boolean(app?.actions?.open && resolveAppOpenUrl(app));
    const targetName = app?.target?.eligible_devices?.[0]?.name || 'Server Host';
    const progress = app?.progress;
    const percent = Math.min(100, Math.max(0, ((progress?.current || 1) / (progress?.total || 7)) * 100));
    const openUrl = resolveAppOpenUrl(app);
    const cardClassName = `lite-catalog-card lite-catalog-app-card ${featured ? 'is-featured' : ''} ${installing ? 'is-installing' : ''}`;

    return (
      <GlassCard
        key={app.id}
        className={cardClassName}
        role="button"
        tabIndex={0}
        onClick={() => setSelectedApp(app)}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            setSelectedApp(app);
          }
        }}
      >
        <div className="lite-catalog-card-top">
          <div className="lite-catalog-icon"><AppIcon app={app} /></div>
          <StatusBadge status={appTone(status)}>{appLabel(app)}</StatusBadge>
        </div>
        <div className="lite-catalog-card-title-row">
          <div>
            <p className="lite-catalog-category">{featured ? 'Featured local app' : app.category || 'Local app'}</p>
            <h2>{app.name}</h2>
          </div>
        </div>
        <p>{app.summary}</p>
        <div className="lite-catalog-meta lite-catalog-meta-grid">
          <span><Server className="h-4 w-4" /> {targetName}</span>
          <span><CheckCircle2 className="h-4 w-4" /> {canOpen ? 'Ready to open' : app?.access?.message || 'Available after install'}</span>
          <span><Clock3 className="h-4 w-4" /> {app?.runtime?.health ? `Health: ${app.runtime.health}` : 'Health: not installed'}</span>
        </div>
        {progress ? (
          <div className="lite-catalog-progress" aria-label="Install progress">
            <div><strong>{progress.step || 'Working'}</strong><span>{progress.current || 1}/{progress.total || 7}</span></div>
            <p>{progress.message || 'Preparing the app.'}</p>
            <div className="lite-catalog-progress-bar"><span style={{ width: `${percent}%` }} /></div>
          </div>
        ) : null}
        <div className="lite-catalog-last-op"><strong>Latest status</strong><p>{lastOperationText(app)}</p></div>
        <div className="lite-catalog-actions">
          <LiteButton onClick={(event) => install(app, event)} disabled={!canInstall} tone={canInstall ? 'primary' : 'secondary'}>{installing ? 'Installing...' : app?.actions?.retry ? 'Retry' : status === 'ready' ? 'Installed' : 'Install'}</LiteButton>
          <LiteButton onClick={(event) => openApp(app, event)} disabled={!canOpen} tone={canOpen ? 'primary' : 'ghost'}><ExternalLink className="h-4 w-4" />{opening ? 'Opening...' : 'Open'}</LiteButton>
          <LiteButton onClick={(event) => { event.stopPropagation(); setSelectedApp(app); }} tone="ghost"><Info className="h-4 w-4" />Details</LiteButton>
        </div>
        {openUrl ? <span className="lite-catalog-open-hint">Opens inside Pocket Lab</span> : null}
      </GlassCard>
    );
  }

  const selectedOpenUrl = resolveAppOpenUrl(selectedApp);
  const selectedStatus = String(selectedApp?.status || '').toLowerCase();
  const selectedInstalling = Boolean(selectedApp && (selectedStatus === 'installing' || busyId === selectedApp.id));
  const selectedCanInstall = Boolean(selectedApp?.actions?.install) && !selectedInstalling;
  const selectedCanOpen = Boolean(selectedApp?.actions?.open && selectedOpenUrl);

  return (
    <>
      <PageHeader
        eyebrow="Apps"
        title="App Catalog"
        description="Install and open local apps from your Pocket Lab. App setup is handled by the Server Host."
        actions={<LiteButton onClick={refresh} tone="secondary"><RefreshCw className="h-4 w-4" />Refresh</LiteButton>}
      />

      <section className="lite-catalog-launcher">
        <div className="lite-catalog-launcher-copy">
          <div className="lite-home-pill lite-catalog-hero-pill"><span className={access.https_ready ? 'lite-ready-dot' : 'lite-ready-dot lite-ready-dot-warning'} />{access.https_ready ? 'Secure access ready' : 'Remote access not ready'}</div>
          <h2>Your local app launcher.</h2>
          <p>Open private apps quickly from the same Pocket Lab address. Keep details available when needed, but keep the main view simple.</p>
        </div>
        <div className="lite-catalog-counts" aria-label="Catalog summary">
          <div><span>Apps</span><strong>{apps.length}</strong></div>
          <div><span>Installed</span><strong>{readyCount}</strong></div>
          <div><span>Working</span><strong>{installingCount}</strong></div>
          <div><span>Review</span><strong>{attentionCount}</strong></div>
        </div>
      </section>

      {featuredApp ? (
        <section className="lite-catalog-featured" aria-label="Featured app">
          {renderAppCard(featuredApp, true)}
        </section>
      ) : null}

      <GlassCard className="lite-catalog-access-card"><div className="lite-catalog-access-icon"><Sparkles className="h-5 w-5" /></div><div><strong>{access.https_ready ? 'Secure access ready' : 'Open waits for secure access'}</strong><p>{access.message || 'Apps open from the current Pocket Lab address when they are ready.'}</p></div></GlassCard>

      <div className="lite-catalog-toolbar">
        <div className="lite-catalog-search-wrap"><Search className="h-5 w-5" /><input className="lite-catalog-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search apps" aria-label="Search apps" /></div>
        <div className="lite-catalog-filter-pills" role="tablist" aria-label="Filter apps">
          {APP_FILTERS.map((filter) => (
            <button key={filter.id} type="button" className={activeFilter === filter.id ? 'is-active' : ''} onClick={() => { safeHaptic(4); setActiveFilter(filter.id); }}>{filter.label}</button>
          ))}
        </div>
        <p>{filteredApps.length} shown</p>
      </div>

      {error ? <StateSurface tone="degraded" title="Catalog needs a moment" description={error} className="mb-5" /> : null}
      {loading ? <CatalogSkeletons /> : null}
      {loading ? <LoadingCard label="Loading apps..." /> : null}

      <div className="lite-catalog-grid">
        {filteredApps.filter((app) => app.id !== featuredApp?.id).map((app) => renderAppCard(app))}
      </div>

      {!loading && filteredApps.length === 0 ? <StateSurface tone="empty" title={query ? 'No matching apps' : 'No apps yet'} description={query ? 'Try a different search term.' : 'Refresh the catalog after setup.'} /> : null}
      <ResultNotice result={result} error={actionError} />

      <AppDetailsDrawer
        app={selectedApp}
        openUrl={selectedOpenUrl}
        opening={Boolean(selectedApp && openingId === selectedApp.id)}
        installing={selectedInstalling}
        canOpen={selectedCanOpen}
        canInstall={selectedCanInstall}
        onClose={() => setSelectedApp(null)}
        onOpen={(event) => openApp(selectedApp, event)}
        onInstall={(event) => install(selectedApp, event)}
      />
    </>
  );
}
'''

css_addition = r'''

/* Pocket Lab Lite App Catalog — mobile-first app launcher experience */
.theme-pocket-lite-daylight .lite-ready-dot-warning { background: #f59e0b; box-shadow: 0 0 0 5px rgba(245, 158, 11, 0.12); }
.theme-pocket-lite-daylight .lite-catalog-launcher { position: relative; overflow: hidden; display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(18rem, 0.65fr); gap: 1rem; margin-bottom: 1rem; padding: 1.15rem; border: 1px solid rgba(148, 163, 184, 0.22); border-radius: 1.5rem; background: linear-gradient(135deg, rgba(255, 255, 255, 0.96), rgba(239, 246, 255, 0.9)); box-shadow: 0 20px 54px rgba(15, 23, 42, 0.08); }
.theme-pocket-lite-daylight .lite-catalog-launcher::after { content: ''; position: absolute; inset: auto -16% -36% 42%; block-size: 10rem; border-radius: 999px; background: radial-gradient(circle, rgba(59, 130, 246, 0.14), transparent 65%); pointer-events: none; }
.theme-pocket-lite-daylight .lite-catalog-launcher-copy { position: relative; z-index: 1; display: grid; gap: 0.65rem; align-content: center; }
.theme-pocket-lite-daylight .lite-catalog-launcher h2 { margin: 0; color: #0f172a; font-size: clamp(1.45rem, 4vw, 2.5rem); font-weight: 950; letter-spacing: -0.04em; line-height: 1; }
.theme-pocket-lite-daylight .lite-catalog-launcher p { max-width: 42rem; margin: 0; color: #475569; font-size: 0.98rem; line-height: 1.65; }
.theme-pocket-lite-daylight .lite-catalog-hero-pill { width: fit-content; }
.theme-pocket-lite-daylight .lite-catalog-counts { position: relative; z-index: 1; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.7rem; }
.theme-pocket-lite-daylight .lite-catalog-counts > div { padding: 0.85rem; border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 1.1rem; background: rgba(255, 255, 255, 0.82); box-shadow: 0 12px 30px rgba(15, 23, 42, 0.06); transition: transform 160ms ease, box-shadow 160ms ease, border-color 160ms ease; }
.theme-pocket-lite-daylight .lite-catalog-counts > div:hover { transform: translateY(-1px); border-color: rgba(59, 130, 246, 0.26); box-shadow: 0 16px 34px rgba(37, 99, 235, 0.1); }
.theme-pocket-lite-daylight .lite-catalog-counts span { display: block; color: #64748b; font-size: 0.72rem; font-weight: 900; letter-spacing: 0.12em; text-transform: uppercase; }
.theme-pocket-lite-daylight .lite-catalog-counts strong { display: block; margin-top: 0.35rem; color: #0f172a; font-size: 1.45rem; font-weight: 950; letter-spacing: -0.03em; }
.theme-pocket-lite-daylight .lite-catalog-featured { margin-bottom: 1rem; }
.theme-pocket-lite-daylight .lite-catalog-access-card { display: flex; align-items: flex-start; gap: 0.85rem; margin-bottom: 1rem; }
.theme-pocket-lite-daylight .lite-catalog-access-icon { display: grid; flex: 0 0 auto; place-items: center; width: 2.75rem; height: 2.75rem; border-radius: 1rem; background: rgba(219, 234, 254, 0.8); color: #2563eb; }
.theme-pocket-lite-daylight .lite-catalog-access-card strong, .theme-pocket-lite-daylight .lite-catalog-last-op strong, .theme-pocket-lite-daylight .lite-catalog-progress strong { color: #0f172a; font-weight: 950; }
.theme-pocket-lite-daylight .lite-catalog-access-card p, .theme-pocket-lite-daylight .lite-catalog-last-op p, .theme-pocket-lite-daylight .lite-catalog-progress p { margin-top: 0.25rem; color: #64748b; font-size: 0.9rem; line-height: 1.55; }
.theme-pocket-lite-daylight .lite-catalog-toolbar { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; gap: 0.75rem; align-items: center; margin-bottom: 1rem; }
.theme-pocket-lite-daylight .lite-catalog-toolbar p { margin: 0; color: #64748b; font-size: 0.86rem; font-weight: 850; white-space: nowrap; }
.theme-pocket-lite-daylight .lite-catalog-search-wrap { display: flex; align-items: center; gap: 0.6rem; min-width: 0; padding: 0.72rem 0.85rem; border: 1px solid rgba(148, 163, 184, 0.26); border-radius: 1rem; background: rgba(255, 255, 255, 0.9); color: #64748b; transition: border-color 160ms ease, box-shadow 160ms ease, transform 160ms ease; }
.theme-pocket-lite-daylight .lite-catalog-search-wrap:focus-within { border-color: rgba(37, 99, 235, 0.42); box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.1); transform: translateY(-1px); }
.theme-pocket-lite-daylight .lite-catalog-search { width: 100%; border: 0; outline: 0; background: transparent; color: #0f172a; font: inherit; font-weight: 850; }
.theme-pocket-lite-daylight .lite-catalog-search::placeholder { color: #94a3b8; }
.theme-pocket-lite-daylight .lite-catalog-filter-pills { display: flex; gap: 0.45rem; overflow-x: auto; padding: 0.2rem; border: 1px solid rgba(148, 163, 184, 0.18); border-radius: 999px; background: rgba(241, 245, 249, 0.74); -webkit-overflow-scrolling: touch; scrollbar-width: thin; }
.theme-pocket-lite-daylight .lite-catalog-filter-pills button { flex: 0 0 auto; border: 0; border-radius: 999px; padding: 0.58rem 0.78rem; background: transparent; color: #64748b; font-size: 0.82rem; font-weight: 950; cursor: pointer; transition: transform 140ms ease, background 140ms ease, color 140ms ease, box-shadow 140ms ease; }
.theme-pocket-lite-daylight .lite-catalog-filter-pills button:active { transform: scale(0.98); }
.theme-pocket-lite-daylight .lite-catalog-filter-pills button.is-active { background: #ffffff; color: #1d4ed8; box-shadow: 0 8px 18px rgba(37, 99, 235, 0.12); }
.theme-pocket-lite-daylight .lite-catalog-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr)); gap: 1rem; }
.theme-pocket-lite-daylight .lite-catalog-card { position: relative; overflow: hidden; min-height: 25rem; cursor: pointer; transition: transform 170ms ease, box-shadow 170ms ease, border-color 170ms ease; animation: lite-catalog-card-enter 220ms ease both; }
.theme-pocket-lite-daylight .lite-catalog-card:hover { transform: translateY(-2px); border-color: rgba(37, 99, 235, 0.22); box-shadow: 0 22px 48px rgba(15, 23, 42, 0.1); }
.theme-pocket-lite-daylight .lite-catalog-card:active { transform: translateY(-1px) scale(0.995); }
.theme-pocket-lite-daylight .lite-catalog-app-card.is-featured { min-height: 23rem; border-color: rgba(37, 99, 235, 0.22); background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(239, 246, 255, 0.68)); }
.theme-pocket-lite-daylight .lite-catalog-app-card.is-installing { border-color: rgba(37, 99, 235, 0.34); }
.theme-pocket-lite-daylight .lite-catalog-card-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 0.75rem; }
.theme-pocket-lite-daylight .lite-catalog-icon { display: grid; place-items: center; width: 3.25rem; height: 3.25rem; overflow: hidden; border: 1px solid rgba(148, 163, 184, 0.18); border-radius: 1.15rem; background: linear-gradient(145deg, rgba(255, 255, 255, 0.98), rgba(219, 234, 254, 0.86)); color: #2563eb; box-shadow: 0 10px 24px rgba(37, 99, 235, 0.1); }
.theme-pocket-lite-daylight .lite-catalog-icon img { width: 74%; height: 74%; object-fit: contain; }
.theme-pocket-lite-daylight .lite-catalog-icon-large { width: 3.65rem; height: 3.65rem; }
.theme-pocket-lite-daylight .lite-catalog-card-title-row { display: flex; justify-content: space-between; gap: 0.75rem; }
.theme-pocket-lite-daylight .lite-catalog-category { margin-top: 1rem !important; color: #2563eb !important; font-size: 0.72rem !important; font-weight: 950 !important; letter-spacing: 0.16em; line-height: 1 !important; text-transform: uppercase; }
.theme-pocket-lite-daylight .lite-catalog-card h2 { margin: 0.45rem 0 0; color: #0f172a; font-size: 1.35rem; font-weight: 950; letter-spacing: -0.03em; }
.theme-pocket-lite-daylight .lite-catalog-card p { color: #475569; line-height: 1.58; }
.theme-pocket-lite-daylight .lite-catalog-meta-grid { display: flex; flex-wrap: wrap; gap: 0.5rem; }
.theme-pocket-lite-daylight .lite-catalog-meta-grid span { display: inline-flex; align-items: center; gap: 0.35rem; max-width: 100%; padding: 0.42rem 0.58rem; border-radius: 999px; background: rgba(241, 245, 249, 0.9); color: #475569; font-size: 0.8rem; font-weight: 850; white-space: normal; }
.theme-pocket-lite-daylight .lite-catalog-progress, .theme-pocket-lite-daylight .lite-catalog-last-op { margin-top: 1rem; padding: 0.85rem; border: 1px solid rgba(148, 163, 184, 0.22); border-radius: 1rem; background: rgba(248, 250, 252, 0.86); }
.theme-pocket-lite-daylight .lite-catalog-progress > div:first-child { display: flex; align-items: center; justify-content: space-between; gap: 0.75rem; }
.theme-pocket-lite-daylight .lite-catalog-progress > div:first-child span { color: #64748b; font-size: 0.8rem; font-weight: 900; }
.theme-pocket-lite-daylight .lite-catalog-progress-bar { overflow: hidden; height: 0.5rem; margin-top: 0.75rem; border-radius: 999px; background: rgba(203, 213, 225, 0.65); }
.theme-pocket-lite-daylight .lite-catalog-progress-bar span { position: relative; display: block; height: 100%; overflow: hidden; border-radius: inherit; background: linear-gradient(90deg, #2563eb, #06b6d4); transition: width 220ms ease; }
.theme-pocket-lite-daylight .lite-catalog-progress-bar span::after { content: ''; position: absolute; inset: 0; background: linear-gradient(90deg, transparent, rgba(255,255,255,0.45), transparent); transform: translateX(-100%); animation: lite-catalog-progress-sheen 1.45s ease-in-out infinite; }
.theme-pocket-lite-daylight .lite-catalog-actions { display: flex; flex-wrap: wrap; gap: 0.6rem; margin-top: 1rem; }
.theme-pocket-lite-daylight .lite-catalog-actions .lite-button:not(:disabled):active { transform: translateY(1px) scale(0.99); }
.theme-pocket-lite-daylight .lite-catalog-open-hint { display: inline-flex; margin-top: 0.7rem; color: #64748b; font-size: 0.78rem; font-weight: 850; }
.theme-pocket-lite-daylight .lite-catalog-skeleton-card { min-height: 16rem; cursor: default; }
.theme-pocket-lite-daylight .lite-catalog-skeleton-icon, .theme-pocket-lite-daylight .lite-catalog-skeleton-line, .theme-pocket-lite-daylight .lite-catalog-skeleton-button { position: relative; overflow: hidden; border-radius: 999px; background: linear-gradient(90deg, rgba(226,232,240,0.78), rgba(248,250,252,0.96), rgba(226,232,240,0.78)); background-size: 220% 100%; animation: lite-catalog-skeleton 1.25s ease-in-out infinite; }
.theme-pocket-lite-daylight .lite-catalog-skeleton-icon { width: 3.25rem; height: 3.25rem; border-radius: 1.15rem; }
.theme-pocket-lite-daylight .lite-catalog-skeleton-line { height: 0.8rem; margin-top: 1rem; }
.theme-pocket-lite-daylight .lite-catalog-skeleton-line.is-title { width: 62%; height: 1.1rem; }
.theme-pocket-lite-daylight .lite-catalog-skeleton-line.is-short { width: 44%; }
.theme-pocket-lite-daylight .lite-catalog-skeleton-button { width: 7.2rem; height: 2.25rem; margin-top: 1.25rem; border-radius: 0.9rem; }
.theme-pocket-lite-daylight .lite-catalog-drawer-shell { position: fixed; inset: 0; z-index: 80; display: grid; place-items: end center; padding: 1rem; }
.theme-pocket-lite-daylight .lite-catalog-drawer-backdrop { position: absolute; inset: 0; border: 0; background: rgba(15, 23, 42, 0.34); backdrop-filter: blur(8px); cursor: pointer; }
.theme-pocket-lite-daylight .lite-catalog-drawer { position: relative; z-index: 1; width: min(42rem, 100%); max-height: min(86vh, 48rem); overflow: auto; padding-bottom: 1rem; border-radius: 1.5rem 1.5rem 1.25rem 1.25rem; animation: lite-catalog-drawer-rise 180ms ease both; }
.theme-pocket-lite-daylight .lite-catalog-drawer-grip { width: 2.8rem; height: 0.32rem; margin: 0 auto 1rem; border-radius: 999px; background: rgba(148, 163, 184, 0.56); }
.theme-pocket-lite-daylight .lite-catalog-drawer-head { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 0.8rem; align-items: start; }
.theme-pocket-lite-daylight .lite-catalog-drawer-head h2 { margin: 0.35rem 0 0; color: #0f172a; font-size: 1.45rem; font-weight: 950; letter-spacing: -0.03em; }
.theme-pocket-lite-daylight .lite-catalog-drawer-head p { margin: 0.35rem 0 0; color: #475569; line-height: 1.55; }
.theme-pocket-lite-daylight .lite-catalog-drawer-close { display: grid; place-items: center; width: 2.45rem; height: 2.45rem; border: 1px solid rgba(148, 163, 184, 0.22); border-radius: 0.9rem; background: rgba(255, 255, 255, 0.9); color: #334155; cursor: pointer; }
.theme-pocket-lite-daylight .lite-catalog-detail-grid { display: grid; gap: 0.6rem; margin-top: 1rem; }
.theme-pocket-lite-daylight .lite-catalog-detail-row { display: flex; align-items: center; justify-content: space-between; gap: 1rem; padding: 0.72rem 0.8rem; border-radius: 0.9rem; background: rgba(248, 250, 252, 0.9); }
.theme-pocket-lite-daylight .lite-catalog-detail-row span { color: #64748b; font-size: 0.82rem; font-weight: 850; }
.theme-pocket-lite-daylight .lite-catalog-detail-row strong { color: #0f172a; font-size: 0.88rem; font-weight: 950; text-align: right; word-break: break-word; }
.theme-pocket-lite-daylight .lite-catalog-detail-note { display: flex; gap: 0.45rem; align-items: flex-start; margin-top: 0.85rem; padding: 0.76rem 0.85rem; border-radius: 0.95rem; background: rgba(239, 246, 255, 0.82); color: #1d4ed8; font-size: 0.86rem; font-weight: 850; line-height: 1.45; }
.theme-pocket-lite-daylight .lite-catalog-drawer-actions { position: sticky; bottom: 0; display: flex; gap: 0.6rem; margin: 1rem -0.2rem -0.2rem; padding: 0.8rem 0.2rem 0.2rem; background: linear-gradient(180deg, rgba(255,255,255,0), rgba(255,255,255,0.96) 28%); }
@keyframes lite-catalog-card-enter { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
@keyframes lite-catalog-drawer-rise { from { opacity: 0; transform: translateY(16px) scale(0.98); } to { opacity: 1; transform: translateY(0) scale(1); } }
@keyframes lite-catalog-progress-sheen { to { transform: translateX(100%); } }
@keyframes lite-catalog-skeleton { 0% { background-position: 120% 0; } 100% { background-position: -120% 0; } }
@media (max-width: 900px) { .theme-pocket-lite-daylight .lite-catalog-launcher { grid-template-columns: 1fr; } .theme-pocket-lite-daylight .lite-catalog-toolbar { grid-template-columns: 1fr; } .theme-pocket-lite-daylight .lite-catalog-toolbar p { justify-self: start; } .theme-pocket-lite-daylight .lite-catalog-filter-pills { width: 100%; } }
@media (max-width: 760px) { .theme-pocket-lite-daylight .lite-catalog-launcher { padding: 1rem; border-radius: 1.25rem; } .theme-pocket-lite-daylight .lite-catalog-counts { grid-template-columns: repeat(4, minmax(4.8rem, 1fr)); overflow-x: auto; padding-bottom: 0.1rem; } .theme-pocket-lite-daylight .lite-catalog-counts > div { min-width: 4.8rem; padding: 0.72rem; } .theme-pocket-lite-daylight .lite-catalog-counts strong { font-size: 1.2rem; } .theme-pocket-lite-daylight .lite-catalog-access-card, .theme-pocket-lite-daylight .lite-catalog-actions, .theme-pocket-lite-daylight .lite-catalog-drawer-actions { align-items: stretch; flex-direction: column; } .theme-pocket-lite-daylight .lite-catalog-grid { grid-template-columns: 1fr; } .theme-pocket-lite-daylight .lite-catalog-card { min-height: auto; } .theme-pocket-lite-daylight .lite-catalog-drawer-shell { padding: 0.65rem; } .theme-pocket-lite-daylight .lite-catalog-drawer { width: 100%; max-height: 88vh; border-radius: 1.35rem 1.35rem 1rem 1rem; } .theme-pocket-lite-daylight .lite-catalog-drawer-head { grid-template-columns: auto minmax(0, 1fr) auto; } .theme-pocket-lite-daylight .lite-catalog-detail-row { align-items: flex-start; flex-direction: column; gap: 0.25rem; } .theme-pocket-lite-daylight .lite-catalog-detail-row strong { text-align: left; } }
@media (prefers-reduced-motion: reduce) { .theme-pocket-lite-daylight .lite-catalog-card, .theme-pocket-lite-daylight .lite-catalog-drawer, .theme-pocket-lite-daylight .lite-catalog-skeleton-icon, .theme-pocket-lite-daylight .lite-catalog-skeleton-line, .theme-pocket-lite-daylight .lite-catalog-skeleton-button, .theme-pocket-lite-daylight .lite-catalog-progress-bar span::after { animation: none !important; transition: none !important; } }
'''

if not CATALOG.exists():
    raise SystemExit(f"Missing {CATALOG}")
if not CSS.exists():
    raise SystemExit(f"Missing {CSS}")

CATALOG.write_text(catalog_source, encoding="utf-8")

css = CSS.read_text(encoding="utf-8")
marker = "/* Pocket Lab Lite App Catalog — PhotoPrism route/progress polish */"
if marker in css:
    css = css[:css.index(marker)].rstrip() + "\n"
else:
    # Remove older launcher/app-catalog patch tail if this script is rerun.
    marker2 = "/* Pocket Lab Lite App Catalog — mobile-first app launcher experience */"
    if marker2 in css:
        css = css[:css.index(marker2)].rstrip() + "\n"

CSS.write_text(css.rstrip() + css_addition + "\n", encoding="utf-8")
print("Pocket Lab Lite App Catalog launcher UI v2 applied.")

import React, { useMemo, useState } from 'react';
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
  ShieldCheck,
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

      <GlassCard className="lite-catalog-access-card"><div className="lite-catalog-access-icon"><ShieldCheck className="h-5 w-5" /></div><div><strong>{access.https_ready ? 'Secure access ready' : 'Open waits for secure access'}</strong><p>{access.message || 'Apps open from the current Pocket Lab address when they are ready.'}</p></div></GlassCard>

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

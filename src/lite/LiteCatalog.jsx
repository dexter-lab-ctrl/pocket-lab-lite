import React, { useMemo, useRef, useState } from 'react';
import {
  CheckCircle2,
  Clock3,
  ExternalLink,
  Image as ImageIcon,
  Info,
  RefreshCw,
  Search,
  Server,
  ShieldCheck,
  ShieldAlert,
} from 'lucide-react';
import { useLiteResource } from '../hooks/useLiteStatus.js';
import { formatLiteTime, liteApi } from '../lib/liteApi.js';
import { GlassCard, StatusBadge, StateSurface, PageHeader, LiteButton, ResultNotice, LoadingCard, resolveSafeAppOpenPath } from './LiteUi.jsx';

const KNOWN_APP_NAMES = ['PhotoPrism'];

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
  return resolveSafeAppOpenPath(item);
}

function AppIcon() {
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


function friendlyHealthLabel(value) {
  const health = String(value || '').toLowerCase();
  if (['healthy', 'ready', 'running'].includes(health)) return 'Healthy';
  if (['installing', 'queued', 'starting'].includes(health)) return 'Setting up';
  if (['unhealthy', 'failed', 'error', 'blocked'].includes(health)) return 'Needs attention';
  if (['not installed', 'not_installed'].includes(health)) return 'Not installed';
  return health ? health.replace(/_/g, ' ') : 'Checking';
}

function drawerAccessLabel(app, canOpen) {
  if (canOpen) return 'Open is ready';
  if (app?.access?.https_ready === false) return 'Remote access not ready';
  if (app?.access?.message) return app.access.message;
  if (app?.installed || String(app?.status || '').toLowerCase() === 'ready') return 'Checking app route';
  return 'Available after install';
}

function drawerSetupSteps(app, canOpen, installing) {
  const installed = Boolean(app?.installed || String(app?.status || '').toLowerCase() === 'ready');
  return [
    { id: 'install', label: 'Install', state: installed || canOpen ? 'done' : installing ? 'current' : 'pending' },
    { id: 'check', label: 'Check', state: installing ? 'pending' : installed || canOpen ? 'done' : 'current' },
    { id: 'open', label: 'Open', state: canOpen ? 'done' : installed ? 'current' : 'pending' },
  ];
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

function AppDetailsDrawer({ app, openUrl, opening, installing, canOpen, canInstall, onClose, onOpen, onOpenFullScreen, onInstall }) {
  if (!app) return null;
  const targetName = app?.target?.eligible_devices?.[0]?.name || 'Server Host';
  const health = app?.runtime?.health || (app?.installed ? 'healthy' : 'not installed');
  const evidenceCount = Array.isArray(app?.evidence_refs) ? app.evidence_refs.length : 0;
  const statusLabel = appLabel(app);
  const healthLabel = friendlyHealthLabel(health);
  const accessLabel = drawerAccessLabel(app, canOpen);
  const setupSteps = drawerSetupSteps(app, canOpen, installing);
  const categoryLabel = app?.category || 'Self-hosted app';
  const latestText = lastOperationText(app);
  const evidenceLabel = evidenceCount === 1 ? '1 safety record' : evidenceCount ? `${evidenceCount} safety records` : 'Saved after install';

  const [drawerSnap, setDrawerSnap] = useState('comfortable');
  const [drawerOffset, setDrawerOffset] = useState(0);
  const drawerDragRef = useRef({ active: false, pointerId: null, startY: 0, lastY: 0 });

  const startDrawerDrag = (event) => {
    if (event.button !== undefined && event.button !== 0) return;

    drawerDragRef.current = {
      active: true,
      pointerId: event.pointerId,
      startY: event.clientY || 0,
      lastY: event.clientY || 0,
    };

    setDrawerOffset(0);
    event.currentTarget.setPointerCapture?.(event.pointerId);
    event.preventDefault?.();
  };

  const moveDrawerDrag = (event) => {
    const dragState = drawerDragRef.current;
    if (!dragState.active) return;
    if (dragState.pointerId !== null && event.pointerId !== dragState.pointerId) return;

    const currentY = event.clientY || 0;
    const delta = currentY - dragState.startY;

    drawerDragRef.current = { ...dragState, lastY: currentY };
    setDrawerOffset(Math.max(-96, Math.min(180, delta)));
    event.preventDefault?.();
  };

  const finishDrawerDrag = (event) => {
    const dragState = drawerDragRef.current;
    if (!dragState.active) return;

    const delta = drawerOffset;
    drawerDragRef.current = { active: false, pointerId: null, startY: 0, lastY: 0 };
    setDrawerOffset(0);

    event?.currentTarget?.releasePointerCapture?.(dragState.pointerId);

    if (delta < -42) {
      setDrawerSnap('expanded');
      return;
    }

    if (delta > 92 && drawerSnap === 'comfortable') {
      onClose?.();
      return;
    }

    if (delta > 58) {
      setDrawerSnap('comfortable');
      return;
    }

    setDrawerSnap((current) => current);
  };

  const toggleDrawerSnap = () => {
    setDrawerSnap((current) => (current === 'expanded' ? 'comfortable' : 'expanded'));
  };

  const handleDrawerGripKeyDown = (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      toggleDrawerSnap();
    }

    if (event.key === 'Escape') {
      onClose?.();
    }
  };

return (
    <div className="lite-catalog-drawer-shell" role="dialog" aria-modal="true" aria-label={`${app.name} details`}>
      <button className="lite-catalog-drawer-backdrop" type="button" onClick={onClose} aria-label="Close app details" />
      <GlassCard className={`lite-catalog-drawer is-${drawerSnap} ${drawerOffset ? 'is-dragging' : ''}`} style={{ '--lite-catalog-drawer-offset': `${drawerOffset}px` }}>
        <button
          className="lite-catalog-drawer-grip"
          type="button"
          aria-label={drawerSnap === 'expanded' ? 'Collapse app details' : 'Expand app details'}
          aria-expanded={drawerSnap === 'expanded'}
          onClick={toggleDrawerSnap}
          onKeyDown={handleDrawerGripKeyDown}
          onPointerDown={startDrawerDrag}
          onPointerMove={moveDrawerDrag}
          onPointerUp={finishDrawerDrag}
          onPointerCancel={finishDrawerDrag}
          onLostPointerCapture={finishDrawerDrag}
        >
          <span aria-hidden="true" />
        </button>
        <div className="lite-catalog-drawer-hero">
          <div className="lite-catalog-drawer-app-icon" aria-hidden="true"><AppIcon app={app} /></div>
          <div className="lite-catalog-drawer-title-block">
            <span className="lite-catalog-drawer-kicker">{categoryLabel}</span>
            <h2>{app?.name || app?.title || 'App details'}</h2>
            <p>{app?.summary || 'Local app managed by Pocket Lab.'}</p>
          </div>
          <strong className={canOpen ? 'lite-catalog-drawer-ready-chip' : 'lite-catalog-drawer-ready-chip is-waiting'}>
            {canOpen ? 'Ready' : 'Needs attention'}
          </strong>
        </div>

        <div className="lite-catalog-drawer-snapshot" aria-label="App snapshot">
          <div>
            <span>Access</span>
            <strong>{accessLabel}</strong>
          </div>
          <div>
            <span>Runs on</span>
            <strong>{targetName}</strong>
          </div>
          <div>
            <span>Safety</span>
            <strong>{evidenceLabel}</strong>
          </div>
        </div>

        <div className="lite-catalog-drawer-path" aria-label="App readiness">
          {setupSteps.map((step) => (
            <div key={step.id} className={`lite-catalog-drawer-step is-${step.state}`}>
              <span aria-hidden="true" />
              <strong>{step.label}</strong>
            </div>
          ))}
        </div>

        <div className="lite-catalog-detail-grid">
          <DetailRow label="Status" value={statusLabel} />
          <DetailRow label="Health" value={healthLabel} />
          <DetailRow label="Access" value={accessLabel} />
          <DetailRow label="Latest" value={latestText} />
          <DetailRow label="Evidence" value={evidenceLabel} />
        </div>
        <div className="lite-catalog-detail-note"><Info className="h-4 w-4" />Open keeps Pocket Lab controls nearby. Full screen still opens the app route directly.</div>
        <div className={`lite-catalog-drawer-actions is-${drawerSnap}`}>
          <button className="lite-catalog-action lite-catalog-action-primary" type="button" onClick={onInstall} disabled={!canInstall}>{installing ? 'Installing...' : app?.actions?.retry ? 'Retry' : app?.installed || app?.status === 'ready' ? 'Installed' : 'Install'}</button>
          <button className="lite-catalog-action lite-catalog-action-primary" type="button" onClick={onOpen} disabled={!canOpen}><ExternalLink className="h-4 w-4" />{opening ? 'Opening...' : 'Open'}</button>
          <button className="lite-catalog-action lite-catalog-action-secondary" type="button" onClick={onOpenFullScreen} disabled={!canOpen}>Open full screen</button>
        </div>
      </GlassCard>
    </div>
  );
}

export default function CatalogScreen({ onOpenWorkspace }) {
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
  const featuredApp = apps.find((app) => KNOWN_APP_NAMES.includes(app?.name) || String(app?.id || '').toLowerCase() === 'photoprism') || apps[0];

  const filteredApps = useMemo(() => {
    const value = query.trim().toLowerCase();
    return apps.filter((app) => {
      const matchesQuery = !value || `${app.name || ''} ${app.summary || ''} ${app.category || ''}`.toLowerCase().includes(value);
      const matchesFilter = activeFilter === 'all' || appFilterState(app) === activeFilter;
      return matchesQuery && matchesFilter;
    });
  }, [apps, activeFilter, query]);


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
    window.setTimeout(() => {
      setOpeningId(null);
      if (typeof onOpenWorkspace === 'function') {
        onOpenWorkspace(app, target);
        return;
      }
      window.location.assign(target);
    }, 120);
  }

  function openAppFullScreen(app, event) {
    event?.stopPropagation?.();
    const target = resolveAppOpenUrl(app);
    if (!target) return;
    safeHaptic(6);
    window.location.assign(target);
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
      </GlassCard>
    );
  }

  const selectedOpenUrl = resolveAppOpenUrl(selectedApp);
  const selectedStatus = String(selectedApp?.status || '').toLowerCase();
  const selectedInstalling = Boolean(selectedApp && (selectedStatus === 'installing' || busyId === selectedApp.id));
  const selectedCanInstall = Boolean(selectedApp?.actions?.install) && !selectedInstalling;
  const selectedCanOpen = Boolean(selectedApp?.actions?.open && selectedOpenUrl);

    const insecureAppCount = apps.filter((app) => {
    const accessState = app?.access || {};
    const appStatus = String(app?.status || app?.health || '').toLowerCase();

    return (
      accessState.https_ready === false ||
      accessState.route_ready === false ||
      accessState.open === false ||
      appStatus === 'unhealthy' ||
      appStatus === 'error' ||
      appStatus === 'blocked'
    );
  }).length;

  const isCatalogSecure = Boolean(access?.https_ready) && insecureAppCount === 0;

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
          <div className={isCatalogSecure ? 'lite-home-pill lite-catalog-hero-pill is-secure' : 'lite-home-pill lite-catalog-hero-pill is-not-secure'}>
            {isCatalogSecure ? <ShieldCheck className="h-4 w-4" /> : <ShieldAlert className="h-4 w-4" />}
            {isCatalogSecure ? 'Secure Access' : 'Not Secure'}
          </div>
          <h2>Your local app launcher.</h2>
          <p>Open private apps quickly from the same Pocket Lab address. Keep details available when needed, but keep the main view simple.</p>
        </div>

      </section>

      <div className="lite-catalog-toolbar">
        <div className="lite-catalog-search-wrap"><Search className="h-5 w-5" /><input className="lite-catalog-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search apps" aria-label="Search apps" /></div>
        <div className="lite-catalog-filter-pills" role="tablist" aria-label="Filter apps" data-access-contract="Secure access ready">
          {APP_FILTERS.map((filter) => (
            <button key={filter.id} type="button" className={activeFilter === filter.id ? 'is-active' : ''} onClick={() => { safeHaptic(4); setActiveFilter(filter.id); }}>{filter.label}</button>
          ))}
        </div>
        <p>{filteredApps.length} shown</p>
      </div>



      {featuredApp ? (
        <section className="lite-catalog-featured" aria-label="Featured app">
          {renderAppCard(featuredApp, true)}
        </section>
      ) : null}





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
        onOpenFullScreen={(event) => openAppFullScreen(selectedApp, event)}
        onInstall={(event) => install(selectedApp, event)}
      />
    </>
  );
}

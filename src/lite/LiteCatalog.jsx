import React, { useMemo, useState } from 'react';
import {
  CheckCircle2,
  HeartPulse,
  ExternalLink,
  FolderOpen,
  FolderPlus,
  HardDrive,
  Image as ImageIcon,
  RefreshCw,
  Search,
  Server,
  ShieldCheck,
  ShieldAlert,
  Smartphone,
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

function isStandalonePwa() {
  try {
    return window.matchMedia?.('(display-mode: standalone)')?.matches || window.navigator?.standalone === true;
  } catch {
    return false;
  }
}

function safeHaptic(duration = 8) {
  try {
    if (!isStandalonePwa()) return;
    navigator.vibrate?.(duration);
  } catch {
    // Optional PWA-only browser feedback.
  }
}

function handleCatalogPointerDown(event) {
  const target = event.target?.closest?.('button, a, [role="button"]');
  if (!target || target.getAttribute?.('aria-disabled') === 'true' || target.disabled) return;
  safeHaptic(6);
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
  if (value === 'ready' && app?.actions?.open) return 'Ready';
  if (value === 'ready' || app?.installed) return 'Ready';
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

function isAppInstalled(app) {
  const status = String(app?.status || '').toLowerCase();
  return Boolean(app?.installed || status === 'ready' || status === 'installed');
}

function isPhotoPrismApp(app) {
  return String(app?.id || '').toLowerCase() === 'photoprism' || String(app?.name || '').toLowerCase() === 'photoprism';
}

function canInstallAppToPhone(app) {
  return Boolean(isPhotoPrismApp(app) && isAppInstalled(app) && resolveAppOpenUrl(app));
}

function storageMappings(app) {
  const mappings = app?.storage?.mappings;
  return Array.isArray(mappings) ? mappings : [];
}

function storageMediaSummary(app) {
  const mappings = storageMappings(app);
  if (!mappings.length) return 'Not connected';
  return mappings
    .map((mapping) => `${mapping.label || mapping.source_label || 'Media folder'} · ${mapping.mode_label || 'Read-only'}`)
    .slice(0, 2)
    .join(', ');
}

function storageDeviceCount(app) {
  const value = app?.device_relationships?.storage_devices_available
    ?? app?.available_device_capabilities?.media_storage
    ?? 0;
  return Number.isFinite(Number(value)) ? Number(value) : 0;
}

function firstStorageDevice(app) {
  const devices = Array.isArray(app?.storage_devices) ? app.storage_devices : [];
  return devices.find((device) => device?.ready) || devices[0] || null;
}

function attentionReason(app, canOpen) {
  const status = String(app?.status || app?.health || '').toLowerCase();
  const health = String(app?.runtime?.health || '').toLowerCase();
  const access = app?.access || {};

  if (access.https_ready === false) return 'Remote access is not ready. Use the server device or check remote access health.';
  if (!isAppInstalled(app) && !canOpen) return 'Install this app to make Open available.';
  if (!canOpen || access.route_ready === false || app?.actions?.open === false) return 'Open is not ready yet. Pocket Lab is still checking the app route.';
  if (['needs_attention', 'unavailable', 'failed', 'error', 'blocked'].includes(status) || ['unhealthy', 'failed', 'error'].includes(health)) {
    return 'App needs attention. The app has not reported a healthy status yet.';
  }
  if (['installing', 'queued', 'running'].includes(status)) return 'Setting up. Pocket Lab is preparing this app.';
  return '';
}

function AppIcon({ app }) {
  const [failed, setFailed] = useState(false);

  if (isPhotoPrismApp(app) && !failed) {
    return (
      <img
        src="/assets/apps/photoprism.svg"
        className="lite-catalog-app-icon-img"
        alt=""
        aria-hidden="true"
        onError={() => setFailed(true)}
      />
    );
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


export default function CatalogScreen({ onOpenWorkspace }) {
  const { data, loading, error, refresh } = useLiteResource(liteApi.catalog, []);
  const [query, setQuery] = useState('');
  const [activeFilter, setActiveFilter] = useState('all');
  const [result, setResult] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const [openingId, setOpeningId] = useState(null);
  const [storageBusy, setStorageBusy] = useState('');

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
    window.location.assign(target);
  }

  function installAppToPhone(app, event) {
    event?.stopPropagation?.();
    const target = resolveAppOpenUrl(app);
    if (!canInstallAppToPhone(app) || !target) return;
    setResult({
      accepted: true,
      summary: `Opening ${app?.name || 'this app'} full screen. Use your browser menu to install it on this phone.`,
    });
    window.setTimeout(() => window.location.assign(target), 160);
  }


  async function connectStorage(app, preset, event) {
    event?.stopPropagation?.();
    if (!isPhotoPrismApp(app)) return;
    const storageDevice = firstStorageDevice(app);
    const presets = {
      phone_pictures: {
        label: 'Pictures',
        source_type: 'phone_media',
        source_path: '~/storage/shared/Pictures',
        target: 'import',
        mode: 'read_only',
      },
      phone_camera: {
        label: 'Phone photos',
        source_type: 'phone_media',
        source_path: '~/storage/shared/DCIM',
        target: 'import',
        mode: 'read_only',
      },
      storage_device: {
        label: storageDevice?.name || 'Storage device',
        source_type: 'storage_device',
        source_path: '~/.pocket_lab/lite/media',
        target: 'import',
        mode: 'read_only',
        device_id: storageDevice?.id,
        device_name: storageDevice?.name,
      },
    };
    if (preset === 'storage_device' && !storageDevice) {
      setActionError('Join a storage device first, then connect it here.');
      return;
    }
    const payload = presets[preset];
    if (!payload) return;
    setStorageBusy(`${app.id}:${preset}`);
    setActionError(null);
    setResult({ status: 'queued', summary: 'Connecting media folder...' });
    try {
      const response = await liteApi.connectPhotoPrismStorage(payload);
      setResult(response);
      refresh();
      window.setTimeout(refresh, 700);
    } catch (err) {
      const detail = err?.payload?.detail;
      if (detail?.status === 'duplicate_mapping') {
        setResult({ status: 'already_connected', summary: detail.summary || 'This media folder is already connected.' });
      } else {
        setActionError(err.message);
      }
    } finally {
      setStorageBusy('');
    }
  }

  function renderAppCard(app, featured = false) {
    const status = String(app.status || 'not_installed').toLowerCase();
    const installing = status === 'installing' || busyId === app.id;
    const opening = openingId === app.id;
    const canInstall = Boolean(app?.actions?.install) && !installing;
    const canOpen = Boolean(app?.actions?.open && resolveAppOpenUrl(app));
    const installed = isAppInstalled(app);
    const canInstallPhone = Boolean(canOpen && canInstallAppToPhone(app));
    const targetName = app?.target?.eligible_devices?.[0]?.name || 'Server Host';
    const reason = attentionReason(app, canOpen);
    const progress = app?.progress;
    const percent = Math.min(100, Math.max(0, ((progress?.current || 1) / (progress?.total || 7)) * 100));
    const cardClassName = `lite-catalog-card lite-catalog-app-card ${featured ? 'is-featured' : ''} ${installing ? 'is-installing' : ''}`;
    const actionsClassName = `lite-catalog-actions ${canInstallPhone ? 'has-phone-install' : ''}`;

    return (
      <GlassCard
        key={app.id}
        className={cardClassName}
      >
        <div className="lite-catalog-card-top">
          <div className="lite-catalog-icon"><AppIcon app={app} /></div>
          <StatusBadge status={appTone(status)} className="lite-catalog-status-badge">{appLabel(app)}</StatusBadge>
        </div>
        <div className="lite-catalog-card-title-row">
          <div>
            <p className="lite-catalog-category">{featured ? 'Featured local app' : app.category || 'Local app'}</p>
            <h2>{app.name}</h2>
          </div>
        </div>
        <p>{app.summary}</p>
        {installed ? (
          <div className="lite-catalog-trust-marker" aria-label="Self-hosted app">
            <ShieldCheck className="h-4 w-4" />
            <span>Self-hosted app</span>
          </div>
        ) : null}
        <div className="lite-catalog-meta lite-catalog-meta-grid">
          <span><Server className="h-4 w-4" /> {targetName}</span>
          <span><CheckCircle2 className="h-4 w-4" /> {canOpen ? 'Ready' : app?.access?.message || 'Available after install'}</span>
          <span><HeartPulse className="h-4 w-4" /> {app?.runtime?.health ? `Health: ${app.runtime.health}` : 'Health: not installed'}</span>
        </div>
        {reason ? (
          <div className="lite-catalog-attention-reason">
            <strong>{installed ? (canOpen ? 'Status note' : 'Attention') : 'Setup'}</strong>
            <p>{reason}</p>
          </div>
        ) : null}
        {progress ? (
          <div className="lite-catalog-progress" aria-label="Install progress">
            <div><strong>{progress.step || 'Working'}</strong><span>{progress.current || 1}/{progress.total || 7}</span></div>
            <p>{progress.message || 'Preparing the app.'}</p>
            <div className="lite-catalog-progress-bar"><span style={{ width: `${percent}%` }} /></div>
          </div>
        ) : null}
        {isPhotoPrismApp(app) ? (
          <div className="lite-catalog-storage-panel">
            <div className="lite-catalog-storage-head">
              <div>
                <span>Media folders</span>
                <strong>{storageMappings(app).length ? storageMediaSummary(app) : 'No folders connected'}</strong>
              </div>
              <FolderOpen className="h-5 w-5" />
            </div>
            <div className="lite-catalog-storage-facts">
              <span><Server className="h-4 w-4" /> Runs on {app?.host_device_name || targetName}</span>
              <span><FolderPlus className="h-4 w-4" /> Media from: {storageMappings(app).length ? app?.storage?.summary || storageMediaSummary(app) : 'Not connected'}</span>
              <span><HardDrive className="h-4 w-4" /> Storage devices: {storageDeviceCount(app)} available</span>
            </div>
            {storageMappings(app).length ? (
              <div className="lite-catalog-storage-chips">
                {storageMappings(app).map((mapping) => (
                  <span key={mapping.mapping_id || mapping.label}>
                    {mapping.label || 'Media folder'} · {mapping.mode_label || 'Read-only'}
                  </span>
                ))}
              </div>
            ) : (
              <p className="lite-catalog-storage-empty">No media folders connected yet. Connect a photo folder to start using PhotoPrism.</p>
            )}
            <div className="lite-catalog-storage-actions">
              <LiteButton tone="secondary" onClick={(event) => connectStorage(app, 'phone_pictures', event)} disabled={Boolean(storageBusy)}>
                <FolderPlus className="h-4 w-4" />{storageBusy === `${app.id}:phone_pictures` ? 'Connecting...' : 'Connect photos'}
              </LiteButton>
              <LiteButton tone="secondary" onClick={(event) => connectStorage(app, 'phone_camera', event)} disabled={Boolean(storageBusy)}>
                Use phone photos
              </LiteButton>
              <LiteButton tone="ghost" onClick={(event) => connectStorage(app, 'storage_device', event)} disabled={Boolean(storageBusy) || storageDeviceCount(app) < 1}>
                Use storage device
              </LiteButton>
            </div>
            {storageDeviceCount(app) < 1 ? (
              <p className="lite-catalog-storage-hint">Join a storage device to use remote media folders.</p>
            ) : null}
          </div>
        ) : null}
        <div className="lite-catalog-last-op"><strong>Latest status</strong><p>{lastOperationText(app)}</p></div>
        <div className={actionsClassName}>
          <LiteButton onClick={(event) => install(app, event)} disabled={!canInstall} tone={canInstall ? 'primary' : 'secondary'}>{installing ? 'Installing...' : app?.actions?.retry ? 'Retry' : status === 'ready' ? 'Installed' : 'Install'}</LiteButton>
          <LiteButton onClick={(event) => openApp(app, event)} disabled={!canOpen} tone={canOpen ? 'primary' : 'ghost'}><ExternalLink className="h-4 w-4" />{opening ? 'Opening...' : 'Open'}</LiteButton>
          <LiteButton onClick={(event) => openAppFullScreen(app, event)} disabled={!canOpen} tone="secondary"><ExternalLink className="h-4 w-4" />Open full screen</LiteButton>
          {canInstallPhone ? (
            <LiteButton onClick={(event) => installAppToPhone(app, event)} tone="secondary"><Smartphone className="h-4 w-4" />Install to phone</LiteButton>
          ) : null}
        </div>
      </GlassCard>
    );
  }

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
    <div className="lite-catalog-screen" onPointerDown={handleCatalogPointerDown}>
      <PageHeader
        eyebrow="Apps"
        title="App Catalog"
        description="Install and open local apps from your Pocket Lab. App setup is handled by the Server Host."
        actions={(
          <div className="lite-catalog-hero-actions">
            <div className={isCatalogSecure ? 'lite-home-pill lite-catalog-hero-pill is-secure' : 'lite-home-pill lite-catalog-hero-pill is-not-secure'}>
              {isCatalogSecure ? <ShieldCheck className="h-4 w-4" /> : <ShieldAlert className="h-4 w-4" />}
              {isCatalogSecure ? 'Secure Access' : 'Not Secure'}
            </div>
            <LiteButton onClick={refresh} tone="secondary"><RefreshCw className="h-4 w-4" />Refresh</LiteButton>
          </div>
        )}
      />

      <div className="lite-catalog-toolbar">
        <div className="lite-catalog-search-wrap"><Search className="h-5 w-5" /><input className="lite-catalog-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search apps" aria-label="Search apps" /></div>
        <div className="lite-catalog-filter-pills" role="tablist" aria-label="Filter apps" data-access-contract="Secure access ready">
          {APP_FILTERS.map((filter) => (
            <button key={filter.id} type="button" className={activeFilter === filter.id ? 'is-active' : ''} onClick={() => setActiveFilter(filter.id)}>{filter.label}</button>
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

      {!loading && filteredApps.length === 0 ? (
        <GlassCard className="lite-catalog-empty-state">
          <div className="lite-catalog-empty-icon"><ImageIcon className="h-5 w-5" /></div>
          <div>
            <h2>{query ? 'No matching apps' : apps.length ? 'No apps in this view' : 'No apps installed yet'}</h2>
            <p>{query ? 'Try another search or clear the filter.' : apps.length ? 'Choose another filter to see more apps.' : 'Install your first local app to start using this self-hosted workspace.'}</p>
          </div>
          <LiteButton onClick={refresh} tone="secondary"><RefreshCw className="h-4 w-4" />Check again</LiteButton>
        </GlassCard>
      ) : null}
      <ResultNotice result={result} error={actionError} />

    </div>
  );
}

import React, { useMemo, useState } from 'react';
import { ExternalLink, LayoutGrid, RefreshCw, Server, ShieldCheck } from 'lucide-react';
import { useLiteResource } from '../hooks/useLiteStatus.js';
import { formatLiteTime, liteApi } from '../lib/liteApi.js';
import { GlassCard, StatusBadge, StateSurface, PageHeader, LiteButton, ResultNotice, LoadingCard } from './LiteUi.jsx';

function appTone(status) {
  const value = String(status || '').toLowerCase();
  if (['ready', 'installed', 'healthy'].includes(value)) return 'healthy';
  if (['installing', 'queued', 'running'].includes(value)) return 'working';
  if (['needs_attention', 'unavailable', 'failed'].includes(value)) return 'degraded';
  return 'ready';
}
function appLabel(app) {
  const value = String(app?.status || '').toLowerCase();
  if (value === 'ready') return 'Ready';
  if (value === 'installing') return 'Installing';
  if (value === 'needs_attention') return 'Needs attention';
  if (value === 'unavailable') return 'Unavailable';
  return 'Available';
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

function openCatalogApp(item) {
  const target = resolveAppOpenUrl(item);
  if (!target) return;
  window.location.assign(target);
}

export default function CatalogScreen() {
  const { data, loading, error, refresh } = useLiteResource(liteApi.catalog, []);
  const [query, setQuery] = useState('');
  const [result, setResult] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const apps = data?.apps || data?.items || [];
  const access = data?.access || {};
  const filteredApps = useMemo(() => {
    const value = query.trim().toLowerCase();
    if (!value) return apps;
    return apps.filter((app) => `${app.name || ''} ${app.summary || ''} ${app.category || ''}`.toLowerCase().includes(value));
  }, [apps, query]);
  const readyCount = apps.filter((app) => app.status === 'ready' || app.installed).length;
  const installingCount = apps.filter((app) => app.status === 'installing').length;
  const attentionCount = apps.filter((app) => ['needs_attention', 'unavailable'].includes(String(app.status || ''))).length;
  async function install(app) {
    setBusyId(app.id); setResult(null); setActionError(null);
    try {
      const targetNodeId = app?.target?.default_node_id || 'pocket-lab-lite-server';
      setResult(await liteApi.installApp(app.id, { target_node_id: targetNodeId }));
      refresh();
    } catch (err) { setActionError(err.message); } finally { setBusyId(null); }
  }
  return (
    <>
      <PageHeader eyebrow="Apps" title="App Catalog" description="Install useful apps for your self-hosted workspace. App setup is handled by the Server Host and opened through secure access when ready." actions={<LiteButton onClick={refresh} tone="secondary"><RefreshCw className="h-4 w-4" />Refresh</LiteButton>} />
      <section className="lite-catalog-hero">
        <div className="lite-catalog-hero-copy"><div className="lite-home-pill"><span className={access.https_ready ? 'lite-ready-dot' : 'lite-ready-dot lite-ready-dot-warning'} />{access.https_ready ? 'Secure access ready' : 'Remote access not ready'}</div><h2>Start with PhotoPrism.</h2><p>PhotoPrism gives this private workspace a photo library. It installs on the Server Host and uses the secure Pocket Lab route when Caddy and Tailscale HTTPS are ready.</p></div>
        <div className="lite-catalog-counts"><div><span>Available</span><strong>{apps.length}</strong></div><div><span>Ready</span><strong>{readyCount}</strong></div><div><span>Working</span><strong>{installingCount}</strong></div><div><span>Review</span><strong>{attentionCount}</strong></div></div>
      </section>
      <GlassCard className="lite-catalog-access-card"><div className="lite-catalog-access-icon"><ShieldCheck className="h-5 w-5" /></div><div><strong>{access.https_ready ? 'Secure app access is ready' : 'Open will wait for secure access'}</strong><p>{access.message || 'Pocket Lab checks whether the private HTTPS route is ready before enabling Open.'}</p></div></GlassCard>
      <div className="lite-catalog-toolbar"><div className="lite-catalog-search-wrap"><LayoutGrid className="h-5 w-5" /><input className="lite-catalog-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search apps" aria-label="Search apps" /></div><p>{filteredApps.length} shown</p></div>
      {error ? <StateSurface tone="degraded" title="Catalog needs a moment" description={error} className="mb-5" /> : null}
      {loading ? <LoadingCard label="Loading apps..." /> : null}
      <div className="lite-catalog-grid">
        {filteredApps.map((app) => {
          const status = String(app.status || 'not_installed').toLowerCase();
          const installing = status === 'installing' || busyId === app.id;
          const canInstall = Boolean(app?.actions?.install) && !installing;
          const canOpen = Boolean(app?.actions?.open && resolveAppOpenUrl(app));
          const targetName = app?.target?.eligible_devices?.[0]?.name || 'Server Host';
          const progress = app?.progress;
          return <GlassCard key={app.id} className="lite-catalog-card lite-catalog-app-card"><div className="lite-catalog-card-top"><div className="lite-catalog-icon"><LayoutGrid className="h-5 w-5" /></div><StatusBadge status={appTone(status)}>{appLabel(app)}</StatusBadge></div><div className="lite-catalog-card-title-row"><div><p className="lite-catalog-category">{app.category || 'App'}</p><h2>{app.name}</h2></div></div><p>{app.summary}</p><div className="lite-catalog-meta lite-catalog-meta-grid"><span><Server className="h-4 w-4" /> {targetName}</span><span>{app?.runtime?.health ? `Health: ${app.runtime.health}` : 'Health: not installed'}</span><span>{app?.access?.route_ready ? 'Route ready' : app?.access?.message || 'Route not ready'}</span><span>{app?.evidence_refs?.length ? `${app.evidence_refs.length} evidence file(s)` : 'Evidence appears after install'}</span></div>{progress ? <div className="lite-catalog-progress" aria-label="Install progress"><div><strong>{progress.step || 'Working'}</strong><span>{progress.current || 1}/{progress.total || 7}</span></div><p>{progress.message || 'Preparing the app.'}</p><div className="lite-catalog-progress-bar"><span style={{ width: `${Math.min(100, Math.max(0, ((progress.current || 1) / (progress.total || 7)) * 100))}%` }} /></div></div> : null}<div className="lite-catalog-last-op"><strong>Latest status</strong><p>{lastOperationText(app)}</p></div><div className="lite-catalog-actions"><LiteButton onClick={() => install(app)} disabled={!canInstall} tone={canInstall ? 'primary' : 'secondary'}>{installing ? 'Installing...' : app?.actions?.retry ? 'Retry' : status === 'ready' ? 'Installed' : 'Install'}</LiteButton><LiteButton onClick={() => openCatalogApp(app)} disabled={!canOpen} tone={canOpen ? 'secondary' : 'ghost'}><ExternalLink className="h-4 w-4" />Open</LiteButton></div></GlassCard>;
        })}
      </div>
      {!loading && filteredApps.length === 0 ? <StateSurface tone="empty" title={query ? 'No matching apps' : 'No apps yet'} description={query ? 'Try a different search term.' : 'Refresh the catalog after setup.'} /> : null}
      <ResultNotice result={result} error={actionError} />
    </>
  );
}

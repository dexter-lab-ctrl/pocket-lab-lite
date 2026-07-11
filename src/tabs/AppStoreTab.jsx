import React, { useEffect, useRef, useState } from 'react';
import * as Icons from 'lucide-react';
import { Loader2, Library, RefreshCw, ArrowDown, TestTube2 } from 'lucide-react';
import HealthEnginePanel from '../components/HealthEnginePanel';
import { useHealthEngine } from '../hooks/useHealthEngine';
import { executeOperation } from '../lib/operations';
import { AdvancedDetails, SimpleStatus } from '../components/SimpleModeControls.jsx';
import { redactTechnicalText } from '../lib/simpleLabels';
import { useControlPlaneStatus, productionWriteBlockedMessage } from '../hooks/useControlPlaneStatus.js';
import LiveEventPanel from '../components/LiveEventPanel.jsx';
import { SkeletonCards } from '../components/ui.jsx';

function normalizeCatalogItems(value) {
  if (Array.isArray(value)) return value;
  if (Array.isArray(value?.catalog)) return value.catalog;
  if (Array.isArray(value?.items)) return value.items;
  if (Array.isArray(value?.apps)) return value.apps;
  if (Array.isArray(value?.blueprints)) return value.blueprints;
  return [];
}


// Accept a `simpleMode` prop. When true, headings and action labels
// are simplified to make the interface easier for non‑technical users.
export default function AppStoreTab({ simpleMode = false }) {
  const [catalog, setCatalog] = useState([]);
  const [loadingApp, setLoadingApp] = useState(null);
  const [toast, setToast] = useState({ show: false, type: '', message: '' });
  const [isFetching, setIsFetching] = useState(true);
  const [sourceMode, setSourceMode] = useState('repo');
  const [sourceRef, setSourceRef] = useState('');
  const [deployStatus, setDeployStatus] = useState({ jobId: '', message: '', phase: 'idle' });
  const [lastCatalogRefresh, setLastCatalogRefresh] = useState('');
  const { health, refresh: refreshHealthEngine } = useHealthEngine(15000);
  const { status: controlPlane } = useControlPlaneStatus();

  const [pullDistance, setPullDistance] = useState(0);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const touchStartY = useRef(0);
  const pullThreshold = 70;
  const isLiveEnv = controlPlane.ready;

  const fetchCatalog = async () => {
    setIsFetching(true);
    if (!isLiveEnv) {
      setCatalog([]);
      setDeployStatus({ jobId: '', phase: 'blocked', message: productionWriteBlockedMessage(simpleMode) });
      setIsFetching(false);
      setIsRefreshing(false);
      setPullDistance(0);
      return;
    }
    try {
      const res = await fetch('/api/catalog.json', { cache: 'no-store', headers: { Accept: 'application/json' } });
      if (!res.ok) throw new Error('Catalog endpoint unavailable');
      setCatalog(await res.json());
    } catch {
      showToast('error', 'Control plane is unreachable.');
    } finally {
      setIsFetching(false);
      setIsRefreshing(false);
      setPullDistance(0);
    }
  };

  const refreshCatalog = async () => {
    try {
      const res = await fetch('/api/catalog/refresh', {
        method: 'POST',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          operation: 'catalog_refresh',
          target: {
            kind: 'app_catalog',
            ref: 'default',
          },
          params: {
            source: 'app_catalog',
          },
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error || 'Catalog refresh failed');
      setLastCatalogRefresh(data.updated_at || new Date().toISOString());
      await fetchCatalog();
    } catch {
      await fetchCatalog();
    }
  };

  useEffect(() => { fetchCatalog(); }, [isLiveEnv]);

  const showToast = (type, message) => {
    setToast({ show: true, type, message });
    setTimeout(() => setToast({ show: false, type: '', message: '' }), 5000);
  };

  const handleTouchStart = (e) => {
    if (window.scrollY <= 0) touchStartY.current = e.touches[0].clientY;
    else touchStartY.current = 0;
  };

  const handleTouchMove = (e) => {
    if (touchStartY.current === 0 || isRefreshing) return;
    const diff = e.touches[0].clientY - touchStartY.current;
    if (diff > 0) setPullDistance(Math.min(diff * 0.4, 120));
  };

  const handleTouchEnd = () => {
    if (pullDistance > pullThreshold && !isRefreshing) {
      if (navigator.vibrate) navigator.vibrate(30);
      setIsRefreshing(true);
      fetchCatalog();
    } else {
      setPullDistance(0);
    }
    touchStartY.current = 0;
  };

  const handleDeploy = async (appId, appTitle) => {
    setLoadingApp(appId);
    setDeployStatus({ jobId: '', message: `Submitting ${appTitle}...`, phase: 'queued' });
    if (!isLiveEnv) {
      setLoadingApp(null);
      const message = productionWriteBlockedMessage(simpleMode);
      setDeployStatus({ jobId: '', message, phase: 'blocked' });
      showToast('error', message);
      return;
    }
    try {
      const result = await executeOperation('deploy_blueprint', {
        target: { type: sourceMode, ref: sourceRef || appId },
        params: { name: appId, playbook: 'site.yml', source_type: sourceMode, source: sourceRef || appId, ref: sourceRef || appId },
      });
      setDeployStatus({ jobId: result?.job_id || '', message: result?.stdout ? 'Deployment completed.' : 'Deployment queued.', phase: result?.status || 'succeeded' });
      await refreshCatalog();
      refreshHealthEngine();
      showToast('success', simpleMode ? `${appTitle} install started.` : `Submitted ${appTitle} via typed blueprint deployment.`);
    } catch (err) {
      setDeployStatus({ jobId: '', message: err.message || 'Deployment failed.', phase: 'error' });
      showToast('error', simpleMode ? `Could not install ${appTitle}. Please check details or try again.` : `Failed to deploy ${appTitle}. Verify source and deployment settings.`);
    } finally {
      setLoadingApp(null);
    }
  };

  const headingLabel = simpleMode ? 'Apps & Services' : 'App catalog';
  const deployButtonLabel = simpleMode ? 'Install' : 'Deploy Workload';

  const catalogItems = normalizeCatalogItems(catalog);
  return (
    <div className="max-w-7xl mx-auto p-4 animate-in fade-in duration-700 space-y-6">
      {toast.show && (
        <div className="fixed top-6 left-1/2 -translate-x-1/2 z-[100] rounded-2xl border border-white/10 bg-slate-900/95 px-4 py-3 text-sm shadow-2xl">
          {toast.message}
        </div>
      )}

      <HealthEnginePanel health={health} onRefresh={refreshHealthEngine} simpleMode={simpleMode} />

      <div className="bg-slate-900/60 backdrop-blur-xl border border-white/10 rounded-[2.5rem] p-6 md:p-10 relative overflow-hidden shadow-2xl">
        <div className="absolute top-0 right-0 p-8 opacity-5 pointer-events-none transform translate-x-4 -translate-y-4">
          <Icons.Package className="w-64 h-64 text-blue-400" />
        </div>

          <div className="relative z-10 flex flex-col gap-6">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-blue-500/10 rounded-xl border border-blue-500/20">
              <TestTube2 className="w-5 h-5 text-blue-400" />
            </div>
            <h3 className="text-xs font-black text-slate-400 uppercase tracking-widest">{headingLabel}</h3>
          </div>

          <div className="flex flex-wrap gap-3 items-center">
            <button
              onClick={() => {
                refreshCatalog().catch((error) => {
                  console.error('Catalog refresh failed', error);
                });
              }} type="button" className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-black/20 px-4 py-3 text-sm font-semibold text-slate-200 hover:bg-black/30">
              <RefreshCw className="w-4 h-4" /> {simpleMode ? 'Check for New Apps' : 'Refresh catalog'}
            </button>
            {lastCatalogRefresh && <span className="text-xs text-slate-500">Last refresh: {new Date(lastCatalogRefresh).toLocaleString()}</span>}
          </div>

          {simpleMode ? (
            <SimpleStatus simpleMode phase={deployStatus.phase} message={deployStatus.message} jobId={deployStatus.jobId} />
          ) : null}

          <AdvancedDetails simpleMode={simpleMode} title="Install source settings">
            <div className="grid gap-3 md:grid-cols-3">
              <label className="block">
                <span className="text-[10px] font-black uppercase tracking-widest text-slate-500">Source mode</span>
                <select value={sourceMode} onChange={(e) => setSourceMode(e.target.value)} className="mt-2 w-full rounded-xl border border-white/10 bg-black/40 px-4 py-3 text-sm text-white">
                  <option value="repo">Repository</option>
                  <option value="oci">OCI artifact</option>
                  <option value="zip">ZIP archive</option>
                  <option value="http">HTTP/HTTPS</option>
                </select>
              </label>
              <label className="block md:col-span-2">
                <span className="text-[10px] font-black uppercase tracking-widest text-slate-500">Source reference</span>
                <input value={sourceRef} onChange={(e) => setSourceRef(e.target.value)} placeholder="catalog://app-or-oci-ref" className="mt-2 w-full rounded-xl border border-white/10 bg-black/40 px-4 py-3 text-sm text-white placeholder:text-slate-500" />
              </label>
            </div>
            <div className="rounded-2xl border border-white/10 bg-black/20 p-4 text-sm text-slate-200">
              Deployment status: {deployStatus.phase} · Task id: {deployStatus.jobId || 'queued'} · {deployStatus.message || 'Ready'}
            </div>
          </AdvancedDetails>

          {isFetching && catalog.length === 0 ? (
            <SkeletonCards count={3} simpleMode={simpleMode} />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 md:gap-6">
              {catalogItems.map((app) => {
                const LucideIcon = Icons[app.icon] || Icons.Box;
                return (
                  <div key={app.id} className="bg-[#05080f] border border-white/10 rounded-3xl p-6 shadow-xl flex flex-col hover:border-indigo-500/50 transition-all group relative overflow-hidden">
                    <div className="absolute top-0 right-0 p-4 opacity-5 pointer-events-none group-hover:scale-110 transition-transform">
                      <LucideIcon className="w-24 h-24 text-white" />
                    </div>
                    <div className="flex items-center space-x-4 mb-4 relative z-10">
                      <div className="p-3 bg-indigo-500/10 rounded-xl border border-indigo-500/30 text-indigo-400">
                        <LucideIcon className="w-6 h-6" />
                      </div>
                      <div>
                        <h3 className="text-lg font-black text-white leading-tight">{app.title}</h3>
                        {!simpleMode && <p className="text-[10px] font-mono text-slate-500">ID: {app.id}</p>}
                      </div>
                    </div>
                    <p className="text-sm text-slate-400 mb-6 flex-1 relative z-10">{app.description}</p>
                    <button
                      onClick={() => handleDeploy(app.id, app.title)}
                      disabled={loadingApp === app.id || !isLiveEnv}
                      className={`w-full py-3 rounded-xl font-bold flex items-center justify-center transition-all relative z-10 ${loadingApp === app.id ? 'bg-indigo-600/50 text-indigo-200 cursor-not-allowed' : 'bg-white/5 hover:bg-indigo-600 text-white border border-white/10 hover:border-indigo-500'}`}
                    >
                      {loadingApp === app.id ? <Loader2 className="w-5 h-5 mr-2 animate-spin" /> : <Icons.PlayCircle className="w-5 h-5 mr-2" />}
                      {!isLiveEnv ? (simpleMode ? 'Unavailable' : 'Control plane required') : (loadingApp === app.id ? (simpleMode ? 'Installing...' : 'Starting Install...') : deployButtonLabel)}
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
      <LiveEventPanel
        simpleMode={simpleMode}
        title="Apps & Services live progress"
        description="Install, catalog, and blueprint events appear here as Pocket Lab processes app changes."
        subjectPrefixes={['pocketlab.events.catalog.', 'pocketlab.events.blueprint.', 'pocketlab.events.operation.']}
        maxItems={4}
        compact
      />

    </div>
  );
}

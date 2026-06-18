import React, { useEffect, useMemo, useState } from 'react';
import { executeOperation } from '../lib/operations';
import { Compass, Layers, UploadCloud, PlayCircle, RotateCcw, Package, ClipboardList } from 'lucide-react';
import { AdvancedDetails, SimpleStatus } from '../components/SimpleModeControls.jsx';
import { simpleActionLabel, redactTechnicalText } from '../lib/simpleLabels';
import { enterpriseDisplayText } from '../lib/enterpriseLabels.js';
import LiveEventPanel from '../components/LiveEventPanel.jsx';
import DesiredStateSnap from '../components/DesiredStateSnap.jsx';

function normalizeBlueprintItems(value) {
  if (Array.isArray(value)) return value;
  if (Array.isArray(value?.blueprints)) return value.blueprints;
  if (Array.isArray(value?.items)) return value.items;
  if (Array.isArray(value?.catalog)) return value.catalog;
  if (Array.isArray(value?.apps)) return value.apps;
  return [];
}


const blueprints = [
  {
    id: 'photoprism',
    name: 'PhotoPrism',
    mode: 'repo',
    ref: 'pocket_lab_iac',
    description: 'Install the approved gallery service package.',
  },
  {
    id: 'security_scanners',
    name: 'Security Scanners',
    mode: 'oci',
    ref: 'oci://ghcr.io/pocket-lab/security-scanners:latest',
    description: 'Import an approved artifact and install it.',
  },
  {
    id: 'host_hardening',
    name: 'Host Hardening',
    mode: 'repo',
    ref: 'pocket_lab_iac',
    description: 'Roll back and re-apply the hardening service package.',
  },
];

export default function BlueprintTab({ motionEnabled, getParallaxStyle, handleEnableMotion, simpleMode = false }) {
  const [selected, setSelected] = useState(blueprints[0]);
  const [packageRef, setPackageRef] = useState(blueprints[0].ref);
  const [packageMode, setPackageMode] = useState(blueprints[0].mode);
  const [packageName, setPackageName] = useState(blueprints[0].name);
  const [status, setStatus] = useState({ phase: 'idle', jobId: '', message: '' });
  const [history, setHistory] = useState([]);

  useEffect(() => {
    setPackageRef(selected.ref);
    setPackageMode(selected.mode);
    setPackageName(selected.name);
  }, [selected]);

  const submit = async (action) => {
    if (navigator.vibrate) navigator.vibrate(15);
    setStatus({ phase: action, jobId: '', message: simpleMode ? `Starting ${simpleActionLabel(action === 'deploy' ? 'deploy_blueprint' : action, action).toLowerCase()}...` : `Submitting ${action} request...` });

    try {
      const params =
        action === 'rollback'
          ? { action: 'rollback', rollback_ref: selected.id, source_type: packageMode, source: packageRef, name: packageName, playbook: 'site.yml' }
          : { action, name: packageName, source_type: packageMode, source: packageRef, ref: packageRef, playbook: 'site.yml' };

      const result = await executeOperation('deploy_blueprint', {
        target: { type: packageMode === 'oci' ? 'oci' : 'repo', ref: packageRef },
        params,
      });

      const item = {
        at: new Date().toLocaleTimeString(),
        action,
        jobId: result?.job_id || '',
        stdout: result?.stdout || '',
      };
      setHistory((prev) => [item, ...prev].slice(0, 8));
      setStatus({ phase: result?.status || 'succeeded', jobId: result?.job_id || '', message: action === 'rollback' ? 'Rollback intent recorded.' : 'Service package request completed.' });
    } catch (err) {
      setStatus({ phase: 'error', jobId: '', message: err.message || 'Operation failed.' });
    }
  };

  const parallaxStyle = typeof getParallaxStyle === 'function' ? getParallaxStyle(0.15) : undefined;
  const title = simpleMode ? 'Apps & Services' : 'Service Package Controls';
  const installLabel = simpleMode ? 'Install' : 'Deploy Package';

  const blueprintItems = normalizeBlueprintItems(blueprints);
  return (
    <div className="max-w-7xl mx-auto p-4 space-y-6 animate-in fade-in duration-700">
      <div className="bg-slate-900/60 backdrop-blur-xl border border-white/10 rounded-[2.5rem] p-8 shadow-2xl relative overflow-hidden">
        <div className="absolute top-0 right-0 p-8 opacity-10 pointer-events-none transform translate-x-4 -translate-y-4" style={parallaxStyle}>
          <Compass className="w-48 h-48 text-indigo-400" />
        </div>
        <div className="relative z-10 flex flex-col gap-6">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div>
              <h2 className="text-4xl font-black text-white tracking-tight">{title}</h2>
              <p className="text-slate-400 text-sm mt-2 max-w-2xl">
                {simpleMode ? 'Choose approved apps or services, then install or roll back using guided safe actions.' : 'Import a package, install it, or send a rollback request through governed operation contracts.'}
              </p>
            </div>
            <div className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-slate-300">
              {simpleMode ? `Status: ${status.message || 'Ready'}` : `Current request: ${status.phase} · ${status.jobId || 'no reference yet'}`}
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-3">
            {blueprintItems.map((bp) => {
              const active = bp.id === selected.id;
              return (
                <button
                  key={bp.id}
                  type="button"
                  onClick={() => setSelected(bp)}
                  className={`rounded-2xl border p-4 text-left transition-all ${
                    active ? 'bg-indigo-500/10 border-indigo-500/30' : 'bg-black/20 border-white/10 hover:border-white/20'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <Package className={`h-5 w-5 ${active ? 'text-indigo-300' : 'text-slate-400'}`} />
                    <div>
                      <div className="font-bold text-white">{bp.name}</div>
                      {!simpleMode && <div className="text-xs text-slate-400">{bp.mode} · {bp.ref}</div>}
                    </div>
                  </div>
                  <p className="mt-3 text-xs text-slate-400">{bp.description}</p>
                </button>
              );
            })}
          </div>

          <AdvancedDetails simpleMode={simpleMode} title="App source details">
            <div className="grid gap-3 md:grid-cols-3">
              <label className="block">
                <span className="text-[10px] font-black uppercase tracking-widest text-slate-500">Package mode</span>
                <select value={packageMode} onChange={(e) => setPackageMode(e.target.value)} className="mt-2 w-full rounded-xl border border-white/10 bg-black/40 px-4 py-3 text-sm text-white">
                  <option value="repo">Repository</option>
                  <option value="oci">OCI artifact</option>
                  <option value="zip">ZIP archive</option>
                  <option value="http">HTTP/HTTPS</option>
                </select>
              </label>
              <label className="block">
                <span className="text-[10px] font-black uppercase tracking-widest text-slate-500">Package ref</span>
                <input value={packageRef} onChange={(e) => setPackageRef(e.target.value)} className="mt-2 w-full rounded-xl border border-white/10 bg-black/40 px-4 py-3 text-sm text-white" />
              </label>
              <label className="block">
                <span className="text-[10px] font-black uppercase tracking-widest text-slate-500">Package name</span>
                <input value={packageName} onChange={(e) => setPackageName(e.target.value)} className="mt-2 w-full rounded-xl border border-white/10 bg-black/40 px-4 py-3 text-sm text-white" />
              </label>
            </div>
          </AdvancedDetails>

          <div className="flex flex-wrap gap-3">
            <button onClick={() => submit('import')} className="inline-flex items-center gap-2 rounded-xl bg-sky-600 px-5 py-3 font-semibold text-white hover:bg-sky-500">
              <UploadCloud className="h-4 w-4" /> {simpleMode ? 'Add to List' : 'Import Package'}
            </button>
            <button onClick={() => submit('deploy')} className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-5 py-3 font-semibold text-white hover:bg-indigo-500">
              <PlayCircle className="h-4 w-4" /> {installLabel}
            </button>
            <button onClick={() => submit('rollback')} className="inline-flex items-center gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 px-5 py-3 font-semibold text-amber-100 hover:bg-amber-500/15">
              <RotateCcw className="h-4 w-4" /> {simpleMode ? 'Undo Last Change' : 'Rollback Last Package'}
            </button>
          </div>

          <div className={`rounded-2xl border p-4 ${status.phase === 'error' ? 'border-red-500/30 bg-red-500/10 text-red-100' : 'border-white/10 bg-black/20 text-slate-200'}`}>
            <div className="font-semibold">{simpleMode ? redactTechnicalText(status.message || 'Ready.') : (status.message || 'Ready.')}</div>
            {!simpleMode && <div className="mt-1 text-xs uppercase tracking-widest text-slate-400">Reference: {status.jobId || 'queued'}</div>}
          </div>
          <DesiredStateSnap className="blueprint-desired-state-snap" simpleMode={simpleMode} active={['deploy', 'rollback'].includes(status.phase)} complete={/completed|succeeded|deployed|created/i.test(status.message || '')} />
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="bg-[#05080f] border border-white/10 rounded-[2rem] p-6 shadow-xl">
          <div className="flex items-center gap-2 mb-4">
            <Layers className="h-4 w-4 text-slate-400" />
            <h3 className="text-xs font-black uppercase tracking-widest text-slate-500">{simpleMode ? 'Selected app details' : 'Package details'}</h3>
          </div>
          <div className="space-y-3 text-sm">
            <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
              <div className="text-xs uppercase tracking-widest text-slate-500">Selected package</div>
              <div className="mt-1 font-semibold text-white">{selected.name}</div>
            </div>
            <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
              <div className="text-xs uppercase tracking-widest text-slate-500">Mode</div>
              <div className="mt-1 font-semibold text-white">{packageMode}</div>
            </div>
            <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
              <div className="text-xs uppercase tracking-widest text-slate-500">Source</div>
              <div className="mt-1 font-mono text-white break-all">{packageRef}</div>
            </div>
          </div>
        </div>

        <div className="bg-[#05080f] border border-white/10 rounded-[2rem] p-6 shadow-xl">
          <div className="flex items-center gap-2 mb-4">
            <ClipboardList className="h-4 w-4 text-slate-400" />
            <h3 className="text-xs font-black uppercase tracking-widest text-slate-500">{simpleMode ? 'Recent Activity' : 'Request history'}</h3>
          </div>
          <div className="space-y-3">
            {history.length === 0 ? (
              <div className="rounded-2xl border border-white/10 bg-black/20 p-4 text-sm text-slate-400">
                No service package requests yet.
              </div>
            ) : history.map((item) => (
              <div key={`${item.at}-${item.jobId}`} className="rounded-2xl border border-white/10 bg-black/20 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="font-semibold text-white">{simpleMode ? simpleActionLabel(item.action === 'deploy' ? 'deploy_blueprint' : item.action, item.action) : enterpriseDisplayText(item.action)}</div>
                    <div className="text-xs text-slate-400">{item.at}</div>
                  </div>
                  <span className="rounded-full border border-white/10 px-2 py-1 text-[10px] font-bold uppercase tracking-widest text-slate-400">
                    {item.jobId || 'queued'}
                  </span>
                </div>
                {!simpleMode && <pre className="mt-3 overflow-auto rounded-xl bg-black/30 p-3 text-[11px] text-slate-300">{enterpriseDisplayText(item.stdout)}</pre>}
              </div>
            ))}
          </div>
        </div>
      </div>
      <LiveEventPanel
        simpleMode={simpleMode}
        title="Service package activity"
        description="Package import, install, rollback, and request progress appears here."
        subjectPrefixes={['pocketlab.events.blueprint.', 'pocketlab.events.operation.']}
        maxItems={4}
        compact
      />

    </div>
  );
}

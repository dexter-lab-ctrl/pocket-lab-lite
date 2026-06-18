import React, { useEffect, useMemo, useRef, useState } from 'react';
import { CloudDownload, RefreshCw, AlertTriangle, ChevronRight, Zap, CheckCircle2, Server, GitBranch, Database, RotateCw, ShieldCheck } from 'lucide-react';
import { applyReleaseUpdate, checkReleaseUpdate, fetchReleaseUpdateStatus } from '../lib/operations';

const POLL_INTERVAL_MS = 5000;

export default function OTAUpdater() {
  const [status, setStatus] = useState('checking');
  const [releaseState, setReleaseState] = useState({
    phase: 'idle',
    current_tag: 'unknown',
    latest_tag: 'unknown',
    latest_release: null,
    update_available: false,
    auto_apply: true,
    last_checked_at: null,
    last_applied_at: null,
    error: null,
    operations: [],
  });
  const [busy, setBusy] = useState(false);
  const reloadTimerRef = useRef(null);

  const loadStatus = async () => {
    try {
      const data = await fetchReleaseUpdateStatus();
      setReleaseState(data || {});
      if (data?.phase === 'applied' || (!data?.update_available && data?.phase === 'current')) {
        setStatus('up-to-date');
      } else if (data?.phase === 'applying') {
        setStatus('updating');
      } else if (data?.update_available) {
        setStatus('available');
      } else {
        setStatus('checking');
      }
      return data;
    } catch (err) {
      setStatus('error');
      setReleaseState((prev) => ({ ...prev, error: err?.message || 'Unable to load release status.' }));
      return null;
    }
  };

  useEffect(() => {
    loadStatus();
    const timer = setInterval(loadStatus, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (releaseState?.phase === 'applied' && !reloadTimerRef.current) {
      reloadTimerRef.current = window.setTimeout(() => {
        window.location.reload();
      }, 1200);
    }
    return () => {
      if (reloadTimerRef.current) {
        window.clearTimeout(reloadTimerRef.current);
        reloadTimerRef.current = null;
      }
    };
  }, [releaseState?.phase]);

  const targetLabel = useMemo(() => releaseState?.latest_tag || 'latest', [releaseState]);
  const currentLabel = useMemo(() => releaseState?.current_tag || 'unknown', [releaseState]);
  const latestReleaseName = useMemo(() => releaseState?.latest_release?.name || releaseState?.latest_release?.tag_name || targetLabel, [releaseState, targetLabel]);

  const runCheck = async () => {
    setBusy(true);
    try {
      await checkReleaseUpdate();
      await loadStatus();
    } finally {
      setBusy(false);
    }
  };

  const runApply = async () => {
    setBusy(true);
    setStatus('updating');
    try {
      await applyReleaseUpdate();
      await loadStatus();
    } catch (err) {
      setStatus('error');
      setReleaseState((prev) => ({ ...prev, error: err?.message || 'Release application failed.' }));
    } finally {
      setBusy(false);
    }
  };

  const statusTone = {
    checking: 'border-slate-500/20 bg-slate-500/10 text-slate-200',
    available: 'border-amber-500/20 bg-amber-500/10 text-amber-200',
    updating: 'border-blue-500/20 bg-blue-500/10 text-blue-200',
    'up-to-date': 'border-emerald-500/20 bg-emerald-500/10 text-emerald-200',
    error: 'border-red-500/20 bg-red-500/10 text-red-200',
  }[status] || 'border-slate-500/20 bg-slate-500/10 text-slate-200';

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-4 animate-in fade-in duration-700">
      <div className="bg-slate-900/60 backdrop-blur-xl border border-white/10 rounded-[2rem] p-4 md:p-6 relative overflow-hidden shadow-2xl">
        <div className="absolute top-0 right-0 p-6 opacity-5 pointer-events-none transform translate-x-4 -translate-y-4">
          <CloudDownload className="w-56 h-56 text-blue-400" />
        </div>

        <div className="relative z-10 flex flex-col gap-4">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <div className="flex items-center space-x-3 mb-3">
                <div className="p-2 bg-blue-500/10 rounded-xl border border-blue-500/20">
                  <Zap className="w-5 h-5 text-blue-400" />
                </div>
                <h3 className="text-xs font-black text-slate-400 uppercase tracking-widest flex items-center">
                  <Server className="w-3 h-3 mr-2" /> Self-updating release channel
                </h3>
              </div>
              <h2 className="text-xl md:text-2xl font-black text-white tracking-tight">Pocket Lab auto-update</h2>
              <p className="text-slate-400 text-sm max-w-3xl leading-relaxed mt-2">
                The release coordinator watches approved releases, runs the governed release workflow, and refreshes the UI once the new bundle is ready.
              </p>
            </div>

            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={runCheck}
                disabled={busy}
                className="inline-flex items-center justify-center gap-2 rounded-xl border border-white/10 bg-black/30 px-4 py-3 text-sm font-semibold text-white hover:bg-black/50 disabled:opacity-50"
              >
                <RefreshCw className={`h-4 w-4 ${busy && status === 'checking' ? 'animate-spin' : ''}`} />
                Check release
              </button>
              <button
                type="button"
                onClick={runApply}
                disabled={busy || status === 'up-to-date'}
                className="inline-flex items-center justify-center gap-2 rounded-xl border border-blue-500/30 bg-blue-600 px-4 py-3 text-sm font-semibold text-white hover:bg-blue-500 disabled:opacity-50"
              >
                <CloudDownload className={`h-4 w-4 ${busy && status === 'updating' ? 'animate-pulse' : ''}`} />
                Apply latest
              </button>
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-4">
            <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500">Current</p>
              <p className="mt-2 text-sm font-mono text-white">{currentLabel}</p>
            </div>
            <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500">Target</p>
              <p className="mt-2 text-sm font-mono text-white">{targetLabel}</p>
            </div>
            <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500">Release</p>
              <p className="mt-2 text-sm font-semibold text-white">{latestReleaseName}</p>
            </div>
            <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500">Mode</p>
              <p className="mt-2 text-sm font-semibold text-white">{releaseState?.auto_apply ? 'Auto apply enabled' : 'Manual apply'}</p>
            </div>
          </div>

          <div className={`rounded-2xl border p-4 ${statusTone}`}>
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                {status === 'error' ? <AlertTriangle className="h-4 w-4" /> : status === 'up-to-date' ? <CheckCircle2 className="h-4 w-4" /> : <RotateCw className={`h-4 w-4 ${status === 'updating' ? 'animate-spin' : ''}`} />}
                <span className="text-sm font-semibold uppercase tracking-widest">{status}</span>
              </div>
              <span className="text-xs uppercase tracking-widest opacity-75">{releaseState?.phase || 'idle'}</span>
            </div>
            <div className="mt-2 text-sm opacity-90">
              {releaseState?.error || (releaseState?.update_available ? 'A newer release is available and the release agent will apply it.' : 'The running instance is aligned with the latest release state.')}
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            <div className="bg-[#05080f] border border-white/5 rounded-2xl p-4">
              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500">Last checked</p>
              <p className="mt-2 text-sm font-mono text-white">{releaseState?.last_checked_at || '—'}</p>
            </div>
            <div className="bg-[#05080f] border border-white/5 rounded-2xl p-4">
              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500">Last applied</p>
              <p className="mt-2 text-sm font-mono text-white">{releaseState?.last_applied_at || '—'}</p>
            </div>
          </div>

          {Array.isArray(releaseState?.operations) && releaseState.operations.length > 0 && (
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              {releaseState.operations.map((op) => (
                <div key={`${op.operation}-${op.job_id || op.status}`} className="rounded-2xl border border-white/10 bg-black/20 p-3">
                  <div className="flex items-center gap-2 text-sm font-semibold text-white">
                    <GitBranch className="h-4 w-4 text-slate-400" />
                    {op.operation}
                  </div>
                  <div className="mt-1 text-xs text-slate-400">{op.status}</div>
                  {op.job_id ? <div className="mt-1 text-[10px] uppercase tracking-widest text-slate-500">Job {op.job_id}</div> : null}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

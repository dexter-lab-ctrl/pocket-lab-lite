import React, { useEffect, useMemo, useState } from 'react';
import HealthEnginePanel from '../components/HealthEnginePanel';
import { useHealthEngine } from '../hooks/useHealthEngine';
import { executeOperation, previewOperation } from '../lib/operations';
import { CheckCircle2, Eye, RefreshCw, ShieldAlert, ShieldCheck, Loader2, GitCompareArrows, Activity, Target } from 'lucide-react';
import { AdvancedDetails } from '../components/SimpleModeControls.jsx';
import { simpleStatusLabel, redactTechnicalText } from '../lib/simpleLabels';
import LiveEventPanel from '../components/LiveEventPanel.jsx';
import DesiredStateSnap from '../components/DesiredStateSnap.jsx';
import { SkeletonCards } from '../components/ui.jsx';

function safeParse(text) {
  try { return JSON.parse(text); } catch { return null; }
}

function badge(status) {
  if (status === 'healthy') return 'bg-emerald-500/10 text-emerald-200 border-emerald-500/20';
  if (status === 'drifted' || status === 'diff_ready') return 'bg-amber-500/10 text-amber-200 border-amber-500/20';
  if (status === 'pending' || status === 'pending_approval') return 'bg-sky-500/10 text-sky-200 border-sky-500/20';
  if (status === 'failed') return 'bg-red-500/10 text-red-200 border-red-500/20';
  return 'bg-slate-500/10 text-slate-300 border-slate-500/20';
}

// Accept a `simpleMode` prop for simplified text and labels.
export default function DriftCenterTab({ simpleMode = false }) {
  const [summary, setSummary] = useState({ healthy: 0, drifted: 0, pending_approval: 0, failed: 0, last_scan_at: null });
  const [jobs, setJobs] = useState([]);
  const [selectedJobId, setSelectedJobId] = useState('');
  const [diffText, setDiffText] = useState('');
  const [operationRuns, setOperationRuns] = useState([]);
  const [running, setRunning] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [taskMessage, setTaskMessage] = useState('');
  const { health, refresh: refreshHealthEngine } = useHealthEngine(15000);

  // Simple experience mode replaces technical wording for a
  // general audience.  The subtitle appears in the header and
  // the button label for scanning drift is simplified.
  const subtitle = simpleMode ? 'Health & Issues' : 'Configuration Health';
  const headingTitle = simpleMode ? 'System health & issues' : 'Operation status stream and drift jobs';
  const scanButtonLabel = simpleMode ? 'Scan for Changes' : 'Scan Drift';

  const selectedJob = useMemo(() => jobs.find((job) => String(job.job_id) === String(selectedJobId)) || null, [jobs, selectedJobId]);
  const hasDrift = Number(summary.drifted || 0) > 0;
  const opaStatus = health?.checks?.find((check) => check.name === 'opa' || check.name === 'policy-engine')?.status || 'unknown';
  const driftBlocked = ['unhealthy', 'unavailable', 'degraded', 'warning', 'maintenance'].includes(opaStatus);

  const loadDrift = async () => {
    try {
      const [summaryRes, jobsRes] = await Promise.all([fetch('/api/drift/summary'), fetch('/api/drift/jobs')]);
      const summaryData = safeParse(await summaryRes.text());
      const jobsData = safeParse(await jobsRes.text());
      if (summaryData) setSummary((prev) => ({ ...prev, ...summaryData }));
      if (Array.isArray(jobsData)) {
        setJobs(jobsData);
        if (!selectedJobId && jobsData[0]?.job_id) setSelectedJobId(jobsData[0].job_id);
      }
    } catch {
      setSummary({ healthy: 0, drifted: 0, pending_approval: 0, failed: 1, last_scan_at: null });
      setJobs([]);
      setTaskMessage(simpleMode ? 'Pocket Lab cannot check changes until the live control plane is ready.' : 'control plane control plane unavailable; drift data is not simulated in production mode.');
    } finally {
      setRefreshing(false);
    }
  };

  const loadOperationRuns = async () => {
    try {
      const res = await fetch('/api/operations/runs');
      const data = safeParse(await res.text());
      if (Array.isArray(data?.runs)) setOperationRuns(data.runs.slice(0, 8));
    } catch {
      setOperationRuns([]);
    }
  };

  const loadSelectedDiff = async (jobId) => {
    if (!jobId) return;
    try {
      const [jobRes, diffRes] = await Promise.all([fetch(`/api/drift/jobs/${encodeURIComponent(jobId)}`), fetch(`/api/drift/jobs/${encodeURIComponent(jobId)}/diff`)]);
      const jobData = safeParse(await jobRes.text());
      const diffData = safeParse(await diffRes.text());
      if (jobData) setJobs((prev) => prev.map((item) => (item.job_id === jobId ? { ...item, ...jobData } : item)));
      setDiffText(JSON.stringify(diffData || jobData?.diff || [], null, 2));
    } catch {
      setDiffText(simpleMode ? 'No change details available while Pocket Lab is offline.' : 'Drift diff unavailable because the Control API control plane could not be reached.');
    }
  };

  useEffect(() => {
    loadDrift();
    loadOperationRuns();
    const driftTimer = setInterval(loadDrift, 10000);
    const runTimer = setInterval(loadOperationRuns, 5000);
    return () => {
      clearInterval(driftTimer);
      clearInterval(runTimer);
    };
  }, []);

  useEffect(() => {
    if (selectedJobId) loadSelectedDiff(selectedJobId);
  }, [selectedJobId]);

  const runTyped = async (mode) => {
    setRunning(true);
    setTaskMessage(simpleMode ? `${mode === 'scan' ? 'Checking' : mode === 'preview' ? 'Preparing review' : mode === 'apply' ? 'Fixing' : mode === 'approve' ? 'Approving' : 'Updating'}...` : `${mode} in progress...`);
    try {
      let result;
      if (mode === 'scan') {
        result = await executeOperation('drift_scan', { target: { type: 'drift', ref: 'workspace' }, params: { scope: 'all' } });
        await loadDrift();
      } else if (mode === 'preview') {
        result = await previewOperation('drift_scan', { target: { type: 'drift', ref: selectedJob?.target || 'workspace' }, params: { scope: selectedJob?.scope || 'service' } });
      } else if (mode === 'apply' || mode === 'approve' || mode === 'ignore') {
        const response = await fetch(`/api/drift/${mode}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ targets: [selectedJob?.target || selectedJob?.job_id || ''] }),
        });
        const data = safeParse(await response.text());
        if (!response.ok) throw new Error(data?.error || `Drift ${mode} rejected`);
        await loadDrift();
        result = data;
      }
      setTaskMessage(simpleMode ? `${mode === 'scan' ? 'Check' : mode === 'preview' ? 'Review' : mode === 'apply' ? 'Fix' : mode === 'approve' ? 'Approval' : 'Update'} completed.` : `${mode} completed${result?.job_id ? ` · task ${result.job_id}` : ''}.`);
    } catch (err) {
      setTaskMessage(simpleMode ? redactTechnicalText(err.message || 'This action could not be completed.') : (err.message || 'Drift action failed.'));
    } finally {
      setRunning(false);
    }
  };

  const scanDrift = async () => {
    setRefreshing(true);
    try {
      await runTyped('scan');
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto p-4 animate-in fade-in duration-700 relative space-y-6">
      <HealthEnginePanel health={health} onRefresh={refreshHealthEngine} simpleMode={simpleMode} />
      <div className="rounded-3xl border border-white/10 bg-slate-900/60 p-6 shadow-2xl">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="flex items-center gap-2 text-slate-400">
              <GitCompareArrows className="h-4 w-4" />
              <span className="text-xs font-black uppercase tracking-widest">{subtitle}</span>
            </div>
            <h2 className="mt-2 text-3xl font-black text-white">{headingTitle}</h2>
            <p className="mt-2 max-w-2xl text-sm text-slate-400">
              {simpleMode ? 'Pocket Lab checks whether anything changed from what should be installed, then helps you review or fix it safely.' : 'The drift view is now tied to typed operations. Each scan, preview, and reconcile action exposes a task id and the live operation stream.'}
            </p>
          </div>
          <AdvancedDetails simpleMode={simpleMode} title="Policy guardrail details">
            <div className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-slate-200">
              OPA: {opaStatus} · Drift blocked: {driftBlocked ? 'yes' : 'no'}
            </div>
          </AdvancedDetails>
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-4">
          <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
            <div className="text-[10px] font-bold uppercase tracking-widest text-slate-500">Healthy</div>
            <div className="mt-1 text-2xl font-black text-white">{summary.healthy ?? 0}</div>
          </div>
          <div className={`rounded-2xl border border-white/10 bg-black/20 p-4 ${hasDrift ? 'drift-ripple-card' : ''}`}>
            <div className="flex items-center justify-between gap-2">
              <div className="text-[10px] font-bold uppercase tracking-widest text-slate-500">{simpleMode ? 'Something Changed' : 'Drifted'}</div>
              {hasDrift ? <span className="drift-detected-badge">{simpleMode ? 'Something Changed' : 'Drift Detected'}</span> : null}
            </div>
            <div className="mt-1 text-2xl font-black text-white drift-count">{summary.drifted ?? 0}</div>
          </div>
          <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
            <div className="text-[10px] font-bold uppercase tracking-widest text-slate-500">{simpleMode ? 'Needs Review' : 'Pending'}</div>
            <div className="mt-1 text-2xl font-black text-white">{summary.pending_approval ?? 0}</div>
          </div>
          <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
            <div className="text-[10px] font-bold uppercase tracking-widest text-slate-500">{simpleMode ? 'Selected Item' : 'Task id'}</div>
            <div className="mt-1 text-sm font-mono text-white">{simpleMode ? (selectedJob?.target || '—') : (selectedJobId || '—')}</div>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap gap-3">
          <button onClick={scanDrift} disabled={running} className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-5 py-3 font-semibold text-white hover:bg-indigo-500 disabled:opacity-50">
            {refreshing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            {scanButtonLabel}
          </button>
          <button onClick={() => runTyped('preview')} disabled={running || !selectedJob} className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-black/20 px-5 py-3 font-semibold text-slate-200 hover:bg-black/30 disabled:opacity-50">
            <Eye className="h-4 w-4" /> {simpleMode ? 'Review Changes' : 'Preview Selected'}
          </button>
          <button onClick={() => runTyped('approve')} disabled={running || !selectedJob} className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-black/20 px-5 py-3 font-semibold text-slate-200 hover:bg-black/30 disabled:opacity-50">
            <ShieldCheck className="h-4 w-4" /> {simpleMode ? 'Looks Good' : 'Approve'}
          </button>
          <button onClick={() => runTyped('apply')} disabled={running || !selectedJob} className={`inline-flex items-center gap-2 rounded-xl border border-white/10 bg-black/20 px-5 py-3 font-semibold text-slate-200 hover:bg-black/30 disabled:opacity-50 risk-level-glow risk-medium ${(!selectedJob || running) ? 'write-blocked-action' : ''}`}>
            <CheckCircle2 className="h-4 w-4" /> {simpleMode ? 'Fix This' : 'Apply'}
          </button>
          <button onClick={() => runTyped('ignore')} disabled={running || !selectedJob} className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-black/20 px-5 py-3 font-semibold text-slate-200 hover:bg-black/30 disabled:opacity-50">
            <ShieldAlert className="h-4 w-4" /> {simpleMode ? 'Leave It Alone' : 'Ignore'}
          </button>
        </div>

        {taskMessage && (
          <div className="mt-4 rounded-2xl border border-white/10 bg-black/20 p-4 text-sm text-slate-200">
            {taskMessage}
          </div>
        )}
        <DesiredStateSnap className="drift-desired-state-snap mt-4" simpleMode={simpleMode} active={running} complete={/completed|succeeded|applied/i.test(taskMessage || '')} />
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <div className="bg-[#05080f] border border-white/10 rounded-[2rem] p-6 shadow-xl">
          <div className="flex items-center gap-2 mb-4">
            <Activity className="h-4 w-4 text-slate-400" />
            <h3 className="text-xs font-black uppercase tracking-widest text-slate-500">{simpleMode ? 'Recent Activity' : 'Operation status stream'}</h3>
          </div>
          <div className="space-y-3">
            {operationRuns.length === 0 ? (
              <SkeletonCards count={2} simpleMode={simpleMode} className="drift-skeletons" />
            ) : operationRuns.map((run) => (
              <div key={run.job_id} className={`rounded-2xl border border-white/10 bg-black/20 p-4 ${String(run.status || '').includes('drift') ? 'drift-ripple-card' : ''}`}>
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="font-semibold text-white">{simpleMode ? redactTechnicalText(run.operation) : run.operation}</div>
                    <div className="text-xs text-slate-400">{new Date(run.created_at || Date.now()).toLocaleString()}</div>
                  </div>
                  <span className={`rounded-full border px-2 py-1 text-[10px] font-bold uppercase tracking-widest ${badge(run.status)}`}>
                    {simpleMode ? simpleStatusLabel(run.status, run.status) : run.status}
                  </span>
                </div>
                {!simpleMode && <div className="mt-2 text-xs text-slate-400">Task id: {run.job_id}</div>}
              </div>
            ))}
          </div>
        </div>

        <div className="bg-[#05080f] border border-white/10 rounded-[2rem] p-6 shadow-xl">
          <div className="flex items-center gap-2 mb-4">
            <Target className="h-4 w-4 text-slate-400" />
            <h3 className="text-xs font-black uppercase tracking-widest text-slate-500">{simpleMode ? 'Issue Details' : 'Drift job details'}</h3>
          </div>

          <label className="block mb-4">
            <span className="text-[10px] font-black uppercase tracking-widest text-slate-500">{simpleMode ? 'Selected issue' : 'Selected job'}</span>
            <select value={selectedJobId} onChange={(e) => setSelectedJobId(e.target.value)} className="mt-2 w-full rounded-xl border border-white/10 bg-black/40 px-4 py-3 text-sm text-white">
              <option value="">Select a job</option>
              {jobs.map((job) => <option key={job.job_id} value={job.job_id}>{simpleMode ? job.target : `${job.job_id} · ${job.target}`}</option>)}
            </select>
          </label>

          {selectedJob ? (
            <div className="space-y-3">
              <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                <div className="text-xs uppercase tracking-widest text-slate-500">Summary</div>
                <div className="mt-1 font-semibold text-white">{selectedJob.summary || '—'}</div>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <div className={`rounded-2xl border border-white/10 bg-black/20 p-4 ${['drifted', 'diff_ready'].includes(selectedJob.status) ? 'drift-ripple-card' : ''}`}>
                  <div className="text-xs uppercase tracking-widest text-slate-500">Status</div>
                  <div className={`mt-1 inline-flex rounded-full border px-2 py-1 text-[10px] font-bold uppercase tracking-widest ${badge(selectedJob.status)}`}>{simpleMode ? simpleStatusLabel(selectedJob.status, selectedJob.status || 'unknown') : (selectedJob.status || 'unknown')}</div>
                </div>
                <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                  <div className="text-xs uppercase tracking-widest text-slate-500">Approval</div>
                  <div className="mt-1 text-sm font-semibold text-white">{selectedJob.approval_state || '—'}</div>
                </div>
              </div>
              <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                <div className="text-xs uppercase tracking-widest text-slate-500">Diff</div>
                <pre className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap text-[11px] text-slate-300">{diffText || '—'}</pre>
              </div>
            </div>
          ) : (
            <div className="rounded-2xl border border-white/10 bg-black/20 p-4 text-sm text-slate-400">Choose a drift job to inspect it.</div>
          )}
        </div>
      </div>
      <LiveEventPanel
        simpleMode={simpleMode}
        title="Health & Issues activity"
        description="Change checks and remediation progress update here in real time."
        subjectPrefixes={['pocketlab.events.drift.', 'pocketlab.events.operation.']}
        maxItems={4}
        compact
      />

    </div>
  );
}

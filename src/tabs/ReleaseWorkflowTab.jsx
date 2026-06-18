import React, { useEffect, useMemo, useState } from 'react';
import { CheckCircle2, CloudDownload, RefreshCw, ShieldCheck, GitBranch, Database, Workflow, FileText, Server, PlayCircle, ExternalLink } from 'lucide-react';
import { executeOperation, fetchReleaseWorkflow, refreshCatalog, checkReleaseUpdate, applyReleaseUpdate, fetchReleaseUpdateStatus } from '../lib/operations';
import { AdvancedDetails } from '../components/SimpleModeControls.jsx';
import { simpleActionLabel, redactTechnicalText } from '../lib/simpleLabels';
import { enterpriseDisplayText, enterpriseOperationLabel } from '../lib/enterpriseLabels.js';
import LiveEventPanel from '../components/LiveEventPanel.jsx';
import ReleaseConveyor from '../components/ReleaseConveyor.jsx';

const OPERATION_CONTEXT = {
  release_prepare: {
    target: { type: 'backup', ref: 'release' },
    params: { scope: 'full' },
  },
  release_sync: {
    target: { type: 'repo', ref: 'pocket_lab_iac' },
    params: { branch: 'main' },
  },
  release_deploy: {
    target: { type: 'repo', ref: 'pocket_lab_iac' },
    params: { playbook: 'site.yml', source_type: 'repo', source: 'pocket_lab_iac' },
  },
  release_verify: {
    target: { type: 'drift', ref: 'workspace' },
    params: { scope: 'all' },
  },
  git_sync: {
    target: { type: 'repo', ref: 'pocket_lab_iac' },
    params: { branch: 'main' },
  },
  drift_scan: {
    target: { type: 'drift', ref: 'workspace' },
    params: { scope: 'all' },
  },
  backup_now: {
    target: { type: 'backup', ref: 'release' },
    params: { scope: 'full' },
  },
  deploy_blueprint: {
    target: { type: 'repo', ref: 'pocket_lab_iac' },
    params: { playbook: 'site.yml', source_type: 'repo', source: 'pocket_lab_iac' },
  },
};

const SUBSYSTEM_ICONS = {
  'Frontend PWA': Workflow,
  'Pocket Lab Control Plane': Server,
  'Environment updates': GitBranch,
  'Service package engine': CloudDownload,
  'App Store': CloudDownload,
  'Catalog store': Database,
  'Security guardrails': ShieldCheck,
  'Configuration Health': RefreshCw,
  'Health engine': CheckCircle2,
  'Identity & Access': Database,
  'Ansible runner': PlayCircle,
};

function stageBadge(operation) {
  if (!operation) return 'bg-slate-500/10 text-slate-300 border-slate-500/20';
  if (operation === 'catalog_refresh') return 'bg-amber-500/10 text-amber-200 border-amber-500/20';
  if (operation.includes('verify') || operation.includes('drift')) return 'bg-emerald-500/10 text-emerald-200 border-emerald-500/20';
  if (operation.includes('deploy')) return 'bg-blue-500/10 text-blue-200 border-blue-500/20';
  if (operation.includes('backup') || operation.includes('prepare')) return 'bg-violet-500/10 text-violet-200 border-violet-500/20';
  return 'bg-slate-500/10 text-slate-300 border-slate-500/20';
}

export default function ReleaseWorkflowTab({ simpleMode = false }) {
  const [workflow, setWorkflow] = useState(null);
  const [loading, setLoading] = useState(true);
  const [statusLine, setStatusLine] = useState('Loading release workflow...');
  const [running, setRunning] = useState('');
  const [history, setHistory] = useState([]);
  const [releaseStatus, setReleaseStatus] = useState(null);

  const stages = useMemo(() => workflow?.stages || [], [workflow]);

  const loadWorkflow = async () => {
    setLoading(true);
    try {
      const data = await fetchReleaseWorkflow();
      setWorkflow(data);
      try {
        setReleaseStatus(await fetchReleaseUpdateStatus());
      } catch {
        setReleaseStatus(null);
      }
      setStatusLine(simpleMode ? 'Updates are ready to review.' : 'Release workflow loaded.');
    } catch (err) {
      setWorkflow(null);
      setStatusLine(err?.message || 'Unable to load release workflow.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadWorkflow();
  }, []);

  const logResult = (label, detail) => {
    setHistory((prev) => [
      { at: new Date().toLocaleTimeString(), label, detail },
      ...prev,
    ].slice(0, 8));
  };

  const runOperation = async (operation) => {
    setRunning(operation);
    setStatusLine(simpleMode ? `Starting ${simpleActionLabel(operation, operation).toLowerCase()}...` : `Running ${enterpriseOperationLabel(operation, operation)}...`);
    try {
      if (operation === 'catalog_refresh') {
        const result = await refreshCatalog();
        logResult(simpleMode ? 'App list updated' : 'catalog_refresh', simpleMode ? `${result?.count ?? 0} apps checked` : `Catalog refreshed · ${result?.count ?? 0} items`);
        setStatusLine(simpleMode ? 'App list updated.' : 'Catalog refreshed.');
        return;
      }

      const context = OPERATION_CONTEXT[operation] || {
        target: { type: 'repo', ref: 'pocket_lab_iac' },
        params: {},
      };
      const result = await executeOperation(operation, context);
      logResult(simpleMode ? simpleActionLabel(operation, redactTechnicalText(operation)) : enterpriseOperationLabel(operation, operation), simpleMode ? 'Completed successfully.' : `${result?.status || 'succeeded'} · ${result?.job_id || 'no reference'}`);
      setStatusLine(simpleMode ? `${simpleActionLabel(operation, 'Action')} completed.` : `${enterpriseOperationLabel(operation, operation)} completed.`);
    } catch (err) {
      logResult(simpleMode ? simpleActionLabel(operation, redactTechnicalText(operation)) : enterpriseOperationLabel(operation, operation), simpleMode ? redactTechnicalText(err?.message || 'Action failed') : enterpriseDisplayText(err?.message || 'Operation failed'));
      setStatusLine(simpleMode ? redactTechnicalText(err?.message || 'Action failed.') : (err?.message || 'Operation failed.'));
    } finally {
      setRunning('');
    }
  };


  const runReleaseCommand = async (kind) => {
    setRunning(kind);
    setStatusLine(simpleMode ? (kind === 'apply' ? 'Starting safe update...' : 'Checking for approved updates...') : `Release ${kind} requested...`);
    try {
      const result = kind === 'apply' ? await applyReleaseUpdate() : await checkReleaseUpdate();
      setReleaseStatus((prev) => ({ ...(prev || {}), phase: result.status || 'queued', last_command_id: result.command_id || result.job_id, last_response: result }));
      logResult(
        simpleMode ? (kind === 'apply' ? 'Safe update started' : 'Update check started') : `release.${kind}`,
        simpleMode ? 'Follow the live update activity below.' : `${result.execution_mode || 'queued'} · ${result.command_id || result.job_id || 'no command id'}`,
      );
      setStatusLine(simpleMode ? 'Pocket Lab accepted the update request.' : `Release ${kind} accepted.`);
    } catch (err) {
      logResult(simpleMode ? 'Update needs attention' : `release.${kind}`, simpleMode ? redactTechnicalText(err?.message || 'Update request failed') : (err?.message || 'Release request failed'));
      setStatusLine(simpleMode ? redactTechnicalText(err?.message || 'Update request failed.') : (err?.message || 'Release request failed.'));
    } finally {
      setRunning('');
    }
  };

  return (
    <div className="max-w-7xl mx-auto p-4 space-y-6 animate-in fade-in duration-700">
      <div className="bg-slate-900/60 backdrop-blur-xl border border-white/10 rounded-[2.5rem] p-6 md:p-8 shadow-2xl relative overflow-hidden">
        <div className="absolute top-0 right-0 p-6 opacity-5 pointer-events-none">
          <Workflow className="w-64 h-64 text-indigo-400" />
        </div>

        <div className="relative z-10 flex flex-col gap-4">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="text-xs font-black uppercase tracking-[0.35em] text-indigo-300/80">{simpleMode ? 'Updates' : 'Release control plane'}</p>
              <h2 className="text-3xl md:text-4xl font-black text-white tracking-tight mt-2">{simpleMode ? 'Update Pocket Lab' : 'Pocket Lab release workflow'}</h2>
              <p className="text-slate-400 text-sm max-w-3xl mt-3">
                {simpleMode ? 'Apply approved updates safely. Pocket Lab backs up, updates, checks health, and verifies that everything still works.' : 'This view connects release intake, validation, service package installation, configuration health checks, system checks, and app update readiness into one governed workflow.'}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => runReleaseCommand('check')}
                disabled={running === 'check'}
                className="inline-flex items-center justify-center gap-2 rounded-2xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-3 text-sm font-semibold text-emerald-100 hover:bg-emerald-500/15 disabled:opacity-60"
              >
                <RefreshCw className={`h-4 w-4 ${running === 'check' ? 'animate-spin' : ''}`} />
                {simpleMode ? 'Check Updates' : 'Check release'}
              </button>
              <button
                type="button"
                onClick={() => runReleaseCommand('apply')}
                disabled={running === 'apply'}
                className="inline-flex items-center justify-center gap-2 rounded-2xl border border-indigo-500/20 bg-indigo-500/10 px-4 py-3 text-sm font-semibold text-indigo-100 hover:bg-indigo-500/15 disabled:opacity-60"
              >
                <CloudDownload className={`h-4 w-4 ${running === 'apply' ? 'animate-pulse' : ''}`} />
                {simpleMode ? 'Update Everything' : 'Apply orchestrated release'}
              </button>
              <button
                type="button"
                onClick={loadWorkflow}
                className="inline-flex items-center justify-center gap-2 rounded-2xl border border-white/10 bg-black/30 px-4 py-3 text-sm font-semibold text-white hover:bg-black/50"
              >
                <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                {simpleMode ? 'Refresh View' : 'Refresh workflow'}
              </button>
            </div>
          </div>

          <ReleaseConveyor className="release-conveyor-inline" simpleMode={simpleMode} enterpriseMode={!simpleMode} activeStage={running === 'check' ? 0 : running === 'apply' ? 3 : /complete|completed|succeeded/i.test(statusLine || '') ? 5 : 1} />

          <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
            <AdvancedDetails simpleMode={simpleMode} title="Update source details">
              <div className="flex items-center gap-2 text-xs uppercase tracking-[0.3em] text-slate-500">
                <ExternalLink className="h-3.5 w-3.5" />
                Loaded from <span className="text-slate-300">/api/release/workflow</span>
              </div>
            </AdvancedDetails>
            <div className="mt-2 text-sm text-slate-300">{statusLine}</div>
            {releaseStatus && (
              <div className="mt-3 grid gap-2 md:grid-cols-3">
                <div className="rounded-xl border border-white/10 bg-white/5 px-3 py-2">
                  <div className="text-[10px] uppercase tracking-[0.25em] text-slate-500">{simpleMode ? 'Current' : 'Current tag'}</div>
                  <div className="mt-1 text-sm font-semibold text-white">{releaseStatus.current_tag || 'unknown'}</div>
                </div>
                <div className="rounded-xl border border-white/10 bg-white/5 px-3 py-2">
                  <div className="text-[10px] uppercase tracking-[0.25em] text-slate-500">{simpleMode ? 'Latest' : 'Latest tag'}</div>
                  <div className="mt-1 text-sm font-semibold text-white">{releaseStatus.latest_tag || 'unknown'}</div>
                </div>
                <div className="rounded-xl border border-white/10 bg-white/5 px-3 py-2">
                  <div className="text-[10px] uppercase tracking-[0.25em] text-slate-500">{simpleMode ? 'State' : 'Updater phase'}</div>
                  <div className="mt-1 text-sm font-semibold text-white">{releaseStatus.phase || 'idle'}</div>
                </div>
              </div>
            )}
            {workflow?.summary?.length ? (
              <div className="mt-3 flex flex-wrap gap-2">
                {workflow.summary.map((item) => (
                  <span key={item} className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-300">
                    {simpleMode ? redactTechnicalText(item) : item}
                  </span>
                ))}
              </div>
            ) : null}
          </div>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        {stages.map((stage) => (
          <article key={stage.id} className="rounded-[2rem] border border-white/10 bg-slate-900/60 p-5 shadow-xl">
            <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
              <div>
                <div className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold ${stageBadge(stage.operations?.[0]?.operation)}`}>
                  {simpleMode ? 'Safe update step' : enterpriseOperationLabel(stage.operations?.[0]?.operation, 'Workflow')}
                </div>
                <h3 className="mt-3 text-2xl font-black text-white">{stage.title}</h3>
                <p className="mt-2 text-sm text-slate-400 max-w-2xl">{stage.purpose}</p>
              </div>
              <div className="flex flex-wrap gap-2">
                {(stage.operations || []).map((op) => (
                  <button
                    key={simpleMode ? simpleActionLabel(op.operation, op.name) : enterpriseDisplayText(op.name)}
                    type="button"
                    disabled={running === op.operation}
                    onClick={() => runOperation(op.operation)}
                    className={`inline-flex items-center gap-2 rounded-xl border px-3 py-2 text-xs font-semibold transition ${
                      running === op.operation
                        ? 'border-blue-500/30 bg-blue-500/10 text-blue-200'
                        : 'border-white/10 bg-black/30 text-slate-200 hover:bg-white/5'
                    }`}
                  >
                    <PlayCircle className="h-3.5 w-3.5" />
                    {simpleMode ? simpleActionLabel(op.operation, op.name) : enterpriseDisplayText(op.name)}
                  </button>
                ))}
              </div>
            </div>

            <div className="mt-5 grid gap-3 lg:grid-cols-2">
              <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                <div className="text-[10px] font-black uppercase tracking-[0.35em] text-slate-500">{simpleMode ? 'What this changes' : 'Exact files touched'}</div>
                <div className="mt-3 space-y-3">
                  {stage.files?.map((file) => (
                    <div key={file.path} className="rounded-xl border border-white/5 bg-white/5 p-3">
                      <div className="flex items-start gap-2">
                        <FileText className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />
                        <div>
                          {!simpleMode && <div className="font-mono text-xs text-slate-200">{file.path}</div>}
                          <div className="mt-1 text-xs text-slate-400">{file.note}</div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                <div className="text-[10px] font-black uppercase tracking-[0.35em] text-slate-500">{simpleMode ? 'Safety checks' : 'Subsystems and steps'}</div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {(stage.subsystems || []).map((item) => {
                    const Icon = SUBSYSTEM_ICONS[item] || CheckCircle2;
                    return (
                      <span key={item} className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-300">
                        <Icon className="h-3.5 w-3.5 text-slate-400" />
                        {item}
                      </span>
                    );
                  })}
                </div>
                <div className="mt-4 space-y-2">
                  {(stage.steps || []).map((step, idx) => (
                    <div key={step} className="flex items-start gap-3 rounded-xl border border-white/5 bg-white/5 px-3 py-2">
                      <span className="mt-0.5 inline-flex h-5 w-5 items-center justify-center rounded-full bg-indigo-500/15 text-[10px] font-black text-indigo-200">
                        {idx + 1}
                      </span>
                      <p className="text-sm text-slate-300">{step}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </article>
        ))}
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.35fr_0.65fr]">
        <div className="rounded-[2rem] border border-white/10 bg-slate-900/60 p-5 shadow-xl">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-xl font-black text-white">{simpleMode ? 'What happens during an update' : 'What the workflow uses'}</h3>
            <div className="text-xs uppercase tracking-[0.3em] text-slate-500">{simpleMode ? 'Plain view' : 'Subsystem map'}</div>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {[
              [simpleMode ? 'Approved updates' : 'GitHub Releases', simpleMode ? 'Pocket Lab checks approved update information.' : 'Public source of truth for versioned frontend builds.'],
              [simpleMode ? 'App refresh' : 'PWA autoUpdate', simpleMode ? 'The app refreshes after an update is applied.' : 'Clients refresh the cached app bundle after deploy.'],
              ['GitOpsTab', 'Runs repository sync and catalog reconciliation.'],
              ['BlueprintTab', 'Promotes repo, zip, OCI, or HTTP packages.'],
              ['DriftCenterTab', 'Confirms that deployed state still matches intent.'],
              ['SecurityPostureTab', 'Blocks rollout when policy posture is weak.'],
              ['IdentityVaultTab', 'Handles secrets, dynamic credentials, and rotation.'],
              ['HealthEnginePanel', 'Surfaces service health before and after promotion.'],
            ].map(([name, detail]) => (
              <div key={name} className="rounded-2xl border border-white/10 bg-black/20 p-4">
                <div className="font-semibold text-white">{name}</div>
                <div className="mt-1 text-sm text-slate-400">{detail}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-[2rem] border border-white/10 bg-slate-900/60 p-5 shadow-xl">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-xl font-black text-white">Recent actions</h3>
            <Database className="h-5 w-5 text-slate-500" />
          </div>
          <div className="mt-4 space-y-3">
            {history.length ? history.map((item) => (
              <div key={`${item.at}-${item.label}`} className="rounded-2xl border border-white/10 bg-black/20 p-4">
                <div className="flex items-center justify-between gap-2">
                  <div className="font-semibold text-white">{simpleMode ? redactTechnicalText(item.label) : enterpriseDisplayText(item.label)}</div>
                  <div className="text-xs text-slate-500">{item.at}</div>
                </div>
                <div className="mt-2 text-sm text-slate-400">{simpleMode ? redactTechnicalText(item.detail) : enterpriseDisplayText(item.detail)}</div>
              </div>
            )) : (
              <div className="rounded-2xl border border-dashed border-white/10 bg-black/10 p-4 text-sm text-slate-500">
                Release actions you run from here will appear in this log.
              </div>
            )}
          </div>
        </div>
      </div>
      <LiveEventPanel
        simpleMode={simpleMode}
        title="Update workflow activity"
        description="Release stages and update actions stream here while Pocket Lab upgrades safely."
        subjectPrefixes={['pocketlab.events.release.', 'pocketlab.events.operation.']}
        maxItems={4}
        compact
      />

    </div>
  );
}

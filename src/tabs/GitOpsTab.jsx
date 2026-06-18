import React, { useEffect, useMemo, useRef, useState } from 'react';
import { executeOperation, previewOperation } from '../lib/operations';
import { CloudCog, TerminalSquare, RefreshCw, PlayCircle, Eye, Lock, GitBranch, FileCode2, Activity, Layers3 } from 'lucide-react';
import { simpleActionLabel, simpleOperationCopy, redactTechnicalText } from '../lib/simpleLabels';
import JetStreamFlowLine from '../components/JetStreamFlowLine.jsx';
import DesiredStateSnap from '../components/DesiredStateSnap.jsx';
import LiveEventPanel from '../components/LiveEventPanel.jsx';
import EvidenceReceipt from '../components/EvidenceReceipt.jsx';
import SafeActionPreview from '../components/SafeActionPreview.jsx';
import { useToast } from '../components/ToastProvider.jsx';
import { createEvidenceReceipt } from '../lib/evidenceReceipts.js';
import { useControlPlaneStatus, productionWriteBlockedMessage } from '../hooks/useControlPlaneStatus.js';
import { GlassCard, PageShell, ProgressiveDisclosure, StandardList, StandardListItem, StatusBadge } from '../components/ui.jsx';
import { enterpriseDisplayText, enterpriseOperationLabel } from '../lib/enterpriseLabels.js';

const TASKS = [
  {
    id: 'sync_repo',
    name: 'Update Environment',
    operation: 'git_sync',
    description: 'Save the approved setup so devices stay updated.',
    mode: 'execute',
    target: { type: 'repo', ref: 'pocket_lab_iac' },
    params: { path: 'README.md', content: '# Pocket Lab\n', message: 'Environment update', branch: 'main' },
    icon: GitBranch,
  },
  {
    id: 'validate_blueprint',
    name: 'Validate Service Package',
    operation: 'drift_scan',
    description: 'Check what would change before anything is updated.',
    mode: 'preview',
    target: { type: 'repo', ref: 'pocket_lab_iac' },
    params: { scope: 'gitops', source: 'pocket_lab_iac' },
    icon: Eye,
  },
  {
    id: 'deploy_blueprint',
    name: 'Install Service',
    operation: 'deploy_blueprint',
    description: 'Install the approved apps and services.',
    mode: 'execute',
    target: { type: 'repo', ref: 'pocket_lab_iac' },
    params: { playbook: 'site.yml', source_type: 'repo', source: 'pocket_lab_iac' },
    icon: PlayCircle,
  },
];

export default function GitOpsTab({ simpleMode = false }) {
  const [activeTask, setActiveTask] = useState(TASKS[0]);
  const [repoRef, setRepoRef] = useState('pocket_lab_iac');
  const [manifestPath, setManifestPath] = useState('README.md');
  const [taskLogs, setTaskLogs] = useState('');
  const [jobId, setJobId] = useState('');
  const [receipt, setReceipt] = useState(null);
  const [running, setRunning] = useState(false);
  const [dispatching, setDispatching] = useState(false);
  const toast = useToast();
  const { status: controlPlane } = useControlPlaneStatus(15000);
  const isLiveEnv = controlPlane.ready;
  const logsEndRef = useRef(null);

  useEffect(() => {
    if (logsEndRef.current) logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
  }, [taskLogs]);

  const tasks = useMemo(() => {
    if (!simpleMode) return TASKS;
    return TASKS.map((task) => ({
      ...task,
      name: simpleOperationCopy(task.operation, simpleActionLabel(task.operation, task.name)).title,
      description: simpleOperationCopy(task.operation, task.name).description,
    }));
  }, [simpleMode]);

  const resolvedTask = useMemo(() => ({
    ...activeTask,
    target: { ...activeTask.target, ref: repoRef || activeTask.target.ref },
    params: {
      ...activeTask.params,
      path: manifestPath || activeTask.params.path,
      source: repoRef || activeTask.params.source,
    },
  }), [activeTask, repoRef, manifestPath]);

  useEffect(() => {
    setActiveTask(tasks[0]);
  }, [tasks]);

  const runTask = async () => {
    if (navigator.vibrate) navigator.vibrate(20);
    setDispatching(true);
    window.setTimeout(() => setDispatching(false), 420);
    setRunning(true);
    setJobId('');
    setReceipt(null);
    setTaskLogs(simpleMode ? `Starting ${resolvedTask.name}...\n` : `[*] Task launcher: ${resolvedTask.name}\n`);
    toast.info(`${resolvedTask.name} is being prepared.`, { title: simpleMode ? 'Getting ready' : 'Action queued' });
    try {
      if (resolvedTask.mode !== 'preview' && !isLiveEnv) {
        const blockedMessage = productionWriteBlockedMessage(simpleMode);
        setTaskLogs((prev) => prev + `\n${blockedMessage}`);
        setReceipt(createEvidenceReceipt({ operation: resolvedTask.operation, status: 'blocked', mode: resolvedTask.mode, message: blockedMessage, simpleMode }));
        toast.warning(blockedMessage, { title: simpleMode ? 'Paused for safety' : 'Control plane unavailable' });
        return;
      }
      const action = resolvedTask.mode === 'preview' ? previewOperation : executeOperation;
      const result = await action(resolvedTask.operation, {
        target: resolvedTask.target,
        params: resolvedTask.params,
      });
      const nextJobId = result?.job_id || '';
      setJobId(nextJobId);
      const receiptMessage = simpleMode ? redactTechnicalText(result?.stdout || 'Completed successfully.') : (enterpriseDisplayText(result?.stdout || 'Task completed.'));
      setTaskLogs((prev) => prev + (simpleMode ? `\n${receiptMessage}\n\nDone.` : `\n${enterpriseDisplayText(result?.stdout || JSON.stringify(result, null, 2))}\n\n[SUCCESS] Task completed.`));
      setReceipt(createEvidenceReceipt({ operation: resolvedTask.operation, jobId: nextJobId, status: 'succeeded', mode: resolvedTask.mode, message: receiptMessage, simpleMode }));
      toast.success(nextJobId ? `${resolvedTask.name} started. Job: ${nextJobId}` : `${resolvedTask.name} completed.`, { title: simpleMode ? 'Started safely' : 'Operation contract accepted' });
    } catch (err) {
      const errorMessage = enterpriseDisplayText(err.message || 'Task failed.');
      const receiptMessage = simpleMode ? redactTechnicalText(errorMessage) : errorMessage;
      setTaskLogs((prev) => prev + (simpleMode ? `\nNeeds attention: ${receiptMessage}` : `\n[ERROR] ${errorMessage}`));
      setReceipt(createEvidenceReceipt({ operation: resolvedTask.operation, status: 'failed', mode: resolvedTask.mode, message: receiptMessage, simpleMode }));
      toast.error(simpleMode ? redactTechnicalText(errorMessage) : errorMessage, { title: simpleMode ? 'Needs attention' : 'Operation failed' });
    } finally {
      setRunning(false);
    }
  };

  const headingTitle = simpleMode ? 'Keep My Environment Updated' : 'Environment Update Launcher';
  const headingCopy = simpleMode
    ? 'Keep Pocket Lab updated with safe, approved actions. Technical controls are available in advanced details.'
    : 'Launch governed environment actions through the control plane. No freeform command editor, no direct shell execution, and no browser access to backend messaging.';

  return (
    <PageShell
      eyebrow={simpleMode ? 'Updates' : (isLiveEnv ? 'Enterprise orchestration' : 'control plane degraded')}
      title={headingTitle}
      description={headingCopy}
      actions={<StatusBadge status={isLiveEnv ? 'healthy' : 'degraded'}>{isLiveEnv ? 'Live control plane' : 'Control plane required'}</StatusBadge>}
    >
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="min-w-0 space-y-5">
          <GlassCard className={`relative overflow-hidden p-5 sm:p-6 lg:p-8 ${dispatching ? 'command-dispatch-active' : ''}`}>
            <div className="pointer-events-none absolute -right-16 -top-16 opacity-10">
              <CloudCog className="h-56 w-56 text-indigo-300" />
            </div>

            <div className="relative z-10 space-y-5">
              <div className="flex flex-wrap items-center gap-2">
                <div className={`rounded-2xl border p-2 ${isLiveEnv ? 'border-indigo-300/25 bg-indigo-500/10 text-indigo-200' : 'border-amber-300/25 bg-amber-500/10 text-amber-200'}`}>
                  {isLiveEnv ? <FileCode2 className="h-5 w-5" /> : <Lock className="h-5 w-5" />}
                </div>
                <div className="min-w-0">
                  <p className="pocket-eyebrow">{simpleMode ? 'Choose an update action' : 'Named action launcher'}</p>
                  <p className="text-sm text-slate-400">Selected: <span className="font-semibold text-slate-200">{resolvedTask.name}</span></p>
                </div>
              </div>

              <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
                {tasks.map((task) => {
                  const Icon = task.icon;
                  const selected = activeTask.id === task.id;
                  return (
                    <button
                      key={task.id}
                      type="button"
                      onClick={() => setActiveTask(task)}
                      className={`min-h-40 rounded-3xl border p-4 text-left transition-all duration-200 ${selected ? 'border-indigo-300/35 bg-indigo-500/15 shadow-lg shadow-indigo-950/25' : 'border-white/10 bg-black/20 hover:border-white/20 hover:bg-white/5'}`}
                    >
                      <div className="flex min-w-0 items-start gap-3">
                        <div className={`shrink-0 rounded-2xl border p-2 ${selected ? 'border-indigo-300/25 bg-indigo-500/10 text-indigo-200' : 'border-white/10 bg-white/5 text-slate-400'}`}>
                          <Icon className="h-5 w-5" />
                        </div>
                        <div className="min-w-0">
                          <div className="break-words text-base font-black leading-6 text-white">{task.name}</div>
                          {!simpleMode && <div className="mt-1 break-all text-xs text-slate-500">{enterpriseOperationLabel(task.operation)}</div>}
                        </div>
                      </div>
                      <p className="mt-4 text-sm leading-6 text-slate-400">{task.description}</p>
                    </button>
                  );
                })}
              </div>

              <SafeActionPreview operation={resolvedTask.operation} simpleMode={simpleMode} defaultOpen={simpleMode} />
              {['git_sync', 'deploy_blueprint', 'drift_scan', 'drift_apply'].includes(resolvedTask.operation) ? (
                <DesiredStateSnap
                  className="gitops-desired-state-snap"
                  simpleMode={simpleMode}
                  active={running}
                  complete={receipt?.status === 'succeeded' || receipt?.status === 'success'}
                />
              ) : null}
              {(running || jobId || taskLogs) ? <JetStreamFlowLine simpleMode={simpleMode} activeIndex={jobId ? 3 : running ? 2 : taskLogs ? 1 : 0} /> : null}
              <EvidenceReceipt receipt={receipt} simpleMode={simpleMode} />

              <ProgressiveDisclosure simpleMode={simpleMode} title={simpleMode ? 'Support settings' : 'Update source settings'}>
                <div className="grid gap-3 lg:grid-cols-2">
                  <label className="block min-w-0">
                    <span className="text-[10px] font-black uppercase tracking-widest text-slate-500">Repository ref</span>
                    <input value={repoRef} onChange={(e) => setRepoRef(e.target.value)} className="pocket-input mt-2 w-full" />
                  </label>
                  <label className="block min-w-0">
                    <span className="text-[10px] font-black uppercase tracking-widest text-slate-500">Manifest path</span>
                    <input value={manifestPath} onChange={(e) => setManifestPath(e.target.value)} className="pocket-input mt-2 w-full" />
                  </label>
                </div>
              </ProgressiveDisclosure>

              <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                <div className="min-w-0 space-y-2">
                  {dispatching ? <p className="command-dispatch-label">{simpleMode ? 'Sending request safely...' : 'Action queued through the control plane'}</p> : null}
                <button
                  type="button"
                  onClick={runTask}
                  disabled={running || (resolvedTask.mode !== 'preview' && !isLiveEnv)}
                  className={`pocket-button pocket-button-primary w-full lg:w-auto ${(resolvedTask.mode !== 'preview' && !isLiveEnv) ? 'write-blocked-action' : ''}`}
                >
                  {running ? <RefreshCw className="h-4 w-4 animate-spin" /> : <PlayCircle className="h-4 w-4" />}
                  {!isLiveEnv && resolvedTask.mode !== 'preview' ? (simpleMode ? 'Unavailable' : 'Control plane required') : (simpleMode ? resolvedTask.name : `Run ${resolvedTask.name}`)}
                </button>
                </div>
                {!simpleMode && (
                  <div className="min-w-0 rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-xs leading-5 text-slate-300">
                    <span className="font-semibold text-slate-200">Task:</span> {resolvedTask.id}
                    <span className="mx-2 text-slate-600">•</span>
                    <span className="font-semibold text-slate-200">Action:</span> <span className="break-all">{enterpriseOperationLabel(resolvedTask.operation)}</span>
                    <span className="mx-2 text-slate-600">•</span>
                    <span className="font-semibold text-slate-200">Job:</span> {jobId || 'queued'}
                  </div>
                )}
              </div>
            </div>
          </GlassCard>

          <GlassCard className="flex min-h-[22rem] flex-col overflow-hidden p-0">
            <div className="flex items-center justify-between border-b border-white/10 bg-slate-950/45 px-4 py-3">
              <div className="flex items-center gap-2">
                <TerminalSquare className="h-4 w-4 text-indigo-300" />
                <span className="text-sm font-black text-slate-200">{simpleMode ? 'Recent Activity' : 'Launcher Stream'}</span>
              </div>
              <StatusBadge status="pending">{simpleMode ? 'Guided' : 'Action-aware'}</StatusBadge>
            </div>

            <div className="flex-1 overflow-y-auto p-5 font-mono text-[12px] leading-6 text-indigo-100/85">
              {taskLogs ? (
                <div className="whitespace-pre-wrap break-words">
                  {taskLogs}
                  <div ref={logsEndRef} />
                </div>
              ) : (
                <div className="flex h-full min-h-56 flex-col items-center justify-center text-center text-slate-500">
                  <Activity className="mb-3 h-12 w-12" />
                  <p>{simpleMode ? 'Choose an update action to begin.' : 'Awaiting task selection.'}</p>
                </div>
              )}
            </div>
          </GlassCard>
        </div>

        <aside className="min-w-0 space-y-5">
          <GlassCard className="p-0">
            <StandardList
              title={simpleMode ? 'Support Details' : 'Named task map'}
              description={simpleMode ? 'These are the safe update actions Pocket Lab can run for you.' : 'Every launcher option maps to a governed operation contract.'}
            >
              {tasks.map((task) => (
                <StandardListItem
                  key={task.id}
                  icon={Layers3}
                  title={task.name}
                  description={task.description}
                  status={task.mode === 'preview' ? 'queued' : 'ready'}
                  simpleMode={simpleMode}
                  metadata={!simpleMode ? [{ label: 'Action', value: enterpriseOperationLabel(task.operation) }, { label: 'Mode', value: task.mode }] : [{ label: 'Type', value: task.mode === 'preview' ? 'Check only' : 'Can make changes' }]}
                />
              ))}
            </StandardList>
          </GlassCard>

          <LiveEventPanel
            simpleMode={simpleMode}
            title="Environment update activity"
            description="Environment update activity appears here while Pocket Lab keeps the environment aligned."
            subjectPrefixes={['pocketlab.events.operation.', 'pocketlab.events.gitops.', 'pocketlab.audit.']}
            maxItems={4}
            compact
          />
        </aside>
      </div>
    </PageShell>
  );
}

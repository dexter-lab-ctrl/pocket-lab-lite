import React, { useState } from 'react';
import { CheckCircle2, Loader2, PlayCircle } from 'lucide-react';
import { executeOperationQueued, previewOperation } from '../lib/operations';
import { simpleOperationCopy, redactTechnicalText } from '../lib/simpleLabels';
import EvidenceReceipt from './EvidenceReceipt.jsx';
import SafeActionPreview from './SafeActionPreview.jsx';
import { useToast } from './ToastProvider.jsx';
import { createEvidenceReceipt } from '../lib/evidenceReceipts.js';
import { enterpriseDisplayText, enterpriseOperationLabel } from '../lib/enterpriseLabels.js';
import { ProgressiveDisclosure } from './ui.jsx';

/**
 * Guided enterprise Simple Mode action. The user sees an outcome and plain
 * language. Technical operation IDs remain available only in advanced details
 * for support/debugging.
 */
export default function SimpleActionWizard({ title, operation, target, params, mode = 'execute', simpleMode = true }) {
  const [state, setState] = useState({ running: false, message: '', error: '', jobId: '', receipt: null });
  const [dispatching, setDispatching] = useState(false);
  const toast = useToast();
  const copy = simpleOperationCopy(operation, title || 'Run Action');
  const displayTitle = title || copy.title;

  const handleRun = async () => {
    const action = mode === 'preview' ? previewOperation : executeOperationQueued;
    setDispatching(true);
    window.setTimeout(() => setDispatching(false), 420);
    setState({ running: true, message: `Starting ${displayTitle.toLowerCase()}...`, error: '', jobId: '', receipt: null });
    toast.info(`${displayTitle} is being prepared.`, { title: simpleMode ? 'Getting ready' : 'Action queued' });
    try {
      const result = await action(operation, { target, params });
      const jobId = result?.job_id || result?.run_id || '';
      const message = jobId ? `${copy.title} has started. Watch live progress above.` : redactTechnicalText(result?.stdout || copy.success);
      setState({
        running: false,
        message,
        error: '',
        jobId,
        receipt: createEvidenceReceipt({ operation, jobId, status: 'succeeded', mode, message, simpleMode }),
      });
      toast.success(message, { title: simpleMode ? 'Started safely' : 'Operation started' });
    } catch (err) {
      const errorMessage = redactTechnicalText(err.message || 'This action could not be completed.');
      setState({
        running: false,
        message: '',
        error: errorMessage,
        jobId: '',
        receipt: createEvidenceReceipt({ operation, status: 'failed', mode, message: errorMessage, simpleMode }),
      });
      toast.error(enterpriseDisplayText(errorMessage), { title: simpleMode ? 'Needs attention' : 'Operation failed' });
    }
  };

  return (
    <div className={`simple-action-card space-y-5 rounded-[1.75rem] border border-white/10 bg-white/5 p-5 shadow-lg shadow-blue-950/10 sm:p-6 ${dispatching ? 'command-dispatch-active' : ''}`}>
      <div>
        <h3 className="text-lg font-black text-white">{displayTitle}</h3>
        <p className="mt-2 text-sm leading-6 text-slate-300">{copy.description}</p>
      </div>
      <SafeActionPreview operation={operation} simpleMode={simpleMode} />
      {dispatching ? <p className="command-dispatch-label">{simpleMode ? 'Sending request safely...' : 'Action queued through the control plane'}</p> : null}
      <button
        type="button"
        onClick={handleRun}
        disabled={state.running}
        className="pocket-button pocket-button-primary rounded-2xl bg-indigo-500 px-5 py-3 text-sm shadow-indigo-950/25 hover:bg-indigo-400 disabled:opacity-50"
      >
        {state.running ? <Loader2 className="h-4 w-4 animate-spin" /> : <PlayCircle className="h-4 w-4" />}
        {state.running ? 'Working...' : displayTitle}
      </button>
      {state.message ? <p className="inline-flex items-center gap-2 text-sm text-emerald-200"><CheckCircle2 className="h-4 w-4" /> {state.message}</p> : null}
      {state.error ? <p className="text-sm text-rose-200">{state.error}</p> : null}
      <EvidenceReceipt receipt={state.receipt} simpleMode={simpleMode} />
      <ProgressiveDisclosure simpleMode={simpleMode} title="Support details">
        <div>Action: <span className="font-mono">{enterpriseOperationLabel(operation)}</span></div>
        <div>Live job: <span className="font-mono">{state.jobId || 'not queued yet'}</span></div>
        <div>Target: <span className="font-mono break-all">{enterpriseDisplayText(JSON.stringify(target))}</span></div>
        <div>Settings: <span className="font-mono break-all">{enterpriseDisplayText(JSON.stringify(params))}</span></div>
      </ProgressiveDisclosure>
    </div>
  );
}

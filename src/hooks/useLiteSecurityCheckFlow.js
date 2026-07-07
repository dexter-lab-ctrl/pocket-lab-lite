import { useEffect, useMemo, useRef } from 'react';
import { useMachine } from '@xstate/react';
import { liteSecurityCheckLabels, liteSecurityCheckMachine, securityCheckFlowSteps } from '../machines/liteSecurityCheckMachine.js';
import { writeBlockedReason } from '../machines/liteFlowGuards.js';
export const LITE_SECURITY_CHECK_FLOW_USES_FASTAPI_ONLY = true;
function timelineHas(security, key) { const timeline = Array.isArray(security?.execution_timeline) ? security.execution_timeline : []; return timeline.some((step) => String(step?.key || '').toLowerCase() === key && ['completed','done','running','active'].includes(String(step?.status || step?.state || '').toLowerCase())); }
export function useLiteSecurityCheckFlow({ security = {}, backendReachable = true, savedStateOnly = false } = {}) {
  const [snapshot, send] = useMachine(liteSecurityCheckMachine);
  const value = String(snapshot.value || 'idle');
  const writeBlocked = savedStateOnly || backendReachable === false;
  const blockedReason = writeBlockedReason({ backendReachable, savedStateOnly });
  const runId = security?.last_run?.run_id || null;
  const runStatus = String(security?.last_run?.status || security?.scan_progress?.status || security?.status || '').toLowerCase();
  const summary = security?.summary || 'Safety check needs attention.';
  const workerPickedUp = timelineHas(security, 'worker_picked_up');
  const lynisRunning = timelineHas(security, 'lynis_host_check');
  const trivyRunning = timelineHas(security, 'trivy_dependency_secret_check');
  const evidenceSaved = timelineHas(security, 'evidence_saved');
  const partialResults = Boolean(security?.last_run?.partial_results);
  const backendStateSignature = JSON.stringify({
    backendReachable,
    savedStateOnly,
    runId,
    runStatus,
    workerPickedUp,
    lynisRunning,
    trivyRunning,
    evidenceSaved,
    partialResults,
    summary,
  });
  const lastBackendStateSignatureRef = useRef('');

  useEffect(() => {
    // SECURITY_FLOW_BACKEND_STATE_SEND_GUARD: only relay meaningful backend-state
    // changes into XState. Without this guard, unstable security object identity can
    // repeatedly send events, causing React error #185 / maximum update depth.
    if (lastBackendStateSignatureRef.current === backendStateSignature) return;
    lastBackendStateSignatureRef.current = backendStateSignature;
    send({ type: 'BACKEND_STATE', backendReachable, savedStateOnly, runId, status: runStatus });
    if (savedStateOnly) send({ type: 'SAVED_STATE_ONLY' });
    if (workerPickedUp) send({ type: 'WORKER_PICKED_UP' });
    if (lynisRunning) send({ type: 'LYNIS_RUNNING' });
    if (trivyRunning) send({ type: 'TRIVY_RUNNING' });
    if (evidenceSaved) send({ type: 'EVIDENCE_SAVED' });
    if (partialResults) send({ type: 'PARTIAL_RESULTS' });
    if (['succeeded','success','healthy','completed'].includes(runStatus)) send({ type: 'COMPLETE' });
    if (['degraded','review','needs_attention','partial'].includes(runStatus)) send({ type: 'NEEDS_ATTENTION' });
    if (['failed','failure','error'].includes(runStatus)) send({ type: 'FAILED', reason: summary });
  }, [backendReachable, backendStateSignature, evidenceSaved, lynisRunning, partialResults, runId, runStatus, savedStateOnly, send, summary, trivyRunning, workerPickedUp]);
  return useMemo(() => ({ value, label: liteSecurityCheckLabels[value] || 'Run Safety Check', steps: securityCheckFlowSteps(value), writeBlocked, blockedReason, context: snapshot.context, requestRun: () => { if (writeBlocked) { send({ type: 'SAVED_STATE_ONLY' }); return { ok: false, reason: blockedReason || 'Reconnect to continue.' }; } send({ type: 'CHECK_READINESS' }); send({ type: 'RUN' }); return { ok: true }; }, accepted: (payload) => send({ type: 'ACCEPTED', payload }), fail: (error) => send({ type: 'FAILED', error }), cancel: () => send({ type: 'CANCEL' }), reset: () => send({ type: 'RESET' }) }), [blockedReason, send, snapshot.context, value, writeBlocked]);
}

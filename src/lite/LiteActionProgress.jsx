import React, { useEffect, useMemo, useRef, useState } from 'react';
import { CheckCircle2, PauseCircle, AlertTriangle } from 'lucide-react';

const DEFAULT_STAGES = ['Getting ready', 'Working', 'Evidence saved'];

const ACTION_STAGE_COPY = {
  check_app: ['Getting ready', 'Route', 'Health', 'Storage', 'Safety', 'Logs created', 'Done'],
  backup_app: ['Getting ready', 'Saving app settings', 'Evidence saved'],
  preview_restore: ['Getting ready', 'Preparing preview', 'Evidence saved'],
  repair_app: ['Getting ready', 'Safe repair', 'Evidence saved'],
  update_app: ['Getting ready', 'Checking readiness', 'Evidence saved'],
  import_photos: ['Getting ready', 'Importing photos', 'Evidence saved'],
  connect_photos: ['Getting ready', 'Connecting photos', 'Ready'],
  phone_storage: ['Getting ready', 'Connecting photos', 'Ready'],
  storage_device: ['Getting ready', 'Connecting photos', 'Ready'],
};

const ACTION_WORKING_COPY = {
  check_app: 'Checking PhotoPrism safely',
  backup_app: 'Saving app settings',
  preview_restore: 'Preparing restore preview',
  repair_app: 'Checking what needs repair',
  update_app: 'Checking readiness only',
  import_photos: 'Importing photos',
  connect_photos: 'Connecting photos',
  phone_storage: 'Connecting photos',
  storage_device: 'Connecting photos',
};

const ACTION_COMPLETE_COPY = {
  check_app: 'Protected app',
  backup_app: 'App backup saved',
  preview_restore: 'Restore preview ready. No changes made.',
  repair_app: 'Nothing needed repair',
  update_app: 'Update readiness checked. No update was applied.',
  import_photos: 'Import completed. PhotoPrism will handle indexing.',
  connect_photos: 'Photos connected',
  phone_storage: 'Photos connected',
  storage_device: 'Photos connected',
};

const ACTION_WORKFLOW_KIND = {
  check_app: 'shield',
  backup_app: 'backup',
  preview_restore: 'preview',
  repair_app: 'repair',
  update_app: 'readiness',
  import_photos: 'media',
  connect_photos: 'media',
  phone_storage: 'media',
  storage_device: 'media',
};

function normalizedStatus(value) {
  return String(value || '').toLowerCase().replace(/[\s-]+/g, '_');
}

function terminalProgressPhase(progress) {
  return ['completed', 'complete', 'done', 'succeeded', 'success', 'verified'].includes(normalizedStatus(progress?.phase));
}

function hasRunEvidence({ progress, result, lastRanAt, firstRanAt, lastResult, troubleshooting, evidenceRef, receiptId }) {
  const resultStatus = normalizedStatus(result?.status);
  return Boolean(
    firstRanAt
    || lastRanAt
    || lastResult
    || evidenceRef
    || receiptId
    || troubleshooting?.available
    || terminalProgressPhase(progress)
    || (['succeeded', 'success', 'done', 'completed', 'verified'].includes(resultStatus) && result?.summary)
  );
}

function normalizeProgressState({
  status,
  enabled,
  disabledReason,
  progress,
  result,
  lastRanAt,
  firstRanAt,
  lastResult,
  troubleshooting,
  evidenceRef,
  receiptId,
}) {
  const raw = normalizedStatus(progress?.phase || status || result?.status);
  if (enabled === false || disabledReason) return 'blocked';
  if (progress?.running || ['queued', 'pending'].includes(raw)) return 'queued';
  if (['running', 'working', 'executing', 'waiting'].includes(raw)) return raw === 'waiting' ? 'waiting' : 'running';
  if (['review', 'degraded', 'warning', 'needs_attention'].includes(raw)) return 'review';
  if (['failed', 'failure', 'error'].includes(raw)) return 'failed';
  if (hasRunEvidence({ progress, result, lastRanAt, firstRanAt, lastResult, troubleshooting, evidenceRef, receiptId })) return 'evidence_saved';
  return 'idle';
}

function progressPercentForState(state, progress) {
  const rawPercent = Number(progress?.percent);
  if (Number.isFinite(rawPercent) && rawPercent > 0 && state !== 'idle') {
    return Math.min(100, Math.max(0, rawPercent));
  }
  if (state === 'queued') return 22;
  if (state === 'running' || state === 'waiting') return 58;
  if (state === 'evidence_saved') return 100;
  if (state === 'review' || state === 'failed') return 100;
  if (state === 'blocked') return 34;
  return 0;
}

function currentLabelForState({ actionId, state, progress, disabledReason, result, lastResult }) {
  if (state === 'blocked') return disabledReason || 'Paused for safety';
  if (state === 'queued') return 'Getting ready';
  if (state === 'running' || state === 'waiting') return ACTION_WORKING_COPY[actionId] || progress?.step || 'Working';
  if (state === 'evidence_saved' && actionId === 'check_app') return 'Done';
  if (state === 'evidence_saved') return lastResult || result?.summary || ACTION_COMPLETE_COPY[actionId] || 'Evidence saved';
  if (state === 'review') return result?.summary || 'Needs review';
  if (state === 'failed') return result?.summary || 'Needs review';
  return 'Not run yet';
}

function activeStageForState(state, stageCount = 3) {
  if (state === 'queued') return 0;
  if (state === 'running' || state === 'waiting') return Math.min(1, stageCount - 1);
  if (state === 'evidence_saved' || state === 'review' || state === 'failed') return Math.max(0, stageCount - 1);
  if (state === 'blocked') return 0;
  return -1;
}

function checkAppProgressPercentForState(state, progress) {
  const rawPercent = Number(progress?.percent);
  if (Number.isFinite(rawPercent) && rawPercent > 0 && state !== 'idle') {
    return Math.min(100, Math.max(0, rawPercent));
  }
  if (state === 'queued') return 14;
  if (state === 'running' || state === 'waiting') return 68;
  if (state === 'evidence_saved' || state === 'review' || state === 'failed') return 100;
  if (state === 'blocked') return 14;
  return 0;
}

function checkAppStageIndex({ state, progress, stageCount }) {
  if (state === 'idle') return -1;
  if (state === 'queued' || state === 'blocked') return 0;
  if (state === 'evidence_saved' || state === 'review' || state === 'failed') return Math.max(0, stageCount - 1);
  const step = normalizedStatus(progress?.step || progress?.label || progress?.phase);
  if (step.includes('route')) return 1;
  if (step.includes('health')) return 2;
  if (step.includes('storage')) return 3;
  if (step.includes('safety') || step.includes('protect')) return 4;
  if (step.includes('log') || step.includes('evidence') || step.includes('troubleshoot')) return 5;
  const percent = checkAppProgressPercentForState(state, progress);
  if (percent >= 92) return 5;
  if (percent >= 74) return 4;
  if (percent >= 56) return 3;
  if (percent >= 38) return 2;
  if (percent >= 18) return 1;
  return 0;
}


function checkAppSegmentCount() {
  return ACTION_STAGE_COPY.check_app.length;
}

function isCheckAppRunningState(state) {
  return ['queued', 'running', 'waiting'].includes(state);
}

function nextCheckAppVisualStep(current, target, maxIndex) {
  const safeCurrent = Number.isFinite(current) ? current : 0;
  const safeTarget = Math.max(0, Math.min(maxIndex, Number.isFinite(target) ? target : 0));
  if (safeCurrent < safeTarget) return safeCurrent + 1;
  if (safeCurrent > safeTarget) return safeCurrent - 1;
  if (safeCurrent < Math.max(0, maxIndex - 1)) return safeCurrent + 1;
  return safeCurrent;
}

function checkAppBlockState({ state, index, visualStep, stageCount }) {
  const complete = state === 'evidence_saved';
  const attention = ['review', 'failed', 'blocked'].includes(state);
  if (complete || visualStep > index) return attention ? 'attention-done' : 'done';
  if (state !== 'idle' && visualStep === index) return attention ? 'attention-leading' : 'leading';
  if (attention && index <= Math.max(0, stageCount - 1)) return 'attention-empty';
  return 'empty';
}

function formatActionRunTime(value) {
  if (!value) return '';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '';
  const now = new Date();
  const sameDay = parsed.getFullYear() === now.getFullYear()
    && parsed.getMonth() === now.getMonth()
    && parsed.getDate() === now.getDate();
  try {
    const time = new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit' }).format(parsed);
    if (sameDay) return `Today, ${time}`;
    return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(parsed);
  } catch (_error) {
    return String(value);
  }
}

function runMetaLabel({ state, lastRanAt, executionOwner, hasEvidence }) {
  const lastRun = formatActionRunTime(lastRanAt);
  if (lastRun) return `Last run: ${lastRun}`;
  if (state === 'idle' && executionOwner === 'browser_navigation') return 'No backend run needed';
  if (state === 'idle') return 'Not run yet';
  if (hasEvidence) return 'Last run: recorded';
  return '';
}

export default function LiteActionProgress({
  actionId,
  status,
  enabled = true,
  disabledReason = '',
  progress = null,
  result = null,
  detailsAvailable = false,
  lastResult = '',
  firstRanAt = '',
  lastRanAt = '',
  runCount = 0,
  troubleshooting = null,
  evidenceRef = '',
  receiptId = '',
  executionOwner = '',
  className = '',
}) {
  const state = useMemo(() => normalizeProgressState({
    status,
    enabled,
    disabledReason,
    progress,
    result,
    lastRanAt,
    firstRanAt,
    lastResult,
    troubleshooting,
    evidenceRef,
    receiptId,
  }), [status, enabled, disabledReason, progress, result, lastRanAt, firstRanAt, lastResult, troubleshooting, evidenceRef, receiptId]);
  const stages = ACTION_STAGE_COPY[actionId] || DEFAULT_STAGES;
  const workflowKind = ACTION_WORKFLOW_KIND[actionId] || 'default';
  const isCheckApp = actionId === 'check_app';
  const percent = isCheckApp ? checkAppProgressPercentForState(state, progress) : progressPercentForState(state, progress);
  const activeStage = isCheckApp ? checkAppStageIndex({ state, progress, stageCount: stages.length }) : activeStageForState(state, stages.length);
  const [checkVisualStep, setCheckVisualStep] = useState(() => Math.max(0, Math.min(stages.length - 1, activeStage)));
  const lastCheckRunRef = useRef('');

  useEffect(() => {
    if (!isCheckApp) return undefined;
    const stageMax = Math.max(0, checkAppSegmentCount() - 1);
    const runKey = `${progress?.command_id || progress?.run_id || progress?.phase || ''}:${lastRanAt || ''}:${firstRanAt || ''}`;
    if (runKey && runKey !== lastCheckRunRef.current && isCheckAppRunningState(state)) {
      lastCheckRunRef.current = runKey;
      setCheckVisualStep(0);
    }
    if (state === 'idle') {
      setCheckVisualStep(-1);
      return undefined;
    }
    if (state === 'evidence_saved') {
      setCheckVisualStep(stageMax);
      return undefined;
    }
    if (['review', 'failed', 'blocked'].includes(state)) {
      setCheckVisualStep(Math.max(0, Math.min(stageMax, activeStage)));
      return undefined;
    }
    const target = Math.max(0, Math.min(stageMax - 1, activeStage >= 0 ? activeStage : 0));
    setCheckVisualStep((current) => {
      if (current < 0) return 0;
      return Math.min(stageMax - 1, current);
    });
    const timer = window.setInterval(() => {
      setCheckVisualStep((current) => nextCheckAppVisualStep(current, target, stageMax));
    }, 420);
    return () => window.clearInterval(timer);
  }, [isCheckApp, state, activeStage, progress?.command_id, progress?.run_id, progress?.phase, lastRanAt, firstRanAt]);

  const effectiveCheckStage = isCheckApp ? Math.max(-1, checkVisualStep) : activeStage;
  const visibleStages = isCheckApp && state === 'evidence_saved' ? ['Done'] : stages;
  const label = currentLabelForState({ actionId, state, progress, disabledReason, result, lastResult });
  const hasEvidence = hasRunEvidence({ progress, result, lastRanAt, firstRanAt, lastResult, troubleshooting, evidenceRef, receiptId });
  const metaLabel = runMetaLabel({ state, lastRanAt, executionOwner, hasEvidence });
  const icon = state === 'blocked'
    ? <PauseCircle className="h-4 w-4" />
    : ['review', 'failed'].includes(state)
      ? <AlertTriangle className="h-4 w-4" />
      : state === 'evidence_saved'
        ? <CheckCircle2 className="h-4 w-4" />
        : null;

  return (
    <div
      className={`lite-action-progress lite-action-progress--${state} lite-action-progress--${workflowKind} ${isCheckApp ? 'lite-action-progress--stepped lite-action-progress--check-app' : ''} ${isCheckApp && state === 'evidence_saved' ? 'lite-action-progress--check-complete' : ''} ${className}`.trim()}
      data-action-id={actionId}
      data-run-count={Number(runCount) || 0}
    >
      <div className="lite-action-progress__label">
        <span>{icon}{label}</span>
        {state === 'evidence_saved' && detailsAvailable ? <small>Evidence saved</small> : null}
      </div>
      <div
        className="lite-action-progress__track"
        role="progressbar"
        aria-label={`${stages.join(' to ')} progress`}
        aria-valuemin="0"
        aria-valuemax="100"
        aria-valuenow={Math.round(percent)}
        style={{ '--lite-action-progress-percent': `${percent}%` }}
      >
        <span className="lite-action-progress__fill" />
        <span className="lite-action-progress__head" aria-hidden="true" />
        {isCheckApp ? (
          <span className="lite-action-progress__segments" aria-hidden="true" data-visual-step={effectiveCheckStage}>
            {stages.map((stage, index) => {
              const blockState = checkAppBlockState({ state, index, visualStep: effectiveCheckStage, stageCount: stages.length });
              const done = blockState === 'done' || blockState === 'attention-done';
              const leading = blockState === 'leading' || blockState === 'attention-leading';
              const attention = blockState.startsWith('attention');
              return (
                <i
                  key={stage}
                  className={`lite-action-progress__segment ${done ? 'is-done' : ''} ${leading ? 'is-leading' : ''} ${attention ? 'is-attention' : ''}`}
                  data-step-label={stage}
                />
              );
            })}
          </span>
        ) : null}
      </div>
      <div className="lite-action-progress__nodes" aria-hidden="true">
        {visibleStages.map((stage, index) => {
          const actualIndex = isCheckApp && state === 'evidence_saved' ? stages.length - 1 : index;
          const done = effectiveCheckStage > actualIndex || state === 'evidence_saved';
          const active = effectiveCheckStage === actualIndex && state !== 'idle';
          return (
            <span key={stage} className={`lite-action-progress__node ${done ? 'is-done' : ''} ${active ? 'is-active' : ''}`}>
              <i>{isCheckApp && state === 'evidence_saved' && stage === 'Done' ? '✓' : ''}</i>
              <b className="lite-action-progress__stage">{stage}</b>
            </span>
          );
        })}
      </div>
      {metaLabel ? <p className="lite-action-progress__meta">{metaLabel}</p> : null}
      {state === 'blocked' && disabledReason ? <p className="lite-action-progress__reason">{disabledReason}</p> : null}
    </div>
  );
}

export { DEFAULT_STAGES, ACTION_STAGE_COPY, ACTION_WORKFLOW_KIND, hasRunEvidence };

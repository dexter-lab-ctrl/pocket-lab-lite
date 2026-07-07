import React, { useMemo } from 'react';
import { CheckCircle2, PauseCircle, AlertTriangle } from 'lucide-react';

const DEFAULT_STAGES = ['Request accepted', 'Working', 'Done'];

const ACTION_STAGE_COPY = {
  check_app: ['Request accepted', 'Working', 'Route checked', 'Health checked', 'Done'],
  backup_app: ['Request accepted', 'Working', 'Saving app records', 'Verifying backup', 'Done'],
  preview_restore: ['Request accepted', 'Working', 'Backup checked', 'Preview prepared', 'No changes made', 'Done'],
  repair_app: ['Request accepted', 'Working', 'Route checked', 'Health checked', 'Done'],
  update_app: ['Request accepted', 'Working', 'Checking current app', 'Backup checked', 'Restore preview checked', 'Done'],
  import_photos: ['Request accepted', 'Working', 'Phone folders checked', 'Importing photos', 'Done'],
  connect_photos: ['Request accepted', 'Working', 'Phone folders checked', 'Access checked', 'Done'],
  phone_storage: ['Request accepted', 'Working', 'Phone folders checked', 'Access checked', 'Done'],
  storage_device: ['Request accepted', 'Working', 'Storage node checked', 'Target checked', 'Done'],
};

const ACTION_WORKING_COPY = {
  check_app: 'Checking PhotoPrism',
  backup_app: 'Saving app records',
  preview_restore: 'Preparing restore preview',
  repair_app: 'Checking repair options',
  update_app: 'Checking update readiness',
  import_photos: 'Importing photos',
  connect_photos: 'Connecting photos',
  phone_storage: 'Connecting photos',
  storage_device: 'Connecting storage',
};

const ACTION_COMPLETE_COPY = {
  check_app: 'Protected app',
  backup_app: 'App backup saved',
  preview_restore: 'Preview ready. No changes made.',
  repair_app: 'Repair details saved',
  update_app: 'Readiness saved. No update was applied.',
  import_photos: 'Import completed. PhotoPrism will handle indexing.',
  connect_photos: 'Photos connected',
  phone_storage: 'Photos connected',
  storage_device: 'Storage connected',
};

const ACTION_WORKFLOW_KIND = {
  check_app: 'signal',
  backup_app: 'vault',
  preview_restore: 'preview',
  repair_app: 'signal',
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
  if (['saved_state', 'saved', 'cached', 'stale', 'expired', 'offline_saved'].includes(raw)) return 'saved_state';
  if (['queued', 'pending', 'accepted'].includes(raw)) return 'queued';
  if (progress?.running || ['running', 'working', 'executing', 'waiting', 'in_progress'].includes(raw)) return raw === 'waiting' ? 'waiting' : 'running';
  if (['review', 'degraded', 'warning', 'needs_attention'].includes(raw)) return 'review';
  if (['failed', 'failure', 'error'].includes(raw)) return 'failed';
  if (hasRunEvidence({ progress, result, lastRanAt, firstRanAt, lastResult, troubleshooting, evidenceRef, receiptId })) return 'evidence_saved';
  return 'idle';
}

function normalizeBackendStepStatus(value) {
  const status = normalizedStatus(value);
  if (['complete', 'completed', 'done', 'success', 'succeeded', 'verified', 'passed', 'saved'].includes(status)) return 'completed';
  if (['active', 'current', 'running', 'working', 'in_progress', 'executing'].includes(status)) return 'active';
  if (['failed', 'failure', 'error'].includes(status)) return 'failed';
  if (['blocked', 'paused', 'cancelled', 'canceled'].includes(status)) return 'blocked';
  if (['waiting', 'pending', 'queued', 'ready', 'idle', 'not_started'].includes(status)) return 'pending';
  return status || 'pending';
}

function normalizeBackendStep(step, index) {
  if (!step || typeof step !== 'object') return null;
  const label = String(step.label || step.title || step.name || step.step || step.id || '').trim();
  if (!label) return null;
  return {
    id: String(step.id || step.key || step.name || `step-${index}`).trim() || `step-${index}`,
    label,
    status: normalizeBackendStepStatus(step.status || step.state || step.phase),
  };
}

function backendProgressSteps(progress) {
  const source = Array.isArray(progress?.steps) && progress.steps.length
    ? progress.steps
    : Array.isArray(progress?.timeline) && progress.timeline.length
      ? progress.timeline
      : [];
  return source
    .map((step, index) => normalizeBackendStep(step, index))
    .filter(Boolean)
    .slice(0, 8);
}

function fallbackProgressSteps({ actionId, state, progress, disabledReason }) {
  if (state === 'idle') return (ACTION_STAGE_COPY[actionId] || DEFAULT_STAGES).map((label, index) => ({
    id: `idle-${index}`,
    label,
    status: 'pending',
  }));
  if (state === 'blocked') return [{ id: 'blocked', label: disabledReason || 'Paused for safety', status: 'blocked' }];
  if (state === 'saved_state') return [{ id: 'saved-state', label: 'Showing saved state', status: 'blocked' }];
  if (state === 'failed') return [{ id: 'failed', label: progress?.step || 'Could not complete', status: 'failed' }];
  if (state === 'review') return [{ id: 'review', label: progress?.step || 'Needs attention', status: 'failed' }];
  if (state === 'evidence_saved') return [{ id: 'done', label: 'Done', status: 'completed' }];
  if (state === 'queued') return [{ id: 'accepted', label: 'Request accepted', status: 'active' }];
  if (state === 'running' || state === 'waiting') return [{ id: 'working', label: progress?.step || ACTION_WORKING_COPY[actionId] || 'Working', status: 'active' }];
  return [{ id: 'ready', label: 'Ready', status: 'pending' }];
}

function progressStepsForAction({ actionId, state, progress, disabledReason }) {
  const backendSteps = backendProgressSteps(progress);
  if (backendSteps.length) return backendSteps;
  return fallbackProgressSteps({ actionId, state, progress, disabledReason });
}

function activeStageForSteps(steps) {
  const activeIndex = steps.findIndex((step) => step.status === 'active');
  if (activeIndex >= 0) return activeIndex;
  const failedIndex = steps.findIndex((step) => step.status === 'failed' || step.status === 'blocked');
  if (failedIndex >= 0) return failedIndex;
  const completedIndexes = steps
    .map((step, index) => (step.status === 'completed' ? index : -1))
    .filter((index) => index >= 0);
  if (!completedIndexes.length) return -1;
  return Math.max(...completedIndexes);
}

function progressPercentForSteps({ state, steps }) {
  if (!steps.length || state === 'idle') return 0;
  if (state === 'blocked' || state === 'saved_state') return 0;
  if (steps.every((step) => step.status === 'completed')) return 100;
  const completed = steps.filter((step) => step.status === 'completed').length;
  return Math.round((completed / steps.length) * 100);
}

function currentLabelForState({ actionId, state, progress, disabledReason, result, lastResult, steps }) {
  const activeStep = steps.find((step) => step.status === 'active');
  const lastCompleted = [...steps].reverse().find((step) => step.status === 'completed');
  if (state === 'blocked') return disabledReason || 'Paused for safety';
  if (state === 'saved_state') return 'Showing saved state';
  if (state === 'queued') return activeStep?.label || 'Request accepted';
  if (state === 'running' || state === 'waiting') return activeStep?.label || progress?.summary || ACTION_WORKING_COPY[actionId] || progress?.step || 'Working';
  if (state === 'evidence_saved') return lastResult || result?.summary || ACTION_COMPLETE_COPY[actionId] || lastCompleted?.label || 'Done';
  if (state === 'review') return result?.summary || 'Needs review';
  if (state === 'failed') return result?.summary || 'Could not complete';
  return 'Not run yet';
}

function statusChipForState({ actionId, state, steps }) {
  if (state === 'queued') return 'Queued';
  if (state === 'running' || state === 'waiting') return steps.find((step) => step.status === 'active')?.label || (actionId === 'update_app' ? 'Checking readiness' : 'Working');
  if (state === 'evidence_saved') {
    if (actionId === 'check_app') return 'Protected app';
    if (actionId === 'backup_app') return 'Saved';
    if (actionId === 'preview_restore') return 'Preview ready';
    if (actionId === 'update_app') return 'Readiness saved';
    return 'Done';
  }
  if (state === 'review') return 'Needs review';
  if (state === 'failed') return 'Could not complete';
  if (state === 'blocked') return 'Paused';
  if (state === 'saved_state') return 'Saved state';
  return 'Ready';
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

function runMetaLabel({ state, actionId, lastRanAt, executionOwner, hasEvidence }) {
  const lastRun = formatActionRunTime(lastRanAt);
  if (lastRun) return `Last run: ${lastRun}`;
  if (state === 'idle' && executionOwner === 'browser_navigation') return 'No backend run needed';
  if (state === 'idle') return 'Not run yet';
  if (state === 'saved_state') return 'Reconnect to continue';
  if (hasEvidence) {
    if (actionId === 'update_app') return 'No update was applied';
    if (actionId === 'preview_restore') return 'No changes made';
    return 'Details saved';
  }
  return '';
}

function nodeState({ state, step }) {
  if (state === 'idle') return 'empty';
  if (step.status === 'completed') return 'done';
  if (step.status === 'active') return 'active';
  if (step.status === 'failed') return 'attention';
  if (step.status === 'blocked') return 'paused';
  return 'empty';
}

function nodeSymbol({ kind, actionId, state, step, index, finalIndex }) {
  if (step.status === 'completed' && (state === 'evidence_saved' || index === finalIndex)) return '✓';
  if (step.status === 'failed') return '!';
  if (step.status === 'blocked') return 'Ⅱ';
  if (kind === 'vault') return index === finalIndex ? '✓' : '▣';
  if (kind === 'preview') return index === finalIndex ? '✓' : '◇';
  if (kind === 'readiness') return index === finalIndex ? '✓' : '▭';
  if (kind === 'media') return index === finalIndex ? '✓' : '●';
  if (actionId === 'check_app') return index === finalIndex ? '✓' : '●';
  return index === finalIndex ? '✓' : '●';
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

  const steps = useMemo(() => progressStepsForAction({ actionId, state, progress, disabledReason }), [actionId, state, progress, disabledReason]);
  const workflowKind = ACTION_WORKFLOW_KIND[actionId] || 'signal';
  const activeStage = activeStageForSteps(steps);
  const percent = progressPercentForSteps({ state, steps });
  const label = currentLabelForState({ actionId, state, progress, disabledReason, result, lastResult, steps });
  const chip = statusChipForState({ actionId, state, steps });
  const finalIndex = steps.length - 1;
  const hasEvidence = hasRunEvidence({ progress, result, lastRanAt, firstRanAt, lastResult, troubleshooting, evidenceRef, receiptId });
  const metaLabel = runMetaLabel({ state, actionId, lastRanAt, executionOwner, hasEvidence });
  const actionNote = actionId === 'update_app' && state === 'evidence_saved'
    ? 'No update was applied.'
    : actionId === 'preview_restore' && state === 'evidence_saved'
      ? 'No changes were made.'
      : state === 'evidence_saved' && detailsAvailable
        ? 'Done ✓'
        : state === 'evidence_saved'
          ? 'Done ✓'
          : '';

  const icon = state === 'blocked' || state === 'saved_state'
    ? <PauseCircle className="h-4 w-4" />
    : ['review', 'failed'].includes(state)
      ? <AlertTriangle className="h-4 w-4" />
      : state === 'evidence_saved'
        ? <CheckCircle2 className="h-4 w-4" />
        : null;

  return (
    <div
      className={`lite-action-progress lite-action-progress--${state} lite-action-progress--${workflowKind} ${className}`.trim()}
      data-action-id={actionId}
      data-run-count={Number(runCount) || 0}
      style={{
        '--lite-action-progress-percent': `${percent}%`,
        '--lite-action-progress-steps': steps.length,
        '--lite-action-progress-active-step': Math.max(0, activeStage),
      }}
    >
      <div className="lite-action-progress__topline">
        <div className="lite-action-progress__label">
          <span className="lite-action-progress__state-icon" aria-hidden="true">{icon}</span>
          <span>{label}</span>
        </div>
        <span className="lite-action-progress__chip">{chip}</span>
      </div>

      <div
        className="lite-action-progress__rail"
        role="progressbar"
        aria-label={`${steps.map((step) => step.label).join(' to ')} progress`}
        aria-valuemin="0"
        aria-valuemax="100"
        aria-valuenow={Math.round(percent)}
      >
        <span className="lite-action-progress__rail-base" aria-hidden="true" />
        <span className="lite-action-progress__rail-fill" aria-hidden="true" />
        <span className="lite-action-progress__rail-pulse" aria-hidden="true" />
        <span className="lite-action-progress__nodes" aria-hidden="true">
          {steps.map((step, index) => {
            const visualState = nodeState({ state, step });
            const active = visualState === 'active';
            const done = visualState === 'done';
            const attention = visualState === 'attention';
            const paused = visualState === 'paused';
            return (
              <span
                key={`${step.id}-${step.label}-${index}`}
                className={`lite-action-progress__node lite-action-progress__node--${visualState} ${active ? 'is-active' : ''} ${done ? 'is-done' : ''} ${attention ? 'is-attention' : ''} ${paused ? 'is-paused' : ''}`}
              >
                <i>{nodeSymbol({ kind: workflowKind, actionId, state, step, index, finalIndex })}</i>
              </span>
            );
          })}
        </span>
      </div>

      <div className="lite-action-progress__stages">
        {steps.map((step, index) => {
          const visualState = nodeState({ state, step });
          return (
            <span key={`${step.id}-${index}`} className={`lite-action-progress__stage lite-action-progress__stage--${visualState}`}>
              {step.label}
            </span>
          );
        })}
      </div>

      {actionNote ? <p className="lite-action-progress__note">{actionNote}</p> : null}
      {metaLabel ? <p className="lite-action-progress__meta">{metaLabel}</p> : null}
      {state === 'blocked' && disabledReason ? <p className="lite-action-progress__reason">{disabledReason}</p> : null}
    </div>
  );
}

export {
  DEFAULT_STAGES,
  ACTION_STAGE_COPY,
  ACTION_WORKFLOW_KIND,
  backendProgressSteps,
  hasRunEvidence,
  normalizeBackendStepStatus,
};

import React, { useMemo } from 'react';
import { CheckCircle2, PauseCircle, AlertTriangle } from 'lucide-react';

const DEFAULT_STAGES = ['Getting ready', 'Working', 'Evidence saved'];

const ACTION_STAGE_COPY = {
  check_app: ['Getting ready', 'Checking app', 'Evidence saved'],
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
  if (state === 'evidence_saved') return lastResult || result?.summary || ACTION_COMPLETE_COPY[actionId] || 'Evidence saved';
  if (state === 'review') return result?.summary || 'Needs review';
  if (state === 'failed') return result?.summary || 'Needs review';
  return 'Not run yet';
}

function activeStageForState(state) {
  if (state === 'queued') return 0;
  if (state === 'running' || state === 'waiting') return 1;
  if (state === 'evidence_saved' || state === 'review' || state === 'failed') return 2;
  if (state === 'blocked') return 0;
  return -1;
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
  const activeStage = activeStageForState(state);
  const percent = progressPercentForState(state, progress);
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
      className={`lite-action-progress lite-action-progress--${state} lite-action-progress--${workflowKind} ${className}`.trim()}
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
      >
        <span className="lite-action-progress__fill" style={{ width: `${percent}%` }} />
        <span className="lite-action-progress__packet" aria-hidden="true" />
        <span className="lite-action-progress__stamp" aria-hidden="true"><CheckCircle2 className="h-3.5 w-3.5" /></span>
      </div>
      <div className="lite-action-progress__nodes" aria-hidden="true">
        {stages.map((stage, index) => {
          const done = activeStage > index || state === 'evidence_saved';
          const active = activeStage === index && state !== 'idle';
          return (
            <span key={stage} className={`lite-action-progress__node ${done ? 'is-done' : ''} ${active ? 'is-active' : ''}`}>
              <i />
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

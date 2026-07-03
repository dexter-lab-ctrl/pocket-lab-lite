import React, { useMemo } from 'react';
import { CheckCircle2, PauseCircle, AlertTriangle } from 'lucide-react';

const DEFAULT_STAGES = ['Getting ready', 'Working', 'Saved for troubleshooting'];

const ACTION_STAGE_COPY = {
  check_app: ['Getting ready', 'Checking safely', 'Saved for troubleshooting'],
  backup_app: ['Getting ready', 'Saving app settings', 'Saved for troubleshooting'],
  preview_restore: ['Getting ready', 'Preparing preview', 'Saved for troubleshooting'],
  repair_app: ['Getting ready', 'Checking repair', 'Saved for troubleshooting'],
  update_app: ['Getting ready', 'Checking readiness', 'Saved for troubleshooting'],
  import_photos: ['Getting ready', 'Importing safely', 'Saved for troubleshooting'],
  connect_photos: ['Getting ready', 'Connecting photos', 'Ready'],
  phone_storage: ['Getting ready', 'Connecting photos', 'Ready'],
  storage_device: ['Getting ready', 'Connecting photos', 'Ready'],
};

const ACTION_WORKING_COPY = {
  check_app: 'Checking safely',
  backup_app: 'Saving app settings',
  preview_restore: 'Preparing restore preview',
  repair_app: 'Checking repair',
  update_app: 'Checking update readiness',
  import_photos: 'Importing photos',
  connect_photos: 'Connecting photos',
  phone_storage: 'Connecting photos',
  storage_device: 'Connecting photos',
};

const ACTION_COMPLETE_COPY = {
  check_app: 'Saved for troubleshooting',
  backup_app: 'App backup saved',
  preview_restore: 'Restore preview ready. No changes made.',
  repair_app: 'Repair completed. No photos changed.',
  update_app: 'Update readiness checked. No update was applied.',
  import_photos: 'Saved for troubleshooting. PhotoPrism will handle indexing.',
  connect_photos: 'Photos connected',
  phone_storage: 'Photos connected',
  storage_device: 'Photos connected',
};

function normalizeProgressState({ status, enabled, disabledReason, progress, result, detailsAvailable }) {
  const raw = String(status || progress?.phase || result?.status || '').toLowerCase().replace(/[\s-]+/g, '_');
  if (enabled === false || disabledReason) return 'blocked';
  if (progress?.running || ['queued', 'pending'].includes(raw)) return 'queued';
  if (['running', 'working', 'executing', 'waiting'].includes(raw)) return raw === 'waiting' ? 'waiting' : 'running';
  if (['review', 'degraded', 'warning', 'needs_attention'].includes(raw)) return 'review';
  if (['failed', 'failure', 'error'].includes(raw)) return 'failed';
  if (detailsAvailable || ['succeeded', 'success', 'done', 'completed', 'verified'].includes(raw)) return 'saved_for_troubleshooting';
  return 'idle';
}

function progressPercentForState(state, progress) {
  const rawPercent = Number(progress?.percent);
  if (Number.isFinite(rawPercent) && rawPercent > 0) {
    return Math.min(100, Math.max(0, rawPercent));
  }
  if (state === 'queued') return 22;
  if (state === 'running' || state === 'waiting') return 58;
  if (state === 'saved_for_troubleshooting') return 100;
  if (state === 'review' || state === 'failed') return 100;
  if (state === 'blocked') return 34;
  return 0;
}

function currentLabelForState({ actionId, state, progress, disabledReason, result, detailsAvailable }) {
  if (state === 'blocked') return disabledReason || 'Paused for safety';
  if (state === 'queued') return 'Getting ready';
  if (state === 'running' || state === 'waiting') return ACTION_WORKING_COPY[actionId] || progress?.step || 'Working';
  if (state === 'saved_for_troubleshooting') return ACTION_COMPLETE_COPY[actionId] || (detailsAvailable ? 'Saved for troubleshooting' : 'Done');
  if (state === 'review') return 'Needs review';
  if (state === 'failed') return 'Needs review';
  if (result?.summary) return result.summary;
  return 'Not checked yet';
}

function activeStageForState(state) {
  if (state === 'queued') return 0;
  if (state === 'running' || state === 'waiting') return 1;
  if (state === 'saved_for_troubleshooting' || state === 'review' || state === 'failed') return 2;
  if (state === 'blocked') return 0;
  return -1;
}

export default function LiteActionProgress({
  actionId,
  status,
  enabled = true,
  disabledReason = '',
  progress = null,
  result = null,
  detailsAvailable = false,
  className = '',
}) {
  const state = useMemo(() => normalizeProgressState({ status, enabled, disabledReason, progress, result, detailsAvailable }), [status, enabled, disabledReason, progress, result, detailsAvailable]);
  const stages = ACTION_STAGE_COPY[actionId] || DEFAULT_STAGES;
  const activeStage = activeStageForState(state);
  const percent = progressPercentForState(state, progress);
  const label = currentLabelForState({ actionId, state, progress, disabledReason, result, detailsAvailable });
  const icon = state === 'blocked'
    ? <PauseCircle className="h-4 w-4" />
    : ['review', 'failed'].includes(state)
      ? <AlertTriangle className="h-4 w-4" />
      : state === 'saved_for_troubleshooting'
        ? <CheckCircle2 className="h-4 w-4" />
        : null;

  return (
    <div className={`lite-action-progress lite-action-progress--${state} ${className}`.trim()} data-action-id={actionId}>
      <div className="lite-action-progress__label">
        <span>{icon}{label}</span>
        {state === 'saved_for_troubleshooting' && detailsAvailable ? <small>Saved for troubleshooting</small> : null}
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
      </div>
      <div className="lite-action-progress__nodes" aria-hidden="true">
        {stages.map((stage, index) => {
          const done = activeStage > index || state === 'saved_for_troubleshooting';
          const active = activeStage === index && state !== 'idle';
          return (
            <span key={stage} className={`lite-action-progress__node ${done ? 'is-done' : ''} ${active ? 'is-active' : ''}`}>
              <i />
              <b className="lite-action-progress__stage">{stage}</b>
            </span>
          );
        })}
      </div>
      {state === 'blocked' && disabledReason ? <p className="lite-action-progress__reason">{disabledReason}</p> : null}
    </div>
  );
}

export { DEFAULT_STAGES, ACTION_STAGE_COPY };

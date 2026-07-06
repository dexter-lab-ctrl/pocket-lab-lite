import React, { useEffect, useMemo, useState } from 'react';
import { CheckCircle2, PauseCircle, AlertTriangle } from 'lucide-react';

const DEFAULT_STAGES = ['Request accepted', 'Working', 'Details saved'];

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

const ACTION_STAGE_ALIASES = {
  check_app: [
    ['request', 'accepted', 'queued', 'getting_ready'],
    ['worker', 'working', 'picked', 'claim'],
    ['route', 'caddy', 'open'],
    ['health', 'status', 'ready'],
    ['detail', 'saved', 'evidence', 'troubleshoot', 'done'],
  ],
  backup_app: [
    ['request', 'accepted', 'queued', 'getting_ready'],
    ['worker', 'working', 'picked', 'claim'],
    ['saving', 'record', 'setting', 'config', 'metadata'],
    ['verify', 'verified', 'backup'],
    ['detail', 'saved', 'evidence', 'troubleshoot', 'done'],
  ],
  preview_restore: [
    ['request', 'accepted', 'queued', 'getting_ready'],
    ['worker', 'working', 'picked', 'claim'],
    ['backup', 'snapshot'],
    ['preview', 'compare', 'plan'],
    ['no_change', 'no_changes', 'read_only'],
    ['detail', 'saved', 'evidence', 'troubleshoot', 'done'],
  ],
  update_app: [
    ['request', 'accepted', 'queued', 'getting_ready'],
    ['worker', 'working', 'picked', 'claim'],
    ['current', 'version', 'installed'],
    ['backup', 'rollback'],
    ['restore', 'preview', 'safety'],
    ['readiness', 'saved', 'no_update', 'done'],
  ],
  import_photos: [
    ['request', 'accepted', 'queued', 'getting_ready'],
    ['worker', 'working', 'picked', 'claim'],
    ['phone', 'folder', 'storage'],
    ['import', 'media', 'photo'],
    ['detail', 'saved', 'evidence', 'troubleshoot', 'done'],
  ],
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

function percentFromProgress(progress) {
  const rawPercent = Number(progress?.percent);
  if (Number.isFinite(rawPercent) && rawPercent > 0) return Math.min(100, Math.max(0, rawPercent));
  return null;
}

function stageIndexFromBackend({ actionId, progress, stages }) {
  const rawStep = normalizedStatus(progress?.step || progress?.label || progress?.stage || progress?.phase || progress?.summary);
  if (!rawStep) return -1;

  const aliases = ACTION_STAGE_ALIASES[actionId] || [];
  const aliasIndex = aliases.findIndex((stageAliases) => stageAliases.some((alias) => rawStep.includes(alias)));
  if (aliasIndex >= 0) return Math.min(stages.length - 1, aliasIndex);

  const stageIndex = stages.findIndex((stage) => {
    const stageKey = normalizedStatus(stage);
    const words = stageKey.split('_').filter(Boolean);
    return words.some((word) => word.length >= 4 && rawStep.includes(word));
  });
  return stageIndex >= 0 ? stageIndex : -1;
}

function stageIndexFromPercent({ state, progress, stages }) {
  const rawPercent = percentFromProgress(progress);
  if (rawPercent == null) return -1;
  if (state === 'idle') return -1;
  if (state === 'evidence_saved' || state === 'review' || state === 'failed') return stages.length - 1;
  const index = Math.floor((rawPercent / 100) * stages.length);
  return Math.max(0, Math.min(stages.length - 2, index));
}

function shouldAnimateProgress(state, progress) {
  return Boolean(progress?.running && progress?.indeterminate !== false && (state === 'running' || state === 'waiting'));
}

function animatedStageLimit(stages) {
  return Math.max(1, stages.length - 2);
}

function activeStageForState({ actionId, state, progress, stages }) {
  if (state === 'idle') return -1;
  if (state === 'blocked' || state === 'saved_state' || state === 'queued') return 0;
  if (state === 'evidence_saved' || state === 'review' || state === 'failed') return stages.length - 1;

  const backendIndex = stageIndexFromBackend({ actionId, progress, stages });
  if (backendIndex >= 0) return Math.min(stages.length - 2, backendIndex);

  const percentIndex = stageIndexFromPercent({ state, progress, stages });
  if (percentIndex >= 0) return percentIndex;

  return Math.min(stages.length - 2, Math.max(1, Math.floor(stages.length / 2)));
}

function progressPercentForStage({ state, activeStage, stages, progress }) {
  const rawPercent = percentFromProgress(progress);
  if (rawPercent != null && state !== 'idle') return rawPercent;
  if (state === 'idle') return 0;
  if (state === 'evidence_saved' || state === 'review' || state === 'failed') return 100;
  if (state === 'blocked' || state === 'saved_state') return 0;
  if (stages.length <= 1 || activeStage < 0) return 0;
  return Math.round((activeStage / (stages.length - 1)) * 100);
}

function currentLabelForState({ actionId, state, progress, disabledReason, result, lastResult }) {
  if (state === 'blocked') return disabledReason || 'Paused for safety';
  if (state === 'saved_state') return 'Showing saved state';
  if (state === 'queued') return 'Getting ready';
  if (state === 'running' || state === 'waiting') return progress?.summary || ACTION_WORKING_COPY[actionId] || progress?.step || 'Working';
  if (state === 'evidence_saved') return lastResult || result?.summary || ACTION_COMPLETE_COPY[actionId] || 'Details saved';
  if (state === 'review') return result?.summary || 'Needs review';
  if (state === 'failed') return result?.summary || 'Could not complete';
  return 'Not run yet';
}

function statusChipForState({ actionId, state }) {
  if (state === 'queued') return 'Queued';
  if (state === 'running' || state === 'waiting') return actionId === 'update_app' ? 'Checking readiness' : 'Working';
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

function nodeState({ state, index, activeStage: displayActiveStage, finalIndex }) {
  if (state === 'idle') return 'empty';
  if (state === 'blocked' || state === 'saved_state') return index === 0 ? 'paused' : 'empty';
  if (state === 'review' || state === 'failed') {
    if (index < activeStage || index === finalIndex) return 'attention';
    return 'empty';
  }
  if (state === 'evidence_saved') return 'done';
  if (index < activeStage) return 'done';
  if (index === activeStage) return 'active';
  return 'empty';
}

function nodeSymbol({ kind, actionId, state, index, finalIndex }) {
  if (state === 'evidence_saved' && index === finalIndex) return '✓';
  if ((state === 'review' || state === 'failed') && index === finalIndex) return '!';
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

  const stages = ACTION_STAGE_COPY[actionId] || DEFAULT_STAGES;
  const workflowKind = ACTION_WORKFLOW_KIND[actionId] || 'signal';
  const activeStage = activeStageForState({ actionId, state, progress, stages });
  const [animatedStage, setAnimatedStage] = useState(activeStage);
  const animateProgress = shouldAnimateProgress(state, progress);

  useEffect(() => {
    setAnimatedStage(activeStage);
    if (!animateProgress) return undefined;
    const limit = animatedStageLimit(stages);
    const timer = window.setInterval(() => {
      setAnimatedStage((current) => {
        const next = Math.max(1, current + 1);
        return next > limit ? 1 : next;
      });
    }, 1050);
    return () => window.clearInterval(timer);
  }, [actionId, activeStage, animateProgress, stages.length]);

  const displayActiveStage = animateProgress ? Math.max(1, Math.min(animatedStage, animatedStageLimit(stages))) : activeStage;
  const percent = progressPercentForStage({ state, activeStage: displayActiveStage, stages, progress });
  const label = currentLabelForState({ actionId, state, progress, disabledReason, result, lastResult });
  const chip = statusChipForState({ actionId, state });
  const finalIndex = stages.length - 1;
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
        '--lite-action-progress-steps': stages.length,
        '--lite-action-progress-active-step': Math.max(0, displayActiveStage),
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
        aria-label={`${stages.join(' to ')} progress`}
        aria-valuemin="0"
        aria-valuemax="100"
        aria-valuenow={Math.round(percent)}
      >
        <span className="lite-action-progress__rail-base" aria-hidden="true" />
        <span className="lite-action-progress__rail-fill" aria-hidden="true" />
        <span className="lite-action-progress__rail-pulse" aria-hidden="true" />
        <span className="lite-action-progress__nodes" aria-hidden="true">
          {stages.map((stage, index) => {
            const visualState = nodeState({ state, index, activeStage: displayActiveStage, finalIndex });
            const active = visualState === 'active';
            const done = visualState === 'done';
            const attention = visualState === 'attention';
            const paused = visualState === 'paused';
            return (
              <span
                key={`${stage}-${index}`}
                className={`lite-action-progress__node lite-action-progress__node--${visualState} ${active ? 'is-active' : ''} ${done ? 'is-done' : ''} ${attention ? 'is-attention' : ''} ${paused ? 'is-paused' : ''}`}
              >
                <i>{nodeSymbol({ kind: workflowKind, actionId, state, index, finalIndex })}</i>
              </span>
            );
          })}
        </span>
      </div>

      <div className="lite-action-progress__stages">
        {stages.map((stage, index) => {
          const visualState = nodeState({ state, index, activeStage: displayActiveStage, finalIndex });
          return (
            <span key={stage} className={`lite-action-progress__stage lite-action-progress__stage--${visualState}`}>
              {stage}
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

export { DEFAULT_STAGES, ACTION_STAGE_COPY, ACTION_WORKFLOW_KIND, hasRunEvidence };

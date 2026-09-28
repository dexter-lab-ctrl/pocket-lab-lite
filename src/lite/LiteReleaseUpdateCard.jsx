import React, { useEffect, useMemo } from 'react';
import { useMachine } from '@xstate/react';
import { CheckCircle2, Download, RefreshCw, ShieldCheck } from 'lucide-react';
import { useLiteMutation } from '../hooks/useLiteMutation.js';
import { useLiteResource } from '../hooks/useLiteStatus.js';
import { liteApi } from '../lib/liteApi.js';
import { liteQueryKeys } from '../lib/liteQueryClient.js';
import { liteReleaseUpdateMachine } from '../machines/liteReleaseUpdateMachine.js';
import { GlassCard, LiteButton, StatusBadge } from './LiteUi.jsx';
import { LiteTechnicalFacts } from './LiteUx.jsx';

const ACTIVE_PHASES = new Set([
  'checking', 'applying', 'downloading', 'staging', 'preparing', 'installing',
  'promoting', 'validating', 'rolling_back',
]);

const RELEASE_PHASES = [
  ['checking', 'Check'],
  ['downloading', 'Download'],
  ['staging', 'Prepare'],
  ['installing', 'Install'],
  ['validating', 'Verify'],
];

const lower = (value) => String(value || '').trim().toLowerCase();

function timestampValue(value) {
  const parsed = Date.parse(String(value || ''));
  return Number.isFinite(parsed) ? parsed : 0;
}

export function isReleaseActive(data = {}) {
  return String(data.status || '').toLowerCase() === 'running'
    || ACTIVE_PHASES.has(String(data.phase || '').toLowerCase());
}

export function isVerifiedCurrentRelease(data = {}) {
  return data.repository_match === true
    && data.manifest_verified === true
    && Boolean(data.current_tag)
    && data.current_tag === data.latest_tag
    && data.update_available !== true
    && data.installed_artifact_verified !== false;
}

export function isReleaseFailureActive(data = {}) {
  if (isReleaseActive(data)) return false;
  if (!(data.status === 'degraded' || data.last_failure_code)) return false;
  if (!isVerifiedCurrentRelease(data)) return true;

  const lastFailure = timestampValue(data.last_failure_at);
  const lastSuccess = timestampValue(data.last_success_at);
  return data.last_terminal_status !== 'succeeded' || lastSuccess < lastFailure;
}

function phaseCopy(data = {}) {
  const phase = String(data.phase || '').toLowerCase();
  if (phase === 'checking') return 'Checking for updates';
  if (phase === 'downloading') return 'Downloading update';
  if (['staging', 'preparing'].includes(phase)) return 'Preparing update';
  if (['applying', 'installing', 'promoting'].includes(phase)) return 'Installing update';
  if (phase === 'validating') return 'Checking the update';
  if (phase === 'rolling_back') return 'Rolling back safely';
  return '';
}

function failureLabel(data = {}) {
  const phase = lower(data.last_failure_stage || data.phase);
  return ['checking', 'check'].includes(phase) ? 'Check failed' : 'Install failed';
}

function wasRecentlyInstalled(data = {}) {
  return ['installed', 'completed', 'promoted'].includes(lower(data.phase))
    || ['installed', 'complete', 'completed'].includes(lower(data.promotion_status));
}

function releaseProgressIndex(data = {}) {
  const phase = lower(data.phase);
  const index = RELEASE_PHASES.findIndex(([key]) => key === phase);
  return index >= 0 ? index : -1;
}

export function releasePresentation(data = {}, savedStateOnly = false) {
  const active = phaseCopy(data);
  if (active) return { label: active, status: 'checking', summary: 'Pocket Lab is handling this update through the local worker.' };
  if (data.last_rollback_status && data.last_rollback_status !== 'rollback_failed' && !isReleaseFailureActive(data)) {
    return { label: 'Rolled back safely', status: 'healthy', summary: 'The previous working interface was restored.' };
  }
  if (isReleaseFailureActive(data)) {
    return { label: failureLabel(data), status: 'failed', summary: 'The current working interface remains available. No unsafe partial update is presented.' };
  }
  if (data.repository_match === false) {
    return { label: 'Update source not verified', status: 'failed', summary: 'Install is blocked until the Pocket Lab Lite source is verified.' };
  }
  if (data.install_mode === 'source') {
    return { label: 'Installed from source', status: 'healthy', summary: 'Published releases are shown for reference; source installs are not compared as older.' };
  }
  if (data.update_available) {
    return { label: 'Update available', status: 'degraded', summary: `Pocket Lab Lite ${data.latest_release_tag || data.latest_tag || ''} is ready to review.`.trim() };
  }
  if (wasRecentlyInstalled(data) && isVerifiedCurrentRelease(data)) {
    return { label: 'Updated successfully', status: 'healthy', summary: 'The installed release was verified and is now current.' };
  }
  if (!data.current_tag && !data.latest_tag && !savedStateOnly) {
    return { label: 'Not checked yet', status: 'unknown', summary: 'Check for a verified Pocket Lab Lite release when you are ready.' };
  }
  return {
    label: savedStateOnly ? 'Showing saved update status' : 'Up to date',
    status: savedStateOnly ? 'degraded' : 'healthy',
    summary: savedStateOnly ? 'Reconnect to check for a newer release.' : 'The installed Pocket Lab Lite release matches the latest verified release.',
  };
}

export default function LiteReleaseUpdateCard() {
  const release = useLiteResource(liteApi.releaseStatus, [], {
    staleTime: 15 * 60_000,
    gcTime: 24 * 60 * 60_000,
    pollingMode: 'slow',
    isLive: isReleaseActive,
    refetchOnWindowFocus: false,
  });
  const [flow, send] = useMachine(liteReleaseUpdateMachine);
  const checkMutation = useLiteMutation({
    mutationFn: liteApi.checkRelease,
    invalidate: [liteQueryKeys.release()],
    invalidateOnSuccess: true,
  });
  const applyMutation = useLiteMutation({
    mutationFn: liteApi.applyRelease,
    invalidate: [liteQueryKeys.release()],
    invalidateOnSuccess: true,
  });
  const data = release.data || {};
  const active = isReleaseActive(data);
  const releaseCurrent = isVerifiedCurrentRelease(data) && !isReleaseFailureActive(data);
  const releaseSavedStateOnly = Boolean(
    release.backendReachable === false
    || (release.savedStateOnly && !releaseCurrent),
  );
  const presentation = useMemo(
    () => releasePresentation(data, releaseSavedStateOnly),
    [data, releaseSavedStateOnly],
  );
  const backendFailed = isReleaseFailureActive(data);

  useEffect(() => {
    if (active) send({ type: 'BACKEND_ACTIVE' });
    else if (backendFailed) send({ type: 'BACKEND_FAILED', reason: 'Update needs attention.' });
    else if (['accepted', 'observing', 'failed'].includes(String(flow.value))) send({ type: 'BACKEND_DONE' });
  }, [active, backendFailed, flow.value, send]);

  const writeBlocked = releaseSavedStateOnly || release.backendReachable === false || active;
  const applyAllowed = Boolean(
    data.update_available
    && data.repository_match === true
    && data.manifest_verified === true
    && !writeBlocked,
  );

  async function runCheck() {
    if (writeBlocked) return;
    send({ type: 'CHECK' });
    try {
      const result = await checkMutation.run({});
      send({ type: 'ACCEPTED', payload: result });
    } catch (error) {
      send({ type: 'FAILED', error });
    }
  }

  async function runApply() {
    if (!applyAllowed) return;
    send({ type: 'APPLY' });
    try {
      const result = await applyMutation.run({});
      send({ type: 'ACCEPTED', payload: result });
    } catch (error) {
      send({ type: 'FAILED', error });
    }
  }

  const failure = checkMutation.error?.message || applyMutation.error?.message || flow.context.failureReason || '';
  const checked = data.last_success_at || data.updated_at || '';
  const progressIndex = releaseProgressIndex(data);
  const progressVisible = active && progressIndex >= 0;
  const Icon = presentation.status === 'healthy' ? CheckCircle2 : ShieldCheck;
  const installedTag = data.installed_release_tag || data.current_tag || 'Not verified';
  const availableTag = data.latest_release_tag || data.latest_tag || 'Not checked';
  const verificationLabel = data.manifest_verified && data.installed_artifact_verified !== false
    ? 'Manifest and files verified'
    : data.install_mode === 'source' ? 'Source install' : 'Verification pending';

  return (
    <GlassCard className={`lite-release-update-card is-${presentation.status}`} data-lite-release-native="true" data-release-state={presentation.status}>
      <div className="lite-release-update-head">
        <span className={`lite-release-update-icon is-${presentation.status}`} aria-hidden="true"><Icon className="h-5 w-5" /></span>
        <div className="lite-release-update-copy">
          <small>System update</small>
          <h2>{presentation.label}</h2>
          <p>{failure || presentation.summary}</p>
        </div>
        <StatusBadge status={failure ? 'failed' : presentation.status}>{failure ? 'Needs attention' : presentation.label}</StatusBadge>
      </div>
      <div className="lite-release-update-meta">
        <div><small>Installed files:</small><strong>{installedTag}</strong></div>
        <div><small>Available</small><strong>{availableTag}</strong></div>
        <div><small>Verification</small><strong>{verificationLabel}</strong></div>
        <div><small>Last checked</small><strong>{checked ? new Date(checked).toLocaleString() : 'Not checked yet'}</strong></div>
      </div>
      {progressVisible ? (
        <div className="lite-release-update-progress" role="status" aria-live="polite">
          <div className="lite-release-update-progress-topline"><strong>{presentation.label}</strong><span>Step {progressIndex + 1} of {RELEASE_PHASES.length}</span></div>
          <ol>
            {RELEASE_PHASES.map(([key, label], index) => (
              <li key={key} className={index < progressIndex ? 'is-done' : index === progressIndex ? 'is-active' : ''}>
                <span aria-hidden="true">{index < progressIndex ? '✓' : index + 1}</span>
                <small>{label}</small>
              </li>
            ))}
          </ol>
        </div>
      ) : null}
      <div className="lite-release-update-actions">
        <LiteButton tone="secondary" onClick={runCheck} disabled={writeBlocked || checkMutation.isPending}>
          <RefreshCw className={`h-4 w-4 ${checkMutation.isPending ? 'animate-spin' : ''}`} />
          <span>{checkMutation.isPending ? 'Checking…' : 'Check now'}</span>
        </LiteButton>
        {data.update_available ? (
          <LiteButton onClick={runApply} disabled={!applyAllowed || applyMutation.isPending}>
            <Download className="h-4 w-4" />
            <span>{applyMutation.isPending ? 'Installing…' : active ? presentation.label : 'Install update'}</span>
          </LiteButton>
        ) : null}
      </div>
      <LiteTechnicalFacts
        title="Technical details"
        description="These release facts are read from the prepared backend status and never trigger an update by themselves."
        facts={[
          { id: 'source', label: 'Source', value: data.repository_match ? 'Pocket Lab Lite verified' : 'Not verified', tone: data.repository_match ? 'healthy' : 'failed' },
          { id: 'manifest', label: 'Manifest', value: data.manifest_verified ? 'Verified' : 'Not verified', tone: data.manifest_verified ? 'healthy' : 'review' },
          { id: 'operation', label: 'Operation', value: data.last_terminal_status || data.phase || 'Not started' },
          { id: 'failure', label: 'Failure record', value: data.last_failure_code || 'None' },
        ]}
      />
      {releaseSavedStateOnly ? <p className="lite-release-update-note">Saved status only. Reconnect before installing an update.</p> : null}
    </GlassCard>
  );
}

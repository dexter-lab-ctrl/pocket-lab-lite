import React, { useEffect, useMemo } from 'react';
import { useMachine } from '@xstate/react';
import { Download, RefreshCw, ShieldCheck } from 'lucide-react';
import { useLiteMutation } from '../hooks/useLiteMutation.js';
import { useLiteResource } from '../hooks/useLiteStatus.js';
import { liteApi } from '../lib/liteApi.js';
import { liteQueryKeys } from '../lib/liteQueryClient.js';
import { liteReleaseUpdateMachine } from '../machines/liteReleaseUpdateMachine.js';
import { GlassCard, LiteButton, StatusBadge } from './LiteUi.jsx';

const ACTIVE_PHASES = new Set([
  'checking', 'applying', 'downloading', 'staging', 'preparing', 'installing',
  'promoting', 'validating', 'rolling_back',
]);

function isReleaseActive(data = {}) {
  return String(data.status || '').toLowerCase() === 'running'
    || ACTIVE_PHASES.has(String(data.phase || '').toLowerCase());
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

function releasePresentation(data = {}, savedStateOnly = false) {
  const active = phaseCopy(data);
  if (active) return { label: active, status: 'checking', summary: 'Pocket Lab is handling this update through the local worker.' };
  if (data.last_rollback_status && data.last_rollback_status !== 'rollback_failed') {
    return { label: 'Rolled back safely', status: 'healthy', summary: 'The previous working interface was restored.' };
  }
  if (data.status === 'degraded' || data.last_failure_code) {
    return { label: 'Update failed', status: 'failed', summary: 'The current working interface remains available.' };
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
  const presentation = useMemo(
    () => releasePresentation(data, release.savedStateOnly),
    [data, release.savedStateOnly],
  );
  const backendFailed = data.status === 'degraded' || Boolean(data.last_failure_code);

  useEffect(() => {
    if (active) send({ type: 'BACKEND_ACTIVE' });
    else if (backendFailed) send({ type: 'BACKEND_FAILED', reason: 'Update needs attention.' });
    else if (String(flow.value) === 'accepted' || String(flow.value) === 'observing') send({ type: 'BACKEND_DONE' });
  }, [active, backendFailed, flow.value, send]);

  const writeBlocked = release.savedStateOnly || release.backendReachable === false || active;
  const applyAllowed = Boolean(
    data.update_available
    && data.repository_match
    && data.manifest_verified
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

  const busy = checkMutation.isPending || applyMutation.isPending || active;
  const failure = checkMutation.error?.message || applyMutation.error?.message || flow.context.failureReason || '';
  const checked = data.last_success_at || data.updated_at || '';

  return (
    <GlassCard className="lite-release-update-card" data-lite-release-native="true">
      <div className="lite-release-update-head">
        <span className="lite-release-update-icon"><ShieldCheck className="h-5 w-5" /></span>
        <div>
          <small>System update</small>
          <h2>{presentation.label}</h2>
          <p>{failure || presentation.summary}</p>
        </div>
        <StatusBadge status={failure ? 'failed' : presentation.status}>{failure ? 'Needs attention' : presentation.label}</StatusBadge>
      </div>
      <div className="lite-release-update-meta">
        <span>Source: {data.repository_match ? 'Pocket Lab Lite verified' : 'Not verified'}</span>
        <span>
          Installed files: {data.installed_artifact_verified
            ? 'Verified'
            : data.install_mode === 'source' ? 'Source install' : 'Not verified yet'}
        </span>
        <span>{checked ? `Last checked ${new Date(checked).toLocaleString()}` : 'Not checked yet'}</span>
      </div>
      <div className="lite-release-update-actions">
        <LiteButton tone="secondary" onClick={runCheck} disabled={writeBlocked || checkMutation.isPending}>
          <RefreshCw className={`h-4 w-4 ${busy ? 'animate-spin' : ''}`} />
          <span>{busy && !applyMutation.isPending ? presentation.label : 'Check now'}</span>
        </LiteButton>
        {data.update_available ? (
          <LiteButton onClick={runApply} disabled={!applyAllowed || applyMutation.isPending}>
            <Download className="h-4 w-4" />
            <span>{applyMutation.isPending || active ? presentation.label : 'Install Update'}</span>
          </LiteButton>
        ) : null}
      </div>
      {release.savedStateOnly ? <p className="lite-release-update-note">Saved status only. Reconnect before installing an update.</p> : null}
    </GlassCard>
  );
}

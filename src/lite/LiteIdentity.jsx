import React, { useMemo, useState } from 'react';
import {
  Activity,
  Copy,
  Database,
  Download,
  EyeOff,
  FileCheck,
  Fingerprint,
  LayoutGrid,
  Lock,
  Menu,
  Network,
  RefreshCw,
  Server,
  ShieldCheck,
  Trash2,
  WifiOff,
  X,
} from 'lucide-react';
import { useLiteResource } from '../hooks/useLiteStatus.js';
import { formatLiteTime, liteApi } from '../lib/liteApi.js';
import {
  GlassCard,
  StatusBadge,
  StateSurface,
  DEVICE_ROLE_OPTIONS,
  NAV_ITEMS,
  roleLabel,
  deviceConnectionLabel,
  canRestartDeviceAgent,
  canRemoveDevice,
  normalizeDeviceName,
  findDeviceNameConflict,
  deviceDuplicateMessage,
  deviceStatusLabel,
  copyTextToClipboard,
  serviceTone,
  normalizeBackendState,
  backendBadgeStatus,
  backendLabel,
  backendHeroTitle,
  securityFindingTone,
  securityFindingLabel,
  clampSecurityProgress,
  parseSecurityTimestamp,
  formatSecurityRemainingSeconds,
  liveSecurityProgress,
  securityProgressStage,
  scanInProgressValue,
  triggerHapticFeedback,
  shortRunId,
  formatSecurityDuration,
  securityTrendLabel,
  securityTrendView,
  securityDeltaTone,
  isSecurityTimeoutFinding,
  securityDeltaBadge,
  securityDeltaTitle,
  securityDeltaDescription,
  securityDeltaAction,
  securityDeltaSummary,
  securityExecutionStateTone,
  securityExecutionStepGlyph,
  securityToolStatusLabel,
  securityExecutionStateFromBackend,
  securityExecutionStepLabel,
  normalizeSecurityExecutionSteps,
  securityExecutionTimeline,
  PageHeader,
  LiteButton,
  ResultNotice,
  LoadingCard,
  friendlyOverallLabel,
  deviceLinkState,
  restartProgressTitle,
  restartStepStateLabel,
  safeRestartSteps
} from './LiteUi.jsx';

export default function IdentityScreen() {
  const { data, loading, error, refresh } = useLiteResource(liteApi.identity, []);
  const [target, setTarget] = useState('local-admin');
  const [result, setResult] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function rotate() {
    setBusy(true);
    setResult(null);
    setActionError(null);
    try {
      setResult(await liteApi.rotateIdentity(target));
      refresh();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Access"
        title="Identity & Access"
        description="Keep passwords and local access in a safe state. Change access only when you need to, with a clear record of the request."
        actions={<LiteButton onClick={refresh} tone="secondary">Refresh</LiteButton>}
      />

      <section className="lite-identity-hero">
        <div className="lite-identity-hero-copy">
          <div className="lite-home-pill">
            <span className="lite-ready-dot" />
            {backendLabel(data?.status, {
              ready: 'Access protected',
              review: 'Access needs review',
              danger: 'Access needs attention',
              checking: 'Checking access',
            })}
          </div>
          <h2>{backendHeroTitle(data?.status, {
            ready: 'Your passwords and access are kept in one safe place.',
            review: 'Access protection may need your review.',
            danger: 'Access needs attention.',
            checking: 'Checking access protection.',
          })}</h2>
          <p>
            Review access readiness, change a password safely, and keep your Pocket Lab protected without handling sensitive details yourself.
          </p>
        </div>

        <div className="lite-identity-status-card">
          <div className="lite-identity-icon">
            <Fingerprint className="h-7 w-7" />
          </div>
          <span>Current state</span>
          <strong>{backendLabel(data?.status, {
            ready: 'Protected',
            review: 'Review',
            danger: 'Attention',
            checking: 'Checking',
          })}</strong>
          <StatusBadge status={backendBadgeStatus(data?.status)}>
            {backendLabel(data?.status, {
              ready: 'Ready',
              review: 'Review',
              danger: 'Attention',
              checking: 'Checking',
            })}
          </StatusBadge>
        </div>
      </section>

      {loading ? <LoadingCard label="Checking access..." /> : null}

      {error ? (
        <StateSurface
          tone="degraded"
          title="Access summary needs a moment"
          description={error}
          className="mb-5"
        />
      ) : null}

      <div className="lite-identity-grid">
        <GlassCard className="lite-identity-card">
          <div className="lite-identity-card-head">
            <div className="lite-identity-mini-icon">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <StatusBadge status={backendBadgeStatus(data?.status)}>
              {backendLabel(data?.status, {
                ready: 'Ready',
                review: 'Review',
                danger: 'Attention',
                checking: 'Checking',
              })}
            </StatusBadge>
          </div>

          <h2>Access readiness</h2>
          <p>
            {data?.summary || 'Pocket Lab is checking whether access protection is ready.'}
          </p>

          <div className="lite-identity-checklist">
            <div>
              <span className="lite-check-dot" />
              Password changes are requested safely
            </div>
            <div>
              <span className="lite-check-dot" />
              Sensitive values stay hidden
            </div>
            <div>
              <span className="lite-check-dot" />
              Changes are recorded for review
            </div>
          </div>
        </GlassCard>

        <GlassCard className="lite-identity-card lite-identity-action-card">
          <div className="lite-identity-card-head">
            <div className="lite-identity-mini-icon">
              <Fingerprint className="h-5 w-5" />
            </div>
            <span className="lite-identity-soft-badge">Safe change</span>
          </div>

          <h2>Change a password</h2>
          <p>
            Choose what you want to update. Pocket Lab will prepare the change and keep the sensitive value hidden.
          </p>

          <label className="lite-identity-field-label" htmlFor="identity-target">
            What should be updated?
          </label>
          <select
            id="identity-target"
            className="pocket-input lite-identity-select"
            value={target}
            onChange={(event) => setTarget(event.target.value)}
          >
            <option value="local-admin">Main admin access</option>
            <option value="app-access">App access password</option>
            <option value="device-access">Device access password</option>
          </select>

          <div className="lite-identity-safe-note">
            <strong>Before it runs</strong>
            <span>You will see a clear request result. The password itself will not be shown here.</span>
          </div>

          <div className="mt-5">
            <LiteButton onClick={rotate} disabled={busy}>
              {busy ? 'Preparing...' : 'Change Password'}
            </LiteButton>
          </div>
        </GlassCard>
      </div>

      <ResultNotice result={result} error={actionError} />
    </>
  );
}

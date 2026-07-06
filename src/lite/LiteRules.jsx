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
  LiteRefreshButton,
  ResultNotice,
  LoadingCard,
  friendlyOverallLabel,
  deviceLinkState,
  restartProgressTitle,
  restartStepStateLabel,
  safeRestartSteps
} from './LiteUi.jsx';

export default function RulesScreen() {
  const { data, loading, error, refresh, cacheStatus, refreshing } = useLiteResource(liteApi.policy, []);
  const [enabled, setEnabled] = useState(false);
  const [result, setResult] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [busy, setBusy] = useState(false);

  React.useEffect(() => {
    if (data) setEnabled(Boolean(data.protection_enabled));
  }, [data]);

  const rulesStatus = data ? (enabled ? 'healthy' : 'degraded') : 'unknown';

  async function apply() {
    setBusy(true);
    setResult(null);
    setActionError(null);
    try {
      setResult(await liteApi.applyPolicy({ protection_enabled: enabled, reason: 'Pocket Lab Lite rules update' }));
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
        eyebrow="Rules"
        title="Safety Rules"
        description="Choose how careful Pocket Lab should be before making changes. Keep protection on for everyday use."
        actions={<LiteRefreshButton scope="rules" refresh={refresh} cacheStatus={cacheStatus} error={error} refreshing={refreshing} />}
      />

      <section className="lite-rules-hero">
        <div className="lite-rules-hero-copy">
          <div className="lite-home-pill">
            <span className="lite-ready-dot" />
            {backendLabel(rulesStatus, {
              ready: 'Protection on',
              review: 'Ready to enable',
              danger: 'Needs attention',
              checking: 'Checking rules',
            })}
          </div>
          <h2>Simple rules help prevent unwanted changes.</h2>
          <p>
            Pocket Lab can pause sensitive actions, ask for confirmation, and keep a clear record of important changes.
          </p>
        </div>

        <div className="lite-rules-status-card">
          <div className="lite-rules-icon">
            <FileCheck className="h-7 w-7" />
          </div>
          <span>Protection</span>
          <strong>{enabled ? 'On' : 'Off'}</strong>
          <StatusBadge status={backendBadgeStatus(rulesStatus)}>
            {backendLabel(rulesStatus, {
              ready: 'Enabled',
              review: 'Review',
              danger: 'Attention',
              checking: 'Checking',
            })}
          </StatusBadge>
        </div>
      </section>

      {loading ? <LoadingCard label="Loading rules..." /> : null}

      {error ? (
        <StateSurface
          tone="degraded"
          title="Rules need a moment"
          description={error}
          className="mb-5"
        />
      ) : null}

      <div className="lite-rules-grid">
        <GlassCard className="lite-rules-card lite-rules-toggle-card">
          <div className="lite-rules-card-head">
            <div className="lite-rules-mini-icon">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <StatusBadge status={backendBadgeStatus(rulesStatus)}>
              {backendLabel(rulesStatus, {
                ready: 'Protected',
                review: 'Not enabled',
                danger: 'Attention',
                checking: 'Checking',
              })}
            </StatusBadge>
          </div>

          <h2>Protection mode</h2>
          <p>
            {data?.summary || 'Pocket Lab is checking whether protection is enabled.'}
          </p>

          <button
            type="button"
            className={`lite-rules-toggle ${enabled ? 'lite-rules-toggle-on' : ''}`}
            onClick={() => setEnabled((value) => !value)}
            aria-pressed={enabled}
          >
            <span className="lite-rules-toggle-track">
              <span className="lite-rules-toggle-thumb" />
            </span>
            <span>
              <strong>{enabled ? 'Protection is on' : 'Protection is off'}</strong>
              <small>{enabled ? 'Recommended for everyday use' : 'Turn on to add an extra safety step'}</small>
            </span>
          </button>

          <div className="mt-5">
            <LiteButton onClick={apply} disabled={busy}>
              {busy ? 'Saving...' : 'Save Rules'}
            </LiteButton>
          </div>
        </GlassCard>

        <GlassCard className="lite-rules-card lite-rules-guide-card">
          <div className="lite-rules-card-head">
            <div className="lite-rules-mini-icon">
              <FileCheck className="h-5 w-5" />
            </div>
            <span className="lite-rules-soft-badge">Recommended</span>
          </div>

          <h2>What these rules do</h2>
          <p>
            Rules keep important actions intentional without making the app hard to use.
          </p>

          <div className="lite-rules-list">
            <div>
              <span>1</span>
              <p>Ask before sensitive changes</p>
            </div>
            <div>
              <span>2</span>
              <p>Keep a clear record</p>
            </div>
            <div>
              <span>3</span>
              <p>Let safe everyday actions stay simple</p>
            </div>
          </div>
        </GlassCard>
      </div>

      <ResultNotice result={result} error={actionError} />
    </>
  );
}

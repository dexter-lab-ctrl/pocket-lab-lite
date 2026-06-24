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

export default function CatalogScreen() {
  const { data, loading, error, refresh } = useLiteResource(liteApi.catalog, []);
  const [query, setQuery] = useState('');
  const [result, setResult] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const items = data?.items || [];

  const filteredItems = useMemo(() => {
    const value = query.trim().toLowerCase();
    if (!value) return items;
    return items.filter((item) => {
      return `${item.name || ''} ${item.summary || ''}`.toLowerCase().includes(value);
    });
  }, [items, query]);

  const installedCount = items.filter((item) => item.installed).length;
  const attentionCount = items.filter((item) => String(item.status || '').toLowerCase().includes('attention')).length;

  async function install(item) {
    setBusyId(item.id);
    setResult(null);
    setActionError(null);
    try {
      setResult(await liteApi.installApp(item.id));
      refresh();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Apps"
        title="App Catalog"
        description="Choose useful apps for this Pocket Lab. Installed apps stay easy to see, and new installs are prepared safely for you."
        actions={<LiteButton onClick={refresh} tone="secondary">Refresh</LiteButton>}
      />

      <section className="lite-catalog-hero">
        <div className="lite-catalog-hero-copy">
          <div className="lite-home-pill">
            <span className="lite-ready-dot" />
            Ready to browse
          </div>
          <h2>Pick what you want this device to run.</h2>
          <p>
            Start with the essentials, add services when you need them, and keep the experience focused on what matters.
          </p>
        </div>

        <div className="lite-catalog-counts">
          <div>
            <span>Available</span>
            <strong>{items.length}</strong>
          </div>
          <div>
            <span>Installed</span>
            <strong>{installedCount}</strong>
          </div>
          <div>
            <span>Review</span>
            <strong>{attentionCount}</strong>
          </div>
        </div>
      </section>

      <div className="lite-catalog-toolbar">
        <div className="lite-catalog-search-wrap">
          <LayoutGrid className="h-5 w-5" />
          <input
            className="lite-catalog-search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search apps"
            aria-label="Search apps"
          />
        </div>
        <p>{filteredItems.length} shown</p>
      </div>

      {error ? (
        <StateSurface
          tone="degraded"
          title="Catalog needs a moment"
          description={error}
          className="mb-5"
        />
      ) : null}

      {loading ? <LoadingCard label="Loading apps..." /> : null}

      <div className="lite-catalog-grid">
        {filteredItems.map((item) => {
          const installed = Boolean(item.installed);
          const needsAttention = String(item.status || '').toLowerCase().includes('attention');

          return (
            <GlassCard key={item.id} className="lite-catalog-card">
              <div className="lite-catalog-card-top">
                <div className="lite-catalog-icon">
                  <LayoutGrid className="h-5 w-5" />
                </div>
                <StatusBadge status={needsAttention ? 'degraded' : installed ? 'healthy' : 'ready'}>
                  {needsAttention ? 'Check' : installed ? 'Installed' : 'Available'}
                </StatusBadge>
              </div>

              <h2>{item.name}</h2>
              <p>{item.summary}</p>

              <div className="lite-catalog-meta">
                <span>{installed ? 'Already on this device' : 'Ready when you are'}</span>
              </div>

              <div className="lite-catalog-actions">
                <LiteButton
                  onClick={() => install(item)}
                  disabled={busyId === item.id || installed}
                  tone={installed ? 'secondary' : 'primary'}
                >
                  {busyId === item.id ? 'Starting...' : installed ? 'Installed' : 'Install'}
                </LiteButton>
              </div>
            </GlassCard>
          );
        })}
      </div>

      {!loading && filteredItems.length === 0 ? (
        <StateSurface
          tone="empty"
          title={query ? 'No matching apps' : 'No apps yet'}
          description={query ? 'Try a different search term.' : 'Refresh the catalog after setup or add app entries to your catalog source.'}
        />
      ) : null}

      <ResultNotice result={result} error={actionError} />
    </>
  );
}

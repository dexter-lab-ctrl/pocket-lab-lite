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

export default function HomeScreen({ status, loading, error, refresh, cacheStatus, refreshing, onNavigate }) {
  const primaryServices = useMemo(() => status.services?.slice(0, 6) || [], [status.services]);
  const stats = status.summary || {};
  const readyServices = primaryServices.filter((service) => serviceTone(service.status) === 'healthy').length;
  const totalServices = primaryServices.length || 0;

  return (
    <>
      <PageHeader
        eyebrow="Home"
        title={backendHeroTitle(status.overall, { ready: 'Your Pocket Lab is ready', review: 'Your Pocket Lab needs review', danger: 'Your Pocket Lab needs attention', checking: 'Checking your Pocket Lab' })}
        description="A calm overview of your apps, devices, safety, and backups. Start common tasks from here without digging through settings."
        actions={<LiteRefreshButton refresh={refresh} cacheStatus={cacheStatus} error={error} refreshing={refreshing} />}
      />

      {error ? (
        <StateSurface
          tone="degraded"
          title="Pocket Lab needs a moment"
          description={error}
          className="mb-5"
        />
      ) : null}

      <section className="lite-home-hero">
        <div className="lite-home-hero-copy">
          <div className="lite-home-pill">
            <span className="lite-ready-dot" />
            {friendlyOverallLabel(status.overall)}
          </div>
          <h2>Manage your private apps and devices from one simple place.</h2>
          <p>
            Pocket Lab Lite keeps the essentials close: apps, access, safety checks,
            devices, rules, and recovery.
          </p>
          <div className="lite-home-actions">
            <LiteButton onClick={() => onNavigate('catalog')}>Browse Apps</LiteButton>
            <LiteButton onClick={() => onNavigate('devices')} tone="secondary">Add Device</LiteButton>
            <LiteButton onClick={() => onNavigate('security')} tone="secondary">Safety Check</LiteButton>
            <LiteButton onClick={() => onNavigate('recovery')} tone="secondary">Backup</LiteButton>
          </div>
        </div>

        <div className="lite-home-readiness-card">
          <p className="lite-home-card-label">Today’s status</p>
          <strong>{readyServices}/{totalServices || '—'}</strong>
          <span>key areas ready</span>
          <StatusBadge status={status.overall}>
            {status.overall === 'healthy' ? 'Ready' : 'Needs attention'}
          </StatusBadge>
        </div>
      </section>

      <div className="lite-home-stats">
        <div className="lite-home-stat-card">
          <span>Apps</span>
          <strong>{stats.apps_available ?? 0}</strong>
          <p>available to install or manage</p>
        </div>
        <div className="lite-home-stat-card">
          <span>Devices</span>
          <strong>{stats.devices_known ?? 0}</strong>
          <p>known to this Pocket Lab</p>
        </div>
        <div className="lite-home-stat-card">
          <span>Safety</span>
          <strong>{stats.security_findings ?? 0}</strong>
          <p>items that need review</p>
        </div>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
        <GlassCard>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-xs font-black uppercase tracking-[0.18em] text-indigo-200">This device</p>
              <h2 className="mt-2 text-2xl font-black text-white">{status.device?.name || 'Pocket Lab'}</h2>
              <p className="mt-2 text-sm leading-6 text-slate-300">
                Set up for a small, private environment with the essentials enabled.
              </p>
            </div>
            <StatusBadge status={status.overall}>
              {status.overall === 'healthy' ? 'Ready' : 'Needs attention'}
            </StatusBadge>
          </div>

          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            <div className="lite-home-device-metric">
              <span>Device load</span>
              <strong>{status.telemetry?.cpu_usage_percent ?? '—'}%</strong>
            </div>
            <div className="lite-home-device-metric">
              <span>Device warmth</span>
              <strong>{status.telemetry?.cpu_temp_c ?? '—'}°C</strong>
            </div>
            <div className="lite-home-device-metric">
              <span>Storage available</span>
              <strong>{status.telemetry?.free_space_mb ?? '—'} MB</strong>
            </div>
            <div className="lite-home-device-metric">
              <span>Memory in use</span>
              <strong>{status.telemetry?.memory_usage_mb ?? '—'} MB</strong>
            </div>
          </div>

          <p className="mt-4 text-xs text-slate-500">Last checked: {formatLiteTime(status.checked_at)}</p>
        </GlassCard>

        <GlassCard>
          <p className="text-xs font-black uppercase tracking-[0.18em] text-cyan-200">Needs attention</p>
          <h2 className="mt-2 text-2xl font-black text-white">
            {(stats.security_findings ?? 0) === 0 ? 'Nothing urgent right now' : 'Review recommended'}
          </h2>
          <p className="mt-2 text-sm leading-6 text-slate-300">
            Pocket Lab will highlight problems here when apps, devices, safety checks,
            or backups need your attention.
          </p>
          <div className="mt-5">
            <LiteButton onClick={() => onNavigate('security')} tone="secondary">Review Safety</LiteButton>
          </div>
        </GlassCard>
      </div>

      <section className="mt-4">
        <div className="mb-3 flex items-end justify-between gap-3">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.18em] text-indigo-200">Key areas</p>
            <h2 className="text-xl font-black text-white">What is ready</h2>
          </div>
          {loading ? <span className="text-sm text-slate-400">Checking...</span> : null}
        </div>

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {loading ? <LoadingCard /> : primaryServices.map((service) => (
            <GlassCard key={service.name} className="lite-home-service-card">
              <div className="flex items-start justify-between gap-3">
                <h3 className="text-base font-black text-white">{service.name}</h3>
                <StatusBadge status={serviceTone(service.status)}>
                  {serviceTone(service.status) === 'healthy' ? 'Ready' : 'Check'}
                </StatusBadge>
              </div>
              <p className="mt-3 text-sm leading-6 text-slate-300">{service.summary}</p>
            </GlassCard>
          ))}
        </div>
      </section>
    </>
  );
}

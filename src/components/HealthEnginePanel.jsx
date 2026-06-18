import React from 'react';
import { AlertTriangle, CheckCircle2, Clock3, RefreshCw, ShieldCheck, Sparkles, XCircle } from 'lucide-react';
import ErrorBoundary from './ErrorBoundary';
import { normalizeHealthPayload } from '../lib/health';

function statusTone(status) {
  if (status === 'healthy') return 'border-emerald-500/30 bg-emerald-500/10 text-emerald-100';
  if (status === 'warning') return 'border-amber-500/30 bg-amber-500/10 text-amber-100';
  if (status === 'maintenance') return 'border-sky-500/30 bg-sky-500/10 text-sky-100';
  if (status === 'unavailable') return 'border-slate-500/30 bg-slate-500/10 text-slate-100';
  if (status === 'degraded') return 'border-rose-500/30 bg-rose-500/10 text-rose-100';
  if (status === 'unhealthy') return 'border-rose-500/30 bg-rose-500/10 text-rose-100';
  return 'border-slate-500/30 bg-slate-500/10 text-slate-100';
}

function statusIcon(status) {
  if (status === 'healthy') return <CheckCircle2 className="h-5 w-5" />;
  if (status === 'warning') return <AlertTriangle className="h-5 w-5" />;
  if (status === 'maintenance') return <Clock3 className="h-5 w-5" />;
  if (status === 'unavailable') return <XCircle className="h-5 w-5" />;
  if (status === 'degraded') return <AlertTriangle className="h-5 w-5" />;
  if (status === 'unhealthy') return <XCircle className="h-5 w-5" />;
  return <Sparkles className="h-5 w-5" />;
}

function badgeTone(status) {
  if (status === 'healthy') return 'bg-emerald-500/15 text-emerald-200 border-emerald-500/30';
  if (status === 'warning') return 'bg-amber-500/15 text-amber-200 border-amber-500/30';
  if (status === 'maintenance') return 'bg-sky-500/15 text-sky-200 border-sky-500/30';
  if (status === 'unavailable') return 'bg-slate-500/15 text-slate-200 border-slate-500/30';
  if (status === 'degraded') return 'bg-rose-500/15 text-rose-200 border-rose-500/30';
  if (status === 'unhealthy') return 'bg-rose-500/15 text-rose-200 border-rose-500/30';
  return 'bg-slate-500/15 text-slate-200 border-slate-500/30';
}

const STATUS_LABELS = {
  healthy: 'Healthy',
  warning: 'Warning',
  degraded: 'Degraded',
  unhealthy: 'Unhealthy',
  unavailable: 'Unavailable',
  maintenance: 'Maintenance',
  unknown: 'Unknown',
};

function HealthServiceBadge({ service, simpleMode = false }) {
  return (
    <span className={`rounded-full border px-3 py-1 text-[10px] font-bold uppercase tracking-[0.18em] ${badgeTone(service.status)}`}>
      {simpleMode ? 'Service' : service.name}: {STATUS_LABELS[service.status] || 'Unknown'}
    </span>
  );
}

function HealthCheckCard({ check, simpleMode = false }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-black/10 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">{simpleMode ? 'Service Check' : (check.group || 'service')}</p>
          <h4 className="mt-1 font-bold text-white">{simpleMode ? 'Pocket Lab service' : check.name}</h4>
          {!simpleMode && <p className="mt-1 text-xs text-slate-400 break-all">{check.url || '—'}</p>}
        </div>
        <span className={`rounded-full border px-3 py-1 text-[10px] font-bold uppercase tracking-[0.18em] ${badgeTone(check.status)}`}>
          {STATUS_LABELS[check.status] || 'Unknown'}
        </span>
      </div>
      <div className="mt-3 flex items-center justify-between text-xs text-slate-400">
        <span>{simpleMode ? 'Recent check' : `${check.results_count ?? 0} result(s)`}</span>
        <span>{simpleMode ? 'Checked automatically' : (typeof check.response_time_ms === 'number' ? `${check.response_time_ms} ms` : '—')}</span>
      </div>
      {check.summary ? <p className="mt-2 text-xs text-slate-300">{check.summary}</p> : null}
    </div>
  );
}

function HealthEnginePanelInner({ health, onRefresh, simpleMode = false, liveStatus = null }) {
  const normalizedHealth = normalizeHealthPayload(health || {});
  const summary = normalizedHealth.summary || {};
  const checks = Array.isArray(normalizedHealth.checks) ? normalizedHealth.checks : [];
  const topChecks = checks.slice(0, 4);
  const sourceLabel = simpleMode ? 'Automatic live system check' : (normalizedHealth.source === 'gatus' ? 'Gatus live data' : 'Pocket Lab fallback snapshot');
  const status = normalizedHealth.status || 'unknown';
  const services = Array.isArray(normalizedHealth.services) ? normalizedHealth.services : [];

  return (
    <div className={`mb-4 rounded-[2rem] border p-5 backdrop-blur ${statusTone(status)}`}>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex items-start gap-3">
          <div className={`rounded-2xl border p-2 ${badgeTone(status)}`}>
            {statusIcon(status)}
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] opacity-80">{simpleMode ? 'System health' : 'Health engine'}</p>
            <h3 className="mt-1 text-lg font-black">{STATUS_LABELS[status] || 'Unknown'}</h3>
            <p className="mt-1 text-sm opacity-90">
              {simpleMode ? `${sourceLabel}. We monitor important services and show what needs attention.` : `${sourceLabel}. Pocket Lab consumes the same engine snapshot in the backend and the UI.`}
            </p>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:min-w-[34rem]">
          <div className="rounded-2xl border border-white/10 bg-black/10 p-3">
            <p className="text-[10px] font-bold uppercase tracking-[0.18em] opacity-70">Healthy</p>
            <p className="mt-1 text-lg font-black">{summary.healthy ?? 0}</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-black/10 p-3">
            <p className="text-[10px] font-bold uppercase tracking-[0.18em] opacity-70">Warning</p>
            <p className="mt-1 text-lg font-black">{summary.warning ?? 0}</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-black/10 p-3">
            <p className="text-[10px] font-bold uppercase tracking-[0.18em] opacity-70">Attention</p>
            <p className="mt-1 text-lg font-black">
              {(summary.warning ?? 0) + (summary.degraded ?? 0) + (summary.unhealthy ?? 0) + (summary.unavailable ?? 0) + (summary.maintenance ?? 0)}
            </p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-black/10 p-3">
            <p className="text-[10px] font-bold uppercase tracking-[0.18em] opacity-70">Last scan</p>
            <p className="mt-1 text-xs font-semibold leading-5">{normalizedHealth.last_checked_at ? new Date(normalizedHealth.last_checked_at).toLocaleString() : '—'}</p>
          </div>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button
          onClick={onRefresh}
          className="inline-flex items-center gap-2 rounded-2xl border border-white/10 bg-black/15 px-4 py-2.5 text-sm font-semibold hover:bg-black/20"
        >
          <RefreshCw className="h-4 w-4" />
          {simpleMode ? 'Check Again' : 'Refresh health snapshot'}
        </button>
        <div className="inline-flex items-center gap-2 rounded-2xl border border-white/10 bg-black/10 px-4 py-2.5 text-xs font-semibold opacity-90">
          <ShieldCheck className="h-4 w-4" />
          {simpleMode ? (liveStatus?.isLive ? 'Live checks streaming' : normalizedHealth.gatus?.reachable ? 'Live checks active' : 'Offline summary active') : (liveStatus?.isLive ? 'Control-plane live stream active' : normalizedHealth.gatus?.reachable ? 'Health service reachable' : 'Fallback snapshot active')}
        </div>
        <div className="inline-flex items-center gap-2 rounded-2xl border border-white/10 bg-black/10 px-4 py-2.5 text-xs font-semibold opacity-90">
          <Clock3 className="h-4 w-4" />
          {simpleMode ? 'Updated automatically' : (liveStatus?.source ? `Source: ${liveStatus.source}` : 'Reads /api/health-engine.json')}
        </div>
      </div>

      {services.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2">
          {services.slice(0, 10).map((service) => (
            <HealthServiceBadge key={service.name} service={service} simpleMode={simpleMode} />
          ))}
        </div>
      )}

      <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {topChecks.length > 0 ? topChecks.map((check, index) => (
          <HealthCheckCard key={check.key || check.name || index} check={check} simpleMode={simpleMode} />
        )) : (
          <div className="rounded-2xl border border-white/10 bg-black/10 p-4 text-sm text-slate-300 xl:col-span-4">
            No health checks are available yet.
          </div>
        )}
      </div>
    </div>
  );
}

export default function HealthEnginePanel(props) {
  return (
    <ErrorBoundary>
      <HealthEnginePanelInner {...props} />
    </ErrorBoundary>
  );
}

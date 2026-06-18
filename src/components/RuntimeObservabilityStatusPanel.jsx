import React, { useEffect, useRef, useState } from 'react';
import {
  Activity,
  BarChart3,
  Clock,
  Database,
  Gauge,
  LayoutDashboard,
  ListChecks,
  RefreshCw,
  ServerCrash,
  ShieldAlert,
} from 'lucide-react';
import { ProgressiveDisclosure, StandardList, StandardListItem, StatusBadge } from './ui.jsx';
import CountUpNumber from './CountUpNumber.jsx';

const SIMPLE_LABELS = {
  prometheus: 'Metrics Engine',
  prometheus_targets: 'Monitoring Targets',
  loki: 'Logs Engine',
  grafana: 'Dashboard Engine',
  gatus: 'Health Checker',
  promtail: 'Log Collector',
};

const TECH_LABELS = {
  prometheus: 'Prometheus Ready',
  prometheus_targets: 'Prometheus Targets',
  loki: 'Loki Ready',
  grafana: 'Grafana Healthy',
  gatus: 'Gatus Reachable',
  promtail: 'Promtail Shipping Logs',
};

const ICONS = {
  prometheus: BarChart3,
  prometheus_targets: ListChecks,
  loki: Database,
  grafana: LayoutDashboard,
  gatus: Gauge,
  promtail: Activity,
};

const OBSERVABILITY_GROUPS = [
  {
    key: 'metrics',
    label: 'Metrics',
    simpleLabel: 'Metrics',
    description: 'Prometheus readiness and monitored target health.',
    simpleDescription: 'Pocket Lab checks whether system measurements are available.',
    icon: BarChart3,
    items: ['prometheus', 'prometheus_targets'],
  },
  {
    key: 'logs',
    label: 'Logs',
    simpleLabel: 'Logs',
    description: 'Loki readiness and inferred Promtail log shipping.',
    simpleDescription: 'Pocket Lab checks whether logs are being collected.',
    icon: Database,
    items: ['loki', 'promtail'],
  },
  {
    key: 'dashboards',
    label: 'Dashboards',
    simpleLabel: 'Dashboards',
    description: 'Grafana health for operational dashboards.',
    simpleDescription: 'Pocket Lab checks whether dashboards are reachable.',
    icon: LayoutDashboard,
    items: ['grafana'],
  },
  {
    key: 'health',
    label: 'Health checks',
    simpleLabel: 'Health checks',
    description: 'Gatus reachability for service checks.',
    simpleDescription: 'Pocket Lab checks whether service checks are reachable.',
    icon: Gauge,
    items: ['gatus'],
  },
];

function statusText(status, simpleMode) {
  if (simpleMode) {
    return {
      healthy: 'Working',
      degraded: 'Needs attention',
      unavailable: 'Not reachable',
      unknown: 'Checking',
    }[status] || 'Checking';
  }
  return {
    healthy: 'Healthy',
    degraded: 'Degraded',
    unavailable: 'Unavailable',
    unknown: 'Unknown',
  }[status] || 'Unknown';
}

function serviceDetail(key, service, targets, simpleMode) {
  if (key === 'prometheus_targets') {
    if (targets.total > 0) {
      return simpleMode ? `${targets.up}/${targets.total} healthy` : `${targets.up}/${targets.total} UP`;
    }
    return targets.reason || 'No target data reported';
  }
  if (key === 'promtail') {
    if (typeof service.recent_log_count === 'number') {
      return simpleMode ? `${service.recent_log_count} recent log entries` : `${service.recent_log_count} recent pm2_logs entries`;
    }
  }
  if (typeof service.latency_ms === 'number') {
    return `${service.latency_ms} ms · ${service.reason || 'checked'}`;
  }
  return service.reason || 'Runtime check pending';
}

function groupStatus(items) {
  if (items.some((item) => item.status === 'unavailable')) return 'unavailable';
  if (items.some((item) => item.status === 'degraded')) return 'degraded';
  if (items.every((item) => item.status === 'healthy')) return 'healthy';
  return 'unknown';
}

function ObservabilityGroup({ group, items, simpleMode, pulse = false }) {
  const Icon = group.icon;
  const status = groupStatus(items);
  return (
    <section className={`observability-group ${pulse ? 'event-pulse-row' : ''}`}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex min-w-0 items-start gap-3">
          <div className={`rounded-2xl border border-cyan-300/20 bg-cyan-500/10 p-2 text-cyan-100 health-dot health-dot-${status === 'healthy' ? 'healthy' : status === 'degraded' ? 'degraded' : status === 'unavailable' ? 'failed' : 'unknown'}`}><Icon className="h-5 w-5" /></div>
          <div className="min-w-0">
            <p className="text-sm font-black text-white">{simpleMode ? group.simpleLabel : group.label}</p>
            <p className="mt-1 text-sm leading-6 text-slate-400">{simpleMode ? group.simpleDescription : group.description}</p>
          </div>
        </div>
        <StatusBadge status={status} simpleMode={simpleMode}>{statusText(status, simpleMode)}</StatusBadge>
      </div>

      <StandardList className="mt-4">
        {items.map((item) => {
          const ItemIcon = ICONS[item.key] || Activity;
          return (
            <StandardListItem
              key={item.key}
              icon={ItemIcon}
              title={item.label}
              description={item.detail}
              status={item.status}
              simpleMode={simpleMode}
              metadata={simpleMode ? [] : [{ label: 'Probe', value: item.key }, { label: 'Status', value: item.status }]}
            />
          );
        })}
      </StandardList>
    </section>
  );
}

export default function RuntimeObservabilityStatusPanel({ snapshot, summary, isLoading, error, onRefresh, simpleMode = false }) {
  const [pulseGroups, setPulseGroups] = useState(false);
  const previousCheckedAtRef = useRef(snapshot?.checked_at || '');

  useEffect(() => {
    if (snapshot?.checked_at && previousCheckedAtRef.current && previousCheckedAtRef.current !== snapshot.checked_at) {
      setPulseGroups(true);
      const timeout = window.setTimeout(() => setPulseGroups(false), 320);
      previousCheckedAtRef.current = snapshot.checked_at;
      return () => window.clearTimeout(timeout);
    }
    previousCheckedAtRef.current = snapshot?.checked_at || previousCheckedAtRef.current;
    return undefined;
  }, [snapshot?.checked_at]);

  const targets = snapshot?.prometheus_targets || {};
  const labels = simpleMode ? SIMPLE_LABELS : TECH_LABELS;
  const services = snapshot?.services || {};
  const items = [
    { key: 'prometheus', service: services.prometheus || {} },
    { key: 'prometheus_targets', service: targets || {} },
    { key: 'loki', service: services.loki || {} },
    { key: 'grafana', service: services.grafana || {} },
    { key: 'gatus', service: services.gatus || {} },
    { key: 'promtail', service: services.promtail || {} },
  ].map(({ key, service }) => ({
    key,
    label: labels[key],
    status: service.status || 'unknown',
    detail: serviceDetail(key, service, targets, simpleMode),
  }));
  const itemByKey = Object.fromEntries(items.map((item) => [item.key, item]));

  const headline = simpleMode ? 'Monitoring Health' : 'Runtime Observability Health';
  const description = simpleMode
    ? 'Pocket Lab groups monitoring into metrics, logs, dashboards, and health checks so it is easier to see what needs attention.'
    : 'Control API performs bounded local probes for Prometheus, Loki, Grafana, Gatus, Prometheus targets, and inferred Promtail log shipping.';

  return (
    <section className="runtime-observability-panel mt-4 rounded-[2rem] border border-white/10 bg-slate-900/60 p-5 shadow-xl">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <ShieldAlert className="h-5 w-5 text-emerald-300" />
            <h3 className="text-lg font-black text-white">{headline}</h3>
          </div>
          <p className="mt-1 max-w-3xl text-sm text-slate-400">{description}</p>
          <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-400">
            <StatusBadge status={snapshot?.status || 'unknown'} simpleMode={simpleMode}>{isLoading ? (simpleMode ? 'Checking' : 'Loading') : statusText(snapshot?.status || 'unknown', simpleMode)}</StatusBadge>
            {snapshot?.cached ? <StatusBadge status="degraded" simpleMode={simpleMode} className="offline-cache-badge">{simpleMode ? 'Saved view' : 'Cached'}</StatusBadge> : null}
            {snapshot?.checked_at ? (
              <span className={`offline-cache-timestamp inline-flex items-center gap-1 ${snapshot?.cached ? 'offline-cache-badge' : ''}`}><Clock className="offline-cache-clock h-3 w-3" /> Checked {new Date(snapshot.checked_at).toLocaleString()}</span>
            ) : null}
            {summary?.total ? <span><CountUpNumber value={summary.healthy} />/{summary.total} {simpleMode ? 'checks working' : 'services healthy'}</span> : null}
          </div>
        </div>
        <button
          type="button"
          onClick={onRefresh}
          className="pocket-button pocket-button-secondary"
        >
          <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
          {simpleMode ? 'Check Again' : 'Refresh status'}
        </button>
      </div>

      {error ? (
        <div className="mt-4 flex items-start gap-2 rounded-2xl border border-red-400/20 bg-red-500/10 p-3 text-sm text-red-200">
          <ServerCrash className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      ) : null}

      <div className="mt-5 grid grid-cols-1 gap-4 xl:grid-cols-2">
        {OBSERVABILITY_GROUPS.map((group) => (
          <ObservabilityGroup
            key={group.key}
            group={group}
            simpleMode={simpleMode}
            pulse={pulseGroups}
            items={group.items.map((key) => itemByKey[key]).filter(Boolean)}
          />
        ))}
      </div>

      <ProgressiveDisclosure simpleMode={simpleMode} title={simpleMode ? 'Show monitoring details' : 'Probe details'} className="mt-4">
        <div className="space-y-3 text-xs leading-6 text-slate-400">
          <p>{simpleMode ? 'Pocket Lab checks these tools through its own control API so the app can show a simple status view.' : 'The frontend receives this summary from Control API. It does not call Prometheus, Loki, Grafana, Gatus, or Promtail directly.'}</p>
          {!simpleMode && Array.isArray(targets.down_targets) && targets.down_targets.length > 0 ? (
            <div className="rounded-2xl border border-amber-400/20 bg-amber-500/10 p-4">
              <p className="text-sm font-black text-amber-100">Down Prometheus targets</p>
              <ul className="mt-2 space-y-1 text-xs text-amber-100/80">
                {targets.down_targets.slice(0, 5).map((target, index) => (
                  <li key={`${target.job}-${target.instance}-${index}`}>{target.job} · {target.instance} · {target.last_error || target.health}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {!simpleMode && snapshot?.warnings?.length ? (
            <div>
              <p className="font-black text-slate-300">Warnings</p>
              {snapshot.warnings.map((warning) => <p key={warning}>• {warning}</p>)}
            </div>
          ) : null}
        </div>
      </ProgressiveDisclosure>
    </section>
  );
}

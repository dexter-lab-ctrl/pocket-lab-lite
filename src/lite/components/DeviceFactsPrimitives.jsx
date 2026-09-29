import '../deviceFacts.css';
import React from 'react';
import {
  normalizeCapabilityEvidence,
  normalizeRuntimeServices,
  resourceFactAvailabilityLabel,
  softwarePostureLabel,
} from '../../lib/liteDeviceFacts.js';

function titleCase(value, fallback = 'Unknown') {
  const text = String(value || '').replace(/[_-]+/g, ' ').trim();
  return text ? text.replace(/\b\w/g, (letter) => letter.toUpperCase()) : fallback;
}

export function FreshnessIndicator({ freshness = 'missing', observedAt = null }) {
  const state = String(freshness || 'missing').toLowerCase().replace(/[\s-]+/g, '_');
  const label = ({ current: 'Current', fresh: 'Current', stale: 'Stale', missing: 'Not reported', saved: 'Saved' })[state] || titleCase(state);
  return (
    <small className={`lite-device-fact-freshness is-${state}`} data-device-fact-freshness={state}>
      {label}{observedAt ? ` · ${String(observedAt).slice(0, 64)}` : ''}
    </small>
  );
}

export function ResourceMetric({ item = {}, variant = 'standard', icon: Icon = null }) {
  const tone = item.tone || item.status || item.observationStatus || 'neutral';
  const value = item.value ?? item.metric ?? resourceFactAvailabilityLabel(item);
  const note = item.note || item.summary || '';
  const parsedMeter = item.meterPercent === null || item.meterPercent === undefined ? NaN : Number(item.meterPercent);
  const meterPercent = Number.isFinite(parsedMeter) && parsedMeter >= 0 && parsedMeter <= 100
    ? Math.round(parsedMeter)
    : null;
  const meterLabel = item.meterLabel || `${item.label || 'Resource'} usage`;
  if (variant === 'compact') {
    return (
      <div className={`lite-home-premium-resource is-${tone}`} data-device-fact-resource={item.key || item.metricKey || item.label}>
        {Icon ? <span><Icon className="h-4 w-4" /></span> : null}
        <div>
          <small>{item.label}</small>
          <strong>{value}</strong>
          {note ? <em>{note}</em> : null}
        </div>
      </div>
    );
  }
  return (
    <article className={`lite-device-health-resource is-${tone}`} data-device-fact-resource={item.key || item.metricKey || item.label}>
      <span>{item.label}</span>
      <strong>{item.statusLabel || resourceFactAvailabilityLabel(item)}</strong>
      <small>{value}</small>
      {meterPercent !== null ? (
        <div
          className="lite-device-resource-meter"
          role="progressbar"
          aria-label={meterLabel}
          aria-valuemin="0"
          aria-valuemax="100"
          aria-valuenow={meterPercent}
        >
          <span style={{ width: `${meterPercent}%` }} />
        </div>
      ) : null}
      {note ? <p>{note}</p> : null}
      {variant === 'detailed' ? <FreshnessIndicator freshness={item.freshness} observedAt={item.observedAt || item.observed_at} /> : null}
    </article>
  );
}

export function CapabilityList({ capabilities = [], statusLabel }) {
  const rows = normalizeCapabilityEvidence(capabilities);
  if (!rows.length) return <p>Capabilities will appear after the device reports safe capability evidence.</p>;
  return (
    <ul className="lite-device-capability-list" data-device-fact-capabilities="true">
      {rows.map((item) => (
        <li key={item.id}>
          <span>{item.label}</span>
          <strong className={`is-${item.status}`}>
            {statusLabel ? statusLabel(item.status, item.reason_code) : titleCase(item.status)}
          </strong>
        </li>
      ))}
    </ul>
  );
}

export function RuntimeServiceList({ services = [] }) {
  const rows = normalizeRuntimeServices(services);
  if (!rows.length) return <p>Runtime services have not been reported by this device.</p>;
  return (
    <ul className="lite-device-capability-list" data-device-fact-services="true">
      {rows.map((service) => (
        <li key={service.service_id}>
          <span>{service.label}</span>
          <strong className={`is-${service.freshness}`}>
            {service.freshness === 'stale' ? `Last reported ${titleCase(service.state)}` : titleCase(service.state)}
          </strong>
        </li>
      ))}
    </ul>
  );
}

export function SoftwarePosture({ facts = {}, posture = {} }) {
  const postureView = posture && typeof posture === 'object' ? posture : {};
  const software = facts?.software && typeof facts.software === 'object' ? facts.software : {};
  const postureParts = Array.isArray(postureView.parts)
    ? postureView.parts.reduce((result, item) => {
      if (item?.component) result[item.component] = item;
      return result;
    }, {})
    : postureView.parts && typeof postureView.parts === 'object' ? postureView.parts : {};
  const rows = ['node_agent', 'supervisor'].map((component) => ({
    component,
    ...(postureParts[component] || {}),
    ...(software[component] || {}),
  }));
  const statusOrder = ['incompatible', 'outdated', 'stale', 'verification_pending', 'unknown', 'current'];
  const normalizedPostureStatus = String(postureView.status || '').toLowerCase().replace(/[\s-]+/g, '_');
  const componentStatuses = rows.map((item) => String(item.status || '').toLowerCase().replace(/[\s-]+/g, '_'));
  const derivedStatus = statusOrder.find((candidate) => componentStatuses.includes(candidate))
    || (rows.some((item) => item.version) ? 'unknown' : 'verification_pending');
  const status = ['current', 'outdated', 'incompatible', 'stale', 'verification_pending', 'unknown'].includes(normalizedPostureStatus)
    ? normalizedPostureStatus
    : derivedStatus;
  const summary = postureView.summary || (status === 'verification_pending'
    ? 'Version evidence has not been reported by this device yet.'
    : status === 'unknown'
      ? 'Version evidence is present, but Pocket Lab cannot classify it yet.'
      : 'Pocket Lab checked the reported device and recovery service evidence.');
  return (
    <div className="lite-device-software-posture" data-device-fact-software={status}>
      <strong>{softwarePostureLabel(status)}</strong>
      <p>{summary}</p>
      <dl>
        {rows.map((item) => (
          <div key={item.component}>
            <dt>{item.component === 'node_agent' ? 'Agent' : 'Supervisor'}</dt>
            <dd>{item.version || 'Not reported'}{item.version ? ` · ${titleCase(item.status || item.freshness, 'Unknown')}` : ''}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

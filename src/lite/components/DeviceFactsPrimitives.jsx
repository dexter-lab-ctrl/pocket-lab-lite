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
  const software = facts?.software && typeof facts.software === 'object' ? facts.software : {};
  const rows = ['node_agent', 'supervisor'].map((component) => ({ component, ...(software[component] || {}) }));
  const status = posture.status || (rows.some((item) => item.freshness === 'stale') ? 'stale' : rows.some((item) => item.version) ? 'unknown' : 'verification_pending');
  return (
    <div className="lite-device-software-posture" data-device-fact-software={status}>
      <strong>{softwarePostureLabel(status)}</strong>
      <dl>
        {rows.map((item) => (
          <div key={item.component}>
            <dt>{item.component === 'node_agent' ? 'Agent' : 'Supervisor'}</dt>
            <dd>{item.version || 'Not reported'}{item.version ? ` · ${titleCase(item.freshness, 'Unknown')}` : ''}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

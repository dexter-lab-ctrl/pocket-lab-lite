import React from 'react';
import { expect, within } from '@storybook/test';
import {
  CapabilityList,
  FreshnessIndicator,
  ResourceMetric,
  RuntimeServiceList,
  SoftwarePosture,
} from './DeviceFactsPrimitives.jsx';

export default {
  title: 'Pocket Lab Lite/Devices/Device Facts primitives',
  parameters: {
    layout: 'padded',
    pocketlab: {
      product: 'Pocket Lab Lite',
      implementation_status: 'verified-source',
      architecture: 'Canonical backend Device Facts → shared frontend normalization → reusable presentation primitives',
    },
  },
};

const resource = (status, overrides = {}) => ({
  key: 'temperature',
  label: 'Temperature',
  status,
  observationStatus: status,
  statusLabel: ({ available: 'Healthy', stale: 'Stale', unsupported: 'Unsupported', permission_denied: 'Permission denied', missing: 'Not reported' })[status] || status,
  value: status === 'available' || status === 'stale' ? '42 °C' : ({ unsupported: 'Unsupported', permission_denied: 'Permission denied', missing: 'Not reported' })[status],
  summary: status === 'stale' ? 'Saved resource evidence is stale.' : 'Resource evidence is explicit.',
  freshness: status === 'stale' ? 'stale' : status === 'missing' ? 'missing' : 'current',
  observedAt: status === 'stale' ? '2026-09-05T10:00:00Z' : '2026-09-05T12:00:00Z',
  ...overrides,
});

export const ResourceComplete = {
  render: () => <ResourceMetric item={resource('available')} variant="detailed" />,
  play: async ({ canvasElement }) => expect(within(canvasElement).getByText('42 °C')).toBeInTheDocument(),
};
export const ResourcePartial = { render: () => <div><ResourceMetric item={resource('available')} variant="detailed" /><ResourceMetric item={resource('unsupported', { label: 'Temperature' })} variant="detailed" /></div> };
export const ResourceStale = { render: () => <ResourceMetric item={resource('stale')} variant="detailed" /> };
export const ResourceUnsupported = { render: () => <ResourceMetric item={resource('unsupported')} variant="detailed" /> };
export const ResourcePermissionDenied = { render: () => <ResourceMetric item={resource('permission_denied')} variant="detailed" /> };
export const ResourceMissing = { render: () => <ResourceMetric item={resource('missing')} variant="detailed" /> };

const capability = (id, status, extra = {}) => ({
  id,
  label: extra.label || id.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase()),
  category: extra.category || 'execution',
  verification_strategy: extra.verification_strategy || 'runtime_evidence',
  status,
  reason_code: extra.reason_code || status,
  source: extra.source || 'runtime_evidence',
  advertised: extra.advertised !== false,
  evaluated_at: '2026-09-05T12:00:00Z',
  verified_at: status === 'verified' ? '2026-09-05T12:00:00Z' : null,
  freshness: status === 'stale' ? 'stale' : 'current',
});

export const CapabilitiesMixed = {
  render: () => <CapabilityList capabilities={[
    capability('serve_control_plane', 'verified'),
    capability('receive_commands', 'verification_pending'),
    capability('backup_target', 'unsupported'),
    capability('future_accelerator', 'verification_pending', { label: 'Future Accelerator', category: 'custom', source: 'agent_advertisement' }),
  ]} />,
};

const service = (id, freshness = 'current', state = 'online') => ({
  service_id: id,
  label: id.replace(/-/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase()),
  category: 'service',
  manager: 'process_manager',
  state,
  reported_at: freshness === 'stale' ? '2026-09-05T10:00:00Z' : '2026-09-05T12:00:00Z',
  freshness,
  restart_supported: false,
  restart_reason: 'backend_guard_required',
  source: 'prepared_service_evidence',
});

export const ServicesMixed = { render: () => <RuntimeServiceList services={[service('gateway-alpha'), service('queue-beta', 'stale'), service('future-sidecar', 'current', 'unknown')]} /> };
export const ServicesNotReported = { render: () => <RuntimeServiceList services={[]} /> };
export const FreshnessCurrent = { render: () => <FreshnessIndicator freshness="current" observedAt="2026-09-05T12:00:00Z" /> };
export const FreshnessStale = { render: () => <FreshnessIndicator freshness="stale" observedAt="2026-09-05T10:00:00Z" /> };
export const SoftwareCurrent = { render: () => <SoftwarePosture posture={{ status: 'current' }} facts={{ software: { node_agent: { version: '2.5.0', freshness: 'current' }, supervisor: { version: '2.5.0', freshness: 'current' } } }} /> };
export const SoftwareOutdated = { render: () => <SoftwarePosture posture={{ status: 'outdated' }} facts={{ software: { node_agent: { version: '2.4.0', freshness: 'current' }, supervisor: { version: '2.5.0', freshness: 'current' } } }} /> };

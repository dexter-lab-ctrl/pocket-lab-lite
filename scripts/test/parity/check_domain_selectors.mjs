#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {
  selectDevicesScreenView,
  selectLiteCatalogAppSummary,
  selectLiteDeviceCard,
  selectPhotoPrismActionsView,
  selectPhotoPrismManageView,
  selectRecoveryScreenView,
  selectRecoverySummaryView,
  selectSecurityScreenView,
  selectSecuritySummaryView,
} from '../../../src/lib/liteViewModels.js';
import { buildLiteHomeOverview } from '../../../src/lib/liteHomePresentation.js';

const home = buildLiteHomeOverview({
  overall: 'healthy',
  device: { name: 'Pocket Lab Server' },
  telemetry: { cpu_usage_percent: 12, memory_usage_mb: 256, free_space_mb: 4096 },
  services: [],
});
assert.equal(home.overallTone, 'ready');
assert.match(home.heroTitle, /workspace/i);

const app = selectLiteCatalogAppSummary({
  id: 'photoprism',
  name: 'PhotoPrism',
  installed: true,
  status: 'ready',
  actions: { open: true },
});
assert.equal(app.id, 'photoprism');
assert.equal(app.name, 'PhotoPrism');
const actions = selectPhotoPrismActionsView({
  status: 'ready',
  actions: { open: { enabled: true, status: 'ready' } },
});
assert.equal(actions.actions.open.enabled, true);
const manage = selectPhotoPrismManageView({
  catalog: { apps: [{ id: 'photoprism', name: 'PhotoPrism', installed: true, status: 'ready' }] },
  appActions: { status: 'ready', actions: {} },
});
assert.equal(manage.app.id, 'photoprism');

const devices = selectDevicesScreenView({
  devices: [{ id: 'server', name: 'Pocket Lab Server', status: 'online', protected_server_host: true }],
  remote_access: { ready: false, status: 'not_ready' },
});
assert.equal(devices.devices[0].status_label, 'Online');
assert.equal(selectLiteDeviceCard({ id: 'device-1', name: 'Device', status: 'offline' }).status_label, 'Offline');

const securityPayload = { status: 'healthy', summary: 'No urgent safety issues', score: 96 };
assert.equal(selectSecuritySummaryView(securityPayload).score, 96);
assert.equal(selectSecurityScreenView(securityPayload).summary, 'No urgent safety issues');

const recoveryPayload = { status: 'healthy', summary: 'Recovery Ready' };
assert.equal(selectRecoverySummaryView(recoveryPayload).status, 'healthy');
assert.equal(selectRecoveryScreenView(recoveryPayload).summary, 'Recovery Ready');

const model = JSON.parse(fs.readFileSync('contracts/parity/parity-model.json', 'utf8'));
for (const domainId of ['identity', 'rules']) {
  const domain = model.domains.find((item) => item.id === domainId);
  assert.ok(domain, `${domainId} domain must exist`);
  assert.deepEqual(domain.selectors, ['direct-render']);
  assert.ok(domain.api_routes.length > 0);
  assert.ok(domain.semantic_mappings.length > 0);
}

console.log('PASS all-tab parity selector/presentation linkage');

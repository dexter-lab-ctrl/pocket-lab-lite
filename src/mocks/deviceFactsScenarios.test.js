import { describe, expect, it } from 'vitest';

import { buildDeviceFactsScenario, DEVICE_FACT_SCENARIOS } from './deviceFactsScenarios.js';

describe('Device Facts regression scenarios', () => {
  it('publishes deterministic coverage for every required Device Facts state', () => {
    const required = [
      'devices-resource-complete', 'devices-resource-partial', 'devices-resource-stale',
      'devices-resource-unsupported', 'devices-resource-permission-denied', 'devices-resource-missing',
      'devices-capability-verified', 'devices-capability-pending', 'devices-capability-stale',
      'devices-capability-unsupported', 'devices-capability-blocked', 'devices-capability-not-applicable',
      'devices-capability-missing', 'devices-capability-mixed', 'devices-capability-unknown',
      'devices-services-mixed', 'devices-services-stale', 'devices-services-unknown', 'devices-services-disappeared',
      'devices-software-current', 'devices-software-outdated', 'devices-software-incompatible', 'devices-software-stale',
      'devices-secondary-complete', 'devices-secondary-offline-saved', 'devices-long-name',
    ];
    required.forEach((scenario) => expect(DEVICE_FACT_SCENARIOS.has(scenario)).toBe(true));
  });

  it('keeps status and Server Host fleet facts identical for a shared snapshot', () => {
    const state = buildDeviceFactsScenario('devices-resource-complete');
    const server = state.devices.find((item) => item.id === 'pocket-lab-lite-server');
    expect(state.status.device_facts.resources.memory.value.free_mb).toBe(2048);
    expect(server.device_facts.resources.memory.value.free_mb).toBe(2048);
    expect(state.status.device_facts.resources.cpu_usage.value.usage_percent).toBe(12);
    expect(server.device_facts.resources.cpu_usage.value.usage_percent).toBe(12);
  });

  it('keeps secondary saved facts stale and does not clone Server Host runtime services', () => {
    const state = buildDeviceFactsScenario('devices-secondary-offline-saved');
    const secondary = state.devices.find((item) => item.id === 'test-phone-4');
    expect(secondary.device_facts.resources.memory.freshness).toBe('stale');
    expect(secondary.runtime_services).toEqual([]);
  });

  it('represents unknown future capabilities and services without unsafe metadata', () => {
    const capabilities = buildDeviceFactsScenario('devices-capability-unknown').target.capability_states;
    expect(capabilities[0].id).toBe('future_accelerator');
    expect(capabilities[0].status).toBe('verification_pending');
    const services = buildDeviceFactsScenario('devices-services-unknown').target.runtime_services;
    expect(services[0].service_id).toBe('future-sidecar');
    const encoded = JSON.stringify({ capabilities, services }).toLowerCase();
    expect(encoded).not.toMatch(/nats:\/\/|password|bearer |\/data\/data\/|\/home\//);
  });
});

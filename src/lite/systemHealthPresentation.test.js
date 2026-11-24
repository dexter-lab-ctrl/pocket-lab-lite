import { describe, expect, it } from 'vitest';
import {
  componentLabel, groupHealthIncidents, healthCounts, healthStatusLabel,
  incidentEvidenceState, recoveryAvailabilityLabel, recoveryDestination,
  recoveryLifecycleLabel, recoveryOperationLabel, systemHealthPresentation,
} from './systemHealthPresentation.js';

// Deterministic presentation contract, tests authored but NOT RUN in H0–H6.
describe('System Health H2 evidence-first presentation', () => {
  const current = { incident_id: 'health-current', source: 'agent', target_id: 'pocket-node',
    state: 'detected', evidence_freshness: 'current', concern_state: 'current_concern' };
  const saved = { ...current, incident_id: 'health-saved', concern_state: 'saved_concern' };
  const resolved = { ...current, incident_id: 'health-resolved', state: 'resolved',
    concern_state: 'resolved_observation' };

  it('keeps current, saved and observed-resolved incidents distinct', () => {
    const groups = groupHealthIncidents([current, saved, resolved]);
    expect(groups.current).toHaveLength(1);
    expect(groups.saved).toHaveLength(1);
    expect(groups.resolved).toHaveLength(1);
    expect(incidentEvidenceState(current, true)).toBe('saved');
    expect(incidentEvidenceState(resolved)).toBe('resolved');
  });

  it('does not turn a stale unresolved issue into green readiness', () => {
    const payload = { status: 'unknown', freshness: 'current',
      healthy_services: 7, unknown_services: 0, current_problems: 0, saved_problems: 1 };
    expect(systemHealthPresentation(payload).state).not.toBe('ready');
    expect(systemHealthPresentation({ status: 'healthy', freshness: 'current',
      saved_problems: 1, unknown_services: 0 }).state).not.toBe('ready');
    expect(systemHealthPresentation(payload, true).state).toBe('saved');
  });

  it('keeps authoritative count semantics when a list is paginated', () => {
    expect(healthCounts({ freshness: 'current', current_problems: 12,
      saved_problems: 17, active_problems: 29, healthy_services: 3 },
      groupHealthIncidents([current, saved]))).toEqual({ current: 12, saved: 17, healthy: 3 });
  });

  it('uses exact known operation mappings and safely handles unknown IDs', () => {
    expect(recoveryOperationLabel('runtime.consumer.reconnect')).toBe('Restore command connection');
    expect(recoveryOperationLabel('device.agent.recover')).toBe('Recover device agent');
    expect(recoveryOperationLabel('app.repair')).toBe('Repair app');
    expect(recoveryOperationLabel('runtime.configuration.restore')).toBe('Restore service configuration');
    expect(recoveryOperationLabel('recovery.database.restore')).toBe('Restore Pocket Lab data');
    expect(recoveryOperationLabel('new.secret.action')).toBe('Existing recovery option');
    expect(recoveryAvailabilityLabel('externally_managed')).toMatch(/existing recovery service/i);
    expect(recoveryAvailabilityLabel('never_automatic')).toMatch(/manual confirmation/i);
    expect(recoveryAvailabilityLabel('not_enabled')).toBe('Not available');
  });

  it('maps durable recovery lifecycle states without treating admission as success', () => {
    expect(recoveryLifecycleLabel('admitted')).toMatch(/queued/i);
    expect(recoveryLifecycleLabel('awaiting_verification')).toMatch(/verification pending/i);
    expect(recoveryLifecycleLabel('verified')).toMatch(/verified/i);
    expect(recoveryLifecycleLabel('verification_failed')).toMatch(/failed/i);
    expect(recoveryLifecycleLabel('unknown-state')).toMatch(/not confirmed/i);
  });

  it('retains recognizable legitimate device identities, including short ones', () => {
    expect(componentLabel('agent', 'pocket-node', 'Secondary phone')).toBe('Secondary phone');
    expect(componentLabel('agent', '3')).toBe('Device');
    expect(componentLabel('supervisor', 'k-u')).toBe('Device');
    expect(componentLabel('agent', '../../bad')).toBe('Device agent');
    expect(componentLabel('strange.source', 'secret.string')).toBe('Component');
    expect(componentLabel('nats', 'consumer:worker')).toBe('Command consumer');
  });

  it('provides only governed navigation to existing controls', () => {
    expect(recoveryDestination('agent')).toBe('devices');
    expect(recoveryDestination('app')).toBe('catalog');
    expect(recoveryDestination('sqlite')).toBe('recovery');
    expect(recoveryDestination('security')).toBe('security');
    expect(recoveryDestination('unknown-source')).toBeNull();
    expect(healthStatusLabel('agent_stopped_without_supervisor')).toMatch(/no supervisor/i);
  });

  it('does not claim diagnosis or repair for missing evidence', () => {
    expect(systemHealthPresentation(null).state).toBe('unknown');
    expect(groupHealthIncidents([{ ...current, concern_state: 'saved_concern',
      evidence_freshness: 'current' }]).saved).toHaveLength(1);
  });
});


// P4 qualification — ADDED, NOT RUN.
it('does not treat a historical device as a current or resolved concern', () => {
  const item = { source: 'agent', target_id: 'retired-id', state: 'detected',
    current_monitoring: false, membership_state: 'removed', concern_state: 'historical_record',
    evidence_freshness: 'current' };
  expect(incidentEvidenceState(item)).toBe('historical');
  expect(incidentEvidenceState(item, true)).toBe('historical');
  const groups = groupHealthIncidents([item]);
  expect(groups.historical).toEqual([item]);
  expect(groups.current).toEqual([]);
  expect(groups.saved).toEqual([]);
  expect(groups.resolved).toEqual([]);
});

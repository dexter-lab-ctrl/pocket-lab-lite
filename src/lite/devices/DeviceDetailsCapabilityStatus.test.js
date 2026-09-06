import { describe, expect, it } from 'vitest';

import { capabilityStatusLabel } from './DeviceDetailsLazy.jsx';

describe('device capability row labels', () => {
  it('maps canonical backend capability states', () => {
    expect(capabilityStatusLabel('verified')).toBe('Verified');
    expect(capabilityStatusLabel('verification_pending')).toBe(
      'Verification pending',
    );
    expect(capabilityStatusLabel('unavailable')).toBe('Unavailable');
    expect(capabilityStatusLabel('unsupported')).toBe('Unsupported');
    expect(capabilityStatusLabel('stale')).toBe('Stale');
    expect(capabilityStatusLabel('blocked')).toBe('Blocked');
    expect(capabilityStatusLabel('not_applicable')).toBe('Not applicable');
    expect(
      capabilityStatusLabel(
        'not_advertised',
        'capability_not_advertised',
      ),
    ).toBe('Not advertised');
  });

  it('keeps legacy capability states compatible', () => {
    expect(capabilityStatusLabel('ready')).toBe('Verified');
    expect(capabilityStatusLabel('available')).toBe('Verification pending');
    expect(capabilityStatusLabel('not_ready')).toBe('Unavailable');
  });
});

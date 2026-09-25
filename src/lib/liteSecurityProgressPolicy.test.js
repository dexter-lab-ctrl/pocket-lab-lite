import { describe, expect, it } from 'vitest';
import { shouldUseLiteSecurityProgressStream } from './liteSecurityProgressPolicy.js';

describe('Lite Security progress stream policy', () => {
  it('does not start a progress stream for passive Manage opens', () => {
    expect(shouldUseLiteSecurityProgressStream({})).toBe(false);
    expect(shouldUseLiteSecurityProgressStream({ activeSecurityDetails: null })).toBe(false);
  });

  it('keeps the stream active for an active scan or check-path details', () => {
    expect(shouldUseLiteSecurityProgressStream({ shouldLoadSecurityProgress: true })).toBe(true);
    expect(shouldUseLiteSecurityProgressStream({ activeSecurityDetails: 'checkPath' })).toBe(true);
  });

  it('does not start a second stream when the root accepted-run owner is active', () => {
    expect(shouldUseLiteSecurityProgressStream({
      rootOwnsAcceptedSecurityRun: true,
      shouldLoadSecurityProgress: true,
      activeSecurityDetails: 'checkPath',
    })).toBe(false);
  });
});

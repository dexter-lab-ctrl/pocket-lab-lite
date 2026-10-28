import { describe, expect, it } from 'vitest';
import {
  areComparableSafetyRuns,
  isMeasuredSafetyProgress,
  isReportedSafetyScore,
  isSafetyCoverageReported,
  safetyCoverageQuality,
} from './safetyAzurePresentation.js';

// DEFINED — NOT EXECUTED. All fixtures are synthetic; no real scans are performed.
describe('Azure Horizon Safety Center backend-truthful presentation', () => {
  it('requires a numeric reported score, never inventing a value for first run or stale metadata', () => {
    expect(isReportedSafetyScore(null, 'backend_reported')).toBe(false);
    expect(isReportedSafetyScore(undefined, 'backend_reported')).toBe(false);
    expect(isReportedSafetyScore(92, 'not_reported')).toBe(false);
    expect(isReportedSafetyScore(92, 'backend_reported')).toBe(true);
    expect(isReportedSafetyScore(0, 'backend_reported')).toBe(true);
    expect(isReportedSafetyScore(Number.NaN, 'backend_reported')).toBe(false);
  });
  it.each(['quick', 'full', 'app'])('does not present an optimistic % for %s', (_profile) => {
    expect(isMeasuredSafetyProgress({ status: 'queued', percent: 4 }, true)).toBe(false);
    expect(isMeasuredSafetyProgress({ status: 'accepted', percent: null })).toBe(false);
    expect(isMeasuredSafetyProgress({ status: 'running', percent: undefined })).toBe(false);
    expect(isMeasuredSafetyProgress({ status: 'running', percent: 31 })).toBe(true);
    expect(isMeasuredSafetyProgress({ status: 'done', percent: 100 })).toBe(true);
  });
  it('rejects out-of-range, text and nonfinite measurements', () => {
    for (const value of [NaN, Infinity, -1, 101, '39', null]) {
      expect(isMeasuredSafetyProgress({ percent: value })).toBe(false);
    }
  });
  it('requires actual coverage metadata from a recorded check', () => {
    expect(isSafetyCoverageReported(null, true)).toBe(false);
    expect(isSafetyCoverageReported({ checked_targets: ['host'] }, false)).toBe(false);
    expect(isSafetyCoverageReported({}, true)).toBe(false);
    expect(isSafetyCoverageReported({ checked_targets: [] }, true)).toBe(true);
  });
  it('distinguishes reported, missing, partial, failed and timed-out coverage', () => {
    expect(safetyCoverageQuality(null, true)).toBe('unreported');
    expect(safetyCoverageQuality({ checked_targets: ['host'] }, false)).toBe('unreported');
    expect(safetyCoverageQuality({ checked_targets: ['host'], skipped_targets: ['media'] }, true)).toBe('reported');
    for (const key of ['partial_targets', 'missing_targets', 'timed_out_targets', 'failed_targets']) {
      expect(safetyCoverageQuality({ checked_targets: ['host'], [key]: ['target'] }, true)).toBe('incomplete');
    }
  });
  it('compares only two distinct, scored runs from the same profile and app', () => {
    const quick = { run_id: 'quick-2', scan_profile: 'quick', score: 91 };
    const prior = { run_id: 'quick-1', scan_profile: 'quick', score: 88 };
    expect(areComparableSafetyRuns(quick, prior)).toBe(true);
    expect(areComparableSafetyRuns(quick, { ...prior, scan_profile: 'full' })).toBe(false);
    expect(areComparableSafetyRuns(quick, { ...prior, score: null })).toBe(false);
    expect(areComparableSafetyRuns(quick, { ...quick })).toBe(false);
    expect(areComparableSafetyRuns({ run_id: 'a2', scan_profile: 'app', app_id: 'photoprism', score: 90 },
      { run_id: 'a1', scan_profile: 'app', app_id: 'another', score: 95 })).toBe(false);
    expect(areComparableSafetyRuns({ run_id: 'a2', scan_profile: 'app', app_id: 'photoprism', score: 90 },
      { run_id: 'a1', scan_profile: 'app', app_id: 'photoprism', score: 92 })).toBe(true);
  });
});

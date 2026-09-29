import { describe, expect, it } from 'vitest';
import {
  isReleaseActive,
  isReleaseFailureActive,
  isVerifiedCurrentRelease,
  releasePresentation,
} from './LiteReleaseUpdateCard.jsx';

const currentRelease = {
  status: 'healthy',
  repository_match: true,
  manifest_verified: true,
  installed_artifact_verified: true,
  current_tag: 'lite-2026.07.29.1',
  latest_tag: 'lite-2026.07.29.1',
  update_available: false,
};

describe('Lite release update presentation', () => {
  it('shows a verified equal release as current when its own query is live', () => {
    expect(isVerifiedCurrentRelease(currentRelease)).toBe(true);
    expect(releasePresentation(currentRelease, false)).toMatchObject({ label: 'Up to date', status: 'healthy' });
  });

  it('uses saved copy only for a genuinely saved release query', () => {
    expect(releasePresentation({ status: 'healthy' }, true)).toMatchObject({
      label: 'Showing saved update status',
      status: 'degraded',
    });
  });

  it('keeps an available release actionable without calling it failed', () => {
    expect(releasePresentation({
      ...currentRelease,
      current_tag: 'lite-2026.07.28.1',
      latest_tag: 'lite-2026.07.29.1',
      latest_release_tag: 'lite-2026.07.29.1',
      update_available: true,
    })).toMatchObject({ label: 'Update available', status: 'degraded' });
  });

  it.each([
    ['checking', 'Checking for updates'],
    ['downloading', 'Downloading update'],
    ['staging', 'Preparing update'],
    ['installing', 'Installing update'],
    ['validating', 'Checking the update'],
  ])('presents %s as active work', (phase, label) => {
    expect(isReleaseActive({ status: 'running', phase })).toBe(true);
    expect(releasePresentation({ status: 'running', phase })).toMatchObject({ label, status: 'checking' });
  });

  it('does not resurrect a historical failure after a verified successful install', () => {
    const data = {
      ...currentRelease,
      phase: 'installed',
      promotion_status: 'installed',
      last_failure_code: 'previous_install_failed',
      last_failure_at: '2026-07-29T10:00:00Z',
      last_success_at: '2026-07-29T10:02:00Z',
      last_terminal_status: 'succeeded',
    };
    expect(isReleaseFailureActive(data)).toBe(false);
    expect(releasePresentation(data)).toMatchObject({ label: 'Updated successfully', status: 'healthy' });
    expect(releasePresentation(data).label).not.toMatch(/failed/i);
  });

  it('shows a current failure only while the failure is newer than success', () => {
    const data = {
      ...currentRelease,
      phase: 'error',
      last_failure_code: 'release_check_failed',
      last_failure_stage: 'checking',
      last_failure_at: '2026-07-29T10:02:00Z',
      last_success_at: '2026-07-29T10:00:00Z',
      last_terminal_status: 'failed',
    };
    expect(isReleaseFailureActive(data)).toBe(true);
    expect(releasePresentation(data)).toMatchObject({ label: 'Check failed', status: 'failed' });
  });

  it('keeps rollback and source-install explanations explicit', () => {
    expect(releasePresentation({ ...currentRelease, last_rollback_status: 'rolled_back' })).toMatchObject({
      label: 'Rolled back safely',
      status: 'healthy',
    });
    expect(releasePresentation({ install_mode: 'source', repository_match: true })).toMatchObject({
      label: 'Installed from source',
      status: 'healthy',
    });
    expect(releasePresentation({ repository_match: false })).toMatchObject({
      label: 'Update source not verified',
      status: 'failed',
    });
  });

  it('does not claim current when the release identity is incomplete', () => {
    expect(isVerifiedCurrentRelease({ ...currentRelease, manifest_verified: false })).toBe(false);
    expect(releasePresentation({})).toMatchObject({ label: 'Not checked yet', status: 'unknown' });
  });
});

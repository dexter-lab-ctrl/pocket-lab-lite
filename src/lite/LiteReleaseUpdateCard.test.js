import { describe, expect, it } from 'vitest';
import { releasePresentation } from './LiteReleaseUpdateCard.jsx';

describe('Lite release update presentation', () => {
  it('shows a verified equal release as current when its own query is live', () => {
    expect(releasePresentation({
      status: 'healthy',
      repository_match: true,
      manifest_verified: true,
      current_tag: 'lite-2026.07.29.1',
      latest_tag: 'lite-2026.07.29.1',
      update_available: false,
    }, false)).toMatchObject({ label: 'Up to date', status: 'healthy' });
  });

  it('uses saved copy only for a genuinely saved release query', () => {
    expect(releasePresentation({ status: 'healthy' }, true)).toMatchObject({
      label: 'Showing saved update status',
      status: 'degraded',
    });
  });
});

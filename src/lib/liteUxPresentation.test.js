import { describe, expect, it } from 'vitest';
import {
  LITE_DEFAULT_UI_FORBIDDEN_TERMS,
  actionOutcomePresentation,
  assertPlainLanguage,
  confirmationPresentation,
  friendlyLiteText,
  liteFreshnessPresentation,
  normalizeTechnicalFacts,
} from './liteUxPresentation.js';

describe('Pocket Lab Lite UX maturity presentation contract', () => {
  it('translates backend implementation language before it reaches normal UI', () => {
    expect(friendlyLiteText('FastAPI queued work for the backend worker over NATS/JetStream.')).toBe(
      'Pocket Lab queued work for the backend Pocket Lab service over Pocket Lab connection.',
    );
    expect(assertPlainLanguage(friendlyLiteText('Polling: slow. Projection stale.'))).toEqual([]);
  });

  it('keeps the forbidden default-UI vocabulary explicit and reviewable', () => {
    expect(LITE_DEFAULT_UI_FORBIDDEN_TERMS).toEqual(expect.arrayContaining([
      'nats',
      'jetstream',
      'fastapi',
      'backend-owned',
      'projection stale',
      'polling:',
    ]));
  });

  it('expresses freshness in user terms rather than cache mechanics', () => {
    expect(liteFreshnessPresentation({ saved: true, lastUpdatedLabel: '12 minutes ago' })).toMatchObject({
      state: 'saved',
      label: 'Showing saved information · 12 minutes ago',
    });
    expect(liteFreshnessPresentation({ refreshing: true }).label).toBe('Refreshing…');
  });

  it('normalizes meaningful technical facts without implementation vocabulary', () => {
    const rows = normalizeTechnicalFacts([
      { label: 'Backend owner', value: 'FastAPI worker' },
      { label: 'Polling', value: 'slow' },
    ]);
    expect(rows).toEqual([
      expect.objectContaining({ label: 'Backend owner', value: 'Pocket Lab Pocket Lab service' }),
      expect.objectContaining({ label: 'Refreshing', value: 'slow' }),
    ]);
  });

  it('models action outcomes as what happened, changed, stayed protected, and next step', () => {
    expect(actionOutcomePresentation({
      title: 'Check complete',
      summary: 'PhotoPrism is healthy.',
      what_changed: 'Nothing changed.',
      what_did_not_happen: 'No photos were scanned.',
      protected_summary: 'Private values stayed hidden.',
      next_action: 'No action is needed.',
    })).toMatchObject({
      title: 'Check complete',
      whatChanged: 'Nothing changed.',
      whatDidNotHappen: 'No photos were scanned.',
      protectedSummary: 'Private values stayed hidden.',
      nextAction: 'No action is needed.',
    });
  });

  it('models confirmations around consequences and reversibility', () => {
    expect(confirmationPresentation({
      title: 'Remove device?',
      will: ['Remove the device relationship.'],
      willNot: ['Erase the phone.'],
      reversible: 'The device can join again.',
      availability: 'Dependent apps may be unavailable.',
    })).toMatchObject({
      will: ['Remove the device relationship.'],
      willNot: ['Erase the phone.'],
      reversible: 'The device can join again.',
    });
  });
});

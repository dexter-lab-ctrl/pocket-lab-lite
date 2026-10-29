import { describe, expect, it } from 'vitest';
import { distinctCatalogStatusSummary } from './catalogPresentation.js';
describe('generic Apps description and operational status separation — not run', () => {
  it('removes duplicate PhotoPrism description without app-specific branching', () => {
    const text = 'Private photo library for your self-hosted workspace.';
    expect(distinctCatalogStatusSummary(text, text)).toBe('');
    expect(distinctCatalogStatusSummary('  Photo Library.  ', 'photo   library')).toBe('');
  });
  it('preserves genuinely different backend operational information', () => {
    expect(distinctCatalogStatusSummary('Private photo library.', 'Running · Transfer needs attention')).toBe('Running · Transfer needs attention');
    expect(distinctCatalogStatusSummary('My app', 'Remote access not ready')).toBe('Remote access not ready');
  });
  it('works for unknown second applications and missing values', () => {
    expect(distinctCatalogStatusSummary('Example App description', 'Example App description')).toBe('');
    expect(distinctCatalogStatusSummary(null, 'Waiting for installation')).toBe('Waiting for installation');
    expect(distinctCatalogStatusSummary('An app', undefined)).toBe('');
  });
});

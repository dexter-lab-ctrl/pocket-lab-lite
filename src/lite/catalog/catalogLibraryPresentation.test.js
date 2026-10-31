// SOURCE-AUTHORED ONLY. Qualification intentionally not executed in this session.
import { describe, expect, it } from 'vitest';
import { catalogLibraryIdentity, partitionCatalogApps, trustedCatalogIconPath } from './catalogPresentation.js';

describe('Azure Horizon native library presentation', () => {
  const apps = [
    { id: 'new', name: 'Available app', installed: false, actions: { install: false } },
    { id: 'photoprism', name: 'PhotoPrism', installed: true, category: 'Photos & media',
      host_device_name: 'Server Phone', access: { route_ready: true },
      lifecycle: { security: { status: 'protected' } } },
    { id: 'other', name: 'Example App', installed: true },
  ];
  it('partitions installed and discoverable apps without mutating registry order', () => {
    const partition = partitionCatalogApps(apps, app => app.installed === true);
    expect(partition.installed.map(app => app.id)).toEqual(['other', 'photoprism']);
    expect(partition.discoverable.map(app => app.id)).toEqual(['new']);
    expect(apps[0].id).toBe('new');
  });
  it('never invents Running or Protected in a saved offline snapshot', () => {
    const identity = catalogLibraryIdentity(apps[1], { installed: true, running: true }, true);
    expect(identity.status).toBe('Saved status');
    expect(identity.safety).toBe('');
    expect(identity.host).toBe('Server Phone');
  });
  it('keeps installed-but-stopped and unknown runtime facts distinct', () => {
    expect(catalogLibraryIdentity(apps[1], { installed: true, stopped: true }).status).toBe('Needs attention');
    expect(catalogLibraryIdentity(apps[2], { installed: true }).status).toBe('Installed');
    expect(catalogLibraryIdentity(apps[1], { installed: true, running: true }).status).toBe('Running');
  });
  it('uses a known local icon and rejects external, traversal and arbitrary image URLs', () => {
    expect(trustedCatalogIconPath({ id: 'photoprism' })).toBe('/assets/apps/photoprism.svg');
    expect(trustedCatalogIconPath({ id: 'other', icon_path: '/assets/apps/other.svg' })).toBe('/assets/apps/other.svg');
    for (const value of ['https://example.org/logo.svg','//evil.test/icon.svg','/assets/apps/../secret.png','data:image/svg+xml,fake']) {
      expect(trustedCatalogIconPath({ id: 'other', icon_path: value })).toBe('');
    }
    expect(trustedCatalogIconPath({ id: 'unknown' })).toBe('');
  });
  it('omits unsupported host and protection claims for generic apps', () => {
    const identity = catalogLibraryIdentity(apps[2], { installed: true }, false);
    expect(identity.host).toBe('');
    expect(identity.safety).toBe('');
    expect(identity.category).toBe('Self-hosted app');
  });
});

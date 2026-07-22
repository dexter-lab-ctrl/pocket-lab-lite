import { describe, expect, it, vi } from 'vitest';
import {
  LITE_INSTALL_MANIFEST,
  validateLiteInstallManifest,
} from './liteInstallManifest.js';
import {
  applyLiteAppBadge,
  buildLiteSafeSharePayload,
  canOfferLiteInstall,
  deriveLiteAppBadgeState,
  isLiteStandaloneDisplay,
  recordLiteInstallCooldown,
  requestLiteInstall,
  shareLiteSafeWorkspace,
} from './liteNativeInstall.js';
import {
  normalizeLiteScreenId,
  parseLiteScreenLaunch,
  replaceLiteScreenLaunch,
} from '../lite/liteNavigationMetadata.js';
import { isLitePwaNavigationPath } from './liteOfflineReadPolicy.js';

function memoryStorage() {
  const values = new Map();
  return {
    getItem: (key) => values.get(key) || null,
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: (key) => values.delete(key),
  };
}

function query(queryKey, data, dataUpdatedAt = 10_000) {
  return { queryKey, state: { data, dataUpdatedAt, error: null } };
}

describe('Pocket Lab Lite N6B native install surface', () => {
  it('emits a stable Lite manifest with complete install identity and safe shortcuts', () => {
    expect(validateLiteInstallManifest(LITE_INSTALL_MANIFEST)).toEqual({ valid: true, errors: [] });
    expect(LITE_INSTALL_MANIFEST).toEqual(expect.objectContaining({
      id: '/pocket-lab-lite/',
      name: 'Pocket Lab Lite',
      short_name: 'Pocket Lab',
      start_url: '/',
      scope: '/',
      display: 'standalone',
      orientation: 'any',
      lang: 'en',
      dir: 'ltr',
    }));
    expect(LITE_INSTALL_MANIFEST.display_override).toEqual([
      'window-controls-overlay',
      'standalone',
      'minimal-ui',
      'browser',
    ]);
    expect(LITE_INSTALL_MANIFEST.icons.map((icon) => `${icon.sizes}:${icon.purpose}`)).toEqual([
      '192x192:any',
      '512x512:any',
      '192x192:maskable',
      '512x512:maskable',
    ]);
    expect(LITE_INSTALL_MANIFEST.shortcuts.map((shortcut) => shortcut.url)).toEqual([
      '/?screen=catalog',
      '/?screen=security',
      '/?screen=devices',
      '/?screen=recovery',
    ]);
    expect(LITE_INSTALL_MANIFEST.shortcuts.every((shortcut) => isLitePwaNavigationPath(shortcut.url))).toBe(true);
    expect(LITE_INSTALL_MANIFEST.shortcuts.some((shortcut) => /apps|api|backup-now|scan|restart/i.test(shortcut.url))).toBe(false);
  });

  it('parses allowlisted shortcut launches and safely falls back for unknown screens', () => {
    expect(parseLiteScreenLaunch({ pathname: '/', search: '?screen=devices' })).toEqual(expect.objectContaining({
      screen_id: 'devices',
      valid: true,
      source: 'manifest-shortcut',
    }));
    expect(parseLiteScreenLaunch({ pathname: '/', search: '?screen=remove-device' })).toEqual(expect.objectContaining({
      screen_id: 'home',
      valid: false,
    }));
    expect(normalizeLiteScreenId('unknown')).toBe('home');
    let replacedUrl = '';
    expect(replaceLiteScreenLaunch('devices', {
      locationObject: { pathname: '/', search: '?screen=devices&token=hidden' },
      historyObject: { state: {}, replaceState: (_state, _title, url) => { replacedUrl = url; } },
    })).toBe(true);
    expect(replacedUrl).toBe('/?screen=devices');
  });

  it('offers installation only with browser eligibility and outside cooldowns or active work', () => {
    const storage = memoryStorage();
    expect(canOfferLiteInstall({ promptAvailable: true, storage, now: 1_000 })).toBe(true);
    expect(canOfferLiteInstall({ promptAvailable: true, installed: true, storage, now: 1_000 })).toBe(false);
    expect(canOfferLiteInstall({ promptAvailable: true, workflowActive: true, storage, now: 1_000 })).toBe(false);
    expect(canOfferLiteInstall({ promptAvailable: true, criticalOverlayOpen: true, storage, now: 1_000 })).toBe(false);
    recordLiteInstallCooldown({ storage, now: 1_000, durationMs: 60_000 });
    expect(canOfferLiteInstall({ promptAvailable: true, storage, now: 30_000 })).toBe(false);
    expect(canOfferLiteInstall({ promptAvailable: true, storage, now: 61_001 })).toBe(true);
    expect(isLiteStandaloneDisplay({ windowObject: { matchMedia: () => ({ matches: true }) }, navigatorObject: {} })).toBe(true);
  });

  it('does not claim installation success before browser confirmation', async () => {
    const accepted = await requestLiteInstall({
      prompt: vi.fn(async () => {}),
      userChoice: Promise.resolve({ outcome: 'accepted' }),
    }, { storage: memoryStorage(), now: 1_000 });
    expect(accepted.status).toBe('accepted_pending_confirmation');

    const storage = memoryStorage();
    const dismissed = await requestLiteInstall({
      prompt: vi.fn(async () => {}),
      userChoice: Promise.resolve({ outcome: 'dismissed' }),
    }, { storage, now: 1_000 });
    expect(dismissed.status).toBe('dismissed');
    expect(canOfferLiteInstall({ promptAvailable: true, storage, now: 2_000 })).toBe(false);
  });

  it('derives a bounded badge only from fresh live network state and clears stale or offline state', async () => {
    const freshMeta = { source: 'network', stale: false, checkedAt: new Date(10_000).toISOString() };
    const queries = [
      query(['lite', 'security', 'progress'], { status: 'running', __liteSnapshot: freshMeta }),
      query(['lite', 'security', 'summary'], { active_scan: true, __liteSnapshot: freshMeta }),
      query(['lite', 'recovery', 'summary'], { status: 'running', __liteSnapshot: freshMeta }),
      query(['lite', 'fleet'], { devices: [{ status: 'repairing' }], __liteSnapshot: freshMeta }),
    ];
    expect(deriveLiteAppBadgeState(queries, { now: 20_000, maxCount: 2 })).toEqual({
      count: 2,
      active_domains: ['fleet', 'recovery'],
      source: 'fresh-current-state',
    });
    expect(deriveLiteAppBadgeState(queries, { online: false, now: 20_000 }).count).toBe(0);
    expect(deriveLiteAppBadgeState(queries, { now: 500_000 }).count).toBe(0);

    const navigatorObject = { setAppBadge: vi.fn(async () => {}), clearAppBadge: vi.fn(async () => {}) };
    expect((await applyLiteAppBadge(navigatorObject, 99, null)).count).toBe(9);
    expect((await applyLiteAppBadge(navigatorObject, 9, 9)).reason).toBe('unchanged');
    await applyLiteAppBadge(navigatorObject, 0, 9);
    expect(navigatorObject.clearAppBadge).toHaveBeenCalledTimes(1);
    expect((await applyLiteAppBadge({}, 1, null)).reason).toBe('unsupported');
  });

  it('shares only a sanitized same-origin screen link with clipboard fallback', async () => {
    expect(buildLiteSafeSharePayload({ origin: 'https://lab.example', screenId: 'security' })).toEqual({
      title: 'Pocket Lab Lite',
      text: 'Pocket Lab Lite — self-hosted workspace.',
      url: 'https://lab.example/?screen=security',
    });
    expect(buildLiteSafeSharePayload({ origin: 'javascript:alert(1)', screenId: 'security' })).toBeNull();
    expect(buildLiteSafeSharePayload({ origin: 'https://user:secret@lab.example', screenId: 'security' })).toBeNull();

    const clipboard = { writeText: vi.fn(async () => {}) };
    await expect(shareLiteSafeWorkspace({
      navigatorObject: { clipboard },
      origin: 'https://lab.example/private?token=hidden',
      screenId: 'devices',
    })).resolves.toEqual({ status: 'copied' });
    expect(clipboard.writeText).toHaveBeenCalledWith('https://lab.example/?screen=devices');

    await expect(shareLiteSafeWorkspace({
      navigatorObject: { share: vi.fn(async () => { throw Object.assign(new Error('cancelled'), { name: 'AbortError' }); }) },
      origin: 'https://lab.example',
    })).resolves.toEqual({ status: 'cancelled' });
  });
});

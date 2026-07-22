import { describe, expect, it, vi } from 'vitest';
import {
  createLiteChunkRecoveryController,
  createLiteScreenPreloader,
  isLiteChunkLoadError,
  litePreloadBlockReason,
  startLiteViewTransition,
} from './liteNavigationRuntime.js';
import { isLiteScreenId, normalizeLiteScreenId } from './liteNavigationConfig.js';

function visibleDocument(overrides = {}) {
  return { visibilityState: 'visible', ...overrides };
}

function onlineNavigator(overrides = {}) {
  return { onLine: true, connection: { saveData: false, effectiveType: '4g' }, ...overrides };
}

describe('Pocket Lab Lite N1 navigation runtime', () => {
  it('normalizes unknown screen ids to the stable default', () => {
    expect(isLiteScreenId('security')).toBe(true);
    expect(isLiteScreenId('unknown')).toBe(false);
    expect(normalizeLiteScreenId('unknown')).toBe('home');
  });

  it('deduplicates concurrent preloads and remembers loaded screens', async () => {
    const loader = vi.fn(async () => ({ default: () => null }));
    const preloader = createLiteScreenPreloader({
      loaders: { security: loader },
      navigatorObject: onlineNavigator(),
      documentObject: visibleDocument(),
    });

    const first = preloader.preload('security');
    const second = preloader.preload('security');
    expect(first).toBe(second);
    expect((await first).preloaded).toBe(true);
    expect(loader).toHaveBeenCalledTimes(1);
    expect((await preloader.preload('security')).reason).toBe('already_loaded');
  });

  it('blocks preload on hidden, data-saving, slow, and offline clients', () => {
    expect(litePreloadBlockReason({ navigatorObject: onlineNavigator(), documentObject: visibleDocument({ visibilityState: 'hidden' }) })).toBe('hidden_document');
    expect(litePreloadBlockReason({ navigatorObject: onlineNavigator({ connection: { saveData: true, effectiveType: '4g' } }), documentObject: visibleDocument() })).toBe('data_saver');
    expect(litePreloadBlockReason({ navigatorObject: onlineNavigator({ connection: { saveData: false, effectiveType: 'slow-2g' } }), documentObject: visibleDocument() })).toBe('slow_connection');
    expect(litePreloadBlockReason({ navigatorObject: onlineNavigator({ onLine: false }), documentObject: visibleDocument() })).toBe('offline');
  });

  it('falls back when View Transitions are unsupported or throw', () => {
    const unsupportedCommit = vi.fn();
    const unsupported = startLiteViewTransition(unsupportedCommit, { documentObject: {} });
    expect(unsupported.started).toBe(false);
    expect(unsupportedCommit).toHaveBeenCalledTimes(1);

    const throwingCommit = vi.fn();
    const throwing = startLiteViewTransition(throwingCommit, {
      documentObject: { startViewTransition: () => { throw new Error('not available'); } },
    });
    expect(throwing.reason).toBe('failed_safe');
    expect(throwingCommit).toHaveBeenCalledTimes(1);
  });

  it('honors reduced motion without invoking View Transitions', () => {
    const commit = vi.fn();
    const transition = vi.fn();
    const result = startLiteViewTransition(commit, {
      reducedMotion: true,
      documentObject: { startViewTransition: transition },
    });
    expect(result.reason).toBe('reduced_motion');
    expect(transition).not.toHaveBeenCalled();
    expect(commit).toHaveBeenCalledTimes(1);
  });

  it('reloads at most once per build for known chunk failures', () => {
    const values = new Map();
    const storage = {
      getItem: (key) => values.get(key) || null,
      setItem: (key, value) => values.set(key, value),
    };
    const locationObject = { reload: vi.fn() };
    const recovery = createLiteChunkRecoveryController({ buildId: 'build-123', storage, locationObject });
    const error = new Error('Failed to fetch dynamically imported module');

    expect(isLiteChunkLoadError(error)).toBe(true);
    expect(recovery.attempt(error)).toBe(true);
    expect(recovery.attempt(error)).toBe(false);
    expect(locationObject.reload).toHaveBeenCalledTimes(1);
  });
});

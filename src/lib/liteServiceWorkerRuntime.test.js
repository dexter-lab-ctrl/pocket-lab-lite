import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  announceLiteServiceWorkerUpdate,
  createLiteControlledServiceWorkerUpdate,
  applyLiteServiceWorkerUpdate,
  getLiteNavigationPreloadDiagnostics,
  getLiteServiceWorkerUpdateState,
  isLiteTextEntryElement,
  liteQueryCacheHasRiskyWorkflow,
  pruneLiteRuntimeCaches,
  resetLiteServiceWorkerRuntimeForTests,
  setLiteServiceWorkerUpdateBlocker,
} from './liteServiceWorkerRuntime.js';

describe('Lite service-worker runtime guards', () => {
  beforeEach(() => resetLiteServiceWorkerRuntimeForTests());

  it('defers a waiting update while a risky workflow is active', async () => {
    const apply = vi.fn(async () => true);
    announceLiteServiceWorkerUpdate(apply);
    setLiteServiceWorkerUpdateBlocker('security-scan', true);
    expect(getLiteServiceWorkerUpdateState().update_blocked).toBe(true);
    expect(await applyLiteServiceWorkerUpdate()).toBe(false);
    expect(apply).not.toHaveBeenCalled();
    setLiteServiceWorkerUpdateBlocker('security-scan', false);
    expect(await applyLiteServiceWorkerUpdate()).toBe(true);
    expect(apply).toHaveBeenCalledTimes(1);
  });

  it('keeps an update blocked from live TanStack workflow state after a lazy screen unmounts', () => {
    expect(liteQueryCacheHasRiskyWorkflow([
      { queryKey: ['lite', 'security', 'progress'], state: { data: { status: 'running', active_scan: true } } },
    ])).toBe(true);
    expect(liteQueryCacheHasRiskyWorkflow([
      { queryKey: ['lite', 'security', 'history'], state: { data: { status: 'running' } } },
      { queryKey: ['lite', 'recovery', 'summary'], state: { data: { status: 'ready' } } },
    ])).toBe(false);
    expect(liteQueryCacheHasRiskyWorkflow([
      { queryKey: ['lite', 'apps', 'lifecycle'], state: { data: { __liteSnapshot: { expired: true }, status: 'running' } } },
    ])).toBe(false);
  });


  it('activates a waiting worker with one confirmed controller-change reload', async () => {
    const listeners = new Map();
    const serviceWorker = {
      addEventListener: (name, listener) => listeners.set(name, listener),
      removeEventListener: (name, listener) => {
        if (listeners.get(name) === listener) listeners.delete(name);
      },
    };
    const values = new Map();
    const storage = {
      getItem: (key) => values.get(key) || null,
      setItem: (key, value) => values.set(key, String(value)),
    };
    const update = vi.fn(async () => true);
    const reload = vi.fn();
    const apply = createLiteControlledServiceWorkerUpdate({
      updateServiceWorker: update,
      navigatorObject: { serviceWorker },
      locationObject: { reload },
      sessionStorageObject: storage,
      buildId: 'build-42',
      timeoutMs: 2_000,
      now: () => 50_000,
    });

    const applying = apply();
    await Promise.resolve();
    expect(update).toHaveBeenCalledWith(false);
    listeners.get('controllerchange')?.();
    await expect(applying).resolves.toBe(true);
    expect(reload).toHaveBeenCalledTimes(1);
    await expect(apply()).resolves.toBe(false);
    expect(reload).toHaveBeenCalledTimes(1);
    expect(JSON.parse(values.get('pocketlab:lite-sw-controller-reload'))).toEqual({
      build_id: 'build-42',
      applied_at: 50_000,
    });
  });

  it('recognizes important text-entry targets for update deferral', () => {
    expect(isLiteTextEntryElement({ tagName: 'INPUT' })).toBe(true);
    expect(isLiteTextEntryElement({ tagName: 'TEXTAREA' })).toBe(true);
    expect(isLiteTextEntryElement({ tagName: 'DIV', isContentEditable: true })).toBe(true);
    expect(isLiteTextEntryElement({ tagName: 'BUTTON' })).toBe(false);
  });

  it('deletes only stale Pocket Lab runtime cache versions', async () => {
    const deleted = [];
    const result = await pruneLiteRuntimeCaches({
      keys: async () => [
        'pocketlab-lite-static-assets-v1',
        'pocketlab-lite-static-assets-v2',
        'pocketlab-lite-static-assets-v3',
        'unrelated-cache-v1',
      ],
      delete: async (name) => { deleted.push(name); return true; },
    });
    expect(deleted).toEqual(['pocketlab-lite-static-assets-v1']);
    expect(result.deleted).toBe(1);
  });

  it('falls back safely when Navigation Preload is unsupported', async () => {
    await expect(getLiteNavigationPreloadDiagnostics({})).resolves.toEqual(expect.objectContaining({
      navigation_preload_supported: false,
      navigation_preload_enabled: false,
    }));
  });

  it('reports Navigation Preload without exposing request data', async () => {
    const diagnostics = await getLiteNavigationPreloadDiagnostics({
      serviceWorker: {
        ready: Promise.resolve({
          navigationPreload: { getState: async () => ({ enabled: true, headerValue: 'private' }) },
        }),
      },
    });
    expect(diagnostics.navigation_preload_supported).toBe(true);
    expect(diagnostics.navigation_preload_enabled).toBe(true);
    expect(diagnostics).not.toHaveProperty('headerValue');
  });
});

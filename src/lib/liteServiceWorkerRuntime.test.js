import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  announceLiteServiceWorkerUpdate,
  applyLiteServiceWorkerUpdate,
  getLiteNavigationPreloadDiagnostics,
  getLiteServiceWorkerUpdateState,
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

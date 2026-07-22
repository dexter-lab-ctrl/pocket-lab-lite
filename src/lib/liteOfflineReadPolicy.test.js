import { describe, expect, it } from 'vitest';
import {
  classifyLiteSafeReadResponse,
  createLiteSafeReadNonce,
  isLitePwaNavigationPath,
  isLiteSafeRuntimeRead,
  liteSafeHistorySchemaCompatible,
  LITE_SAFE_HISTORY_CACHE_SCHEMA_VERSION,
} from './liteOfflineReadPolicy.js';

describe('Lite offline read policy', () => {
  it('allows only reviewed sanitized GET routes', () => {
    expect(isLiteSafeRuntimeRead({ method: 'GET', path: '/api/lite/security/history?limit=20' })).toBe(true);
    expect(isLiteSafeRuntimeRead({ method: 'GET', path: '/api/lite/recovery/backups?limit=10' })).toBe(true);
    expect(isLiteSafeRuntimeRead({ method: 'POST', path: '/api/lite/security/history' })).toBe(false);
    expect(isLiteSafeRuntimeRead({ method: 'GET', path: '/api/lite/device/invites' })).toBe(false);
    expect(isLiteSafeRuntimeRead({ method: 'GET', path: '/api/lite/fleet' })).toBe(false);
    expect(isLiteSafeRuntimeRead({ method: 'GET', path: '/api/lite/recovery/details' })).toBe(false);
    expect(isLiteSafeRuntimeRead({ method: 'GET', path: '/api/lite/security/evidence/run-1' })).toBe(false);
    expect(isLiteSafeRuntimeRead({ method: 'GET', path: '/api/lite/apps/photoprism/backups/one/receipt' })).toBe(false);
  });


  it('marks service-worker cache fallbacks without exposing payload data', () => {
    const nonce = createLiteSafeReadNonce({
      getRandomValues(values) {
        values[0] = 123;
        values[1] = 456;
        return values;
      },
    });
    expect(nonce).toMatch(/^plr-[a-z0-9-]+$/);
    expect(classifyLiteSafeReadResponse({ requestNonce: nonce, responseNonce: nonce, serviceWorkerControlled: true })).toBe('network');
    expect(classifyLiteSafeReadResponse({ requestNonce: nonce, responseNonce: 'older-response', serviceWorkerControlled: true })).toBe('http-cache');
    expect(classifyLiteSafeReadResponse({ requestNonce: nonce, responseNonce: '', serviceWorkerControlled: true })).toBe('http-cache');
    expect(classifyLiteSafeReadResponse({ requestNonce: nonce, responseNonce: '', serviceWorkerControlled: false })).toBe('network');
  });

  it('keeps application routes outside PWA navigation handling', () => {
    expect(isLitePwaNavigationPath('/')).toBe(true);
    expect(isLitePwaNavigationPath('/app-workspace/photoprism')).toBe(true);
    expect(isLitePwaNavigationPath('/apps/photoprism/')).toBe(false);
    expect(isLitePwaNavigationPath('/api/lite/status')).toBe(false);
  });

  it('drops incompatible safe-history schemas', () => {
    expect(liteSafeHistorySchemaCompatible({ cache_schema_version: LITE_SAFE_HISTORY_CACHE_SCHEMA_VERSION })).toBe(true);
    expect(liteSafeHistorySchemaCompatible({ cache_schema_version: LITE_SAFE_HISTORY_CACHE_SCHEMA_VERSION - 1 })).toBe(false);
    expect(liteSafeHistorySchemaCompatible({})).toBe(false);
  });
});

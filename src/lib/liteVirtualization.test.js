import { beforeEach, describe, expect, it } from 'vitest';
import {
  clearLiteVirtualScrollState,
  createLiteCursorRequestGuard,
  liteStableRowKey,
  mergeLiteCursorPages,
  normalizeLiteVirtualRows,
  readLiteVirtualScrollState,
  saveLiteVirtualScrollState,
  selectLiteVirtualMode,
} from './liteVirtualization.js';

describe('Lite virtualization policy', () => {
  beforeEach(() => clearLiteVirtualScrollState());

  it('uses hysteresis instead of oscillating around the threshold', () => {
    expect(selectLiteVirtualMode({ count: 35, domain: 'securityHistory' })).toBe(false);
    expect(selectLiteVirtualMode({ count: 36, domain: 'securityHistory' })).toBe(true);
    expect(selectLiteVirtualMode({ count: 32, domain: 'securityHistory', previousMode: true })).toBe(true);
    expect(selectLiteVirtualMode({ count: 28, domain: 'securityHistory', previousMode: true })).toBe(false);
  });

  it('uses durable IDs and deterministic fallbacks', () => {
    expect(liteStableRowKey({ run_id: 'security-123' }, { domain: 'securityHistory' }))
      .toMatch(/^securityhistory:run_id:[a-z0-9]+-security-123$/);
    const first = liteStableRowKey({ title: 'Saved run', completed_at: '2026-07-20T00:00:00Z' }, { domain: 'history' });
    const second = liteStableRowKey({ title: 'Saved run', completed_at: '2026-07-20T00:00:00Z' }, { domain: 'history' });
    expect(first).toBe(second);
    expect(first).toContain('fallback');
  });

  it('deduplicates repeated rows and cursor pages without reordering them', () => {
    const normalized = normalizeLiteVirtualRows([
      { run_id: 'run-2' },
      { run_id: 'run-2' },
      { run_id: 'run-1' },
    ], { domain: 'securityHistory' });
    expect(normalized.rows.map((row) => row.run_id)).toEqual(['run-2', 'run-1']);
    expect(normalized.duplicateCount).toBe(1);

    const merged = mergeLiteCursorPages([
      { history: [{ run_id: 'run-3' }, { run_id: 'run-2' }] },
      { history: [{ run_id: 'run-2' }, { run_id: 'run-1' }] },
    ], { domain: 'securityHistory' });
    expect(merged.rows.map((row) => row.run_id)).toEqual(['run-3', 'run-2', 'run-1']);
  });


  it('preserves repeated ID-less rows while reporting fallback collisions', () => {
    const normalized = normalizeLiteVirtualRows([
      { title: 'Same summary', completed_at: '2026-07-20T00:00:00Z' },
      { title: 'Same summary', completed_at: '2026-07-20T00:00:00Z' },
    ], { domain: 'history' });
    expect(normalized.rows).toHaveLength(2);
    expect(new Set(normalized.keys).size).toBe(2);
    expect(normalized.duplicateCount).toBe(0);
    expect(normalized.fallbackCollisionCount).toBe(1);
  });

  it('guards repeated cursor requests until the current request finishes', () => {
    const guard = createLiteCursorRequestGuard();
    expect(guard.begin('cursor-1')).toBe(true);
    expect(guard.begin('cursor-1')).toBe(false);
    guard.finish('cursor-1');
    expect(guard.begin('cursor-1')).toBe(true);
    guard.clear();
    expect(guard.size()).toBe(0);
  });

  it('keys scroll state by domain and dataset identity', () => {
    saveLiteVirtualScrollState('securityHistory', 'quick', 640);
    saveLiteVirtualScrollState('securityHistory', 'full', 120);
    expect(readLiteVirtualScrollState('securityHistory', 'quick')).toBe(640);
    expect(readLiteVirtualScrollState('securityHistory', 'full')).toBe(120);
    expect(readLiteVirtualScrollState('recoveryHistory', 'quick')).toBe(0);
  });
});

import { describe, expect, it } from 'vitest';
import { systemHealthPresentation } from './LiteSystemHealth.jsx';

describe('System Health authoritative presentation', () => {
  it('never labels missing data healthy', () => {
    expect(systemHealthPresentation(undefined).state).toBe('unknown');
  });
  it('renders stale or offline data as saved', () => {
    expect(systemHealthPresentation({ status: 'healthy', freshness: 'stale' }).state).toBe('saved');
    expect(systemHealthPresentation({ status: 'healthy', freshness: 'current' }, true).state).toBe('saved');
  });
  it('keeps unavailable evidence distinct from saved information', () => {
    const result = systemHealthPresentation({ status: 'unknown', freshness: 'unavailable', summary: 'Health evidence is unavailable.' });
    expect(result.state).toBe('unknown');
    expect(result.title).toMatch(/needs confirmation/i);
  });
  it('uses observed unknown counts to avoid false green', () => {
    expect(systemHealthPresentation({ status: 'healthy', freshness: 'current', unknown_services: 2 }).state).toBe('unknown');
  });
  it('reports attention only when backend indicates a real problem', () => {
    expect(systemHealthPresentation({ status: 'attention', freshness: 'current', active_problems: 1 }).state).toBe('attention');
  });
  it('shows verified observations without claiming repair succeeded', () => {
    const result = systemHealthPresentation({ status: 'healthy', freshness: 'current', unknown_services: 0 });
    expect(result.state).toBe('ready');
    expect(result.title).toMatch(/observed/i);
  });
});

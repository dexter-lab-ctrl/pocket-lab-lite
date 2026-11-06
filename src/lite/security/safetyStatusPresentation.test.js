import { describe, expect, it } from 'vitest';
import { deriveSafetyStatusPresentation, safetyToolPresentation } from './safetyStatusPresentation.js';

// Unit coverage for scanner-state presentation; fixtures remain synthetic and read-only.
// Inputs model sanitized FastAPI data; they are not synthetic production results.
const checked = {
  lynis: { status: 'completed' },
  trivy: { status: 'completed' },
};

describe('Safety scanner authority', () => {
  it('never presents an unscanned profile as a completed clean check', () => {
    const view = deriveSafetyStatusPresentation({ hasRun: false, coverageReported: false });
    expect(view.headline).toBe('Not checked');
    expect(view.findingLabel).toBe('Critical finding assessment not final');
    expect(view.fullyReported).toBe(false);
  });

  it.each(['queued', 'accepted', 'running', 'working', 'in_progress', 'pending'])(
    'preserves pending execution for %s without manufacturing a clean outcome',
    (status) => {
      const view = deriveSafetyStatusPresentation({ status, hasRun: true, coverageReported: true });
      expect(view.headline).toBe('Safety check in progress');
      expect(view.findingLabel).not.toContain('No critical');
      expect(view.scanners.every((scanner) => scanner.complete === false)).toBe(true);
    },
  );

  it('requires both scanner completion and reported coverage for a full outcome', () => {
    const completed = deriveSafetyStatusPresentation({
      status: 'completed', hasRun: true, toolResults: checked, coverageReported: true,
    });
    expect(completed.fullyReported).toBe(true);
    expect(completed.findingLabel).toBe('No critical findings reported');
    const unreported = deriveSafetyStatusPresentation({
      status: 'completed', hasRun: true, toolResults: {}, coverageReported: true,
    });
    expect(unreported.fullyReported).toBe(false);
    expect(unreported.findingLabel).toBe('Critical finding assessment not final');
  });

  it('keeps findings visible and labels partial source evidence accurately', () => {
    const view = deriveSafetyStatusPresentation({
      status: 'partial', hasRun: true, toolResults: { lynis: { status: 'completed' }, trivy: { status: 'timed_out' } },
      criticalCount: 2, coverageReported: true,
    });
    expect(view.fullyReported).toBe(false);
    expect(view.findingLabel).toBe('2 critical findings reported so far');
    expect(view.scanners.find((scanner) => scanner.name === 'Trivy').status).toBe('Incomplete');
  });

  it.each(['failed', 'cancelled'])('preserves terminal %s instead of success', (status) => {
    const view = deriveSafetyStatusPresentation({ status, hasRun: true, criticalCount: 0, toolResults: checked, coverageReported: true });
    expect(view.fullyReported).toBe(false);
    expect(view.findingLabel).not.toContain('No critical');
  });

  it('keeps saved and offline data visibly provisional', () => {
    const view = deriveSafetyStatusPresentation({
      status: 'completed', hasRun: true, toolResults: checked, coverageReported: true, offline: true,
    });
    expect(view.headline).toBe('Saved safety result');
    expect(view.tone).toBe('neutral');
  });

  it('uses app-specific scanner requirements without inventing Lynis execution', () => {
    const view = deriveSafetyStatusPresentation({
      status: 'completed', hasRun: true, profile: 'app', toolResults: { trivy: { status: 'done' } }, coverageReported: true,
    });
    expect(view.scanners.map((scanner) => scanner.name)).toEqual(['Trivy']);
    expect(view.fullyReported).toBe(true);
  });

  it('does not treat a terminal run status as proof a scanner ran', () => {
    expect(safetyToolPresentation('Lynis', {}, [], 'completed').status).toBe('Not reported');
    expect(safetyToolPresentation('Trivy', { status: 'missing_tool' }).status).toBe('Unavailable');
  });
});

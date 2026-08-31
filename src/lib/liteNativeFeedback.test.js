import { afterEach, describe, expect, it, vi } from 'vitest';
import { createLiteFeedbackDeduper, triggerLiteHaptic } from './liteNativeFeedback.js';

const originalNavigator = globalThis.navigator;
const originalDocument = globalThis.document;
const originalWindow = globalThis.window;

function setVisibility(value) {
  Object.defineProperty(globalThis.document, 'visibilityState', { configurable: true, value });
}

function installBrowser(vibrate = vi.fn(() => true)) {
  Object.defineProperty(globalThis, 'navigator', { configurable: true, value: { vibrate } });
  Object.defineProperty(globalThis, 'document', { configurable: true, value: { visibilityState: 'visible' } });
  Object.defineProperty(globalThis, 'window', { configurable: true, value: { matchMedia: vi.fn(() => ({ matches: false })) } });
  return vibrate;
}

afterEach(() => {
  Object.defineProperty(globalThis, 'navigator', { configurable: true, value: originalNavigator });
  Object.defineProperty(globalThis, 'document', { configurable: true, value: originalDocument });
  Object.defineProperty(globalThis, 'window', { configurable: true, value: originalWindow });
});

describe('Lite native feedback', () => {
  it('is a no-op when vibration is unavailable, the page is hidden, or reduced motion is requested', () => {
    installBrowser(null);
    expect(triggerLiteHaptic('accepted')).toBe(false);

    const vibrate = vi.fn(() => true);
    installBrowser(vibrate);
    setVisibility('hidden');
    expect(triggerLiteHaptic('success')).toBe(false);
    expect(vibrate).not.toHaveBeenCalled();

    setVisibility('visible');
    window.matchMedia = vi.fn(() => ({ matches: true }));
    expect(triggerLiteHaptic('warning')).toBe(false);
    expect(vibrate).not.toHaveBeenCalled();
  });

  it('uses bounded semantic patterns and safely falls back for unknown kinds', () => {
    const vibrate = installBrowser();

    expect(triggerLiteHaptic('accepted')).toBe(true);
    expect(triggerLiteHaptic('success')).toBe(true);
    expect(triggerLiteHaptic('blocked')).toBe(true);
    expect(triggerLiteHaptic('unknown')).toBe(true);
    expect(vibrate.mock.calls).toEqual([[10], [[10, 30, 14]], [[18, 35, 18]], [10]]);
  });

  it('deduplicates a completed event without persisting payloads', () => {
    const vibrate = installBrowser();
    const deduper = createLiteFeedbackDeduper(2);

    expect(deduper.trigger('security-run-1', 'success')).toBe(true);
    expect(deduper.trigger('security-run-1', 'success')).toBe(false);
    expect(deduper.trigger('security-run-2', 'warning')).toBe(true);
    expect(vibrate).toHaveBeenCalledTimes(2);
  });

  it('keeps visual completion claims usable when vibration is unavailable', () => {
    installBrowser(null);
    const deduper = createLiteFeedbackDeduper();

    expect(deduper.once('backup-run-1', 'success')).toBe(true);
    expect(deduper.once('backup-run-1', 'success')).toBe(false);
  });
});

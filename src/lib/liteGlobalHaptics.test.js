// @vitest-environment jsdom
// Source-authored global feedback coverage. Deliberately NOT executed in PR #640.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { installLiteGlobalHaptics, liteHapticTarget } from './liteGlobalHaptics.js';

let dispose;
let vibrate;
beforeEach(() => {
  document.body.innerHTML = '';
  vibrate = vi.fn(() => true);
  Object.defineProperty(navigator, 'vibrate', { configurable: true, value: vibrate });
  window.matchMedia = vi.fn(() => ({ matches: false }));
  dispose = installLiteGlobalHaptics(document, window);
});
afterEach(() => {
  dispose?.();
  document.body.innerHTML = '';
  vi.restoreAllMocks();
});

function click(control, detail = 0) {
  control.dispatchEvent(new MouseEvent('click', { bubbles: true, detail }));
}

describe('Global Lite button/tab/navigation haptics — source only', () => {
  it('covers ordinary buttons and late-mounted dialogs without wrapping each screen', () => {
    const button = document.createElement('button');
    button.textContent = 'Open Devices';
    document.body.appendChild(button);
    click(button);
    expect(vibrate).toHaveBeenCalledWith(8);
  });
  it('recognizes nested navigation tab glyphs as one control', () => {
    const nav = document.createElement('nav');
    const tab = document.createElement('button');
    tab.setAttribute('role', 'tab');
    const glyph = document.createElement('span');
    tab.appendChild(glyph); nav.appendChild(tab); document.body.appendChild(nav);
    expect(liteHapticTarget({ target: glyph })).toBe(tab);
    click(glyph);
    expect(vibrate).toHaveBeenCalledTimes(1);
  });
  it('rejects disabled, inert, busy, opt-out and manually-owned controls', () => {
    const button = document.createElement('button');
    document.body.appendChild(button);
    for (const attribute of ['disabled','aria-disabled','aria-busy','data-lite-haptic']) {
      button.removeAttribute('disabled'); button.removeAttribute('aria-disabled');
      button.removeAttribute('aria-busy'); button.removeAttribute('data-lite-haptic');
      button.setAttribute(attribute,
        attribute === 'data-lite-haptic' ? 'manual' : attribute === 'disabled' ? '' : 'true');
      expect(liteHapticTarget({ target: button })).toBeNull();
      click(button);
    }
    expect(vibrate).not.toHaveBeenCalled();
  });
  it('does not vibrate for ordinary non-interactive card clicks', () => {
    const card = document.createElement('div');
    card.textContent = 'Saved device status'; document.body.appendChild(card);
    click(card);
    expect(vibrate).not.toHaveBeenCalled();
  });
  it('deduplicates installation, without stacking document listeners', () => {
    const otherDispose = installLiteGlobalHaptics(document, window);
    const button = document.createElement('button'); document.body.appendChild(button);
    click(button);
    expect(vibrate).toHaveBeenCalledTimes(1);
    expect(otherDispose).toBe(dispose);
  });
  it('does not vibrate when the browser lacks navigator.vibrate', () => {
    Object.defineProperty(navigator, 'vibrate', { configurable: true, value: undefined });
    const button = document.createElement('button'); document.body.appendChild(button);
    expect(() => click(button)).not.toThrow();
  });
  it('delegates one haptic to late-mounted Safety navigation and disclosure in a portal', () => {
    const portal = document.createElement('div');
    portal.setAttribute('data-lite-overlay-portal', 'true');
    portal.innerHTML = '<button aria-label="Open Safety history"><span>History</span></button>';
    document.body.appendChild(portal);
    click(portal.querySelector('span'));
    click(portal.querySelector('span')); // global 65ms deduplication
    expect(vibrate).toHaveBeenCalledTimes(1);
  });

  it('does not vibrate for passive Safety status, drag grip, or disabled snap controls', () => {
    const portal = document.createElement('div');
    portal.innerHTML = '<p aria-live="polite">Scanner pending</p><button data-lite-haptic="off">Drag grip</button><button disabled>Expand</button>';
    document.body.appendChild(portal);
    click(portal.querySelector('p'));
    click(portal.querySelector('[data-lite-haptic="off"]'));
    click(portal.querySelector('[disabled]'));
    expect(vibrate).not.toHaveBeenCalled();
  });

});

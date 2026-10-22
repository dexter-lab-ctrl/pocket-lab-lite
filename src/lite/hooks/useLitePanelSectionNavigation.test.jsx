// @vitest-environment jsdom
import React from 'react';
import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  nextLitePanelNavState, useLitePanelSectionNavigation,
} from './useLitePanelSectionNavigation.js';

afterEach(cleanup);

describe('shared Home panel navigation scroll state', () => {
  it('retracts past the hysteresis threshold, reveals on direction reversal, and resets at top', () => {
    const initial = { baseline: 0, hidden: false, scrolled: false };
    expect(nextLitePanelNavState(initial, 11).hidden).toBe(false);
    const hidden = nextLitePanelNavState(initial, 100);
    expect(hidden).toMatchObject({ hidden: true, scrolled: true });
    expect(nextLitePanelNavState(hidden, 94).hidden).toBe(true);
    expect(nextLitePanelNavState(hidden, 50).hidden).toBe(false);
    expect(nextLitePanelNavState(hidden, 0)).toMatchObject({ hidden: false, scrolled: false });
  });
  it('never hides tabs while they contain keyboard focus', () => {
    expect(nextLitePanelNavState({ baseline: 0, hidden: true, scrolled: true }, 100, true).hidden).toBe(false);
  });
  it('listens to the panel body, not window, and cleans listeners on close', () => {
    const { result, rerender, unmount } = renderHook(({ open }) => useLitePanelSectionNavigation(open), {
      initialProps: { open: false },
    });
    const body = document.createElement('div');
    const nav = document.createElement('nav');
    const tab = document.createElement('button');
    nav.append(tab);
    body.append(nav);
    document.body.append(body);
    result.current.bodyRef.current = body;
    result.current.navRef.current = nav;
    const add = vi.spyOn(body, 'addEventListener');
    const remove = vi.spyOn(body, 'removeEventListener');
    rerender({ open: true });
    expect(add).toHaveBeenCalledWith('scroll', expect.any(Function), { passive: true });
    act(() => { body.scrollTop = 120; body.dispatchEvent(new Event('scroll')); });
    expect(result.current.hidden).toBe(true);
    act(() => { tab.dispatchEvent(new Event('focusin', { bubbles: true })); });
    expect(result.current.hidden).toBe(false);
    act(() => { body.scrollTop = 0; result.current.reveal(true); });
    expect(result.current.scrolled).toBe(false);
    unmount();
    expect(remove).toHaveBeenCalledWith('scroll', expect.any(Function));
    body.remove();
  });
});

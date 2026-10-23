// @vitest-environment jsdom
import React from 'react';
import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { nextLitePanelNavState, useLitePanelSectionNavigation } from './useLitePanelSectionNavigation.js';

afterEach(cleanup);

function mountedNav() {
  const body = document.createElement('div');
  const nav = document.createElement('nav');
  const tab = document.createElement('button');
  nav.append(tab);
  body.append(nav);
  document.body.append(body);
  return { body, nav, tab, remove: () => body.remove() };
}

describe('shared Home panel navigation scroll state', () => {
  it('retracts past threshold, reveals on upward travel and stays visible near the top', () => {
    const initial = { baseline: 0, hidden: false, scrolled: false };
    expect(nextLitePanelNavState(initial, 11).hidden).toBe(false);
    const hidden = nextLitePanelNavState(initial, 100);
    expect(hidden).toMatchObject({ hidden: true, scrolled: true });
    expect(nextLitePanelNavState(hidden, 94).hidden).toBe(true);
    expect(nextLitePanelNavState(hidden, 50).hidden).toBe(false);
    expect(nextLitePanelNavState(hidden, 0)).toMatchObject({ hidden: false, scrolled: false });
  });
  it('uses keyboard focus, not incidental pointer focus, as the visibility lock', () => {
    const hidden = { baseline: 20, hidden: true, scrolled: true };
    expect(nextLitePanelNavState(hidden, 100, true).hidden).toBe(false);
    expect(nextLitePanelNavState(hidden, 100, false).hidden).toBe(true);
  });
  it('attaches passive listeners only to the active panel body and cleans them', () => {
    const { result, rerender, unmount } = renderHook(({ open }) => useLitePanelSectionNavigation(open), {
      initialProps: { open: false },
    });
    const { body, nav, remove } = mountedNav();
    result.current.bodyRef.current = body;
    result.current.navRef.current = nav;
    const add = vi.spyOn(body, 'addEventListener');
    const detach = vi.spyOn(body, 'removeEventListener');
    rerender({ open: true });
    expect(add).toHaveBeenCalledWith('scroll', expect.any(Function), { passive: true });
    expect(add).toHaveBeenCalledWith('wheel', expect.any(Function), { passive: true });
    expect(add).toHaveBeenCalledWith('touchstart', expect.any(Function), { passive: true });
    act(() => { body.scrollTop = 120; body.dispatchEvent(new Event('scroll')); });
    expect(result.current.hidden).toBe(true);
    act(() => result.current.reveal(true));
    expect(body.scrollTop).toBe(0);
    expect(result.current.scrolled).toBe(false);
    unmount();
    expect(detach).toHaveBeenCalledWith('scroll', expect.any(Function));
    expect(detach).toHaveBeenCalledWith('wheel', expect.any(Function));
    remove();
  });
  it('does not let touch-retained focus pin the navigation while momentum continues', () => {
    const { result, rerender, unmount } = renderHook(({ open }) => useLitePanelSectionNavigation(open), {
      initialProps: { open: false },
    });
    const { body, nav, tab, remove } = mountedNav();
    result.current.bodyRef.current = body;
    result.current.navRef.current = nav;
    rerender({ open: true });
    act(() => {
      tab.dispatchEvent(new Event('pointerdown', { bubbles: true }));
      tab.focus();
      body.scrollTop = 110;
      body.dispatchEvent(new Event('scroll'));
    });
    expect(document.activeElement).toBe(tab);
    expect(result.current.keyboardFocused).toBe(false);
    expect(result.current.hidden).toBe(true);
    act(() => { body.scrollTop = 60; body.dispatchEvent(new Event('scroll')); });
    expect(result.current.hidden).toBe(false);
    unmount();
    remove();
  });
  it('reveals keyboard-focused navigation and releases the lock on wheel input', () => {
    const { result, rerender, unmount } = renderHook(({ open }) => useLitePanelSectionNavigation(open), {
      initialProps: { open: false },
    });
    const { body, nav, tab, remove } = mountedNav();
    result.current.bodyRef.current = body;
    result.current.navRef.current = nav;
    rerender({ open: true });
    act(() => { body.scrollTop = 140; body.dispatchEvent(new Event('scroll')); });
    expect(result.current.hidden).toBe(true);
    act(() => {
      tab.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true }));
      tab.focus();
    });
    expect(result.current.hidden).toBe(false);
    expect(result.current.keyboardFocused).toBe(true);
    act(() => {
      body.dispatchEvent(new WheelEvent('wheel', { bubbles: true }));
      body.scrollTop = 190;
      body.dispatchEvent(new Event('scroll'));
    });
    expect(result.current.hidden).toBe(true);
    expect(result.current.keyboardFocused).toBe(false);
    unmount();
    remove();
  });
  it('ignores nested independent scrolling and resets on reopening', () => {
    const { result, rerender, unmount } = renderHook(({ open }) => useLitePanelSectionNavigation(open), {
      initialProps: { open: false },
    });
    const { body, nav, remove } = mountedNav();
    const nested = document.createElement('div');
    body.append(nested);
    result.current.bodyRef.current = body;
    result.current.navRef.current = nav;
    rerender({ open: true });
    act(() => { nested.scrollTop = 160; nested.dispatchEvent(new Event('scroll')); });
    expect(result.current.hidden).toBe(false);
    act(() => { body.scrollTop = 120; body.dispatchEvent(new Event('scroll')); });
    expect(result.current.hidden).toBe(true);
    rerender({ open: false });
    expect(result.current.hidden).toBe(false);
    rerender({ open: true });
    expect(result.current.hidden).toBe(false);
    unmount();
    remove();
  });
});

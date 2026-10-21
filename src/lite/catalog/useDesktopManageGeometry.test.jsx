// @vitest-environment jsdom
import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { clampManageGeometry, defaultManageGeometry, useDesktopManageGeometry } from '../components/useDesktopManageGeometry.js';

describe('shared Devices + Apps desktop geometry', () => {
  let originalMatchMedia;
  beforeEach(() => {
    originalMatchMedia = window.matchMedia;
    window.matchMedia = vi.fn(() => ({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
  });
  afterEach(() => { window.matchMedia = originalMatchMedia; });
  it('clamps dimensions and position to the visible viewport', () => {
    const value = clampManageGeometry({left: -9999,top: -9999,width: 20000,height: 20000});
    expect(value.left).toBeGreaterThanOrEqual(0);
    expect(value.top).toBeGreaterThanOrEqual(0);
    expect(value.left + value.width).toBeLessThanOrEqual(innerWidth);
    expect(value.top + value.height).toBeLessThanOrEqual(innerHeight);
  });
  it('respects minimum dimensions where viewport space permits', () => {
    const value = clampManageGeometry({left:0,top:0,width:20,height:20});
    expect(value.width).toBeGreaterThanOrEqual(Math.min(360, innerWidth - 32));
    expect(value.height).toBeGreaterThanOrEqual(Math.min(360, innerHeight - 32));
  });
  it('creates a default right-aligned desktop panel with no persistent state', () => {
    const initial = defaultManageGeometry({defaultWidth:620});
    expect(initial).toMatchObject({width:expect.any(Number),height:expect.any(Number)});
    expect(initial.left + initial.width).toBeLessThanOrEqual(innerWidth);
  });
  it('exposes keyboard movement, resizing and reset for both Manage surfaces', () => {
    const {result} = renderHook(() => useDesktopManageGeometry({open:true,defaultWidth:620}));
    const first = result.current.geometry;
    expect(result.current.desktopPanel).toBe(true);
    const event = {key:'ArrowLeft',shiftKey:false,preventDefault:vi.fn()};
    act(() => result.current.adjustPanelWithKeyboard('move',event));
    expect(event.preventDefault).toHaveBeenCalled();
    expect(result.current.geometry.left).toBeLessThanOrEqual(first.left);
    act(() => result.current.adjustPanelWithKeyboard('resize',{key:'ArrowDown',shiftKey:true,preventDefault:vi.fn()}));
    expect(result.current.geometry.height).toBeGreaterThanOrEqual(first.height);
    act(() => result.current.reset());
    expect(result.current.geometry).toEqual(defaultManageGeometry({defaultWidth:620}));
  });
  it('drops desktop transforms and handles at mobile breakpoint', () => {
    window.matchMedia = vi.fn(() => ({matches:false,addEventListener:vi.fn(),removeEventListener:vi.fn()}));
    const {result} = renderHook(() => useDesktopManageGeometry({open:true}));
    expect(result.current.desktopPanel).toBe(false);
    expect(result.current.panelStyle).toBeUndefined();
  });
});

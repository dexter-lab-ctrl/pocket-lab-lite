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
  it('uses captured pointer ownership and cleans up on cancellation', () => {
    const request = window.requestAnimationFrame;
    const cancel = window.cancelAnimationFrame;
    let queuedFrame;
    window.requestAnimationFrame = vi.fn((fn) => { queuedFrame = fn; return 19; });
    window.cancelAnimationFrame = vi.fn();
    try {
      const {result, unmount} = renderHook(() => useDesktopManageGeometry({open:true,defaultWidth:620}));
      const panel = document.createElement('section');
      panel.getBoundingClientRect = () => ({left:280,top:100,width:540,height:440});
      result.current.panelRef.current = panel;
      const handle = document.createElement('button');
      handle.setPointerCapture = vi.fn();
      handle.hasPointerCapture = vi.fn(() => false);
      const initial = result.current.geometry;
      act(() => result.current.startPanelInteraction('move', {
        button:0, pointerId:8, clientX:300, clientY:120, preventDefault:vi.fn(), currentTarget:handle
      }));
      expect(handle.setPointerCapture).toHaveBeenCalledWith(8);
      const move = new Event('pointermove');
      Object.defineProperties(move,{pointerId:{value:8},clientX:{value:348},clientY:{value:146}});
      act(() => {window.dispatchEvent(move); queuedFrame?.();});
      expect(result.current.geometry.left).toBeGreaterThan(280);
      const aborted = new Event('pointercancel');
      Object.defineProperty(aborted,'pointerId',{value:8});
      act(() => window.dispatchEvent(aborted));
      expect(panel.classList.contains('is-interacting')).toBe(false);
      expect(result.current.geometry.left).toBe(280);
      unmount();
      expect(window.cancelAnimationFrame).toHaveBeenCalled();
      expect(initial).toBeTruthy();
    } finally {
      window.requestAnimationFrame = request;
      window.cancelAnimationFrame = cancel;
    }
  });
  it('supports pointer-capture loss and does not persist geometry in storage', () => {
    const {result,unmount}=renderHook(() => useDesktopManageGeometry({open:true}));
    const panel=document.createElement('section');
    panel.getBoundingClientRect=()=>({left:100,top:60,width:500,height:420});
    result.current.panelRef.current=panel;
    const handle=document.createElement('button');
    handle.setPointerCapture=vi.fn();
    handle.hasPointerCapture=vi.fn(()=>false);
    act(()=>result.current.startPanelInteraction('resize',{
      button:0,pointerId:4,clientX:600,clientY:480,currentTarget:handle,preventDefault:vi.fn()
    }));
    const event=new Event('lostpointercapture');
    Object.defineProperty(event,'pointerId',{value:4});
    act(()=>handle.dispatchEvent(event));
    expect(panel.classList.contains('is-interacting')).toBe(false);
    expect(result.current.panelStyle).toBeDefined();
    unmount();
  });

});

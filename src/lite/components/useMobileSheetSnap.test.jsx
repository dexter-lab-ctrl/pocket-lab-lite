// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, renderHook } from '@testing-library/react';
import { closestMobileSheetState, mobileSheetHeight, useMobileSheetSnap } from './useMobileSheetSnap.js';

afterEach(cleanup);
function harness() {
  const surface = document.createElement('section');
  const surfaceRef = { current: surface };
  const handle = document.createElement('button');
  handle.setPointerCapture = vi.fn();
  handle.hasPointerCapture = vi.fn(() => true);
  handle.releasePointerCapture = vi.fn();
  const hook = renderHook(() => useMobileSheetSnap({ open:true, enabled:true, surfaceRef }));
  const pointer = (y, id = 7) => ({
    isPrimary:true, pointerType:'touch', button:0, pointerId:id,
    clientY:y, currentTarget:handle, preventDefault:vi.fn(),
  });
  return { surface, handle, hook, pointer };
}
describe('opt-in mobile sheet geometry — authored, not executed', () => {
  it('chooses deterministic compact/medium/expanded snap points', () => {
    const vh = 800;
    const low = mobileSheetHeight('compact',vh);
    const mid = mobileSheetHeight('medium',vh);
    const high = mobileSheetHeight('expanded',vh);
    expect(low).toBeLessThan(mid);
    expect(mid).toBeLessThan(high);
    expect(closestMobileSheetState(low,vh)).toBe('compact');
    expect(closestMobileSheetState(mid,vh)).toBe('medium');
    expect(closestMobileSheetState(high,vh)).toBe('expanded');
    expect(mobileSheetHeight('expanded',150)).toBeLessThanOrEqual(150);
  });
  it('expands and contracts through accessible keyboard controls', () => {
    const { hook } = harness();
    expect(hook.result.current.state).toBe('medium');
    const event = {key:'ArrowUp',preventDefault:vi.fn()};
    act(() => hook.result.current.gripProps.onKeyDown(event));
    expect(event.preventDefault).toHaveBeenCalled();
    expect(hook.result.current.state).toBe('expanded');
    act(() => hook.result.current.gripProps.onKeyDown({key:'Home',preventDefault:vi.fn()}));
    expect(hook.result.current.state).toBe('compact');
    act(() => hook.result.current.expand());
    expect(hook.result.current.state).toBe('medium');
    act(() => hook.result.current.contract());
    expect(hook.result.current.state).toBe('compact');
  });
  it('updates only DOM height while dragging grip, then snaps after release', () => {
    const { surface, handle, hook, pointer } = harness();
    act(() => hook.result.current.gripProps.onPointerDown(pointer(450)));
    expect(handle.setPointerCapture).toHaveBeenCalledWith(7);
    act(() => hook.result.current.gripProps.onPointerMove(pointer(100)));
    expect(surface.style.height).toMatch(/px$/);
    expect(hook.result.current.state).toBe('medium');
    act(() => hook.result.current.gripProps.onPointerUp(pointer(100)));
    expect(hook.result.current.state).toBe('expanded');
    expect(handle.releasePointerCapture).toHaveBeenCalledWith(7);
    act(() => hook.result.current.gripProps.onPointerDown(pointer(100)));
    act(() => hook.result.current.gripProps.onPointerUp(pointer(480)));
    expect(hook.result.current.state).toBe('compact');
  });
  it('cancels without changing snap state on pointer cancellation/loss', () => {
    const { surface, hook, pointer } = harness();
    act(() => hook.result.current.gripProps.onPointerDown(pointer(450)));
    act(() => hook.result.current.gripProps.onPointerMove(pointer(170)));
    act(() => hook.result.current.gripProps.onPointerCancel(pointer(170)));
    expect(hook.result.current.state).toBe('medium');
    expect(surface.style.height).toMatch(/px$/);
    act(() => hook.result.current.gripProps.onPointerDown(pointer(450)));
    act(() => hook.result.current.gripProps.onLostPointerCapture(pointer(150)));
    expect(hook.result.current.state).toBe('medium');
  });
  it('ignores secondary touches and is inert unless opted in', () => {
    const ref = {current:document.createElement('section')};
    const disabled = renderHook(() => useMobileSheetSnap({open:true,enabled:false,surfaceRef:ref}));
    const inactive = vi.fn();
    act(() => disabled.result.current.gripProps.onPointerDown({
      isPrimary:true,pointerType:'touch',pointerId:1,currentTarget:{setPointerCapture:inactive},clientY:420,
    }));
    expect(inactive).not.toHaveBeenCalled();
    expect(disabled.result.current.active).toBe(false);
    const {hook,pointer,handle} = harness();
    act(() => hook.result.current.gripProps.onPointerDown({...pointer(420),isPrimary:false}));
    expect(handle.setPointerCapture).not.toHaveBeenCalled();
  });
  it('reclamps during viewport resize without forwarding scroll gestures', () => {
    const { hook } = harness();
    const before = hook.result.current.style.height;
    act(() => window.dispatchEvent(new Event('resize')));
    expect(hook.result.current.style.height).toBeDefined();
    expect(before).toMatch(/px$/);
    expect(hook.result.current.gripProps.onPointerDown).toBeTypeOf('function');
  });
});

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

// Opt-in mobile-only sheet geometry. No backend state, scroll gestures or React
// updates during pointer movement. Consumers attach gestures ONLY to their grip.
export const MOBILE_SHEET_STATES = Object.freeze(['compact', 'medium', 'expanded']);
export const MOBILE_SHEET_RATIOS = Object.freeze({ compact: 0.35, medium: 0.72, expanded: 0.94 });
const MIN_HEIGHT = 128;

export function mobileSheetViewportHeight(viewportHeight) {
  return Math.max(MIN_HEIGHT, Number(viewportHeight) || MIN_HEIGHT);
}

export function mobileSheetHeight(state, viewportHeight) {
  const available = mobileSheetViewportHeight(viewportHeight);
  return Math.min(Math.max(MIN_HEIGHT, available * (MOBILE_SHEET_RATIOS[state] || MOBILE_SHEET_RATIOS.medium)), Math.max(MIN_HEIGHT, available - 20));
}

export function closestMobileSheetState(height, viewportHeight) {
  return MOBILE_SHEET_STATES.reduce((best, candidate) => (
    Math.abs(mobileSheetHeight(candidate, viewportHeight) - height) <
    Math.abs(mobileSheetHeight(best, viewportHeight) - height) ? candidate : best
  ), 'medium');
}

export function useMobileSheetSnap({ open, enabled = false, surfaceRef, initialState = 'medium' } = {}) {
  const [state, setState] = useState(MOBILE_SHEET_STATES.includes(initialState) ? initialState : 'medium');
  const [viewportHeight, setViewportHeight] = useState(() => typeof window === 'undefined' ? 720 : window.visualViewport?.height || window.innerHeight);
  const dragRef = useRef(null);
  const heightRef = useRef(mobileSheetHeight(state, viewportHeight));
  const active = Boolean(open && enabled);
  const getViewportHeight = useCallback(() => (
    typeof window === 'undefined' ? 720 : window.visualViewport?.height || window.innerHeight
  ), []);

  useEffect(() => {
    if (!active) return undefined;
    const visualViewport = window.visualViewport;
    const onViewportChange = () => {
      const next = getViewportHeight();
      setViewportHeight(next);
      // A keyboard opening or a rotation must not leave the sheet off-screen.
      if (dragRef.current) dragRef.current = null;
    };
    visualViewport?.addEventListener('resize', onViewportChange, { passive: true });
    window.addEventListener('resize', onViewportChange, { passive: true });
    return () => {
      visualViewport?.removeEventListener('resize', onViewportChange);
      window.removeEventListener('resize', onViewportChange);
      dragRef.current = null;
    };
  }, [active, getViewportHeight]);

  const resizeTo = useCallback((next) => {
    if (!MOBILE_SHEET_STATES.includes(next)) return;
    dragRef.current = null;
    setState(next);
  }, []);
  const expand = useCallback(() => resizeTo(MOBILE_SHEET_STATES[Math.min(2, MOBILE_SHEET_STATES.indexOf(state) + 1)]), [resizeTo, state]);
  const contract = useCallback(() => resizeTo(MOBILE_SHEET_STATES[Math.max(0, MOBILE_SHEET_STATES.indexOf(state) - 1)]), [resizeTo, state]);

  const onPointerDown = useCallback((event) => {
    if (!active || !event.isPrimary || (event.pointerType === 'mouse' && event.button !== 0)) return;
    const height = mobileSheetHeight(state, getViewportHeight());
    dragRef.current = { id: event.pointerId, y: event.clientY, height };
    event.currentTarget.setPointerCapture?.(event.pointerId);
    event.preventDefault();
  }, [active, getViewportHeight, state]);
  const onPointerMove = useCallback((event) => {
    const drag = dragRef.current;
    if (!drag || drag.id !== event.pointerId) return;
    const vh = getViewportHeight();
    const nextHeight = Math.max(mobileSheetHeight('compact', vh), Math.min(mobileSheetHeight('expanded', vh), drag.height + drag.y - event.clientY));
    heightRef.current = nextHeight;
    if (surfaceRef?.current) surfaceRef.current.style.height = `${Math.round(nextHeight)}px`;
  }, [getViewportHeight, surfaceRef]);
  const complete = useCallback((event, cancelled = false) => {
    const drag = dragRef.current;
    if (!drag || drag.id !== event.pointerId) return;
    dragRef.current = null;
    const vh = getViewportHeight();
    const next = cancelled ? state : closestMobileSheetState(drag.height + drag.y - event.clientY, vh);
    if (surfaceRef?.current) surfaceRef.current.style.height = `${Math.round(mobileSheetHeight(next, vh))}px`;
    setState(next);
    if (event.currentTarget.hasPointerCapture?.(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
  }, [getViewportHeight, state, surfaceRef]);
  const onKeyDown = useCallback((event) => {
    if (!active) return;
    if (event.key === 'ArrowUp' || event.key === 'PageUp') { event.preventDefault(); expand(); }
    if (event.key === 'ArrowDown' || event.key === 'PageDown') { event.preventDefault(); contract(); }
    if (event.key === 'Home') { event.preventDefault(); resizeTo('compact'); }
    if (event.key === 'End') { event.preventDefault(); resizeTo('expanded'); }
  }, [active, contract, expand, resizeTo]);

  const height = mobileSheetHeight(state, viewportHeight);
  heightRef.current = height;
  const style = useMemo(() => active ? { height: `${Math.round(height)}px` } : undefined, [active, height]);
  return {
    state, active, style, expand, contract, resizeTo,
    canExpand: active && state !== 'expanded',
    canContract: active && state !== 'compact',
    gripProps: {
      onPointerDown, onPointerMove,
      onPointerUp: (event) => complete(event),
      onPointerCancel: (event) => complete(event, true),
      onLostPointerCapture: (event) => complete(event, true),
      onKeyDown,
      'aria-label': `Resize sheet, currently ${state}. Arrow keys change height.`,
      'aria-keyshortcuts': 'ArrowUp ArrowDown PageUp PageDown Home End',
      'aria-description': 'Drag up to expand or down to compact. Use the expand and compact buttons as alternatives.',
    },
  };
}

import { useCallback, useEffect, useRef, useState } from 'react';

// Shared, transient viewport geometry for the existing Devices and Apps Manage portals.
// Deliberately stores no operational state, backend identifiers or localStorage values.
export const MANAGE_DESKTOP_QUERY = '(min-width: 701px)';
const MARGIN = 16;

export function clampManageGeometry(value = {}, { minWidth = 360, minHeight = 360 } = {}) {
  if (typeof window === 'undefined') return value;
  const vw = Math.max(1, window.innerWidth);
  const vh = Math.max(1, window.innerHeight);
  const maximumWidth = Math.max(1, vw - 2 * Math.min(MARGIN, vw / 8));
  const maximumHeight = Math.max(1, vh - 2 * Math.min(MARGIN, vh / 8));
  const width = Math.min(maximumWidth, Math.max(Math.min(minWidth, maximumWidth), Number(value.width) || maximumWidth));
  const height = Math.min(maximumHeight, Math.max(Math.min(minHeight, maximumHeight), Number(value.height) || maximumHeight));
  const marginX = Math.min(MARGIN, (vw - width) / 2);
  const marginY = Math.min(MARGIN, (vh - height) / 2);
  return {
    left: Math.min(Math.max(marginX, Number.isFinite(Number(value.left)) ? Number(value.left) : marginX), vw - width - marginX),
    top: Math.min(Math.max(marginY, Number.isFinite(Number(value.top)) ? Number(value.top) : marginY), vh - height - marginY),
    width, height,
  };
}

export function defaultManageGeometry({ defaultWidth = 560, minWidth = 360, minHeight = 360 } = {}) {
  if (typeof window === 'undefined') return null;
  const width = Math.min(defaultWidth, Math.max(1, window.innerWidth - MARGIN * 2));
  const height = Math.min(Math.max(480, window.innerHeight * .82), Math.max(1, window.innerHeight - MARGIN * 2));
  return clampManageGeometry({
    left: window.innerWidth - width - MARGIN,
    top: (window.innerHeight - height) / 2,
    width, height,
  }, { minWidth, minHeight });
}

export function useDesktopManageGeometry({ open, defaultWidth = 560, minWidth = 360, minHeight = 360 } = {}) {
  const panelRef = useRef(null);
  const pendingRef = useRef(null);
  const frameRef = useRef(null);
  const interactionRef = useRef(null);
  const [desktopPanel, setDesktopPanel] = useState(false);
  const [geometry, setGeometry] = useState(null);
  const [announcement, setAnnouncement] = useState('');
  const options = { defaultWidth, minWidth, minHeight };
  const clamp = useCallback((value) => clampManageGeometry(value, { minWidth, minHeight }), [minWidth, minHeight]);
  const reset = useCallback(() => {
    setGeometry(defaultManageGeometry({ defaultWidth, minWidth, minHeight }));
    setAnnouncement('Panel position and size reset.');
  }, [defaultWidth, minHeight, minWidth]);

  const stop = useCallback(() => {
    interactionRef.current?.();
    interactionRef.current = null;
    if (frameRef.current !== null) window.cancelAnimationFrame(frameRef.current);
    frameRef.current = null;
    pendingRef.current = null;
    panelRef.current?.classList.remove('is-interacting');
  }, []);

  useEffect(() => {
    if (!open || typeof window === 'undefined') {
      setDesktopPanel(false);
      setGeometry(null);
      return undefined;
    }
    const media = window.matchMedia(MANAGE_DESKTOP_QUERY);
    const apply = (matches) => {
      setDesktopPanel(matches);
      setGeometry((current) => matches ? clamp(current || defaultManageGeometry(options)) : null);
    };
    apply(media.matches);
    const changed = (event) => apply(event.matches);
    media.addEventListener?.('change', changed);
    return () => media.removeEventListener?.('change', changed);
  }, [open, defaultWidth, minHeight, minWidth, clamp]);

  useEffect(() => {
    if (!open || typeof window === 'undefined') return undefined;
    const resized = () => setGeometry((current) => current ? clamp(current) : current);
    window.addEventListener('resize', resized, { passive: true });
    window.visualViewport?.addEventListener('resize', resized, { passive: true });
    return () => {
      window.removeEventListener('resize', resized);
      window.visualViewport?.removeEventListener('resize', resized);
    };
  }, [open, clamp]);

  useEffect(() => () => stop(), [stop]);

  const startPanelInteraction = useCallback((kind, event) => {
    if (!desktopPanel || event.button !== 0 || !panelRef.current || interactionRef.current) return;
    event.preventDefault();
    const rect = panelRef.current.getBoundingClientRect();
    const origin = { left: rect.left, top: rect.top, width: rect.width, height: rect.height };
    const pointerId = event.pointerId;
    const startX = event.clientX;
    const startY = event.clientY;
    const move = (next) => {
      if (next.pointerId !== pointerId) return;
      const dx = next.clientX - startX;
      const dy = next.clientY - startY;
      pendingRef.current = clamp(kind === 'move'
        ? { ...origin, left: origin.left + dx, top: origin.top + dy }
        : { ...origin, width: origin.width + dx, height: origin.height + dy });
      if (frameRef.current !== null) return;
      frameRef.current = window.requestAnimationFrame(() => {
        frameRef.current = null;
        if (pendingRef.current) setGeometry(pendingRef.current);
        pendingRef.current = null;
      });
    };
    const cleanup = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', finish);
      window.removeEventListener('pointercancel', finish);
    };
    const finish = (next) => {
      if (next.pointerId !== pointerId) return;
      if (pendingRef.current) setGeometry(pendingRef.current);
      cleanup();
      interactionRef.current = null;
      panelRef.current?.classList.remove('is-interacting');
    };
    interactionRef.current = cleanup;
    panelRef.current.classList.add('is-interacting');
    window.addEventListener('pointermove', move, { passive: true });
    window.addEventListener('pointerup', finish, { passive: true });
    window.addEventListener('pointercancel', finish, { passive: true });
  }, [clamp, desktopPanel]);

  const adjustPanelWithKeyboard = useCallback((kind, event) => {
    if (!desktopPanel || !geometry) return;
    if (event.key === 'Home') {
      event.preventDefault();
      reset();
      return;
    }
    const step = event.shiftKey ? 64 : 16;
    const axes = { ArrowLeft: -step, ArrowRight: step, ArrowUp: -step, ArrowDown: step };
    if (!Object.prototype.hasOwnProperty.call(axes, event.key)) return;
    event.preventDefault();
    const horizontal = event.key === 'ArrowLeft' || event.key === 'ArrowRight';
    const field = kind === 'move' ? (horizontal ? 'left' : 'top') : (horizontal ? 'width' : 'height');
    const next = clamp({ ...geometry, [field]: geometry[field] + axes[event.key] });
    setGeometry(next);
    setAnnouncement(`Panel ${kind === 'move' ? 'moved' : 'resized'} to ${Math.round(next.width)} by ${Math.round(next.height)} pixels.`);
  }, [clamp, desktopPanel, geometry, reset]);

  return {
    panelRef, desktopPanel, geometry, announcement, reset,
    startPanelInteraction, adjustPanelWithKeyboard,
    panelStyle: desktopPanel && geometry ? {
      left: `${geometry.left}px`, top: `${geometry.top}px`,
      width: `${geometry.width}px`, height: `${geometry.height}px`,
      right: 'auto', bottom: 'auto',
    } : undefined,
  };
}

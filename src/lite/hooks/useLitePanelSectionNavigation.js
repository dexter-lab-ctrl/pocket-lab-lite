import { useCallback, useEffect, useRef, useState } from 'react';

// Shared by Home's Workspace and Activity panels. Tracks their own scroll element,
// never the window or the operational query cache.
export const LITE_PANEL_NAV_TOP = 8;
export const LITE_PANEL_NAV_DIRECTION_THRESHOLD = 14;

export function nextLitePanelNavState(previous, top, focused = false) {
  const scrollTop = Math.max(0, Number(top) || 0);
  const atTop = scrollTop <= LITE_PANEL_NAV_TOP;
  const scrolled = !atTop;
  const baseline = Number(previous?.baseline) || 0;
  const delta = scrollTop - baseline;
  if (atTop || focused) return { baseline: scrollTop, hidden: false, scrolled };
  if (Math.abs(delta) < LITE_PANEL_NAV_DIRECTION_THRESHOLD) {
    return { baseline, hidden: Boolean(previous?.hidden), scrolled };
  }
  return { baseline: scrollTop, hidden: delta > 0, scrolled };
}

export function useLitePanelSectionNavigation(open) {
  const bodyRef = useRef(null);
  const navRef = useRef(null);
  const scrollState = useRef({ baseline: 0, hidden: false, scrolled: false });
  const [hidden, setHidden] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  const reveal = useCallback((resetScroll = false) => {
    scrollState.current = { ...scrollState.current, hidden: false };
    setHidden(false);
    if (resetScroll && bodyRef.current) {
      bodyRef.current.scrollTop = 0;
      scrollState.current = { baseline: 0, hidden: false, scrolled: false };
      setScrolled(false);
    }
  }, []);

  useEffect(() => {
    const body = bodyRef.current;
    if (!open || !body) {
      scrollState.current = { baseline: 0, hidden: false, scrolled: false };
      setHidden(false);
      setScrolled(false);
      return undefined;
    }
    scrollState.current = { baseline: Math.max(0, body.scrollTop), hidden: false, scrolled: body.scrollTop > LITE_PANEL_NAV_TOP };
    setHidden(false);
    setScrolled(scrollState.current.scrolled);
    const onScroll = () => {
      // Pointer scrolling can leave the last tab focused on touch browsers.
      // Let the scroll direction retract the sticky strip; :focus-within in
      // the panel stylesheet keeps a keyboard-focused strip visible and the
      // focusin handler below restores the explicit state for keyboard use.
      const next = nextLitePanelNavState(scrollState.current, body.scrollTop, false);
      scrollState.current = next;
      setHidden((current) => current === next.hidden ? current : next.hidden);
      setScrolled((current) => current === next.scrolled ? current : next.scrolled);
    };
    const onFocus = (event) => {
      if (navRef.current?.contains(event.target)) reveal();
    };
    body.addEventListener('scroll', onScroll, { passive: true });
    body.addEventListener('focusin', onFocus);
    return () => {
      body.removeEventListener('scroll', onScroll);
      body.removeEventListener('focusin', onFocus);
    };
  }, [open, reveal]);

  return { bodyRef, navRef, hidden, scrolled, reveal };
}

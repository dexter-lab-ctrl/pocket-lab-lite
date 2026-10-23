import { useCallback, useEffect, useRef, useState } from 'react';

// The LiteDetailsPanel body is the single vertical scroll owner in both Home
// panels. No window scroll listener and no second Activity-specific algorithm.
export const LITE_PANEL_NAV_TOP = 8;
export const LITE_PANEL_NAV_DIRECTION_THRESHOLD = 14;

export function nextLitePanelNavState(previous, top, keyboardFocused = false) {
  const scrollTop = Math.max(0, Number(top) || 0);
  const atTop = scrollTop <= LITE_PANEL_NAV_TOP;
  const scrolled = !atTop;
  const baseline = Number(previous?.baseline) || 0;
  const delta = scrollTop - baseline;
  if (atTop || keyboardFocused) return { baseline: scrollTop, hidden: false, scrolled };
  if (Math.abs(delta) < LITE_PANEL_NAV_DIRECTION_THRESHOLD) {
    return { baseline, hidden: Boolean(previous?.hidden), scrolled };
  }
  return { baseline: scrollTop, hidden: delta > 0, scrolled };
}

export function useLitePanelSectionNavigation(open) {
  const bodyRef = useRef(null);
  const navRef = useRef(null);
  const scrollState = useRef({ baseline: 0, hidden: false, scrolled: false });
  // A touched button may retain DOM focus after click; this is NOT keyboard
  // focus and must not pin the strip through a subsequent momentum scroll.
  const keyboardIntentRef = useRef(false);
  const [hidden, setHidden] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const [keyboardFocused, setKeyboardFocused] = useState(false);

  const reveal = useCallback((resetScroll = false) => {
    scrollState.current = { ...scrollState.current, hidden: false };
    setHidden(false);
    if (resetScroll && bodyRef.current) {
      // Section contents replace each other; reset the real scroll owner,
      // even if the browser did not emit a scroll event during the swap.
      bodyRef.current.scrollTop = 0;
      scrollState.current = { baseline: 0, hidden: false, scrolled: false };
      setScrolled(false);
    }
  }, []);

  useEffect(() => {
    const body = bodyRef.current;
    if (!open || !body) {
      scrollState.current = { baseline: 0, hidden: false, scrolled: false };
      keyboardIntentRef.current = false;
      setHidden(false);
      setScrolled(false);
      setKeyboardFocused(false);
      return undefined;
    }
    const top = Math.max(0, body.scrollTop);
    scrollState.current = { baseline: top, hidden: false, scrolled: top > LITE_PANEL_NAV_TOP };
    keyboardIntentRef.current = false;
    setHidden(false);
    setScrolled(scrollState.current.scrolled);
    setKeyboardFocused(false);

    const pointerIntent = () => {
      keyboardIntentRef.current = false;
      setKeyboardFocused((current) => current ? false : current);
    };
    const onKeyDown = (event) => {
      if (event.key === 'Tab' || navRef.current?.contains(event.target)) {
        keyboardIntentRef.current = true;
        // A keyboard user must never tab into an invisible nav.
        reveal();
      }
    };
    const onFocus = (event) => {
      if (!navRef.current?.contains(event.target)) return;
      const fromKeyboard = keyboardIntentRef.current || event.target.matches?.(':focus-visible');
      if (fromKeyboard) {
        keyboardIntentRef.current = true;
        setKeyboardFocused(true);
        reveal();
      }
    };
    const onFocusOut = (event) => {
      if (!navRef.current?.contains(event.relatedTarget)) setKeyboardFocused(false);
    };
    const onScroll = () => {
      const navHasKeyboardFocus = keyboardIntentRef.current
        && navRef.current?.contains(document.activeElement);
      const next = nextLitePanelNavState(scrollState.current, body.scrollTop, navHasKeyboardFocus);
      scrollState.current = next;
      setHidden((current) => current === next.hidden ? current : next.hidden);
      setScrolled((current) => current === next.scrolled ? current : next.scrolled);
    };
    body.addEventListener('scroll', onScroll, { passive: true });
    body.addEventListener('wheel', pointerIntent, { passive: true });
    body.addEventListener('touchstart', pointerIntent, { passive: true });
    body.addEventListener('pointerdown', pointerIntent, { passive: true });
    body.addEventListener('keydown', onKeyDown);
    body.addEventListener('focusin', onFocus);
    body.addEventListener('focusout', onFocusOut);
    return () => {
      body.removeEventListener('scroll', onScroll);
      body.removeEventListener('wheel', pointerIntent);
      body.removeEventListener('touchstart', pointerIntent);
      body.removeEventListener('pointerdown', pointerIntent);
      body.removeEventListener('keydown', onKeyDown);
      body.removeEventListener('focusin', onFocus);
      body.removeEventListener('focusout', onFocusOut);
    };
  }, [open, reveal]);

  return { bodyRef, navRef, hidden, scrolled, keyboardFocused, reveal };
}

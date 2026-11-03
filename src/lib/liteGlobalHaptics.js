import { triggerLiteHaptic } from './liteNativeFeedback.js';

// One delegated interaction layer covers current and lazy-loaded Lite screens
// and portalled dialogs. It never changes the action or owns authorization.
const CLICKABLE = 'button, a[href], [role="button"], [role="tab"], [role="menuitem"], [role="switch"], input[type="button"], input[type="submit"]';
const IGNORE = '[disabled], [aria-disabled="true"], [aria-busy="true"], [inert], [data-lite-haptic="off"], [data-lite-haptic="manual"]';
let installedCleanup = null;

export function liteHapticTarget(event) {
  const target = event?.target;
  const element = target?.nodeType === 3 ? target.parentElement : target;
  if (!element || typeof element.closest !== 'function') return null;
  const control = element.closest(CLICKABLE);
  if (!control || control.closest(IGNORE)) return null;
  // Hidden or disconnected portals cannot receive meaningful interaction.
  if (!control.isConnected || control.getAttribute('aria-hidden') === 'true') return null;
  return control;
}

export function installLiteGlobalHaptics(doc = typeof document === 'undefined' ? null : document,
  win = typeof window === 'undefined' ? null : window) {
  if (!doc || !win || typeof doc.addEventListener !== 'function') return () => {};
  if (installedCleanup) return installedCleanup;
  let lastPointerType = '';
  let lastPointerAt = 0;
  let lastFeedbackAt = -Infinity;
  const onPointerDown = (event) => {
    lastPointerType = event.pointerType || '';
    lastPointerAt = Date.now();
  };
  const onClick = (event) => {
    if (!liteHapticTarget(event)) return;
    const now = Date.now();
    const pointerType = event.pointerType || (now - lastPointerAt < 1200 ? lastPointerType : '');
    if (pointerType === 'mouse') return;
    // Keyboard activation uses detail=0. Touch browsers that expose MouseEvent
    // rather than PointerEvent still qualify when their primary pointer is coarse.
    const coarse = win.matchMedia?.('(pointer: coarse)')?.matches === true;
    if (pointerType !== 'touch' && pointerType !== 'pen' && event.detail !== 0 && !coarse) return;
    if (now - lastFeedbackAt < 65) return;
    lastFeedbackAt = now;
    triggerLiteHaptic('tap'); // unsupported Safari/iOS is a silent no-op
  };
  doc.addEventListener('pointerdown', onPointerDown, true);
  doc.addEventListener('click', onClick, true);
  installedCleanup = () => {
    doc.removeEventListener('pointerdown', onPointerDown, true);
    doc.removeEventListener('click', onClick, true);
    installedCleanup = null;
  };
  return installedCleanup;
}

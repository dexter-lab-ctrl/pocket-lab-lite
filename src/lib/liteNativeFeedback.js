export const LITE_HAPTIC_PATTERNS = Object.freeze({
  tap: 8,
  accepted: 10,
  success: [10, 30, 14],
  confirm: 18,
  warning: [18, 35, 18],
  blocked: [18, 35, 18],
  destructive_confirm: 18,
  progress_milestone: 10,
});

function reducedMotionPreferred() {
  try {
    return typeof window !== 'undefined'
      && typeof window.matchMedia === 'function'
      && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  } catch {
    return false;
  }
}

export function triggerLiteHaptic(kind = 'accepted') {
  if (typeof navigator === 'undefined' || typeof navigator.vibrate !== 'function') return false;
  if (typeof document !== 'undefined' && document.visibilityState === 'hidden') return false;
  if (reducedMotionPreferred()) return false;
  try {
    return Boolean(navigator.vibrate(LITE_HAPTIC_PATTERNS[kind] || LITE_HAPTIC_PATTERNS.accepted));
  } catch {
    return false;
  }
}

// Keeps completion feedback tied to a bounded, meaningful event identity.
// Callers retain the deduper for their screen or root lifecycle; no payload is persisted.
export function createLiteFeedbackDeduper(limit = 64) {
  const seen = new Set();
  const max = Math.max(1, Math.min(128, Number(limit) || 64));
  const claim = (eventId) => {
    const id = String(eventId || '').trim().slice(0, 160);
    if (id && seen.has(id)) return false;
    if (id) {
      seen.add(id);
      if (seen.size > max) seen.delete(seen.values().next().value);
    }
    return true;
  };
  return {
    // Claiming is deliberately separate from whether a browser supports
    // vibration. Callers can keep a visual completion notice deduplicated on
    // every platform, while haptics remain an optional enhancement.
    once(eventId, kind = 'accepted') {
      if (!claim(eventId)) return false;
      triggerLiteHaptic(kind);
      return true;
    },
    trigger(eventId, kind = 'accepted') {
      if (!claim(eventId)) return false;
      return triggerLiteHaptic(kind);
    },
  };
}

const HAPTIC_PATTERNS = {
  accepted: 10,
  success: [10, 30, 14],
  confirm: 18,
  warning: [18, 35, 18],
};

export function triggerLiteHaptic(kind = 'accepted') {
  if (typeof navigator === 'undefined' || typeof navigator.vibrate !== 'function') return false;
  if (typeof document !== 'undefined' && document.visibilityState === 'hidden') return false;
  try {
    return Boolean(navigator.vibrate(HAPTIC_PATTERNS[kind] || HAPTIC_PATTERNS.accepted));
  } catch {
    return false;
  }
}

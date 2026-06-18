import React, { useEffect, useState } from 'react';

function prefersReducedMotion() {
  return typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
}

export default function CountUpNumber({ value = 0, duration = 420, className = '', format, suffix = '', decimals = 0 }) {
  const numericValue = Number.isFinite(Number(value)) ? Number(value) : 0;
  const [displayValue, setDisplayValue] = useState(prefersReducedMotion() ? numericValue : 0);

  useEffect(() => {
    if (prefersReducedMotion()) {
      setDisplayValue(numericValue);
      return undefined;
    }

    let frame = 0;
    const start = performance.now();
    const from = 0;
    const to = numericValue;

    const tick = (now) => {
      const progress = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplayValue(from + (to - from) * eased);
      if (progress < 1) frame = requestAnimationFrame(tick);
    };

    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [numericValue, duration]);

  const rendered = typeof format === 'function'
    ? format(displayValue)
    : displayValue.toFixed(decimals);

  return <span className={`metric-count-up ${className}`}>{rendered}{suffix}</span>;
}

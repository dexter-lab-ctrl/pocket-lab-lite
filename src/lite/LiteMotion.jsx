import React, { useCallback, useState } from 'react';
import { animated, useSpring } from '@react-spring/web';

export function useLiteReducedMotion() {
  const [reduced, setReduced] = useState(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return false;
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  });

  React.useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return undefined;
    const query = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReduced(query.matches);
    update();
    query.addEventListener?.('change', update);
    return () => query.removeEventListener?.('change', update);
  }, []);

  return reduced;
}

export function triggerLiteTactileFeedback(kind = 'light') {
  if (typeof navigator === 'undefined' || typeof navigator.vibrate !== 'function') return;
  const pattern = kind === 'accepted' ? 12 : kind === 'selection' ? 8 : 6;
  try {
    navigator.vibrate(pattern);
  } catch (_error) {
    // Vibration support is browser/device dependent. Ignore safely.
  }
}

export function useLiteRipple({ disabled = false } = {}) {
  const reducedMotion = useLiteReducedMotion();
  const [ripples, setRipples] = useState([]);

  const onPointerDown = useCallback((event) => {
    if (disabled || reducedMotion) return;
    const target = event.currentTarget;
    if (!target?.getBoundingClientRect) return;
    const rect = target.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height) * 1.18;
    const x = event.clientX - rect.left - size / 2;
    const y = event.clientY - rect.top - size / 2;
    const id = `${Date.now()}-${Math.round(Math.random() * 100000)}`;
    setRipples((items) => [...items.slice(-2), { id, x, y, size }]);
    window.setTimeout(() => {
      setRipples((items) => items.filter((item) => item.id !== id));
    }, 560);
  }, [disabled, reducedMotion]);

  const rippleNode = ripples.length ? (
    <span className="lite-motion-ripples" aria-hidden="true">
      {ripples.map((ripple) => (
        <span
          key={ripple.id}
          className="lite-motion-ripple"
          style={{
            width: ripple.size,
            height: ripple.size,
            transform: `translate3d(${ripple.x}px, ${ripple.y}px, 0)`,
          }}
        />
      ))}
    </span>
  ) : null;

  return { rippleHandlers: { onPointerDown }, rippleNode };
}

export function LitePressableButton({
  children,
  className = '',
  disabled = false,
  onClick,
  onPointerDown,
  haptic = 'light',
  type = 'button',
  ...props
}) {
  const reducedMotion = useLiteReducedMotion();
  const { rippleHandlers, rippleNode } = useLiteRipple({ disabled });
  const [pressed, setPressed] = useState(false);
  const spring = useSpring({
    transform: !reducedMotion && pressed && !disabled ? 'scale(0.985)' : 'scale(1)',
    config: { tension: 420, friction: 32, clamp: true },
  });

  function handlePointerDown(event) {
    rippleHandlers.onPointerDown(event);
    setPressed(true);
    onPointerDown?.(event);
  }

  function clearPressed() {
    setPressed(false);
  }

  function handleClick(event) {
    if (disabled) return;
    triggerLiteTactileFeedback(haptic);
    onClick?.(event);
  }

  return (
    <animated.button
      {...props}
      type={type}
      disabled={disabled}
      className={`lite-motion-pressable ${className}`.trim()}
      style={{ ...(props.style || {}), ...spring }}
      onPointerDown={handlePointerDown}
      onPointerUp={clearPressed}
      onPointerCancel={clearPressed}
      onPointerLeave={clearPressed}
      onClick={handleClick}
    >
      <span className="lite-motion-pressable-content">{children}</span>
      {rippleNode}
    </animated.button>
  );
}

export function LiteElevationSurface({
  as = 'div',
  children,
  className = '',
  disabled = false,
  active = false,
  ...props
}) {
  const Component = as === 'section' ? animated.section : animated.div;
  const reducedMotion = useLiteReducedMotion();
  const spring = useSpring({
    opacity: disabled ? 0.72 : 1,
    transform: !reducedMotion && active ? 'translateY(-1px)' : 'translateY(0px)',
    config: { tension: 360, friction: 34, clamp: true },
  });

  return (
    <Component
      {...props}
      className={`lite-motion-elevation-surface ${className}`.trim()}
      style={{ ...(props.style || {}), ...spring }}
    >
      {children}
    </Component>
  );
}

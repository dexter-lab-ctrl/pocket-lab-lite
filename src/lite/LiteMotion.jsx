import React, { useCallback, useLayoutEffect, useRef, useState } from 'react';
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

function animatedElement(as = 'div') {
  if (as === 'section') return animated.section;
  if (as === 'article') return animated.article;
  if (as === 'p') return animated.p;
  if (as === 'span') return animated.span;
  return animated.div;
}

export function LiteElevationSurface({
  as = 'div',
  children,
  className = '',
  disabled = false,
  active = false,
  settle = false,
  ...props
}) {
  const Component = animatedElement(as);
  const reducedMotion = useLiteReducedMotion();
  const spring = useSpring({
    from: settle && !reducedMotion ? { opacity: 0.01, transform: 'translateY(6px) scale(0.992)' } : undefined,
    opacity: disabled ? 0.72 : 1,
    transform: !reducedMotion && active ? 'translateY(-1px) scale(1.002)' : 'translateY(0px) scale(1)',
    config: { tension: 360, friction: 34, clamp: true },
  });

  return (
    <Component
      {...props}
      className={`lite-motion-elevation-surface ${settle ? 'lite-motion-settle-in' : ''} ${className}`.trim()}
      style={{ ...(props.style || {}), ...spring }}
    >
      {children}
    </Component>
  );
}

export function LiteMotionReveal({
  as = 'div',
  children,
  className = '',
  show = true,
  role,
  ariaLive,
  motionKey = '',
  ...props
}) {
  const Component = animatedElement(as);
  const reducedMotion = useLiteReducedMotion();
  const spring = useSpring({
    from: !reducedMotion ? { opacity: 0, transform: 'translateY(5px) scale(0.992)' } : { opacity: 1, transform: 'none' },
    opacity: show ? 1 : 0,
    transform: !reducedMotion && show ? 'translateY(0px) scale(1)' : 'translateY(5px) scale(0.992)',
    config: { tension: 380, friction: 32, clamp: true },
  });

  if (!show) return null;

  return (
    <Component
      {...props}
      role={role}
      aria-live={ariaLive}
      className={`lite-motion-reveal ${className}`.trim()}
      style={{ ...(props.style || {}), ...spring }}
      data-motion-key={motionKey || undefined}
    >
      {children}
    </Component>
  );
}


export function liteContextualActionKind(actionId = '') {
  const id = String(actionId || '').toLowerCase();
  if (['connect_photos', 'import_photos'].includes(id)) return 'photos';
  if (id === 'check_app') return 'safety';
  if (['backup_app', 'preview_restore', 'backup_to_storage', 'repair_app'].includes(id)) return 'recovery';
  if (['install_app', 'update_app'].includes(id)) return 'setup';
  if (id === 'remove_app') return 'danger';
  return 'neutral';
}

export function LiteContextualActionCue({
  actionId,
  active = false,
  completed = false,
  review = false,
}) {
  const kind = liteContextualActionKind(actionId);
  if (kind === 'neutral') return null;

  return (
    <span
      className={`lite-contextual-action-cue is-${kind} ${active ? 'is-active' : ''} ${completed ? 'is-complete' : ''} ${review ? 'is-review' : ''}`.trim()}
      aria-hidden="true"
      data-action-kind={kind}
    >
      <span className="lite-contextual-action-cue__track" />
      <span className="lite-contextual-action-cue__node" />
      <span className="lite-contextual-action-cue__spark" />
    </span>
  );
}


export function useLiteFlipList(keys = [], { enabled = true } = {}) {
  const reducedMotion = useLiteReducedMotion();
  const nodesRef = useRef(new Map());
  const previousRectsRef = useRef(new Map());
  const keySignature = Array.isArray(keys) ? keys.map((key) => String(key)).join('|') : String(keys || '');

  const register = useCallback((key) => (node) => {
    const id = String(key || 'item');
    if (node) {
      nodesRef.current.set(id, node);
    } else {
      nodesRef.current.delete(id);
    }
  }, []);

  useLayoutEffect(() => {
    if (!enabled || reducedMotion || typeof window === 'undefined') {
      const nextRects = new Map();
      nodesRef.current.forEach((node, key) => {
        if (node?.getBoundingClientRect) nextRects.set(key, node.getBoundingClientRect());
      });
      previousRectsRef.current = nextRects;
      return;
    }

    const previousRects = previousRectsRef.current;
    const nextRects = new Map();

    nodesRef.current.forEach((node, key) => {
      if (!node?.getBoundingClientRect) return;
      const next = node.getBoundingClientRect();
      nextRects.set(key, next);
      const previous = previousRects.get(key);
      if (!previous || typeof node.animate !== 'function') return;

      const dx = previous.left - next.left;
      const dy = previous.top - next.top;
      const dw = previous.width && next.width ? previous.width / Math.max(next.width, 1) : 1;
      const dh = previous.height && next.height ? previous.height / Math.max(next.height, 1) : 1;
      const moved = Math.abs(dx) > 1 || Math.abs(dy) > 1 || Math.abs(dw - 1) > 0.015 || Math.abs(dh - 1) > 0.015;
      if (!moved) return;

      node.animate(
        [
          { transform: `translate3d(${dx}px, ${dy}px, 0) scale(${dw}, ${dh})`, opacity: 0.96 },
          { transform: 'translate3d(0, 0, 0) scale(1, 1)', opacity: 1 },
        ],
        {
          duration: 240,
          easing: 'cubic-bezier(0.2, 0.86, 0.22, 1)',
          fill: 'both',
        },
      );
    });

    previousRectsRef.current = nextRects;
  }, [enabled, reducedMotion, keySignature]);

  return register;
}

export function LiteFlipGroup({
  keys = [],
  children,
  className = '',
  enabled = true,
}) {
  const register = useLiteFlipList(keys, { enabled });
  return (
    <div className={`lite-motion-flip-group ${className}`.trim()} data-lite-flip-group="true">
      {typeof children === 'function' ? children(register) : children}
    </div>
  );
}

export function LiteSharedElementCue({
  kind = 'card-to-sheet',
  active = true,
  label = '',
}) {
  if (!active) return null;
  return (
    <span
      className={`lite-shared-element-cue is-${kind}`.trim()}
      aria-hidden="true"
      data-shared-motion="visual-clone-only"
      data-shared-label={label || undefined}
    >
      <span className="lite-shared-element-cue__glow" />
      <span className="lite-shared-element-cue__line" />
      <span className="lite-shared-element-cue__dot" />
      <span className="lite-shared-element-cue__wake" />
      <span className="lite-shared-element-cue__arrival" />
    </span>
  );
}

export function LiteProgressMorphPanel({
  children,
  className = '',
  active = false,
  motionKey = '',
  ...props
}) {
  const reducedMotion = useLiteReducedMotion();
  const spring = useSpring({
    from: !reducedMotion ? { opacity: 0, transform: 'translateY(6px) scale(0.992)' } : { opacity: 1, transform: 'none' },
    opacity: 1,
    transform: !reducedMotion && active ? 'translateY(0px) scale(1)' : 'translateY(0px) scale(1)',
    config: { tension: 420, friction: 36, clamp: true },
  });

  return (
    <animated.div
      {...props}
      className={`lite-motion-progress-morph ${active ? 'is-active' : ''} ${className}`.trim()}
      style={{ ...(props.style || {}), ...spring }}
      data-motion-key={motionKey || undefined}
    >
      {children}
    </animated.div>
  );
}

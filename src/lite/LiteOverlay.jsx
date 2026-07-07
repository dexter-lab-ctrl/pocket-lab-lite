import React, { useEffect, useId, useMemo, useRef } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import { animated, useSpring } from '@react-spring/web';
import { useDrag } from '@use-gesture/react';

export function useVisualViewportHeight(open = true) {
  useEffect(() => {
    if (!open || typeof window === 'undefined') return undefined;
    const update = () => {
      document.documentElement.style.setProperty('--lite-visual-viewport-height', `${Math.round(window.visualViewport?.height || window.innerHeight)}px`);
    };
    update();
    window.visualViewport?.addEventListener('resize', update);
    window.visualViewport?.addEventListener('scroll', update);
    window.addEventListener('resize', update);
    return () => {
      window.visualViewport?.removeEventListener('resize', update);
      window.visualViewport?.removeEventListener('scroll', update);
      window.removeEventListener('resize', update);
    };
  }, [open]);
}

export function useBodyScrollLock(open = true) {
  useEffect(() => {
    if (!open || typeof document === 'undefined') return undefined;
    const body = document.body;
    const previousOverflow = body.style.overflow;
    const previousOverscroll = body.style.overscrollBehavior;
    body.style.overflow = 'hidden';
    body.style.overscrollBehavior = 'contain';
    return () => {
      body.style.overflow = previousOverflow;
      body.style.overscrollBehavior = previousOverscroll;
    };
  }, [open]);
}

export function useEscapeToClose(open, onClose) {
  useEffect(() => {
    if (!open) return undefined;
    const onKeyDown = (event) => {
      if (event.key !== 'Escape') return;
      event.stopPropagation();
      onClose?.();
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [open, onClose]);
}

export function useFocusReturn(open, closeRef) {
  const returnRef = useRef(null);
  useEffect(() => {
    if (!open) return undefined;
    returnRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const timer = window.setTimeout(() => closeRef?.current?.focus?.({ preventScroll: true }), 0);
    return () => {
      window.clearTimeout(timer);
      const target = returnRef.current;
      window.setTimeout(() => target?.focus?.({ preventScroll: true }), 0);
    };
  }, [open, closeRef]);
}

function useReducedMotionPreference() {
  const reducedMotionRef = useRef(false);
  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return undefined;
    const query = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => { reducedMotionRef.current = Boolean(query.matches); };
    update();
    query.addEventListener?.('change', update);
    return () => query.removeEventListener?.('change', update);
  }, []);
  return reducedMotionRef;
}

export function LiteOverlayRoot({ children }) {
  if (typeof document === 'undefined') return null;
  return createPortal(children, document.body);
}

export function LiteBackdrop({ onClose, label = 'Close overlay', className = '' }) {
  return <button type="button" className={`lite-overlay-backdrop ${className}`.trim()} onClick={onClose} aria-label={label} />;
}

const LITE_SHEET_VARIANTS = {
  manage: {
    layer: 'lite-catalog-manage-layer',
    backdrop: 'lite-catalog-manage-backdrop',
    surface: 'lite-catalog-manage-sheet',
    grip: 'lite-catalog-manage-grip',
    head: 'lite-catalog-manage-head',
    close: 'lite-catalog-manage-close',
    scroll: 'lite-catalog-manage-scroll',
    eyebrow: 'Manage',
    closeLabel: 'Close app actions',
    backdropLabel: 'Close app management',
    gripLabel: 'Drag app actions sheet',
  },
  security: {
    layer: 'lite-security-overlay-layer',
    backdrop: 'lite-security-overlay-backdrop',
    surface: 'lite-security-overlay-surface',
    grip: 'lite-security-overlay-grip',
    head: 'lite-security-overlay-head',
    close: 'lite-security-overlay-close',
    scroll: 'lite-security-overlay-scroll',
    eyebrow: 'Security Details',
    closeLabel: 'Close security details',
    backdropLabel: 'Close security details',
    gripLabel: 'Drag security details sheet',
  },
};

export function LiteSheet({
  open,
  onClose,
  title,
  eyebrow,
  description = '',
  children,
  className = '',
  layerClassName = '',
  headerClassName = '',
  bodyClassName = '',
  closeClassName = '',
  gripClassName = '',
  labelledBy,
  surfaceRef,
  bodyRef,
  surfaceStyle,
  surfaceProps = {},
  gripProps = {},
  closeRef: externalCloseRef,
  SurfaceComponent = 'section',
  variant = 'manage',
  motion = 'none',
}) {
  const generatedId = useId();
  const titleId = labelledBy || `lite-sheet-title-${generatedId}`;
  const internalCloseRef = useRef(null);
  const closeRef = externalCloseRef || internalCloseRef;
  const variantClasses = LITE_SHEET_VARIANTS[variant] || LITE_SHEET_VARIANTS.manage;
  const reducedMotionRef = useReducedMotionPreference();
  const safeMotionEnabled = motion === 'safe-grip' && open;

  useVisualViewportHeight(open);
  useBodyScrollLock(open);
  useEscapeToClose(open, onClose);
  useFocusReturn(open, closeRef);

  const [{ y, scale, opacity }, api] = useSpring(() => ({
    y: 0,
    scale: 1,
    opacity: 1,
    config: { tension: 420, friction: 36, clamp: false },
  }));

  useEffect(() => {
    if (!open) return;
    api.start({ y: 0, scale: 1, opacity: 1, immediate: reducedMotionRef.current });
  }, [api, open, reducedMotionRef]);

  const bindGripDrag = useDrag(
    ({ active, movement: [, my], velocity: [, vy], direction: [, dy], cancel }) => {
      if (!safeMotionEnabled || reducedMotionRef.current) return;
      const nextY = Math.max(0, my);
      if (active) {
        api.start({ y: nextY, scale: 1 - Math.min(nextY / 2400, 0.018), immediate: true });
        return;
      }
      const shouldClose = nextY > 96 || (vy > 0.45 && dy > 0);
      if (shouldClose) {
        cancel?.();
        api.start({ y: 36, opacity: 0.96, immediate: false });
        window.setTimeout(() => onClose?.(), 80);
        return;
      }
      api.start({ y: 0, scale: 1, opacity: 1, immediate: false });
    },
    {
      axis: 'y',
      pointer: { touch: true },
      filterTaps: true,
      rubberband: true,
      from: () => [0, y.get()],
    },
  );

  const mergedGripProps = safeMotionEnabled
    ? { ...bindGripDrag(), ...gripProps }
    : gripProps;

  const AnimatedSurface = useMemo(() => animated(SurfaceComponent), [SurfaceComponent]);
  const Surface = safeMotionEnabled ? AnimatedSurface : SurfaceComponent;
  const motionStyle = safeMotionEnabled
    ? {
        y,
        scale,
        opacity,
        touchAction: 'none',
        ...surfaceStyle,
      }
    : surfaceStyle;

  if (!open) return null;
  return (
    <LiteOverlayRoot>
      <div className={`lite-overlay-root ${variantClasses.layer} ${layerClassName}`.trim()} role="presentation">
        <LiteBackdrop onClose={onClose} label={variantClasses.backdropLabel} className={variantClasses.backdrop} />
        <Surface
          ref={surfaceRef}
          className={`lite-overlay-surface ${variantClasses.surface} ${className}`.trim()}
          style={motionStyle}
          role="dialog"
          aria-modal="true"
          aria-labelledby={titleId}
          data-lite-sheet-variant={variant}
          data-lite-safe-motion={safeMotionEnabled ? 'safe-grip' : 'none'}
          {...surfaceProps}
        >
          <button type="button" className={`lite-overlay-grip ${variantClasses.grip} ${gripClassName}`.trim()} aria-label={variantClasses.gripLabel} {...mergedGripProps}>
            <span aria-hidden="true" />
          </button>
          <div className={`lite-overlay-head ${variantClasses.head} ${headerClassName}`.trim()}>
            <div>
              <span>{eyebrow || variantClasses.eyebrow}</span>
              <strong id={titleId}>{title}</strong>
              {description ? <p>{description}</p> : null}
            </div>
            <button ref={closeRef} type="button" className={`lite-overlay-close ${variantClasses.close} ${closeClassName}`.trim()} onClick={onClose} aria-label={variantClasses.closeLabel}>
              <X className="h-4 w-4" />
            </button>
          </div>
          <div ref={bodyRef} className={`lite-overlay-scroll ${variantClasses.scroll} ${bodyClassName}`.trim()}>
            {children}
          </div>
        </Surface>
      </div>
    </LiteOverlayRoot>
  );
}

export function LiteDetailsPanel({ open, onClose, title = 'Details', description = '', children }) {
  return (
    <LiteSheet open={open} onClose={onClose} title={title} eyebrow="Action Details" description={description} layerClassName="lite-details-overlay-layer" className="lite-details-panel" bodyClassName="lite-details-panel-scroll" gripClassName="lite-details-panel-grip">
      {children}
    </LiteSheet>
  );
}

export const APP_CATALOG_MANAGE_SHEET_PORTAL_OVERLAY = true;
export const LITE_OVERLAY_PRIMITIVES_READY = true;
export const LITE_OVERLAY_SAFE_GESTURE_SPRING_READY = true;

import React, { useEffect, useId, useRef } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';

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

export function LiteOverlayRoot({ children }) {
  if (typeof document === 'undefined') return null;
  return createPortal(children, document.body);
}

export function LiteBackdrop({ onClose, label = 'Close overlay', className = '' }) {
  return <button type="button" className={`lite-overlay-backdrop ${className}`.trim()} onClick={onClose} aria-label={label} />;
}

export function LiteSheet({
  open,
  onClose,
  title,
  eyebrow = 'Manage',
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
}) {
  const generatedId = useId();
  const titleId = labelledBy || `lite-sheet-title-${generatedId}`;
  const internalCloseRef = useRef(null);
  const closeRef = externalCloseRef || internalCloseRef;

  useVisualViewportHeight(open);
  useBodyScrollLock(open);
  useEscapeToClose(open, onClose);
  useFocusReturn(open, closeRef);

  if (!open) return null;
  const Surface = SurfaceComponent;
  return (
    <LiteOverlayRoot>
      <div className={`lite-overlay-root lite-catalog-manage-layer ${layerClassName}`.trim()} role="presentation">
        <LiteBackdrop onClose={onClose} label="Close app management" className="lite-catalog-manage-backdrop" />
        <Surface
          ref={surfaceRef}
          className={`lite-overlay-surface lite-catalog-manage-sheet ${className}`.trim()}
          style={surfaceStyle}
          role="dialog"
          aria-modal="true"
          aria-labelledby={titleId}
          {...surfaceProps}
        >
          <button type="button" className={`lite-overlay-grip lite-catalog-manage-grip ${gripClassName}`.trim()} aria-label="Drag app actions sheet" {...gripProps}>
            <span aria-hidden="true" />
          </button>
          <div className={`lite-overlay-head lite-catalog-manage-head ${headerClassName}`.trim()}>
            <div>
              <span>{eyebrow}</span>
              <strong id={titleId}>{title}</strong>
              {description ? <p>{description}</p> : null}
            </div>
            <button ref={closeRef} type="button" className={`lite-overlay-close lite-catalog-manage-close ${closeClassName}`.trim()} onClick={onClose} aria-label="Close app actions">
              <X className="h-4 w-4" />
            </button>
          </div>
          <div ref={bodyRef} className={`lite-overlay-scroll lite-catalog-manage-scroll ${bodyClassName}`.trim()}>
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

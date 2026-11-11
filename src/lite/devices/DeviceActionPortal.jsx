import React, { useEffect } from 'react';
import { createPortal } from 'react-dom';

/**
 * Render device action surfaces outside the animated screen stage so fixed
 * positioning remains viewport-relative. The Pocket Lab app shell is preferred
 * over document.body to preserve the active theme and shared presentation
 * context. This component owns presentation only; backend authorization and
 * device lifecycle authority remain unchanged.
 *
 * A dedicated layer/backdrop is used instead of a pseudo-element attached to
 * the sheet. That keeps the visual separation independent of the sheet's own
 * overflow rules and prevents long, scrollable content from clipping the
 * backdrop on constrained mobile viewports.
 */
let activeDeviceOverlays = 0;
let originalBodyOverflow = '';

export default function DeviceActionPortal({ children, onBackdropClick = null }) {
  useEffect(() => {
    if (typeof document === 'undefined') return undefined;
    if (activeDeviceOverlays === 0) originalBodyOverflow = document.body.style.overflow;
    activeDeviceOverlays += 1;
    document.body.style.overflow = 'hidden';
    return () => {
      activeDeviceOverlays = Math.max(0, activeDeviceOverlays - 1);
      if (activeDeviceOverlays === 0) document.body.style.overflow = originalBodyOverflow;
    };
  }, []);
  if (typeof document === 'undefined') return children;
  const host = document.querySelector('.pocket-app-shell') || document.body;
  return createPortal(
    <div className="lite-device-action-layer" data-lite-device-action-layer="true">
      <div className={`lite-device-action-backdrop ${onBackdropClick ? 'is-interactive' : ''}`.trim()} aria-hidden="true" onClick={onBackdropClick || undefined} />
      {children}
    </div>,
    host,
  );
}

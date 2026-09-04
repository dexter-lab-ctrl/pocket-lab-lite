import React from 'react';
import { createPortal } from 'react-dom';

/**
 * Render device action surfaces outside the animated screen stage so fixed
 * positioning remains viewport-relative. The Pocket Lab app shell is preferred
 * over document.body to preserve the active theme and shared presentation
 * context. This component owns presentation only; backend authorization and
 * device lifecycle authority remain unchanged.
 */
export default function DeviceActionPortal({ children }) {
  if (typeof document === 'undefined') return children;
  const host = document.querySelector('.pocket-app-shell') || document.body;
  return createPortal(children, host);
}

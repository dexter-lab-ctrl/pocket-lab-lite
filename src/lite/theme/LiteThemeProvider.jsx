import React, { useEffect } from 'react';
import { useLiteUiStore } from '../../stores/liteUiStore.js';
import { applyLiteThemePreference } from './liteThemeRuntime.js';

export function LiteThemeProvider({ children }) {
  const preference = useLiteUiStore((state) => state.appearancePreference);
  useEffect(() => {
    if (typeof window === 'undefined') return undefined;
    const media = window.matchMedia?.('(prefers-color-scheme: dark)');
    const update = () => applyLiteThemePreference(preference, { media });
    update();
    if (preference !== 'system') return undefined;
    media?.addEventListener?.('change', update);
    return () => media?.removeEventListener?.('change', update);
  }, [preference]);
  return children;
}

export function LiteThemeControl() {
  const preference = useLiteUiStore((state) => state.appearancePreference);
  const setPreference = useLiteUiStore((state) => state.setAppearancePreference);
  return <label className="lite-theme-control">
    <span className="sr-only">Appearance</span>
    <select aria-label="Appearance" value={preference} onChange={(event) => setPreference(event.target.value)}>
      <option value="system">System</option>
      <option value="light">Light</option>
      <option value="dark">Dark</option>
    </select>
  </label>;
}

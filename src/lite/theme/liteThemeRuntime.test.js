// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  LITE_THEME_STORAGE_KEY, applyLiteThemePreference, normalizeLiteThemePreference,
  readLiteThemePreference, resolveLiteTheme, saveLiteThemePreference,
} from './liteThemeRuntime.js';

beforeEach(() => {
  const meta = document.createElement('meta');
  meta.name = 'theme-color';
  meta.content = '#F4F9FF';
  document.head.appendChild(meta);
});

afterEach(() => {
  localStorage.clear();
  document.documentElement.removeAttribute('data-lite-theme');
  document.documentElement.style.colorScheme = '';
  document.querySelector('meta[name="theme-color"]')?.remove();
  vi.restoreAllMocks();
});

describe('Azure Horizon appearance contract', () => {
  it('normalizes all preferences and safely rejects malformed local values', () => {
    expect(['light','dark','system'].map(normalizeLiteThemePreference)).toEqual(['light','dark','system']);
    expect(normalizeLiteThemePreference('daylight')).toBe('light');
    expect(normalizeLiteThemePreference('garbage')).toBe('system');
    localStorage.setItem(LITE_THEME_STORAGE_KEY, 'garbage');
    expect(readLiteThemePreference()).toBe('system');
  });

  it('uses System only for resolution and never persists the resolved OS appearance', () => {
    saveLiteThemePreference('system');
    expect(resolveLiteTheme('system', false)).toBe('light');
    expect(resolveLiteTheme('system', true)).toBe('dark');
    expect(localStorage.getItem(LITE_THEME_STORAGE_KEY)).toBe('system');
    applyLiteThemePreference('system', { media: { matches: true } });
    expect(document.documentElement.dataset.liteTheme).toBe('dark');
    expect(document.documentElement.style.colorScheme).toBe('dark');
    expect(localStorage.getItem(LITE_THEME_STORAGE_KEY)).toBe('system');
  });

  it('applies the explicit theme, including meta theme color for installed PWAs', () => {
    applyLiteThemePreference('dark', { media: { matches: false } });
    expect(document.documentElement).toHaveClass('theme-pocket-lite-dark');
    expect(document.querySelector('meta[name="theme-color"]')?.content).toBe('#050607');
    applyLiteThemePreference('light', { media: { matches: true } });
    expect(document.documentElement).not.toHaveClass('theme-pocket-lite-dark');
    expect(document.documentElement.dataset.liteTheme).toBe('light');
    expect(document.documentElement.style.colorScheme).toBe('light');
  });

  it('has safe SSR/denied-storage fallbacks without operational state writes', () => {
    expect(resolveLiteTheme(undefined, false)).toBe('light');
    const denied = { getItem: () => { throw new Error('disabled'); }, setItem: () => { throw new Error('disabled'); } };
    expect(readLiteThemePreference(denied)).toBe('system');
    expect(saveLiteThemePreference('dark', denied)).toBe('dark');
    const setSpy = vi.spyOn(Storage.prototype, 'setItem');
    saveLiteThemePreference('light');
    expect(setSpy).toHaveBeenCalledWith(LITE_THEME_STORAGE_KEY, 'light');
    expect(setSpy).toHaveBeenCalledTimes(1);
  });
});

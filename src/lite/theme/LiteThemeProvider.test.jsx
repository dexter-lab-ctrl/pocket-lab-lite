// @vitest-environment jsdom
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { useLiteUiStore } from '../../stores/liteUiStore.js';
import { LiteDetailsPanel } from '../LiteOverlay.jsx';
import { LiteThemeControl, LiteThemeProvider } from './LiteThemeProvider.jsx';

let prefersDark = false;
const listeners = new Set();
window.matchMedia = vi.fn(() => ({
  get matches() { return prefersDark; },
  media: '(prefers-color-scheme: dark)',
  addEventListener: (_type, callback) => listeners.add(callback),
  removeEventListener: (_type, callback) => listeners.delete(callback),
}));

afterEach(() => {
  cleanup();
  listeners.clear();
  prefersDark = false;
  useLiteUiStore.getState().setAppearancePreference('system');
  localStorage.clear();
});

describe('Azure Horizon shared theme + portal', () => {
  it('updates and persists Light/Dark/System through the existing UI-only store', async () => {
    render(<LiteThemeProvider><LiteThemeControl /></LiteThemeProvider>);
    fireEvent.change(screen.getByRole('combobox', { name: 'Appearance' }), { target: { value: 'dark' } });
    await waitFor(() => expect(document.documentElement.dataset.liteTheme).toBe('dark'));
    expect(localStorage.getItem('pocketlab:appearance')).toBe('dark');
    fireEvent.change(screen.getByRole('combobox', { name: 'Appearance' }), { target: { value: 'light' } });
    await waitFor(() => expect(document.documentElement.dataset.liteTheme).toBe('light'));
  });

  it('responds to OS change while System is selected', async () => {
    useLiteUiStore.getState().setAppearancePreference('system');
    render(<LiteThemeProvider><LiteThemeControl /></LiteThemeProvider>);
    prefersDark = true;
    listeners.forEach((listener) => listener({ matches: true }));
    await waitFor(() => expect(document.documentElement.dataset.liteTheme).toBe('dark'));
    expect(localStorage.getItem('pocketlab:appearance')).toBe('system');
  });

  it('keeps portal sheets in the resolved root theme without nested Daylight overrides', () => {
    useLiteUiStore.getState().setAppearancePreference('dark');
    const close = vi.fn();
    render(<LiteThemeProvider>
      <LiteDetailsPanel open title="Workspace details" onClose={close}><button type="button">Inner action</button></LiteDetailsPanel>
    </LiteThemeProvider>);
    const dialog = screen.getByRole('dialog', { name: 'Workspace details' });
    expect(dialog.closest('[data-lite-overlay-portal]')).not.toHaveClass('theme-pocket-lite-daylight');
    expect(document.documentElement.dataset.liteTheme).toBe('dark');
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(close).toHaveBeenCalledTimes(1);
  });
});

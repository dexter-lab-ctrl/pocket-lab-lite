// Harmless local UI preference only. Operational state remains FastAPI-owned.
export const LITE_THEME_STORAGE_KEY = 'pocketlab:appearance';
export const LITE_THEME_PREFERENCES = Object.freeze(['light', 'dark', 'system']);

export function normalizeLiteThemePreference(value) {
  const normalized = String(value || '').toLowerCase();
  if (normalized === 'daylight') return 'light'; // old Storybook/local setting
  return LITE_THEME_PREFERENCES.includes(normalized) ? normalized : 'system';
}

export function readLiteThemePreference(storage = typeof window !== 'undefined' ? window.localStorage : null) {
  try {
    const stored = storage?.getItem(LITE_THEME_STORAGE_KEY);
    if (stored !== null && stored !== undefined) return normalizeLiteThemePreference(stored);
    return normalizeLiteThemePreference(storage?.getItem('POCKETLAB_LITE_THEME') || 'system');
  } catch {
    return 'system';
  }
}

export function resolveLiteTheme(preference, prefersDark = false) {
  const preferred = normalizeLiteThemePreference(preference);
  return preferred === 'system' ? (prefersDark ? 'dark' : 'light') : preferred;
}

export function applyLiteResolvedTheme(resolved, doc = typeof document !== 'undefined' ? document : null) {
  if (!doc?.documentElement) return;
  const theme = resolved === 'dark' ? 'dark' : 'light';
  const root = doc.documentElement;
  root.dataset.liteTheme = theme;
  root.dataset.pocketlabLiteTheme = theme === 'dark' ? 'dark' : 'daylight';
  root.classList.toggle('theme-pocket-lite-dark', theme === 'dark');
  root.classList.toggle('theme-pocket-lite-daylight', theme === 'light');
  root.style.colorScheme = theme;
  const metaTheme = doc.querySelector('meta[name="theme-color"]');
  if (metaTheme) metaTheme.setAttribute('content', theme === 'dark' ? '#050607' : '#F4F9FF');
  const appleBar = doc.querySelector('meta[name="apple-mobile-web-app-status-bar-style"]');
  if (appleBar) appleBar.setAttribute('content', theme === 'dark' ? 'black' : 'default');
}

export function applyLiteThemePreference(preference, options = {}) {
  const media = options.media || (typeof window !== 'undefined' ? window.matchMedia?.('(prefers-color-scheme: dark)') : null);
  const resolved = resolveLiteTheme(preference, Boolean(media?.matches));
  applyLiteResolvedTheme(resolved, options.doc);
  return resolved;
}

export function saveLiteThemePreference(preference, storage = typeof window !== 'undefined' ? window.localStorage : null) {
  const normalized = normalizeLiteThemePreference(preference);
  try { storage?.setItem(LITE_THEME_STORAGE_KEY, normalized); } catch { /* private browsing */ }
  return normalized;
}

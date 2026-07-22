import { getLiteManifestShortcutDefinitions } from '../lite/liteNavigationMetadata.js';

export const LITE_INSTALL_ID = '/pocket-lab-lite/';
export const LITE_INSTALL_START_URL = '/';
export const LITE_INSTALL_SCOPE = '/';
export const LITE_INSTALL_THEME_COLOR = '#f8fafc';
export const LITE_INSTALL_BACKGROUND_COLOR = '#f8fafc';

export const LITE_INSTALL_ICON_ASSETS = Object.freeze([
  Object.freeze({ src: '/icons/pocket-lab-lite-192.svg', sizes: '192x192', type: 'image/svg+xml', purpose: 'any' }),
  Object.freeze({ src: '/icons/pocket-lab-lite-512.svg', sizes: '512x512', type: 'image/svg+xml', purpose: 'any' }),
  Object.freeze({ src: '/icons/pocket-lab-lite-maskable-192.svg', sizes: '192x192', type: 'image/svg+xml', purpose: 'maskable' }),
  Object.freeze({ src: '/icons/pocket-lab-lite-maskable-512.svg', sizes: '512x512', type: 'image/svg+xml', purpose: 'maskable' }),
]);

const FORBIDDEN_INSTALL_PATH = /^\/(?:api|apps|terminal|gitea|docs)(?:\/|$)/i;

function isSafeSameOriginPath(value, { allowQuery = false } = {}) {
  const raw = String(value || '').trim();
  if (!raw.startsWith('/') || raw.startsWith('//') || raw.includes('\\')) return false;
  try {
    const parsed = new URL(raw, 'https://pocketlab.invalid/');
    if (parsed.origin !== 'https://pocketlab.invalid') return false;
    if (parsed.username || parsed.password || parsed.hash) return false;
    if (!allowQuery && parsed.search) return false;
    if (FORBIDDEN_INSTALL_PATH.test(parsed.pathname)) return false;
    return true;
  } catch {
    return false;
  }
}

export function createLiteInstallManifest() {
  const shortcutIcon = Object.freeze([
    Object.freeze({ src: '/icons/pocket-lab-lite-192.svg', sizes: '192x192', type: 'image/svg+xml' }),
  ]);
  const shortcuts = getLiteManifestShortcutDefinitions().map((shortcut) => ({
    name: shortcut.name,
    short_name: shortcut.short_name,
    description: shortcut.description,
    url: shortcut.url,
    icons: shortcutIcon,
  }));

  return {
    id: LITE_INSTALL_ID,
    name: 'Pocket Lab Lite',
    short_name: 'Pocket Lab',
    description: 'Self-hosted workspace for private apps, devices, safety, and recovery.',
    start_url: LITE_INSTALL_START_URL,
    scope: LITE_INSTALL_SCOPE,
    display: 'standalone',
    display_override: ['window-controls-overlay', 'standalone', 'minimal-ui', 'browser'],
    orientation: 'any',
    theme_color: LITE_INSTALL_THEME_COLOR,
    background_color: LITE_INSTALL_BACKGROUND_COLOR,
    categories: ['utilities', 'productivity', 'security'],
    lang: 'en',
    dir: 'ltr',
    icons: LITE_INSTALL_ICON_ASSETS,
    shortcuts,
    prefer_related_applications: false,
  };
}

export function validateLiteInstallManifest(manifest = {}) {
  const errors = [];
  const requiredStrings = ['id', 'name', 'short_name', 'description', 'start_url', 'scope', 'display', 'orientation', 'theme_color', 'background_color', 'lang', 'dir'];
  for (const field of requiredStrings) {
    if (!String(manifest?.[field] || '').trim()) errors.push(`missing:${field}`);
  }
  if (!isSafeSameOriginPath(manifest.id)) errors.push('invalid:id');
  if (!isSafeSameOriginPath(manifest.start_url)) errors.push('invalid:start_url');
  if (manifest.scope !== '/') errors.push('invalid:scope');
  if (manifest.display !== 'standalone') errors.push('invalid:display');
  if (manifest.orientation !== 'any') errors.push('invalid:orientation');
  if (!Array.isArray(manifest.display_override) || manifest.display_override[0] !== 'window-controls-overlay' || !manifest.display_override.includes('standalone')) {
    errors.push('invalid:display_override');
  }

  const icons = Array.isArray(manifest.icons) ? manifest.icons : [];
  const requiredIcons = new Set(['192x192:any', '512x512:any', '192x192:maskable', '512x512:maskable']);
  for (const icon of icons) {
    if (!isSafeSameOriginPath(icon?.src)) errors.push('invalid:icon_path');
    requiredIcons.delete(`${icon?.sizes}:${icon?.purpose}`);
  }
  if (requiredIcons.size) errors.push(`missing:icons:${[...requiredIcons].sort().join(',')}`);

  const shortcuts = Array.isArray(manifest.shortcuts) ? manifest.shortcuts : [];
  const shortcutUrls = new Set();
  for (const shortcut of shortcuts) {
    if (!isSafeSameOriginPath(shortcut?.url, { allowQuery: true })) errors.push('invalid:shortcut_url');
    if (!/^\/\?screen=(?:catalog|devices|security|recovery)$/.test(String(shortcut?.url || ''))) errors.push('invalid:shortcut_screen');
    if (shortcutUrls.has(shortcut.url)) errors.push('duplicate:shortcut_url');
    shortcutUrls.add(shortcut.url);
  }
  if (shortcuts.length !== 4) errors.push('invalid:shortcut_count');

  return Object.freeze({ valid: errors.length === 0, errors: Object.freeze(errors) });
}

export const LITE_INSTALL_MANIFEST = Object.freeze(createLiteInstallManifest());
const validation = validateLiteInstallManifest(LITE_INSTALL_MANIFEST);
if (!validation.valid) {
  throw new Error(`Invalid Pocket Lab Lite install manifest: ${validation.errors.join(', ')}`);
}

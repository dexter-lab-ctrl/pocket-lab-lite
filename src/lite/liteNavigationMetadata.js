export const DEFAULT_LITE_SCREEN_ID = 'home';
export const LITE_SCREEN_LAUNCH_PARAMETER = 'screen';

export const LITE_SCREEN_METADATA = Object.freeze([
  Object.freeze({ id: 'home', label: 'Home' }),
  Object.freeze({
    id: 'catalog',
    label: 'App Catalog',
    shortcut: Object.freeze({
      name: 'Apps',
      shortName: 'Apps',
      description: 'Open the Pocket Lab Lite app workspace.',
    }),
  }),
  Object.freeze({ id: 'identity', label: 'Identity & Access' }),
  Object.freeze({
    id: 'security',
    label: 'Security',
    shortcut: Object.freeze({
      name: 'Security',
      shortName: 'Security',
      description: 'Review the current Pocket Lab Lite safety summary.',
    }),
  }),
  Object.freeze({
    id: 'devices',
    label: 'Devices',
    shortcut: Object.freeze({
      name: 'Devices',
      shortName: 'Devices',
      description: 'Open connected devices and remote-access status.',
    }),
  }),
  Object.freeze({ id: 'rules', label: 'Rules' }),
  Object.freeze({
    id: 'recovery',
    label: 'Recovery',
    shortcut: Object.freeze({
      name: 'Recovery',
      shortName: 'Recovery',
      description: 'Review backup and recovery readiness.',
    }),
  }),
]);

const LITE_SCREEN_IDS = new Set(LITE_SCREEN_METADATA.map((item) => item.id));
const LITE_SHORTCUT_SCREEN_IDS = new Set(
  LITE_SCREEN_METADATA.filter((item) => item.shortcut).map((item) => item.id),
);

function normalizedScreenValue(value) {
  return String(value || '').trim().toLowerCase().slice(0, 32);
}

function toLaunchUrl(locationLike = globalThis.location) {
  try {
    if (locationLike instanceof URL) return new URL(locationLike.href);
    if (typeof locationLike === 'string') return new URL(locationLike, 'https://pocketlab.invalid/');
    const href = locationLike?.href;
    if (href) return new URL(href, 'https://pocketlab.invalid/');
    const pathname = String(locationLike?.pathname || '/');
    const search = String(locationLike?.search || '');
    const hash = String(locationLike?.hash || '');
    return new URL(`${pathname}${search}${hash}`, 'https://pocketlab.invalid/');
  } catch {
    return new URL('/', 'https://pocketlab.invalid/');
  }
}

export function isLiteScreenId(value) {
  return LITE_SCREEN_IDS.has(normalizedScreenValue(value));
}

export function isLiteShortcutScreenId(value) {
  return LITE_SHORTCUT_SCREEN_IDS.has(normalizedScreenValue(value));
}

export function normalizeLiteScreenId(value, fallback = DEFAULT_LITE_SCREEN_ID) {
  const normalized = normalizedScreenValue(value);
  if (LITE_SCREEN_IDS.has(normalized)) return normalized;
  const normalizedFallback = normalizedScreenValue(fallback);
  return LITE_SCREEN_IDS.has(normalizedFallback) ? normalizedFallback : DEFAULT_LITE_SCREEN_ID;
}

export function createLiteScreenLaunchUrl(screenId) {
  const normalized = normalizeLiteScreenId(screenId);
  return `/?${LITE_SCREEN_LAUNCH_PARAMETER}=${encodeURIComponent(normalized)}`;
}

export function parseLiteScreenLaunch(locationLike = globalThis.location, fallback = DEFAULT_LITE_SCREEN_ID) {
  const url = toLaunchUrl(locationLike);
  const requested = normalizedScreenValue(url.searchParams.get(LITE_SCREEN_LAUNCH_PARAMETER));
  const hasRequestedScreen = requested.length > 0;
  const valid = !hasRequestedScreen || isLiteScreenId(requested);
  return Object.freeze({
    requested_screen_id: hasRequestedScreen ? requested : null,
    screen_id: normalizeLiteScreenId(requested, fallback),
    valid,
    source: hasRequestedScreen ? (isLiteShortcutScreenId(requested) ? 'manifest-shortcut' : 'screen-link') : 'default',
  });
}

export function initialLiteScreenIdFromLocation(locationLike = globalThis.location) {
  return parseLiteScreenLaunch(locationLike).screen_id;
}

export function replaceLiteScreenLaunch(screenId, {
  historyObject = globalThis.history,
  locationObject = globalThis.location,
} = {}) {
  if (!historyObject?.replaceState || !locationObject) return false;
  const pathname = String(locationObject.pathname || '/');
  if (!['/', '/index.html'].includes(pathname)) return false;
  const normalized = normalizeLiteScreenId(screenId);
  const nextUrl = createLiteScreenLaunchUrl(normalized);
  try {
    historyObject.replaceState(
      { ...(historyObject.state || {}), pocketLabLiteScreen: normalized },
      '',
      nextUrl,
    );
    return true;
  } catch {
    return false;
  }
}

export function getLiteManifestShortcutDefinitions() {
  return LITE_SCREEN_METADATA
    .filter((item) => item.shortcut)
    .map((item) => Object.freeze({
      id: item.id,
      name: item.shortcut.name,
      short_name: item.shortcut.shortName,
      description: item.shortcut.description,
      url: createLiteScreenLaunchUrl(item.id),
    }));
}

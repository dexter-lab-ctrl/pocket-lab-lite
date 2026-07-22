import React from 'react';
import HomeScreen from './LiteHome.jsx';
import { DEFAULT_LITE_SCREEN_ID, NAV_ITEMS, normalizeLiteScreenId } from './liteNavigationConfig.js';
import { createLiteScreenPreloader } from './liteNavigationRuntime.js';

const SCREEN_DEFINITIONS = Object.freeze({
  home: Object.freeze({
    component: HomeScreen,
    intrinsicSize: '44rem',
    idlePreload: 'catalog',
  }),
  catalog: Object.freeze({
    loader: () => import('./LiteCatalog.jsx'),
    intrinsicSize: '58rem',
    idlePreload: 'devices',
  }),
  identity: Object.freeze({
    loader: () => import('./LiteIdentity.jsx'),
    intrinsicSize: '46rem',
    idlePreload: 'rules',
  }),
  security: Object.freeze({
    loader: () => import('./LiteSecurity.jsx'),
    intrinsicSize: '52rem',
    idlePreload: 'recovery',
  }),
  devices: Object.freeze({
    loader: () => import('./LiteDevices.jsx'),
    intrinsicSize: '60rem',
    idlePreload: 'security',
  }),
  rules: Object.freeze({
    loader: () => import('./LiteRules.jsx'),
    intrinsicSize: '42rem',
    idlePreload: 'identity',
  }),
  recovery: Object.freeze({
    loader: () => import('./LiteRecovery.jsx'),
    intrinsicSize: '54rem',
    idlePreload: 'catalog',
  }),
});

export const LITE_SCREEN_REGISTRY = Object.freeze(NAV_ITEMS.map((item) => Object.freeze({
  ...item,
  ...SCREEN_DEFINITIONS[item.id],
})));

const screenById = new Map(LITE_SCREEN_REGISTRY.map((entry) => [entry.id, entry]));
const modulePromises = new Map();
const lazyComponents = new Map();

function sanitizedDiagnostic(eventName, detail) {
  if (!import.meta.env.DEV) return;
  console.warn(`[Pocket Lab Lite] ${eventName}`, { screenId: detail?.screenId || 'unknown' });
}

function loadScreenModule(screenId) {
  const entry = screenById.get(screenId);
  if (!entry?.loader) return Promise.resolve({ default: entry?.component || HomeScreen });
  if (modulePromises.has(screenId)) return modulePromises.get(screenId);

  const modulePromise = entry.loader().catch((error) => {
    modulePromises.delete(screenId);
    throw error;
  });
  modulePromises.set(screenId, modulePromise);
  return modulePromise;
}

const screenPreloader = createLiteScreenPreloader({
  loaders: new Map(LITE_SCREEN_REGISTRY.filter((entry) => entry.loader).map((entry) => [
    entry.id,
    () => loadScreenModule(entry.id),
  ])),
  diagnostic: sanitizedDiagnostic,
});

export function getLiteScreenEntry(screenId) {
  return screenById.get(normalizeLiteScreenId(screenId)) || screenById.get(DEFAULT_LITE_SCREEN_ID);
}

export function getLiteScreenComponent(screenId, retryGeneration = 0) {
  const entry = getLiteScreenEntry(screenId);
  if (entry.component) return entry.component;

  const cacheKey = `${entry.id}:${Math.max(0, Number(retryGeneration) || 0)}`;
  if (!lazyComponents.has(cacheKey)) {
    lazyComponents.set(cacheKey, React.lazy(() => loadScreenModule(entry.id)));
  }
  return lazyComponents.get(cacheKey);
}

export function preloadLiteScreen(screenId, options = {}) {
  const entry = getLiteScreenEntry(screenId);
  return screenPreloader.preload(entry.id, options);
}

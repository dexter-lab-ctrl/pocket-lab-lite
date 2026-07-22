import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';
import { readFileSync } from 'node:fs';
import {
  LITE_SAFE_RUNTIME_READ_MAX_AGE_SECONDS,
  LITE_SAFE_RUNTIME_READ_MAX_ENTRIES,
  LITE_WORKBOX_CACHE_NAMES,
} from './src/lib/liteOfflineReadPolicy.js';

const packageMetadata = JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf8'));
const pocketLabBuildId = process.env.POCKETLAB_BUILD_ID || process.env.GITHUB_SHA || packageMetadata.version || 'development';

const noPwaFallbackPattern = /^\/(?:api|terminal|apps|gitea|docs)(?:\/|$)|^\/openapi\.json$/;

export default defineConfig({
  define: {
    'import.meta.env.VITE_POCKETLAB_BUILD_ID': JSON.stringify(pocketLabBuildId),
  },
  build: {
    manifest: true,
  },
  plugins: [
    react(),
    VitePWA({
      registerType: 'prompt',
      includeAssets: ['icon.svg'],
      workbox: {
        cleanupOutdatedCaches: true,
        navigationPreload: true,
        navigateFallback: '/index.html',
        navigateFallbackDenylist: [noPwaFallbackPattern],
        runtimeCaching: [
          {
            urlPattern: ({ request, url }) => request.method === 'GET'
              && request.mode === 'navigate'
              && url.origin === self.location.origin
              && !/^\/(?:api|terminal|apps|gitea|docs)(?:\/|$)|^\/openapi\.json$/.test(url.pathname),
            handler: 'NetworkFirst',
            options: {
              cacheName: LITE_WORKBOX_CACHE_NAMES.appShell,
              networkTimeoutSeconds: 4,
              precacheFallback: { fallbackURL: '/index.html' },
              expiration: { maxEntries: 4, maxAgeSeconds: 60 * 60 * 24 },
              cacheableResponse: { statuses: [200] },
            },
          },
          {
            urlPattern: ({ url, request }) => request.method === 'GET'
              && url.origin === self.location.origin
              && /^(?:\/api\/lite\/(?:status|catalog|revisions|apps\/lifecycle|apps\/photoprism\/actions|security\/(?:summary|freshness|progress)|security\/profiles\/(?:quick|full|app)|security\/history|recovery\/(?:summary|backups)))$/.test(url.pathname),
            handler: 'NetworkFirst',
            options: {
              cacheName: LITE_WORKBOX_CACHE_NAMES.safeReads,
              networkTimeoutSeconds: 3,
              expiration: {
                maxEntries: LITE_SAFE_RUNTIME_READ_MAX_ENTRIES,
                maxAgeSeconds: LITE_SAFE_RUNTIME_READ_MAX_AGE_SECONDS,
              },
              cacheableResponse: { statuses: [200] },
            },
          },
          {
            urlPattern: ({ request, url }) => url.origin === self.location.origin
              && !/^\/(?:api|terminal|apps|gitea|docs)(?:\/|$)|^\/openapi\.json$/.test(url.pathname)
              && ['style', 'script', 'worker'].includes(request.destination),
            handler: 'StaleWhileRevalidate',
            options: {
              cacheName: LITE_WORKBOX_CACHE_NAMES.staticAssets,
              expiration: { maxEntries: 60, maxAgeSeconds: 60 * 60 * 24 * 30 },
              cacheableResponse: { statuses: [200] },
            },
          },
          {
            urlPattern: ({ request, url }) => url.origin === self.location.origin
              && !/^\/(?:api|terminal|apps|gitea|docs)(?:\/|$)|^\/openapi\.json$/.test(url.pathname)
              && (request.destination === 'image' || /\/manifest\.webmanifest$/.test(url.pathname)),
            handler: 'CacheFirst',
            options: {
              cacheName: LITE_WORKBOX_CACHE_NAMES.images,
              expiration: { maxEntries: 40, maxAgeSeconds: 60 * 60 * 24 * 30 },
              cacheableResponse: { statuses: [200] },
            },
          },
        ],
      },
      manifest: {
        id: '/pocketlab-admin/',
        name: 'Pocket Lab Admin Console',
        short_name: 'Lab Admin',
        start_url: '/?app=admin_console',
        scope: '/',
        theme_color: '#020617',
        background_color: '#020617',
        display: 'standalone',
        icons: [
          {
            src: 'icon.svg',
            sizes: '192x192 512x512',
            type: 'image/svg+xml',
            purpose: 'any maskable'
          }
        ]
      }
    })
  ]
});

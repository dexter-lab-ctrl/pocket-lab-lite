import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';
import { readFileSync } from 'node:fs';

const packageMetadata = JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf8'));
const pocketLabBuildId = process.env.POCKETLAB_BUILD_ID || process.env.GITHUB_SHA || packageMetadata.version || 'development';

const safeLiteReadApiPattern = /^\/api\/lite\/(?:status|catalog|fleet|security|recovery|apps\/photoprism\/actions)$/;
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
      registerType: 'autoUpdate',
      includeAssets: ['icon.svg'],
      workbox: {
        cleanupOutdatedCaches: true,
        navigateFallback: '/index.html',
        navigateFallbackDenylist: [noPwaFallbackPattern],
        runtimeCaching: [
          {
            urlPattern: ({ request }) => request.destination === 'document',
            handler: 'NetworkFirst',
            options: {
              cacheName: 'pocketlab-lite-app-shell-v1',
              networkTimeoutSeconds: 4,
              expiration: { maxEntries: 4, maxAgeSeconds: 60 * 60 * 24 },
              cacheableResponse: { statuses: [200] },
            },
          },
          {
            urlPattern: ({ url, request }) => request.method === 'GET' && url.origin === self.location.origin && safeLiteReadApiPattern.test(url.pathname),
            handler: 'NetworkFirst',
            options: {
              cacheName: 'pocketlab-lite-safe-read-api-v1',
              networkTimeoutSeconds: 3,
              expiration: { maxEntries: 12, maxAgeSeconds: 60 * 10 },
              cacheableResponse: { statuses: [200] },
            },
          },
          {
            urlPattern: ({ request }) => ['style', 'script', 'worker'].includes(request.destination),
            handler: 'StaleWhileRevalidate',
            options: {
              cacheName: 'pocketlab-lite-static-assets-v2',
              expiration: { maxEntries: 60, maxAgeSeconds: 60 * 60 * 24 * 30 },
              cacheableResponse: { statuses: [200] },
            },
          },
          {
            urlPattern: ({ request, url }) => request.destination === 'image' || /\/manifest\.webmanifest$/.test(url.pathname),
            handler: 'CacheFirst',
            options: {
              cacheName: 'pocketlab-lite-icons-images-v1',
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

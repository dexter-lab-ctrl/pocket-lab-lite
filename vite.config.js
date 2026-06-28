import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['icon.svg'],
      workbox: {
        navigateFallbackDenylist: [/^\/api/, /^\/terminal/, /^\/apps\//, /^\/gitea\//, /^\/docs/, /^\/openapi\.json/]
      },
      manifest: {
        id: '/pocketlab-admin/',
        name: 'Pocket Lab Admin Console',
        short_name: 'Lab Admin', // Distinct from PhotoPrism
        // CRITICAL FIX: The unique query parameter prevents Android from grouping this with PhotoPrism
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

/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      // One service worker, registered only by src/services/pwa.ts; new versions wait for the user (no surprise reloads).
      registerType: 'prompt',
      injectRegister: false,
      // public/manifest.webmanifest is the single source of the manifest.
      manifest: false,
      workbox: {
        // App shell, build assets, icons and the manifest (everything in dist with these extensions).
        globPatterns: ['**/*.{js,css,html,svg,png,webmanifest}'],
        navigateFallback: '/index.html',
        navigateFallbackDenylist: [/^\/api\//],
        cleanupOutdatedCaches: true,
        // Explicit allowlist: only public font files are cached at runtime. API calls
        // (patient histories, predictions, alerts, live events) are never cached and
        // go straight to the network, so offline they fail visibly instead of showing old data.
        runtimeCaching: [
          {
            urlPattern: /^https:\/\/fonts\.googleapis\.com\//,
            handler: 'StaleWhileRevalidate',
            options: { cacheName: 'vg-google-fonts-css', expiration: { maxEntries: 8 } },
          },
          {
            urlPattern: /^https:\/\/fonts\.gstatic\.com\//,
            handler: 'CacheFirst',
            options: {
              cacheName: 'vg-google-fonts-files',
              expiration: { maxEntries: 30, maxAgeSeconds: 60 * 60 * 24 * 365 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
        ],
      },
      devOptions: { enabled: false },
    }),
  ],
  server: { port: 5173 },
  test: { environment: 'jsdom', globals: true, setupFiles: ['./src/test/setup.ts'] },
});

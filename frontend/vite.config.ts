import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'
import { retainAssets } from './scripts/retainAssets'

const retainedAssets = retainAssets()

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    react(),
    retainedAssets.plugin,
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['saggia-mark.svg', 'favicon.svg', 'icon-192.png', 'icon-512.png', 'icon-192-maskable.png', 'icon-512-maskable.png', 'apple-touch-icon.png', 'favicon.png', 'favicon-16.png', 'logo-mark.png'],
      manifest: {
        name: 'SaggIA',
        short_name: 'SaggIA',
        description: 'Studio privato per scrivere saggi documentati.',
        theme_color: '#163b39',
        background_color: '#F4F0EA',
        display: 'standalone',
        start_url: '/',
        scope: '/',
        icons: [
          {
            src: '/icon-192.png',
            sizes: '192x192',
            type: 'image/png',
          },
          {
            src: '/icon-512.png',
            sizes: '512x512',
            type: 'image/png',
          },
          {
            src: '/icon-192-maskable.png',
            sizes: '192x192',
            type: 'image/png',
            purpose: 'maskable',
          },
          {
            src: '/icon-512-maskable.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
        ],
      },
      workbox: {
        cacheId: 'saggia',
        navigateFallbackDenylist: [/^\/api(?:\/|$)/],
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
        manifestTransforms: [async entries => ({ manifest: entries.filter(entry => retainedAssets.isCurrentAsset(entry.url)), warnings: [] })],
        runtimeCaching: [
          {
            urlPattern: /^https:\/\/fonts\.googleapis\.com\/.*/i,
            handler: 'CacheFirst',
            options: {
              cacheName: 'saggia-google-fonts-cache',
              expiration: {
                maxEntries: 10,
                maxAgeSeconds: 60 * 60 * 24 * 365, // 1 year
              },
            },
          },
          {
            urlPattern: /^https:\/\/fonts\.gstatic\.com\/.*/i,
            handler: 'CacheFirst',
            options: {
              cacheName: 'saggia-google-fonts-static-cache',
              expiration: {
                maxEntries: 10,
                maxAgeSeconds: 60 * 60 * 24 * 365, // 1 year
              },
            },
          },
          {
            urlPattern: /\/api\/.*/i,
            handler: 'NetworkOnly',
          },
        ],
      },
    }),
  ],
  server: {
    host: '127.0.0.1',
    port: 5174,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: '../backend/static',
    emptyOutDir: false,
  },
})


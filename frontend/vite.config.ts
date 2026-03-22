import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.svg', 'icon-192.png', 'icon-512.png', 'icon-192-maskable.png', 'icon-512-maskable.png', 'apple-touch-icon.png', 'favicon.png', 'favicon-16.png', 'logo-narrai.png', 'logo-narrai-header.png'],
      manifest: {
        name: 'NarrAI - Crea libri con AI',
        short_name: 'NarrAI',
        description: 'Crea libri unici con l\'intelligenza artificiale',
        theme_color: '#0f3460',
        background_color: '#0f3460',
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
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
        runtimeCaching: [
          {
            urlPattern: /^https:\/\/fonts\.googleapis\.com\/.*/i,
            handler: 'CacheFirst',
            options: {
              cacheName: 'google-fonts-cache',
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
              cacheName: 'google-fonts-static-cache',
              expiration: {
                maxEntries: 10,
                maxAgeSeconds: 60 * 60 * 24 * 365, // 1 year
              },
            },
          },
          {
            urlPattern: /\/api\/.*/i,
            handler: 'NetworkFirst',
            options: {
              cacheName: 'api-cache',
              networkTimeoutSeconds: 10,
            },
          },
        ],
      },
    }),
  ],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8004',
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) {
            return undefined;
          }

          if (
            id.includes('/react/') ||
            id.includes('/react-dom/') ||
            id.includes('/scheduler/')
          ) {
            return 'vendor-react';
          }

          if (id.includes('/react-router/') || id.includes('/react-router-dom/')) {
            return 'vendor-router';
          }

          if (id.includes('/framer-motion/')) {
            return 'vendor-motion';
          }

          if (id.includes('/recharts/') || id.includes('/victory-vendor/')) {
            return 'vendor-charts';
          }

          if (id.includes('/@dnd-kit/')) {
            return 'vendor-dnd';
          }

          if (
            id.includes('/react-markdown/') ||
            id.includes('/remark-gfm/') ||
            id.includes('/remark-') ||
            id.includes('/rehype-') ||
            id.includes('/unified/') ||
            id.includes('/micromark/') ||
            id.includes('/mdast-util-') ||
            id.includes('/hast-util-') ||
            id.includes('/vfile/')
          ) {
            return 'vendor-markdown';
          }

          if (id.includes('/lucide-react/')) {
            return 'vendor-ui';
          }

          return 'vendor-misc';
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    css: true,
  },
})



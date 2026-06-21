import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  server: {
    allowedHosts: true,
    proxy: Object.fromEntries(
      ['/onboarding', '/profiles', '/sessions', '/chat', '/conversations', '/rides', '/adaptations', '/health', '/calendar'].map((path) => [
        path,
        {
          target: 'http://localhost:8000',
          changeOrigin: true,
          bypass(req) {
            // Let Vite serve index.html for browser navigation (HTML requests)
            if (req.headers?.accept?.includes('text/html')) return req.url ?? '/'
          },
        },
      ])
    ),
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.ico', 'apple-touch-icon.png'],
      manifest: {
        name: 'PacerAI',
        short_name: 'PacerAI',
        theme_color: '#228BE6',
        background_color: '#F9F9FA',
        display: 'standalone',
        start_url: '/',
        icons: [
          {
            src: 'apple-touch-icon.png',
            sizes: '180x180',
            type: 'image/png',
          },
          {
            src: 'pwa-192x192.png',
            sizes: '192x192',
            type: 'image/png',
          },
          {
            src: 'pwa-512x512.png',
            sizes: '512x512',
            type: 'image/png',
          },
        ],
      },
      workbox: {
        navigateFallback: '/index.html',
        runtimeCaching: [
          {
            urlPattern: /^https:\/\/.*\/api\/sessions\/session\/.*/i,
            handler: 'NetworkFirst',
            options: {
              cacheName: 'session-cache',
              expiration: { maxEntries: 5 },
            },
          },
        ],
      },
    }),
  ],
})

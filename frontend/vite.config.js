import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

const DJANGO = 'http://127.0.0.1:8000'

// https://vite.dev/config/
export default defineConfig(({ command }) => ({
  plugins: [vue(), command === 'serve' && vueDevTools()].filter(Boolean),
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  // In production Django serves the built files under /static/.
  base: command === 'build' ? '/static/' : '/',
  build: {
    outDir: '../djangoProject/spa',
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    // Lets a temporary public link (Cloudflare Quick Tunnel or ngrok) reach the dev server.
    allowedHosts: ['.trycloudflare.com', '.ngrok-free.app', '.ngrok-free.dev'],
    // The browser only ever talks to this one address; Vite forwards these paths to Django.
    proxy: {
      '/api': DJANGO,
      '/admin': DJANGO,
      '/static/admin': DJANGO,
      '/static/rest_framework': DJANGO,
      '/static/drf_spectacular_sidecar': DJANGO,
    },
  },
}))

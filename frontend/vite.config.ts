import path from 'node:path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    // Bound explicitly to IPv4: left to resolve "localhost" itself, Vite binds
    // only [::1], and Chrome — which tries 127.0.0.1 first — shows an error page.
    host: '127.0.0.1',
    // Dev-server only; it has no effect on `npm run build`.
    //
    // With VITE_API_URL set to an absolute URL — which every existing script and
    // harness does — requests never touch this proxy. It exists for the one case
    // that cannot use an absolute URL: sharing the running app over a tunnel,
    // where the API has to look same-origin or CORS rejects it and the tunnel
    // hostname is random so it cannot be added to ALLOWED_ORIGINS in advance.
    //
    // Run it as:  VITE_API_URL= npm run dev
    proxy: {
      '/api': {
        target: process.env.DEV_API_TARGET ?? 'http://127.0.0.1:8020',
        changeOrigin: true,
      },
    },
    // Vite rejects requests whose Host header it does not recognise, which is a
    // sensible default and is exactly what a tunnel sends. Only the tunnel
    // provider's domain is allowed, not a wildcard.
    allowedHosts: ['.trycloudflare.com'],
  },
})

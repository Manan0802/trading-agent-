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
  },
})

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev server binds to 0.0.0.0 so the dashboard is reachable from your phone
// on the same network during development. Production serving + the
// Cloudflare Tunnel come in Phase 4.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 4280,
    host: true,
    proxy: {
      '/api': 'http://localhost:8787',
    },
  },
  preview: {
    port: 4280,
    host: true,
  },
})

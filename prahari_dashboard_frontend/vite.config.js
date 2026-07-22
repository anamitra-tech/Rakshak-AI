import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      // 127.0.0.1, not localhost: uvicorn's default bind (no --host flag,
      // per the backend README's own run command) is IPv4-only
      // (127.0.0.1). On this machine Node's dns.lookup resolves
      // "localhost" to the IPv6 loopback (::1) first, which nothing is
      // listening on -- every proxied /api/* call 502'd as a result
      // (confirmed: curl -6 http://localhost:8000 fails to connect while
      // curl -4 succeeds). Forcing the literal IPv4 address sidesteps the
      // resolution order entirely.
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
})

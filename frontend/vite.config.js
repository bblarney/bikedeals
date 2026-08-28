import process from 'node:process'

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Vite does not read PORT. Without this it silently auto-increments off a
    // busy 5173 and says so only in its own stdout, so anything that asked for
    // a specific port (a second dev session, CI tooling) ends up pointing at a
    // dead one. Falling through to undefined keeps the normal 5173 default.
    port: process.env.PORT ? Number(process.env.PORT) : undefined,
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})

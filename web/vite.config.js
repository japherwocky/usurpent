import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

// In production Tornado serves the built app from web/dist. In development
// Vite serves the app and proxies the WebSocket to the running Tornado server.
export default defineConfig({
  plugins: [svelte()],
  server: {
    proxy: {
      '/ws': {
        target: 'ws://localhost:8001',
        ws: true,
      },
    },
  },
  build: {
    outDir: 'dist',
  },
});

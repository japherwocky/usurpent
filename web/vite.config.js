import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

// In production Tornado serves the built app from web/dist. In development
// Vite serves the app and proxies the WebSocket to the running Tornado server.
export default defineConfig({
  plugins: [svelte()],
  server: {
    // The project lives on a Windows-mounted drive (/mnt/d) under WSL, where
    // inotify file-change events don't propagate reliably. Poll instead so
    // Vite picks up edits without a manual touch/restart.
    watchOptions: { usePolling: true },
    proxy: {
      '/api': {
        target: 'http://localhost:8011',
      },
      '/ws': {
        target: 'ws://localhost:8011',
        ws: true,
      },
    },
  },
  build: {
    outDir: 'dist',
  },
});

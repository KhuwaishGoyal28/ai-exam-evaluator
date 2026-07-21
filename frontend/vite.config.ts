import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  // base must be "/" so all asset URLs are absolute — required when FastAPI
  // serves index.html from a non-root directory path
  base: '/',
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      // In local dev, proxy /api calls to the FastAPI backend
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    // Output to frontend/dist/ — build.sh copies this to backend/static/
    outDir: 'dist',
    emptyOutDir: true,
  },
});

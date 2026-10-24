import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

// In development the Flask API is proxied so the browser sees a single origin
// (cookies + CSRF work exactly like in production). The backend port is read
// from PORT in ../.env or ../backend/.env (backend/.env wins), default 5000.
export default defineConfig(({ mode }) => {
  const env = { ...loadEnv(mode, '..', ''), ...loadEnv(mode, '../backend', '') };
  const backend = process.env.VITE_BACKEND_URL || `http://localhost:${env.PORT || 5000}`;

  return {
    plugins: [react()],
    server: {
      port: 5180,
      proxy: {
        '/api': backend,
      },
    },
    preview: {
      proxy: {
        '/api': backend,
      },
    },
    build: {
      chunkSizeWarningLimit: 1200,
      rollupOptions: {
        output: {
          manualChunks: {
            grid: ['ag-grid-community', 'ag-grid-react'],
          },
        },
      },
    },
  };
});

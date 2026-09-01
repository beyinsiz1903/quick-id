import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  return {
    plugins: [react()],
    resolve: {
      alias: { '@': path.resolve(process.cwd(), 'src') },
    },
    server: {
      proxy: {
        '/api': { target: env.VITE_BACKEND_URL || 'http://localhost:8000', changeOrigin: true },
      },
    },
    build: { outDir: 'build' },
  };
});

/* eslint-env node */
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '');
  const backendTarget = env.VITE_BACKEND_TARGET || 'http://localhost:5000';
  const fastapiTarget = env.VITE_FASTAPI_TARGET || 'http://localhost:8000';

  return {
    plugins: [react()],
    server: {
      proxy: {
        '/api-fastapi': {
          target: fastapiTarget,
          changeOrigin: true,
          secure: false,
          rewrite: (path) => path.replace(/^\/api-fastapi/, ''),
        },
        '^/api(?:/|$)': {
          target: backendTarget,
          changeOrigin: true,
          secure: false,
        },
      },
      strictPort: true,
    },
  };
});

import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import path from 'path';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
  },
  build: {
    rollupOptions: {
      output: {
        // Split stable vendor libraries into their own long-cached chunk
        // so app code changes don't bust the whole bundle.
        manualChunks: (id) => {
          if (id.includes('node_modules')) {
            if (/[\\/](react|react-dom|react-router|react-router-dom)[\\/]/.test(id)) {
              return 'react';
            }
            if (id.includes('@tanstack')) return 'query';
            return 'vendor';
          }
        },
      },
    },
  },
});

import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import { resolve } from 'node:path';

export default defineConfig(({ command }) => ({
  plugins: [vue()],
  base: command === 'serve' ? '/' : '/assets/',
  build: {
    outDir: resolve(import.meta.dirname, '../painel-frontend'),
    emptyOutDir: true,
    assetsDir: 'bundles',
    rollupOptions: {
      input: Object.fromEntries(
        ['index', 'dados', 'analise', 'login', 'equipe'].map((name) => [
          name,
          resolve(import.meta.dirname, `${name}.html`),
        ]),
      ),
    },
  },
  server: {
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
}));

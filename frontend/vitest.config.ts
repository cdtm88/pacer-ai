import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/tests/setup.ts'],
    globals: true,
    include: ['src/tests/**/*.{test,spec}.{ts,tsx}'],
    // Node's experimental native Web Storage implementation shadows jsdom's
    // simulated localStorage across worker threads under some conditions,
    // causing intermittent cross-file test pollution that only reproduces
    // with the full suite. jsdom's own localStorage is complete and correct
    // for our needs — disable Node's native one so jsdom is the sole source.
    poolOptions: {
      threads: { execArgv: ['--no-experimental-webstorage'] },
      forks: { execArgv: ['--no-experimental-webstorage'] },
    },
  },
})

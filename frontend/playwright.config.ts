import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  retries: 1,
  timeout: 20_000,
  use: {
    baseURL: 'http://localhost:5174',
    headless: true,
    viewport: { width: 390, height: 844 }, // iPhone 14 – tests both mobile nav and content
  },
  webServer: {
    command: 'npx vite --mode test --port 5174',
    url: 'http://localhost:5174',
    reuseExistingServer: true,
    timeout: 60_000,
  },
})

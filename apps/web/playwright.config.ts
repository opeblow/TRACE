import { defineConfig, devices } from '@playwright/test'

// Browser tests run against the static export with the API mocked at the network layer,
// so they are fast and deterministic. Build first with NEXT_PUBLIC_API_URL=http://api.test.
export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? 'list' : 'line',
  use: { baseURL: 'http://localhost:4310', reducedMotion: 'reduce' },
  webServer: { command: 'node e2e/serve.mjs out 4310', url: 'http://localhost:4310', reuseExistingServer: !process.env.CI },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'] } },
    { name: 'mobile', use: { ...devices['Pixel 7'] } },
  ],
})

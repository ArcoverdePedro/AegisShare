const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  retries: 1,
  workers: 1,
  timeout: 30_000,
  expect: {
    timeout: 8_000,
  },
  use: {
    baseURL: process.env.PWA_BASE_URL || 'http://127.0.0.1:8000',
    browserName: 'chromium',
    trace: 'retain-on-failure',
  },
});

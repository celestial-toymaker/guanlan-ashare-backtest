import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  timeout: 90000,
  workers: 1,
  use: { baseURL: 'http://127.0.0.1:8765', headless: true,
    launchOptions: { executablePath: process.env.ASHARE_CHROMIUM },
    screenshot: 'only-on-failure', trace: 'retain-on-failure' },
  reporter: [['list'], ['json', { outputFile: '../work/browser-tests.json' }]],
});

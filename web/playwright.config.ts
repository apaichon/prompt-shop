import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './tests/browser', fullyParallel: true, retries: 0, workers: 2,
  reporter: [['list']],
  use: { baseURL: 'http://127.0.0.1:4174', browserName: 'chromium', launchOptions: { args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] }, viewport: { width: 1280, height: 900 }, trace: 'retain-on-failure' },
  webServer: { command: 'npm run preview -- --port 4174', url: 'http://127.0.0.1:4174', reuseExistingServer: !process.env.CI }
});

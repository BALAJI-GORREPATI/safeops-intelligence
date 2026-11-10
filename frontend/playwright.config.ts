import { defineConfig } from '@playwright/test';
export default defineConfig({ testDir: './tests', timeout: 90000, fullyParallel: false, workers: 1,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: { baseURL: 'http://127.0.0.1:3000', trace: 'retain-on-failure', screenshot: 'only-on-failure' },
});

import { test, expect, Page } from '@playwright/test';

async function login(page: Page, role = 'admin') {
  await page.goto('/');
  await page.getByLabel('Working role').selectOption(role);
  await page.getByLabel('Demo password').fill(process.env.DEMO_PASSWORD || 'SafeOps-local-demo');
  await page.getByRole('button', { name: 'Open workspace' }).click();
  await expect(page.getByRole('heading', { name: 'Safety overview' })).toBeVisible();
  await expect(page.getByLabel('Dataset').locator('option')).not.toHaveCount(1);
  const options = await page.getByLabel('Dataset').locator('option').evaluateAll(options => options.map(o => ({ value: (o as HTMLOptionElement).value, text: o.textContent || '' })));
  const starter = options.find(o => o.text.includes('Starter'))!;
  await page.getByLabel('Dataset').selectOption(starter.value);
  return starter.value;
}

test('dashboard, filters, traceability, acknowledgement and refresh persistence', async ({ page }) => {
  const errors: string[] = []; page.on('pageerror', error => errors.push(error.message));
  const workspace = await login(page);
  await expect(page.getByText('Physical alarms', { exact: true })).toBeVisible();
  await expect(page.locator('.recharts-area-area')).toBeVisible();
  await page.screenshot({ path: 'test-results/dashboard-desktop.png', fullPage: true });
  await page.getByRole('link', { name: 'Alarms', exact: true }).click();
  await page.getByLabel('Severity filter').selectOption('CRITICAL');
  await expect.poll(async () => page.locator('tbody tr').count()).toBeGreaterThan(0);
  await expect(page.locator('tbody tr').first().getByText('Critical', { exact: true })).toBeVisible();
  await page.getByLabel('Severity filter').selectOption('');
  await page.getByLabel('Status filter').selectOption('UNACKNOWLEDGED');
  await expect.poll(async () => page.locator('tbody tr').count()).toBeGreaterThan(0);
  const alarms = await (await page.request.get(`/api/alarms?workspace=${workspace}&status=UNACKNOWLEDGED&limit=1`)).json();
  const id = alarms.items[0].id;
  await page.goto('/alarms?detail='+id);
  const dialog = page.getByRole('dialog');
  await expect(dialog.getByRole('heading', { name: 'Operator response' })).toBeVisible();
  await dialog.getByLabel('Operator note').fill('Browser test: inspected guard and confirmed safe stop.');
  page.once('dialog', d => d.accept());
  await dialog.getByRole('button', { name: 'Acknowledge alarm' }).click();
  await expect(page.getByRole('status')).toContainText('Saved');
  await page.reload();
  await expect(page).toHaveURL('http://127.0.0.1:3000/');
  await expect(page.getByRole('heading', { name: 'Safety overview' })).toBeVisible();
  await expect(page.getByLabel('Dataset', { exact: true })).toHaveValue('manual');
  await page.goto('/alarms?detail='+id);
  await expect(page.getByRole('dialog').getByText('Browser test: inspected guard and confirmed safe stop.')).toBeVisible();
  const detail = await (await page.request.get('/api/alarms/'+id)).json();
  expect(detail.acknowledgement.note).toContain('Browser test');
  await page.getByRole('button', { name: 'Close dialog' }).click();
  await page.getByLabel('Dataset', { exact: true }).selectOption(workspace);
  await page.getByRole('link', { name: 'Incidents', exact: true }).click();
  await expect.poll(async () => page.locator('tbody tr').count()).toBeGreaterThan(0);
  const incidents = await (await page.request.get(`/api/incidents?workspace=${workspace}&limit=100`)).json();
  const incident = incidents.items.find((i: Record<string, unknown>) => !i.missing_context);
  await page.goto('/incidents?detail='+incident.id);
  await expect(page.getByRole('heading', { name: 'Machine & triggering evidence' })).toBeVisible();
  await page.getByRole('button', { name: 'Chronological timeline' }).click();
  await expect(page.getByRole('dialog').getByText('Alarm occurred', { exact: true })).toBeVisible();
  await page.screenshot({ path: 'test-results/incident-trace.png', fullPage: true });
  expect(errors).toEqual([]);
});

test('create action, complete, independently verify and close through UI', async ({ page }) => {
  const workspace = await login(page);
  const incidents = await (await page.request.get(`/api/incidents?workspace=${workspace}&status=OPEN&limit=100`)).json();
  const incident = incidents.items.find((i: Record<string, unknown>) => !i.missing_context);
  await page.getByRole('link', { name: 'Corrective actions', exact: true }).click();
  await page.getByRole('button', { name: 'New action' }).click();
  await page.getByLabel('Related open incident').fill(incident.id);
  await page.getByLabel('Description', { exact: true }).fill('E2E: inspect guard sensor, replace damaged cable and test safe restart.');
  await page.getByLabel('Responsible engineer').selectOption('USR-DEMO-engineer');
  const due = new Date(Date.now()+3*86400000); due.setMinutes(due.getMinutes()-due.getTimezoneOffset());
  await page.getByLabel('Due date & time (local)').fill(due.toISOString().slice(0,16));
  await page.getByRole('button', { name: 'Save record' }).click();
  await expect(page.getByRole('status')).toContainText('saved');
  const actions = await (await page.request.get(`/api/actions?workspace=${workspace}&q=E2E&limit=100`)).json();
  const id = actions.items[actions.items.length-1].id;
  const forbidden = await page.request.post(`/api/actions/${id}/transition`, { data: { status: 'CLOSED', note: 'Try to close before verification' } });
  expect(forbidden.status()).toBe(409);
  await page.goto('/actions?detail='+id);
  for (const status of ['In progress', 'Completed', 'Verified', 'Closed']) {
    await page.getByLabel('Work note').fill('E2E: procedure performed, observations recorded and evidence reviewed.');
    if (status === 'Verified') await page.getByLabel('Verification evidence').fill('Independent guard cycle and supervised safe restart passed.');
    page.once('dialog', d => d.accept());
    await page.getByRole('button', { name: 'Mark '+status, exact: true }).click();
    await expect.poll(async () => (await (await page.request.get('/api/actions/'+id)).json()).action.status).toBe(status.toUpperCase().replaceAll(' ', '_'));
  }
  await page.reload();
  await expect(page).toHaveURL('http://127.0.0.1:3000/');
  await expect(page.getByRole('heading', { name: 'Safety overview' })).toBeVisible();
  await page.goto('/actions?detail='+id);
  await expect(page.getByRole('dialog').getByText('Independent guard cycle and supervised safe restart passed.', { exact: true })).toBeVisible();
});

test('data validation, reproduction and role restrictions', async ({ page }) => {
  await login(page);
  await page.getByRole('link', { name: 'Data & validation', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Detection Evaluation', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Run validation', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('completed');
  await page.getByRole('button', { name: 'Test reproducibility', exact: true }).click();
  await expect(page.getByText('Reproducible: both runs match')).toBeVisible();
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('link', { name: 'Export bundle' }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/^safeops-sim-.*\.zip$/);
  expect(await download.failure()).toBeNull();
  await page.getByRole('button', { name: 'Sign out' }).click();
  await expect(page).toHaveURL('http://127.0.0.1:3000/');
  await page.getByLabel('Working role').selectOption('planner');
  await page.getByLabel('Demo password').fill(process.env.DEMO_PASSWORD || 'SafeOps-local-demo');
  await page.getByRole('button', { name: 'Open workspace' }).click();
  await expect(page.getByRole('heading', { name: 'Safety overview' })).toBeVisible();
  const forbidden = await page.request.post('/api/config/plants', { data: { name: 'Unauthorized plant', location: 'Pune' } });
  expect(forbidden.status()).toBe(403);
});

test('administrator generates a dataset through the background job UI', async ({ page }) => {
  await login(page);
  await page.getByRole('link', { name: 'Data & validation', exact: true }).click();
  await page.getByLabel('Random seed').fill('20261110');
  await page.getByRole('button', { name: 'Generate dataset', exact: true }).click();
  await expect.poll(async () => {
    const runs = await (await page.request.get('/api/datasets')).json();
    return runs.find((r: Record<string, any>) => r.config.seed === 20261110)?.status;
  }, { timeout: 60000 }).toBe('COMPLETED');
  await expect(page.getByRole('combobox', { name: 'Dataset', exact: true }).locator('option').filter({ hasText: '20261110' })).toHaveCount(1);
  await page.getByRole('combobox', { name: 'Dataset', exact: true }).selectOption({ label: 'Starter · 800 alarms · seed 20261110' });
  await expect(page.getByRole('heading', { name: 'Detection Evaluation', exact: true })).toBeVisible();
});

test('mobile and desktop layouts stay within viewport', async ({ page }) => {
  await login(page);
  for (const width of [1440, 768, 390]) {
    await page.setViewportSize({ width, height: 900 });
    for (const route of ['/', '/machines', '/alarms', '/incidents', '/actions', '/data']) {
      await page.goto(route);
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
      if (route === '/') await expect(page.getByText('Physical alarms', { exact: true })).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    }
    if (width === 390) {
      await page.goto('/');
      await expect(page.getByText('Physical alarms', { exact: true })).toBeVisible();
      await expect(page.locator('.recharts-area-area')).toBeVisible();
      await page.screenshot({ path: 'test-results/dashboard-mobile.png', fullPage: true });
      await page.getByRole('button', { name: 'Toggle navigation' }).click();
      await expect(page.getByRole('link', { name: 'Machines', exact: true })).toBeVisible();
    }
  }
});

for (const role of ['operator', 'engineer', 'planner']) {
  test(`${role} cannot see or access dataset administration, including after refresh`, async ({ page }) => {
    const workspace = await login(page, role);
    await expect(page.getByRole('link', { name: 'Data & validation', exact: true })).toHaveCount(0);
    await expect(page.getByText('Local PostgreSQL', { exact: true })).toHaveCount(0);
    await expect(page.getByText('DEMO ENVIRONMENT', { exact: true })).toHaveCount(0);
    await page.reload();
    await expect(page.getByRole('heading', { name: 'Safety overview' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Data & validation', exact: true })).toHaveCount(0);
    const direct = await page.request.get('/data', { maxRedirects: 0 });
    expect(direct.status()).toBe(307);
    expect(direct.headers().location).toBe('/');
    await page.goto('/data');
    await expect(page).toHaveURL('http://127.0.0.1:3000/');
    await expect(page.getByRole('heading', { name: 'Data & validation' })).toHaveCount(0);
    for (const resource of ['report', 'export?format=csv', 'export?format=json', 'export?format=sql', 'export?format=validation', 'export?format=ground-truth']) {
      expect((await page.request.get(`/api/datasets/${workspace}/${resource}`)).status()).toBe(403);
    }
    expect((await page.request.get('/api/datasets')).status()).toBe(403);
    for (const operation of ['validate', 'reproduce']) {
      expect((await page.request.post(`/api/datasets/${workspace}/${operation}`, { data: {} })).status()).toBe(403);
    }
    expect((await page.request.post('/api/datasets', { data: { preset: 'starter' } })).status()).toBe(403);
    await expect(page.getByRole('button', { name: /next.js dev tools/i })).not.toBeVisible();
  });
}

test('administrator sees readable findings, compact inventory and every export control', async ({ page }) => {
  await login(page);
  await page.getByRole('link', { name: 'Data & validation', exact: true }).click();
  for (const name of ['Dataset Generation', 'Dataset Integrity', 'Detection Evaluation', 'Exports & Reproducibility']) {
    await expect(page.getByRole('heading', { name, exact: true })).toBeVisible();
  }
  await expect(page.getByText('Local PostgreSQL', { exact: true })).toHaveCount(0);
  await expect(page.getByText('DEMO ENVIRONMENT', { exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: /next.js dev tools/i })).not.toBeVisible();
  const detailCounts = page.locator('details').filter({ has: page.getByText('Detailed Record Counts', { exact: true }) });
  await expect(detailCounts).not.toHaveAttribute('open');
  await page.getByLabel('Rule filter').selectOption('ACK_BEFORE_ALARM');
  await expect(page.locator('.readable-finding')).toHaveCount(1);
  const finding = page.locator('.readable-finding').first();
  await finding.locator('summary').click();
  await expect(finding.getByText('Alarm occurred', { exact: true })).toBeVisible();
  await expect(finding.getByText('Acknowledged', { exact: true })).toBeVisible();
  await expect(finding.getByText('Expected condition', { exact: true })).toBeVisible();
  await expect(finding.getByText('Expected anomaly · detected', { exact: true })).toBeVisible();
  await expect(finding.locator('pre, code')).toHaveCount(0);
  expect(await finding.innerText()).not.toContain('"alarm_at"');
  await expect(finding.getByRole('link')).not.toHaveCount(0);
  await page.screenshot({ path: 'test-results/admin-data-cleanup.png', fullPage: true });
  for (const name of ['Export CSV', 'Export JSON', 'Export SQL', 'Download validation report', 'Download ground-truth report']) {
    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('link', { name, exact: true }).click();
    const download = await downloadPromise;
    expect(await download.failure()).toBeNull();
  }
  await page.getByRole('button', { name: 'Sign out' }).click();
  await expect(page).toHaveURL('http://127.0.0.1:3000/');
  await expect(page.getByRole('heading', { name: 'Enter your workspace' })).toBeVisible();
  await page.getByLabel('Working role').selectOption('engineer');
  await page.getByLabel('Demo password').fill(process.env.DEMO_PASSWORD || 'SafeOps-local-demo');
  await page.getByRole('button', { name: 'Open workspace' }).click();
  await expect(page.getByRole('heading', { name: 'Safety overview' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Data & validation', exact: true })).toHaveCount(0);
  await page.goto('/data');
  await expect(page).toHaveURL('http://127.0.0.1:3000/');
});

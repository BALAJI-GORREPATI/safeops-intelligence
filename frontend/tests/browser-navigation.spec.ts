import { expect, Page, test } from '@playwright/test';

async function login(page: Page, role = 'admin') {
  await page.goto('/');
  await page.getByLabel('Working role').selectOption(role);
  await page.getByLabel('Demo password').fill(process.env.DEMO_PASSWORD || 'SafeOps-local-demo');
  await page.getByRole('button', { name: 'Open workspace' }).click();
  await expect(page.getByRole('heading', { name: 'Safety overview' })).toBeVisible();
  const datasets = page.getByRole('combobox', { name: 'Dataset', exact: true });
  await expect.poll(() => datasets.locator('option').count()).toBeGreaterThan(1);
  const entries = await datasets.locator('option').evaluateAll(items => items.map(item => ({ id: (item as HTMLOptionElement).value, name: item.textContent || '' })));
  const starter = entries.find(item => item.name.includes('Starter'))!;
  await datasets.selectOption(starter.id);
  return starter.id;
}

async function expectOverviewDefaults(page: Page, role: string) {
  await expect(page).toHaveURL('http://127.0.0.1:3000/');
  await expect(page.getByRole('heading', { name: 'Safety overview', exact: true })).toBeVisible();
  await expect(page.getByLabel('Dataset', { exact: true })).toHaveValue('manual');
  await expect(page.getByLabel('Plant', { exact: true })).toHaveValue('');
  await expect(page.getByLabel('Period', { exact: true })).toHaveValue('all');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'Enter your workspace' })).toHaveCount(0);
  await expect(page.getByRole('link', { name: 'Data & validation', exact: true })).toHaveCount(role === 'admin' ? 1 : 0);
  expect((await (await page.request.get('/api/auth/me')).json()).role).toBe(role);
}

test('all six pages and four detail panels have no manual refresh controls', async ({ page }) => {
  const workspace = await login(page);
  for (const route of ['/', '/machines', '/alarms', '/incidents', '/actions', '/data']) {
    await page.goto(route);
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    await expect(page.getByRole('button', { name: /refresh/i })).toHaveCount(0);
    await expect(page.getByText('Records refreshed. Latest available information is displayed.', { exact: true })).toHaveCount(0);
    await expect(page.locator('.refresh-feedback, .refresh-spinning, .detail-refresh-feedback')).toHaveCount(0);
    expect(await page.locator('.heading-actions').count() === 0 || await page.locator('.heading-actions button').count() > 0).toBe(true);
  }
  for (const resource of ['machines', 'alarms', 'incidents', 'actions']) {
    const records = await (await page.request.get(`/api/${resource}?workspace=${workspace}&limit=1`)).json();
    await page.goto(`/${resource}?detail=${records.items[0].id}`);
    await expect(page.getByRole('dialog').locator('.record-id')).toHaveText(records.items[0].id);
    await expect(page.getByRole('dialog').getByRole('button', { name: /refresh/i })).toHaveCount(0);
  }
});

for (const route of ['/', '/machines', '/alarms', '/incidents', '/actions', '/data']) {
  test(`browser reload from ${route} resets the workspace and preserves authentication`, async ({ page, context }) => {
    await login(page);
    const options = await (await page.request.get('/api/workspaces')).json();
    const full = options.find((r: any) => r.config.preset === 'full');
    await page.getByLabel('Dataset', { exact: true }).selectOption(full.id);
    if (route !== '/') await page.goto(route);
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    const selector = page.getByLabel('Dataset', { exact: true });
    await expect(selector).toHaveValue(full.id);
    if (route !== '/data') {
      const plants = page.getByLabel('Plant', { exact: true });
      await expect.poll(() => plants.locator('option').count()).toBeGreaterThan(1);
      const plant = await plants.locator('option').nth(1).getAttribute('value');
      await plants.selectOption(plant!);
      if (route === '/' || route === '/alarms') {
        await page.getByLabel('Period', { exact: true }).selectOption('custom');
        await page.getByLabel('Start date').fill('2026-10-04');
        await page.getByLabel('End date').fill('2026-10-20');
      }
      if (route !== '/') {
        await page.getByLabel('Search records').fill('test temporary search');
        if (route !== '/machines') await page.getByLabel('Severity filter').selectOption('CRITICAL');
      }
    } else {
      await page.getByLabel('Random seed').fill('123456');
      await page.getByLabel('Rule filter').selectOption('ACK_BEFORE_ALARM');
    }
    await page.evaluate(() => {
      localStorage.setItem('safeops-unrelated-preference', 'keep-this');
      sessionStorage.setItem('safeops-unrelated-tab-state', 'also-keep-this');
    });
    const session = (await context.cookies()).find(c => c.name === 'safeops_session');
    const writes: string[] = [];
    page.on('request', request => {
      if (request.url().includes('/api/') && ['POST', 'PUT', 'PATCH', 'DELETE'].includes(request.method())) writes.push(request.method()+' '+request.url());
    });
    const latest = page.waitForResponse(r => new URL(r.url()).pathname === '/api/dashboard' && new URL(r.url()).searchParams.get('workspace') === 'manual');
    await page.reload();
    await expectOverviewDefaults(page, 'admin');
    expect((await latest).status()).toBe(200);
    expect((await context.cookies()).find(c => c.name === 'safeops_session')?.value).toBe(session?.value);
    expect(await page.evaluate(() => localStorage.getItem('safeops-workspace'))).toBe('manual');
    expect(await page.evaluate(() => localStorage.getItem('safeops-unrelated-preference'))).toBe('keep-this');
    expect(await page.evaluate(() => sessionStorage.getItem('safeops-unrelated-tab-state'))).toBe('also-keep-this');
    expect(await page.evaluate(() => (performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming).type)).toBe('reload');
    expect(writes).toEqual([]);
    // The navigation entry remains "reload" for this document. It must not
    // repeatedly reset the user when they then navigate using the sidebar.
    await page.getByRole('link', { name: 'Machines', exact: true }).click();
    await expect(page).toHaveURL('http://127.0.0.1:3000/machines');
    await expect(page.getByRole('heading', { name: 'Machines', exact: true })).toBeVisible();
    await expect(page.getByLabel('Search records')).toHaveValue('');
    if (route === '/alarms') {
      await page.getByRole('link', { name: 'Alarms', exact: true }).click();
      await expect(page.getByLabel('Severity filter')).toHaveValue('');
      await expect(page.getByLabel('Status filter')).toHaveValue('');
      await expect(page.getByLabel('Machine filter')).toHaveValue('');
      await expect(page.getByRole('button', { name: 'Previous', exact: true })).toBeDisabled();
    }
  });
}

test('a reload clears root URL queries and leaves normal direct detail links usable', async ({ page }) => {
  const workspace = await login(page);
  const incidents = await (await page.request.get(`/api/incidents?workspace=${workspace}&limit=1`)).json();
  const direct = `/incidents?detail=${incidents.items[0].id}`;
  await page.goto(direct);
  await expect(page.getByRole('dialog').locator('.record-id')).toHaveText(incidents.items[0].id);
  expect(await page.evaluate(() => (performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming).type)).toBe('navigate');
  await page.reload();
  await expectOverviewDefaults(page, 'admin');
  await page.goto(direct);
  await expect(page.getByRole('dialog').locator('.record-id')).toHaveText(incidents.items[0].id);
  await page.goto('/?severity=CRITICAL&status=OPEN#temporary-panel');
  expect(new URL(page.url()).searchParams.get('severity')).toBe('CRITICAL');
  await page.reload();
  await expectOverviewDefaults(page, 'admin');
});

test('sidebar and ordinary direct navigation do not trigger a reload reset', async ({ page }) => {
  const workspace = await login(page);
  for (const [title, route] of [['Machines', '/machines'], ['Alarms', '/alarms'], ['Incidents', '/incidents'], ['Corrective actions', '/actions'], ['Data & validation', '/data'], ['Overview', '/']]) {
    await page.getByRole('link', { name: title, exact: true }).click();
    await expect(page).toHaveURL('http://127.0.0.1:3000'+route);
    await expect(page.getByLabel('Dataset', { exact: true })).toHaveValue(workspace);
  }
  for (const type of ['machines', 'alarms', 'incidents', 'actions']) {
    const response = await (await page.request.get(`/api/${type}?workspace=${workspace}&limit=1`)).json();
    const id = response.items[0].id;
    await page.goto(`/${type}?detail=${id}`);
    await expect(page.getByRole('dialog').locator('.record-id')).toHaveText(id);
    await expect(page).toHaveURL(`http://127.0.0.1:3000/${type}?detail=${id}`);
  }
});

test('pagination resets after browser reload while saved records remain intact', async ({ page }) => {
  const workspace = await login(page);
  await page.goto('/alarms');
  await expect(page.getByRole('button', { name: 'Next', exact: true })).toBeEnabled();
  await page.getByRole('button', { name: 'Next', exact: true }).click();
  await expect(page.locator('.pagination')).toContainText('26');
  const alarms = await (await page.request.get(`/api/alarms?workspace=${workspace}&limit=1`)).json();
  const alarmBefore = await (await page.request.get('/api/alarms/'+alarms.items[0].id)).json();
  await page.reload();
  await expectOverviewDefaults(page, 'admin');
  const alarmAfter = await (await page.request.get('/api/alarms/'+alarms.items[0].id)).json();
  expect(alarmAfter).toEqual(alarmBefore);
  await page.getByRole('link', { name: 'Alarms', exact: true }).click();
  await page.getByLabel('Dataset', { exact: true }).selectOption(workspace);
  await expect(page.getByRole('button', { name: 'Previous', exact: true })).toBeDisabled();
  await expect(page.locator('.pagination')).toContainText('1–25');
});

for (const role of ['operator', 'engineer', 'planner']) {
  test(`${role} retains their session and restricted access after browser reload`, async ({ page, context }) => {
    const workspace = await login(page, role);
    await page.getByRole('link', { name: 'Alarms', exact: true }).click();
    await page.getByLabel('Severity filter').selectOption('CRITICAL');
    const session = (await context.cookies()).find(c => c.name === 'safeops_session');
    await page.reload();
    await expectOverviewDefaults(page, role);
    expect((await context.cookies()).find(c => c.name === 'safeops_session')?.value).toBe(session?.value);
    expect((await page.request.get(`/api/datasets/${workspace}/report`)).status()).toBe(403);
    expect((await page.request.get(`/api/datasets/${workspace}/export?format=ground-truth`)).status()).toBe(403);
    await page.goto('/data');
    await expect(page).toHaveURL('http://127.0.0.1:3000/');
  });
}

test('automatic post-save updates still retrieve persisted machine-state changes', async ({ page }) => {
  const workspace = await login(page);
  const machines = await (await page.request.get(`/api/machines?workspace=${workspace}&limit=1`)).json();
  const id = machines.items[0].id;
  await page.goto('/machines?detail='+id);
  const dialog = page.getByRole('dialog');
  await expect(dialog.locator('.record-id')).toHaveText(id);
  await dialog.getByText('Record a machine-state change', { exact: true }).click();
  await dialog.getByRole('combobox', { name: 'Machine state', exact: true }).selectOption('STOPPED');
  await dialog.getByRole('combobox', { name: 'Interlock', exact: true }).selectOption('ENGAGED');
  await dialog.getByRole('combobox', { name: 'Guard', exact: true }).selectOption('CLOSED');
  const note = 'Browser reload regression: supervised stop '+Date.now();
  await dialog.getByLabel('Reason', { exact: true }).fill(note);
  page.once('dialog', d => d.accept());
  await dialog.getByRole('button', { name: 'Save state event' }).click();
  await expect(dialog.locator('.timeline').getByText(note, { exact: true })).toBeVisible();
  await page.goto('/incidents');
  await page.reload();
  await expectOverviewDefaults(page, 'admin');
  await page.goto('/machines?detail='+id);
  await expect(page.getByRole('dialog').locator('.timeline').getByText(note, { exact: true })).toBeVisible();
});

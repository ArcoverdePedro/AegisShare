const { test, expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;
test.use({ timezoneId: 'America/Fortaleza' });
const LIST = '/laboratorio/pedidos/';
const CREATE = '/laboratorio/encontros/05000000-0000-4000-8000-000000000002/pedidos/novo/';
const EXAM = '05000000-0000-4000-8000-000000000003';

async function localRows(page) {
  return page.evaluate(async () => {
    const counts = {};
    for (const info of await indexedDB.databases()) {
      const db = await new Promise((resolve, reject) => {
        const request = indexedDB.open(info.name);
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
      });
      for (const store of db.objectStoreNames) {
        counts[`${info.name}/${store}`] = await new Promise((resolve, reject) => {
          const request = db.transaction(store).objectStore(store).count();
          request.onsuccess = () => resolve(request.result);
          request.onerror = () => reject(request.error);
        });
      }
      db.close();
    }
    return counts;
  });
}

async function login(page, role = 'operator') {
  await page.goto('/login/');
  await page.getByLabel('Usuário').fill(`ci-lis-${role}`);
  await page.getByLabel('Senha').fill(`ci-lis-${role}-password`);
  await page.getByRole('button', { name: 'Entrar', exact: true }).click();
  await expect(page).toHaveURL(/\/$/);
}
async function order(page) {
  await page.goto(CREATE);
  await page.getByLabel('Exame', { exact: true }).selectOption(EXAM);
  await page.getByRole('button', { name: 'Registrar pedido' }).click();
  await expect(page.getByRole('heading', { name: 'Pedido laboratorial' })).toBeVisible();
  return page.url();
}
async function fillCollection(page, code) {
  await page.getByLabel('Código da amostra').fill(code);
  const timestamp = await page.evaluate(() => {
    const d = new Date();
    d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
    return d.toISOString().slice(0, 19).replace(/:00$/, '');
  });
  await page.getByLabel('Data e hora da coleta').fill(timestamp);
  await page.getByLabel('Confirme que conferiu').check();
}

test('CA-LIS-01/02/05: pedido, coleta e conflito sem sobrescrever', async ({ page }) => {
  await login(page);
  const detail = await order(page);
  await page.getByRole('link', { name: 'Registrar coleta' }).click();
  // Campos usam horário local; aguardar próximo segundo evita coleta anterior ao pedido.
  const nextSecond = Math.floor(Date.now() / 1000) + 1;
  await expect.poll(() => Math.floor(Date.now() / 1000), { intervals: [100] }).toBeGreaterThanOrEqual(nextSecond);
  await fillCollection(page, `LIS-${Date.now()}`);
  const oldForm = await page.locator('form.box').evaluate(form => Object.fromEntries(new FormData(form)));
  await page.getByRole('button', { name: 'Registrar coleta', exact: true }).click();
  await expect(page).toHaveURL(detail);
  await expect(page.getByRole('heading', { name: 'Coleta registrada' })).toBeVisible();
  const conflict = await page.request.post(`${detail}coleta/`, { form: { ...oldForm, accession_code: 'CHANGED' } });
  expect(conflict.status()).toBe(409);
  await page.reload();
  await expect(page.getByText('Código da amostra: CHANGED', { exact: true })).toHaveCount(0);
});

test('CA-LIS-03: pedido fora do escopo não é revelado', async ({ page }) => {
  await login(page);
  const detail = await order(page);
  await login(page, 'outsider');
  expect((await page.goto(detail)).status()).toBe(404);
  expect((await page.goto(CREATE)).status()).toBe(404);
  await page.goto(LIST);
  await expect(page.getByText('Pessoa Sintética LIS')).toHaveCount(0);
});

test('CA-LIS-07: offline não confirma nem guarda pedido', async ({ page, context }) => {
  await login(page);
  await page.evaluate(() => navigator.serviceWorker.ready);
  await page.goto(CREATE);
  await expect.poll(() => page.evaluate(() => Boolean(navigator.serviceWorker.controller))).toBe(true);
  await page.getByLabel('Exame', { exact: true }).selectOption(EXAM);
  const databases = await page.evaluate(async () => (await indexedDB.databases()).map(db => db.name));
  const rows = await localRows(page);
  await context.setOffline(true);
  await Promise.all([
    page.waitForEvent('framenavigated', frame => frame === page.mainFrame()),
    page.getByRole('button', { name: 'Registrar pedido' }).click(),
  ]);
  await page.goto(LIST);
  await expect(page.getByRole('heading', { name: 'Você está sem conexão' })).toBeVisible();
  await context.setOffline(false);
  await page.goto(LIST);
  expect(await localRows(page)).toEqual(rows);
  const storage = await page.evaluate(async () => {
    const urls = [];
    let sensitive = false;
    for (const name of await caches.keys()) {
      for (const request of await (await caches.open(name)).keys()) {
        urls.push(request.url);
        const response = await (await caches.open(name)).match(request);
        if (/text|json|javascript/.test(response.headers.get('content-type') || '')) {
          const body = await response.text();
          sensitive ||= body.includes('Pessoa Sintética LIS') || body.includes('Exame Sintético LIS');
        }
      }
    }
    return { urls, sensitive, databases: (await indexedDB.databases()).map(db => db.name) };
  });
  expect(storage.sensitive).toBe(false);
  expect(storage.urls.some(url => url.includes('/laboratorio/'))).toBe(false);
  expect(storage.databases).toEqual(databases);
});

test('CA-LIS-04/07: telas em telefone e tablet sem barreiras graves', async ({ page }) => {
  test.setTimeout(90000);
  await login(page);
  const detail = await order(page);
  for (const viewport of [{ width: 390, height: 844 }, { width: 768, height: 1024 }]) {
    await page.setViewportSize(viewport);
    for (const url of [LIST, CREATE, detail, `${detail}coleta/`]) {
      await page.goto(url);
      const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
      expect(result.violations.filter(v => ['serious', 'critical'].includes(v.impact))).toEqual([]);
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(viewport.width + 1);
    }
  }
});

const { test, expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;
test.use({ timezoneId: 'America/Fortaleza' });
const LIST = '/cirurgias/solicitacoes/';
const CREATE = '/cirurgias/encontros/07000000-0000-4000-8000-000000000002/solicitacoes/nova/';
const PROCEDURE = '07000000-0000-4000-8000-000000000003';

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
  await page.getByLabel('Usuário').fill(`ci-surgery-${role}`);
  await page.getByLabel('Senha').fill(`ci-surgery-${role}-password`);
  await page.getByRole('button', { name: 'Entrar', exact: true }).click();
  await expect(page).toHaveURL(/\/$/);
}
async function order(page) {
  await page.goto(CREATE);
  await page.getByLabel('Procedimento', { exact: true }).selectOption(PROCEDURE);
  await page.getByRole('button', { name: 'Registrar solicitação' }).click();
  await expect(page.getByRole('heading', { name: 'Solicitação de procedimento' })).toBeVisible();
  return page.url();
}
test('CA-SURG-01/05: solicitação e retry preservam protocolo', async ({page}) => {
  await login(page);
  await page.goto(CREATE);
  await page.getByLabel('Procedimento', {exact:true}).selectOption(PROCEDURE);
  const data = await page.locator('form.box').evaluate(form=>Object.fromEntries(new FormData(form)));
  await page.getByRole('button', {name:'Registrar solicitação'}).click();
  await expect(page.getByRole('heading',{name:'Solicitação de procedimento',exact:true})).toBeVisible();
  const detail = page.url();
  const retry = await page.request.post(CREATE, {form:data});
  expect(retry.status()).toBe(200);
  expect(retry.url()).toBe(detail);
  await expect(page.getByText('Solicitação registrada — sem agendamento ou autorização cirúrgica')).toBeVisible();
});

test('CA-SURG-03: solicitação fora do escopo não é revelado', async ({ page }) => {
  await login(page);
  const detail = await order(page);
  await login(page, 'outsider');
  expect((await page.goto(detail)).status()).toBe(404);
  expect((await page.goto(CREATE)).status()).toBe(404);
  await page.goto(LIST);
  await expect(page.getByText('Pessoa Sintética SURG')).toHaveCount(0);
});

test('CA-SURG-07: offline não confirma nem guarda solicitação', async ({ page, context }) => {
  await login(page);
  await page.evaluate(() => navigator.serviceWorker.ready);
  await page.goto(CREATE);
  await expect.poll(() => page.evaluate(() => Boolean(navigator.serviceWorker.controller))).toBe(true);
  await page.getByLabel('Procedimento', { exact: true }).selectOption(PROCEDURE);
  const databases = await page.evaluate(async () => (await indexedDB.databases()).map(db => db.name));
  const rows = await localRows(page);
  await context.setOffline(true);
  await Promise.all([
    page.waitForEvent('framenavigated', frame => frame === page.mainFrame()),
    page.getByRole('button', { name: 'Registrar solicitação' }).click(),
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
          sensitive ||= body.includes('Pessoa Sintética SURG') || body.includes('Procedimento Sintético SURG');
        }
      }
    }
    sensitive ||= JSON.stringify(localStorage).includes('Pessoa Sintética SURG') || JSON.stringify(sessionStorage).includes('Pessoa Sintética SURG');
    return { urls, sensitive, databases: (await indexedDB.databases()).map(db => db.name) };
  });
  expect(storage.sensitive).toBe(false);
  expect(storage.urls.some(url => url.includes('/cirurgias/'))).toBe(false);
  expect(storage.databases).toEqual(databases);
});

test('CA-SURG-04/07: telas em telefone e tablet sem barreiras graves', async ({ page }) => {
  test.setTimeout(90000);
  await login(page);
  const detail = await order(page);
  for (const viewport of [{ width: 390, height: 844 }, { width: 768, height: 1024 }]) {
    await page.setViewportSize(viewport);
    for (const url of [LIST, CREATE, detail]) {
      await page.goto(url);
      const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
      expect(result.violations.filter(v => ['serious', 'critical'].includes(v.impact))).toEqual([]);
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(viewport.width + 1);
    }
  }
});


test('CA-SURG-02: concessão revogada depois de abrir formulário', async ({page, browser}) => {
  await login(page, 'delegate');
  const detail = await order(page);
  await page.goto(CREATE);
  await page.getByLabel('Procedimento', {exact:true}).selectOption(PROCEDURE);
  const adminContext = await browser.newContext({baseURL: process.env.PWA_BASE_URL || 'http://127.0.0.1:8000'});
  try {
    const adminPage = await adminContext.newPage();
    await login(adminPage, 'admin');
    await adminPage.goto('/aegis-admin/pep/patientaccessgrant/07000000-0000-4000-8000-000000000004/delete/');
    await adminPage.locator('input[type=submit]').click();
    await expect(adminPage).toHaveURL(/\/aegis-admin\/pep\/patientaccessgrant\/$/);
    const posted = page.waitForResponse(response => response.url().endsWith(CREATE) && response.request().method()==='POST');
    await page.getByRole('button',{name:'Registrar solicitação'}).click();
    expect((await posted).status()).toBe(404);
    expect((await page.goto(detail)).status()).toBe(404);
    await page.goto(LIST);
    await expect(page.getByText('Pessoa Sintética SURG')).toHaveCount(0);
  } finally {
    await adminContext.close();
  }
});

const { test, expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;
const fs = require('node:fs/promises');

const URL = '/interop/exportar/';
const PATIENT = '12000000-0000-4000-8000-000000000001';
const NAME = 'Pessoa Sintética Interop E2E';

async function login(page, role = 'exporter') {
  await page.goto('/login/');
  await page.getByLabel('Usuário').fill(`ci-interop-${role}`);
  await page.getByLabel('Senha').fill(`ci-interop-${role}-password`);
  await page.getByRole('button', { name: 'Entrar' }).click();
  await expect(page).toHaveURL(/\/$/);
}

test('CA-INT-01/04: download contém somente o cadastro mínimo', async ({ page }) => {
  await login(page);
  const response = await page.goto(URL);
  expect(response.headers()['cache-control']).toContain('no-store');
  await page.getByLabel('Paciente', { exact: true }).selectOption(PATIENT);
  await page.getByLabel('Confirmo a exportação').check();
  const downloadPromise = page.waitForEvent('download');
  const responsePromise = page.waitForResponse((response) =>
    response.url().endsWith(URL) && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Baixar arquivo' }).click();
  const download = await downloadPromise;
  const attachment = await responsePromise;
  expect(attachment.headers()['cache-control']).toContain('no-store');
  expect(download.suggestedFilename()).toMatch(/^patient-export-[0-9a-f-]+\.json$/);
  const content = await fs.readFile(await download.path(), 'utf8');
  expect(JSON.parse(content)).toEqual({
    resourceType: 'Patient', id: PATIENT, active: true,
    name: [{ text: NAME }], birthDate: '1990-01-15',
  });
  expect(content).not.toContain('E2E-INTEROP-PRIVATE-ID');
});

test('CA-INT-02/03: formulário rejeita paciente fora do escopo e confirmação ausente', async ({ page }) => {
  await login(page, 'outsider');
  await page.goto(URL);
  await expect(page.getByRole('option', { name: new RegExp(NAME) })).toHaveCount(0);
  const token = await page.getByRole('main').locator('[name=csrfmiddlewaretoken]').inputValue();
  const rejected = await page.request.post(URL, {
    form: { patient: PATIENT, confirm: 'on', csrfmiddlewaretoken: token },
  });
  expect(rejected.headers()['content-disposition']).toBeUndefined();
  expect(await rejected.text()).toContain('Selecione um paciente disponível.');
  expect(await rejected.text()).not.toContain(NAME);
  const missingConfirmation = await page.request.post(URL, {
    form: { csrfmiddlewaretoken: token },
  });
  expect(await missingConfirmation.text()).toContain('Confirme a exportação');
});

test('CA-INT-06: PWA não armazena nem enfileira exportações offline', async ({ page, context }) => {
  await login(page);
  await page.goto(URL);
  await page.evaluate(() => navigator.serviceWorker.ready);
  await expect.poll(() => page.evaluate(() => Boolean(navigator.serviceWorker.controller))).toBe(true);
  await page.getByLabel('Paciente', { exact: true }).selectOption(PATIENT);
  await page.getByLabel('Confirmo a exportação').check();
  const databasesBefore = await page.evaluate(() => indexedDB.databases());
  let downloads = 0;
  page.on('download', () => downloads++);
  await context.setOffline(true);
  await Promise.all([
    page.waitForEvent('framenavigated', (frame) => frame === page.mainFrame()),
    page.getByRole('button', { name: 'Baixar arquivo' }).click(),
  ]);
  await page.waitForLoadState('load');
  await page.goto(URL);
  await expect(page.getByRole('heading', { name: /offline|conexão/i }).first()).toBeVisible();
  await expect(page.getByText(NAME)).toHaveCount(0);
  expect(downloads).toBe(0);
  expect(await page.evaluate(() => indexedDB.databases())).toEqual(databasesBefore);
  const stored = await page.evaluate(async () => {
    const records = [];
    for (const name of await caches.keys()) {
      const cache = await caches.open(name);
      for (const request of await cache.keys()) {
        const response = await cache.match(request);
        records.push({ url: request.url, body: await response.text() });
      }
    }
    return JSON.stringify(records);
  });
  expect(stored).not.toContain(NAME);
  expect(stored).not.toContain('/interop/');
  await context.setOffline(false);
});

test('formulário acessível em telefone e tablet', async ({ page }) => {
  await login(page);
  for (const viewport of [{ width: 390, height: 844 }, { width: 768, height: 1024 }]) {
    await page.setViewportSize(viewport);
    await page.goto(URL);
    await expect(page.getByRole('heading', { name: 'Exportar cadastro de paciente' })).toBeVisible();
    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
    expect(results.violations.filter((v) => ['serious', 'critical'].includes(v.impact))).toEqual([]);
    const width = await page.evaluate(() => document.documentElement.scrollWidth);
    expect(width).toBeLessThanOrEqual(viewport.width + 1);
  }
});

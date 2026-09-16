const { test, expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;

const LIST = '/lgpd/solicitacoes/';
const CREATE = `${LIST}nova/`;
const DETAIL = `${LIST}13000000-0000-4000-8000-000000000002/`;
const PATIENT = '13000000-0000-4000-8000-000000000001';
const NAME = 'Pessoa Sintética Compliance E2E';

async function login(page, role = 'operator') {
  await page.goto('/login/');
  await page.getByLabel('Usuário').fill(`ci-compliance-${role}`);
  await page.getByLabel('Senha').fill(`ci-compliance-${role}-password`);
  await page.getByRole('button', { name: 'Entrar' }).click();
  await expect(page).toHaveURL(/\/$/);
}

async function createRequest(page, summary) {
  await page.goto(CREATE);
  await page.getByLabel('Paciente', { exact: true }).selectOption(PATIENT);
  await page.getByLabel('Categoria').selectOption('ACCESS');
  await page.getByLabel('Resumo da solicitação').fill(summary);
  await page.getByRole('button', { name: 'Registrar solicitação' }).click();
  await expect(page.getByRole('heading', { name: 'Solicitação do titular', exact: true })).toBeVisible();
  return page.url();
}

test('CA-LGP-01/02/07: ciclo administrativo preserva histórico e escapa texto', async ({ page }) => {
  await login(page);
  const summary = '<script>window.lgpLeak=1</script> Resumo sintético';
  await createRequest(page, summary);
  await expect(page.getByText(summary, { exact: true })).toBeVisible();
  expect(await page.evaluate(() => window.lgpLeak)).toBeUndefined();
  await page.getByRole('link', { name: 'Iniciar análise' }).click();
  await page.getByLabel('Nota de atendimento').fill('Análise sintética iniciada');
  await page.getByRole('button', { name: 'Registrar andamento' }).click();
  await page.getByRole('link', { name: 'Encerrar administrativamente' }).click();
  await page.getByRole('button', { name: 'Registrar andamento' }).click();
  await expect(page.getByText('Registre uma nota de atendimento para encerrar a solicitação.')).toBeVisible();
  await page.getByLabel('Nota de atendimento').fill('Encerramento sintético registrado');
  await page.getByRole('button', { name: 'Registrar andamento' }).click();
  for (const state of ['Recebida', 'Em análise', 'Encerrada administrativamente']) {
    await expect(page.getByRole('heading', { name: state, exact: true })).toBeVisible();
  }
  await expect(page.getByRole('link', { name: 'Encerrar administrativamente' })).toHaveCount(0);
});

test('CA-LGP-03: operador fora do escopo não vê solicitação ou paciente', async ({ page }) => {
  await login(page, 'outsider');
  await page.goto(LIST);
  await expect(page.getByText(NAME)).toHaveCount(0);
  const response = await page.goto(DETAIL);
  expect(response.status()).toBe(404);
  expect(response.headers()['cache-control']).toContain('no-store');
  expect(await response.text()).not.toContain('Resumo sintético');
  await page.goto(CREATE);
  await expect(page.getByRole('option', { name: new RegExp(NAME) })).toHaveCount(0);
});

test('CA-LGP-04: formulário antigo recebe conflito sem sobrescrever o andamento', async ({ page, context }) => {
  await login(page);
  const detail = await createRequest(page, 'Solicitação sintética de concorrência');
  await page.getByRole('link', { name: 'Iniciar análise' }).click();
  const stale = await context.newPage();
  await stale.goto(page.url());
  await page.getByLabel('Nota de atendimento').fill('Nota vencedora');
  await page.getByRole('button', { name: 'Registrar andamento' }).click();
  await stale.getByLabel('Nota de atendimento').fill('Nota obsoleta');
  const conflict = stale.waitForResponse((r) => r.request().method() === 'POST');
  await stale.getByRole('button', { name: 'Registrar andamento' }).click();
  expect((await conflict).status()).toBe(409);
  await expect(stale.getByText('Esta solicitação foi atualizada. Consulte o histórico antes de continuar.').first()).toBeVisible();
  await page.goto(detail);
  await expect(page.getByText('Nota vencedora', { exact: true })).toBeVisible();
  await expect(page.getByText('Nota obsoleta', { exact: true })).toHaveCount(0);
  await stale.close();
});

test('CA-LGP-06: offline não confirma nem armazena solicitação', async ({ page, context }) => {
  await login(page);
  await page.goto(CREATE);
  await page.evaluate(() => navigator.serviceWorker.ready);
  await expect.poll(() => page.evaluate(() => Boolean(navigator.serviceWorker.controller))).toBe(true);
  await page.getByLabel('Paciente', { exact: true }).selectOption(PATIENT);
  await page.getByLabel('Categoria').selectOption('OTHER');
  const marker = 'LGP-OFFLINE-SENSITIVE-MARKER';
  await page.getByLabel('Resumo da solicitação').fill(marker);
  const databases = await page.evaluate(() => indexedDB.databases());
  await context.setOffline(true);
  await Promise.all([
    page.waitForEvent('framenavigated', (frame) => frame === page.mainFrame()),
    page.getByRole('button', { name: 'Registrar solicitação' }).click(),
  ]);
  await page.waitForLoadState('load');
  await page.goto(LIST);
  await expect(page.getByRole('heading', { name: 'Você está sem conexão' })).toBeVisible();
  expect(await page.evaluate(() => indexedDB.databases())).toEqual(databases);
  const storage = await page.evaluate(async ({ marker, name }) => {
    const paths = [];
    let hasSensitiveContent = false;
    for (const cacheName of await caches.keys()) {
      const cache = await caches.open(cacheName);
      for (const request of await cache.keys()) {
        paths.push(new URL(request.url).pathname);
        const response = await cache.match(request);
        if (/text|json|javascript/.test(response.headers.get('content-type') || '')) {
          const body = await response.text();
          hasSensitiveContent ||= body.includes(marker) || body.includes(name);
        }
      }
    }
    const local = JSON.stringify({ local: { ...localStorage }, session: { ...sessionStorage } });
    hasSensitiveContent ||= local.includes(marker) || local.includes(name);
    return { paths, hasSensitiveContent };
  }, { marker, name: NAME });
  expect(storage.hasSensitiveContent).toBe(false);
  expect(storage.paths.some((path) => path.startsWith('/lgpd/'))).toBe(false);
  await context.setOffline(false);
});

test('lista, cadastro, detalhe e andamento acessíveis em telefone e tablet', async ({ page }) => {
  test.setTimeout(60000);
  await login(page);
  for (const viewport of [{ width: 390, height: 844 }, { width: 768, height: 1024 }]) {
    await page.setViewportSize(viewport);
    for (const url of [LIST, CREATE, DETAIL, `${DETAIL}transicao/`]) {
      await page.goto(url);
      const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
      expect(result.violations.filter((v) => ['serious', 'critical'].includes(v.impact))).toEqual([]);
      const sizes = await page.evaluate(() => ({ width: document.documentElement.scrollWidth, overflowing: [...document.querySelectorAll('body *')].filter((element) => element.getBoundingClientRect().right > innerWidth).map((element) => ({ tag: element.tagName, className: element.className, width: element.getBoundingClientRect().width, left: element.getBoundingClientRect().left, position: getComputedStyle(element).position })) }));
      expect(sizes.width, JSON.stringify({ url, ...sizes })).toBeLessThanOrEqual(viewport.width + 1);
    }
  }
});

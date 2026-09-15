const { test, expect } = require('@playwright/test');

const RX_ADMIN = {
  username: 'ci-rx-accessibility',
  password: 'ci-rx-accessibility-password',
};

const RX_CACHE_PREFIXES = [
  '/prescricoes/',
  '/dispensacoes/',
  '/medicamentos/',
  '/estoque-farmacia/',
  '/dispensar/',
];

async function login(page) {
  await page.goto('/login/');
  await page.getByLabel('Usuário').fill(RX_ADMIN.username);
  await page.getByLabel('Senha').fill(RX_ADMIN.password);
  await page.getByRole('button', { name: 'Entrar' }).click();
  await expect(page).toHaveURL(/\/$/);
}

async function waitForServiceWorkerControl(page) {
  await page.evaluate(async () => {
    if (!('serviceWorker' in navigator)) throw new Error('Service Worker indisponível');
    await navigator.serviceWorker.ready;
  });

  const alreadyControlled = await page.evaluate(() => Boolean(navigator.serviceWorker.controller));
  if (!alreadyControlled) {
    await page.reload();
  }

  await expect.poll(async () => page.evaluate(() => Boolean(navigator.serviceWorker.controller))).toBe(true);
}

async function cachedPaths(page) {
  return page.evaluate(async () => {
    const paths = [];
    for (const cacheName of await caches.keys()) {
      const cache = await caches.open(cacheName);
      for (const request of await cache.keys()) {
        paths.push(new URL(request.url).pathname);
      }
    }
    return paths;
  });
}

async function expectNoRxCache(page) {
  const paths = await cachedPaths(page);
  for (const prefix of RX_CACHE_PREFIXES) {
    expect(
      paths.some((path) => path.startsWith(prefix)),
      `${prefix} não pode estar no Cache Storage`,
    ).toBe(false);
  }
}

async function expectNoOfflineQueueDatabase(page) {
  const exists = await page.evaluate(async () =>
    (await indexedDB.databases()).some((database) => database.name === 'aegisshare-offline'),
  );
  expect(exists).toBe(false);
}

async function selectFirstPopulated(select) {
  const value = await select.locator('option').evaluateAll((options) => {
    const option = options.find((item) => item.value);
    return option ? option.value : null;
  });
  expect(value).toBeTruthy();
  await select.selectOption(value);
}

test('superfícies RX atuais permanecem network-only e fora do cache/fila offline', async ({
  page,
  context,
}) => {
  await login(page);

  await page.goto('/medicamentos/');
  await expect(page.getByRole('heading', { name: 'Catálogo de medicamentos' })).toBeVisible();
  await expect(page.getByText('Medicamento Sintético Acessibilidade')).toBeVisible();

  await page.goto('/estoque-farmacia/');
  await expect(page.getByRole('heading', { name: 'Estoque farmacêutico' })).toBeVisible();
  await expect(page.getByText('Medicamento Sintético Acessibilidade')).toBeVisible();

  await page.goto('/prescricoes/');
  await expect(page.getByRole('heading', { name: 'Prescrições' })).toBeVisible();
  await expect(page.getByText('Paciente Sintético RX E2E').first()).toBeVisible();

  await page.goto('/dispensacoes/');
  await expect(page.getByRole('heading', { name: 'Dispensações' })).toBeVisible();

  await waitForServiceWorkerControl(page);
  await expectNoRxCache(page);
  await expectNoOfflineQueueDatabase(page);

  await context.setOffline(true);
  await page.goto('/prescricoes/?pwa-rx-offline-ci=1');
  await expect(page.getByRole('heading', { name: 'Você está sem conexão' })).toBeVisible();
  await expect(page.getByText('Nenhum dado clínico identificável')).toBeVisible();
  await expect(page.getByText('Paciente Sintético RX E2E')).toHaveCount(0);
  await expect(page.getByText('Medicamento Sintético Acessibilidade')).toHaveCount(0);
  await context.setOffline(false);

  await expectNoRxCache(page);
  await expectNoOfflineQueueDatabase(page);
});

test('criação e edição de medicamento não entram em cache nem fila offline', async ({
  page,
  context,
}) => {
  await login(page);
  await waitForServiceWorkerControl(page);

  const suffix = Date.now().toString();
  const code = `E2E-RX-NET-${suffix}`;
  const name = `Medicamento Network Only ${suffix}`;
  const updatedPresentation = `Comprimido atualizado ${suffix}`;
  const offlineCode = `E2E-RX-OFFLINE-${suffix}`;
  const offlineName = `Medicamento Offline Não Persistido ${suffix}`;

  await page.goto('/medicamentos/novo/');
  await expect(page.getByRole('heading', { name: 'Novo medicamento' })).toBeVisible();
  await page.getByLabel('Código interno').fill(code);
  await page.getByLabel('Medicamento').fill(name);
  await page.getByLabel('Apresentação').fill('Comprimido');
  await page.getByLabel('Concentração / força').fill('10 mg');
  await page.getByLabel('Via sugerida (informativa)').fill('Oral');
  await page.getByLabel('Unidade de dispensação').fill('unidade');
  await page.getByRole('button', { name: 'Salvar medicamento' }).click();

  await expect(page).toHaveURL(/\/medicamentos\/$/);
  await expect(page.getByText('Medicamento cadastrado com sucesso.')).toBeVisible();
  const createdRow = page.getByRole('row').filter({ hasText: name });
  await expect(createdRow).toBeVisible();
  await expectNoRxCache(page);
  await expectNoOfflineQueueDatabase(page);

  await createdRow.getByRole('link', { name: 'Editar' }).click();
  await expect(page.getByRole('heading', { name: 'Editar medicamento' })).toBeVisible();
  await page.getByLabel('Apresentação').fill(updatedPresentation);
  await page.getByRole('button', { name: 'Salvar medicamento' }).click();

  await expect(page).toHaveURL(/\/medicamentos\/$/);
  await expect(page.getByText('Medicamento atualizado com sucesso.')).toBeVisible();
  const updatedRow = page.getByRole('row').filter({ hasText: name });
  await expect(updatedRow).toContainText(updatedPresentation);
  await expectNoRxCache(page);
  await expectNoOfflineQueueDatabase(page);

  await context.setOffline(true);
  const offlineMutation = await page.evaluate(
    async ({ code: attemptedCode, name: attemptedName }) => {
      try {
        const payload = new URLSearchParams({
          code: attemptedCode,
          name: attemptedName,
          presentation: 'Comprimido',
          strength_text: '5 mg',
          route_hint: 'Oral',
          dispense_unit: 'unidade',
          active: 'on',
        });
        const response = await fetch('/medicamentos/novo/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: payload.toString(),
          credentials: 'same-origin',
        });
        return { resolved: true, status: response.status };
      } catch (error) {
        return { resolved: false, errorName: error.name };
      }
    },
    { code: offlineCode, name: offlineName },
  );
  expect(offlineMutation.resolved).toBe(false);
  await context.setOffline(false);

  await expectNoRxCache(page);
  await expectNoOfflineQueueDatabase(page);
  await page.goto('/medicamentos/');
  await expect(page.getByText(offlineName)).toHaveCount(0);
});

test('dispensação offline falha e não é enfileirada nem persistida', async ({ page, context }) => {
  await login(page);
  await waitForServiceWorkerControl(page);

  await page.goto('/dispensacoes/');
  const rowsBefore = await page.getByRole('table').getByRole('row').count();

  await page.goto('/prescricoes/');
  const validatedRow = page.getByRole('row').filter({ hasText: 'Validada' }).first();
  await expect(validatedRow).toBeVisible();
  await validatedRow.getByRole('link', { name: 'Abrir' }).click();
  await page.getByRole('link', { name: 'Dispensar' }).click();
  await expect(page.getByRole('heading', { name: 'Dispensação por lote' })).toBeVisible();

  await selectFirstPopulated(page.getByLabel('Item prescrito'));
  await selectFirstPopulated(page.getByLabel('Lote'));
  await page.getByLabel('Quantidade').fill('1');
  await page.getByLabel('Confirmo a dispensação e a baixa de estoque').check();

  await context.setOffline(true);
  const offlineMutation = await page.evaluate(async () => {
    const form = document.querySelector('form[method="post"]');
    try {
      const response = await fetch(window.location.pathname, {
        method: 'POST',
        body: new FormData(form),
        credentials: 'same-origin',
      });
      return { resolved: true, status: response.status };
    } catch (error) {
      return { resolved: false, errorName: error.name };
    }
  });
  expect(offlineMutation.resolved).toBe(false);
  await context.setOffline(false);

  await expectNoRxCache(page);
  await expectNoOfflineQueueDatabase(page);
  await page.goto('/dispensacoes/');
  const rowsAfter = await page.getByRole('table').getByRole('row').count();
  expect(rowsAfter).toBe(rowsBefore);
});

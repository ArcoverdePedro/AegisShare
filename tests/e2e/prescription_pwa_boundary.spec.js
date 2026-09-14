const { test, expect } = require('@playwright/test');

const RX_ADMIN = {
  username: 'ci-rx-accessibility',
  password: 'ci-rx-accessibility-password',
};

const RX_CACHE_PREFIXES = [
  '/prescricoes/',
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

  await waitForServiceWorkerControl(page);
  await expectNoRxCache(page);

  const offlineDatabaseBefore = await page.evaluate(async () =>
    (await indexedDB.databases()).some((database) => database.name === 'aegisshare-offline'),
  );
  expect(offlineDatabaseBefore).toBe(false);

  await context.setOffline(true);
  await page.goto('/medicamentos/?pwa-rx-offline-ci=1');
  await expect(page.getByRole('heading', { name: 'Você está sem conexão' })).toBeVisible();
  await expect(page.getByText('Nenhum dado clínico identificável')).toBeVisible();
  await expect(page.getByText('Medicamento Sintético Acessibilidade')).toHaveCount(0);
  await context.setOffline(false);

  await expectNoRxCache(page);
  const offlineDatabaseAfter = await page.evaluate(async () =>
    (await indexedDB.databases()).some((database) => database.name === 'aegisshare-offline'),
  );
  expect(offlineDatabaseAfter).toBe(false);
});

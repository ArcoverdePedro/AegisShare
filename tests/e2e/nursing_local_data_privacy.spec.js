const { test, expect } = require('@playwright/test');

const NURSE = {
  username: 'ci-nursing-offline',
  password: 'ci-nursing-offline-password',
};
const OPEN_ENCOUNTER_ID = '20000000-0000-4000-8000-000000000004';
const VITALS_FORM_URL = `/enfermagem/encontros/${OPEN_ENCOUNTER_ID}/sinais-vitais/novo/`;
const ENCOUNTER_URL = `/enfermagem/encontros/${OPEN_ENCOUNTER_ID}/`;
const SYNC_URL_PATTERN = '**/enfermagem/sinais-vitais/sincronizar/';
const SYNC_PRIVACY_MARKER = '37.77';
const LOGOUT_PRIVACY_MARKER = '37.78';

async function login(page) {
  await page.goto('/login/');
  await page.getByLabel('Usuário').fill(NURSE.username);
  await page.getByLabel('Senha').fill(NURSE.password);
  await page.getByRole('button', { name: 'Entrar' }).click();
  await expect(page).toHaveURL(/\/$/);
}

async function openVitalsForm(page) {
  await page.goto(VITALS_FORM_URL);
  await expect(page.getByRole('heading', { name: 'Registrar sinais vitais' })).toBeVisible();
  await expect.poll(() => page.evaluate(() => Boolean(window.AegisOfflineQueue))).toBe(true);
  await page.evaluate(() => window.AegisOfflineQueue.clear());
}

async function rawOfflineQueue(page) {
  return page.evaluate(async () => {
    const database = await new Promise((resolve, reject) => {
      const request = indexedDB.open(window.AegisOfflineQueue.databaseName, 1);
      request.onerror = () => reject(request.error);
      request.onsuccess = () => resolve(request.result);
    });
    try {
      const records = await new Promise((resolve, reject) => {
        const transaction = database.transaction('queue', 'readonly');
        const request = transaction.objectStore('queue').getAll();
        request.onerror = () => reject(request.error);
        request.onsuccess = () => resolve(request.result);
      });
      return JSON.stringify(records);
    } finally {
      database.close();
    }
  });
}

async function cacheSnapshot(page) {
  return page.evaluate(async () => {
    const entries = [];
    for (const cacheName of await caches.keys()) {
      const cache = await caches.open(cacheName);
      for (const request of await cache.keys()) {
        const response = await cache.match(request);
        entries.push({
          cacheName,
          method: request.method,
          pathname: new URL(request.url).pathname,
          body: response ? await response.clone().text() : '',
        });
      }
    }
    return entries;
  });
}

async function queueMetadata(page) {
  return page.evaluate(() => window.AegisOfflineQueue.listMetadata());
}

test('sinais vitais offline não deixam plaintext clínico no armazenamento local ou console', async ({ page, context }) => {
  const consoleMessages = [];
  page.on('console', (message) => consoleMessages.push(message.text()));

  await login(page);
  await openVitalsForm(page);
  await context.setOffline(true);
  await page.getByLabel('Temperatura (°C)').fill(SYNC_PRIVACY_MARKER);
  await page.getByRole('button', { name: 'Confirmar registro' }).click();

  await expect.poll(async () => (await queueMetadata(page)).length).toBe(1);
  await expect.poll(async () => (await queueMetadata(page))[0]?.status).toBe('pending');

  const rawQueue = await rawOfflineQueue(page);
  expect(rawQueue).not.toContain(SYNC_PRIVACY_MARKER);
  expect(rawQueue).toContain('payload_ciphertext');
  expect(rawQueue).toContain('payload_iv');

  const cachedEntries = await cacheSnapshot(page);
  expect(JSON.stringify(cachedEntries)).not.toContain(SYNC_PRIVACY_MARKER);
  expect(cachedEntries.some((entry) => entry.pathname.startsWith('/enfermagem/'))).toBe(false);
  expect(consoleMessages.join('\n')).not.toContain(SYNC_PRIVACY_MARKER);

  await context.setOffline(false);
  await page.evaluate(() => window.dispatchEvent(new Event('online')));
  await expect.poll(async () => (await queueMetadata(page)).length).toBe(0);

  await page.goto(ENCOUNTER_URL);
  await expect(page.getByRole('row').filter({ hasText: /37[,.]77 °C/ })).toHaveCount(1);
  expect(consoleMessages.join('\n')).not.toContain(SYNC_PRIVACY_MARKER);
});

test('logout remove a fila clínica pendente da sessão', async ({ page, context }) => {
  await login(page);
  await openVitalsForm(page);
  await context.setOffline(true);
  await page.getByLabel('Temperatura (°C)').fill(LOGOUT_PRIVACY_MARKER);
  await page.getByRole('button', { name: 'Confirmar registro' }).click();

  await expect.poll(async () => (await queueMetadata(page)).length).toBe(1);
  expect(await rawOfflineQueue(page)).not.toContain(LOGOUT_PRIVACY_MARKER);
  expect(
    await page.evaluate(async () =>
      (await indexedDB.databases()).some((database) => database.name === 'aegisshare-offline')
    )
  ).toBe(true);

  await page.route(SYNC_URL_PATTERN, (route) => route.abort('failed'));
  await context.setOffline(false);
  await page.evaluate(() => window.dispatchEvent(new Event('online')));
  await expect.poll(async () => (await queueMetadata(page))[0]?.status).toBe('pending');

  await page.getByRole('button', { name: new RegExp(NURSE.username) }).click();
  await page.getByRole('button', { name: 'Sair' }).click();
  await expect(page.getByRole('link', { name: 'Entrar' })).toBeVisible();

  await expect.poll(async () => page.evaluate(async () =>
    !(await indexedDB.databases()).some((database) => database.name === 'aegisshare-offline')
  )).toBe(true);
});

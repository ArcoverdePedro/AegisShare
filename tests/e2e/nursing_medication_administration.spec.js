const { test, expect } = require('@playwright/test');

const NURSE = {
  username: 'ci-nursing-offline',
  password: 'ci-nursing-offline-password',
};
const OPEN_ENCOUNTER_ID = '20000000-0000-4000-8000-000000000004';
const DISPENSE_ITEM_ID = '80000000-0000-4000-8000-000000000004';
const MEDICATION_LIST_URL = `/enfermagem/encontros/${OPEN_ENCOUNTER_ID}/medicacoes/`;
const ADMINISTER_URL = `/enfermagem/medicacoes/${DISPENSE_ITEM_ID}/administrar/`;

async function login(page) {
  await page.goto('/login/');
  await page.getByLabel('Usuário').fill(NURSE.username);
  await page.getByLabel('Senha').fill(NURSE.password);
  await page.getByRole('button', { name: 'Entrar' }).click();
  await expect(page).toHaveURL(/\/$/);
}

async function openAdministration(page) {
  await page.goto(ADMINISTER_URL);
  await expect(page.getByRole('heading', { name: 'Confirmar administração' })).toBeVisible();
  await expect(page.getByText('Medicamento Sintético Administração E2E')).toBeVisible();
  await expect(page.getByText(/NUR-E2E-LOT-001/)).toBeVisible();
}

async function fillAdministration(page) {
  await page.getByLabel('Dose efetivamente administrada').fill('10');
  await page.getByLabel('Unidade da dose administrada').fill('mg');
  await page.getByLabel(/Confirmo que a dose informada foi efetivamente administrada/).check();
}

async function offlineStorageSnapshot(page) {
  return page.evaluate(async () => {
    const databases = await indexedDB.databases();
    const databaseNames = databases.map((database) => database.name).filter(Boolean);
    let queueRecords = [];

    if (databaseNames.includes('aegisshare-offline')) {
      const database = await new Promise((resolve, reject) => {
        const request = indexedDB.open('aegisshare-offline');
        request.onerror = () => reject(request.error);
        request.onsuccess = () => resolve(request.result);
      });
      try {
        if (database.objectStoreNames.contains('queue')) {
          queueRecords = await new Promise((resolve, reject) => {
            const transaction = database.transaction('queue', 'readonly');
            const request = transaction.objectStore('queue').getAll();
            request.onerror = () => reject(request.error);
            request.onsuccess = () => resolve(request.result);
          });
        }
      } finally {
        database.close();
      }
    }

    const cachedRequests = [];
    for (const cacheName of await caches.keys()) {
      const cache = await caches.open(cacheName);
      for (const request of await cache.keys()) {
        cachedRequests.push({ method: request.method, url: request.url });
      }
    }

    return {
      queue: JSON.stringify(queueRecords),
      cachedRequests,
    };
  });
}

test('administrar medicamento online preserva lote e prescrição', async ({ page }) => {
  await login(page);
  await openAdministration(page);
  await fillAdministration(page);

  await page.getByRole('button', { name: 'Confirmar administração' }).click();

  await expect(page).toHaveURL(MEDICATION_LIST_URL);
  await expect(page.getByText('Administração registrada com sucesso.')).toBeVisible();
  await expect(page.getByText('Medicamento Sintético Administração E2E')).toBeVisible();
  await expect(page.getByText(/NUR-E2E-LOT-001/)).toBeVisible();
});

test('administração não funciona offline', async ({ page, context }) => {
  await login(page);
  await openAdministration(page);
  await fillAdministration(page);

  const operationKey = await page.locator('input[name="operation_key"]').inputValue();
  expect(await page.evaluate(() => typeof window.AegisOfflineQueue)).toBe('undefined');
  await expect(page.locator('[data-nursing-vitals-offline]')).toHaveCount(0);

  const failedRequestPromise = page.waitForEvent('requestfailed', {
    predicate: (request) => request.method() === 'POST' && request.url().includes(ADMINISTER_URL),
  });

  await context.setOffline(true);
  await page.getByRole('button', { name: 'Confirmar administração' }).click({ noWaitAfter: true });
  const failedRequest = await failedRequestPromise;
  expect(failedRequest.failure()?.errorText || '').toContain('ERR_INTERNET_DISCONNECTED');

  await context.setOffline(false);
  await page.goto(ADMINISTER_URL);
  const storage = await offlineStorageSnapshot(page);

  expect(storage.queue).not.toContain(operationKey);
  expect(storage.queue).not.toContain('nursing.medication');
  expect(storage.cachedRequests.some((request) => request.method === 'POST')).toBe(false);
  await expect(page.getByText('Administração registrada com sucesso.')).toHaveCount(0);
});

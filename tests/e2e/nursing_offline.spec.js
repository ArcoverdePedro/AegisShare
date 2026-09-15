const { test, expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;

const NURSE = {
  username: 'ci-nursing-offline',
  password: 'ci-nursing-offline-password',
};
const OPEN_ENCOUNTER_ID = '20000000-0000-4000-8000-000000000004';
const CLOSED_ENCOUNTER_ID = '20000000-0000-4000-8000-000000000005';
const VITALS_FORM_URL = `/enfermagem/encontros/${OPEN_ENCOUNTER_ID}/sinais-vitais/novo/`;
const ENCOUNTER_URL = `/enfermagem/encontros/${OPEN_ENCOUNTER_ID}/`;
const SYNC_URL_PATTERN = '**/enfermagem/sinais-vitais/sincronizar/';

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

async function expectNoSeriousAxeViolations(page) {
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .analyze();
  const blocking = results.violations.filter(
    (violation) => violation.impact === 'critical' || violation.impact === 'serious'
  );
  expect(blocking, JSON.stringify(blocking, null, 2)).toEqual([]);
}

async function expectNoPageOverflow(page) {
  const sizes = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    viewportWidth: window.innerWidth,
  }));
  expect(sizes.scrollWidth).toBeLessThanOrEqual(sizes.viewportWidth + 1);
}

async function queueMetadata(page) {
  return page.evaluate(() => window.AegisOfflineQueue.listMetadata());
}

test('piloto de sinais vitais permanece cifrado e acessível nos estados online, pendente e sincronizado', async ({ page, context }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page);
  await openVitalsForm(page);

  await expectNoSeriousAxeViolations(page);
  await expectNoPageOverflow(page);

  await context.setOffline(true);
  await page.getByLabel('Temperatura (°C)').fill('36.51');
  await page.getByRole('button', { name: 'Confirmar registro' }).click();

  const offlineStatus = page.locator('[data-offline-status]');
  await expect(offlineStatus).toContainText('Ainda não foi confirmado no prontuário');
  await expect.poll(async () => (await queueMetadata(page)).length).toBe(1);
  await expect.poll(async () => (await queueMetadata(page))[0]?.status).toBe('pending');
  await expectNoSeriousAxeViolations(page);
  await expectNoPageOverflow(page);

  const rawQueue = await page.evaluate(async () => {
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
  expect(rawQueue).not.toContain('36.51');

  await context.setOffline(false);
  await page.evaluate(() => window.dispatchEvent(new Event('online')));
  await expect(offlineStatus).toContainText('foram confirmados no prontuário');
  await expect.poll(async () => (await queueMetadata(page)).length).toBe(0);
  await expectNoSeriousAxeViolations(page);
  await expectNoPageOverflow(page);

  await page.goto(ENCOUNTER_URL);
  await expect(page.getByRole('row').filter({ hasText: /36[,.]51 °C/ })).toHaveCount(1);
});

test('encontro encerrado mantém envelope cifrado em conflito para revisão explícita', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page);
  await openVitalsForm(page);

  await page.evaluate(async ({ closedEncounterId }) => {
    const form = document.querySelector('[data-nursing-vitals-offline]');
    await window.AegisOfflineQueue.enqueue({
      operationType: 'nursing.vitals.record',
      userSessionFingerprint: form.dataset.sessionFingerprint,
      payload: {
        encounter_id: closedEncounterId,
        recorded_at: form.elements.namedItem('recorded_at').value,
        replaces_id: null,
        measurements: { temperature_c: '39.99' },
      },
    });
    window.dispatchEvent(new Event('online'));
  }, { closedEncounterId: CLOSED_ENCOUNTER_ID });

  await expect.poll(async () => (await queueMetadata(page))[0]?.status).toBe('conflict');
  await expect(page.locator('[data-offline-status]')).toContainText('exigem revisão');
  await expectNoSeriousAxeViolations(page);
  await expectNoPageOverflow(page);

  const serialized = await page.evaluate(async () => {
    const metadata = await window.AegisOfflineQueue.listMetadata({ status: 'conflict' });
    return JSON.stringify(metadata);
  });
  expect(serialized).not.toContain('39.99');
});

test('resposta perdida após commit é reenviada sem duplicar o registro', async ({ page, context }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page);
  await openVitalsForm(page);

  let firstSync = true;
  await page.route(SYNC_URL_PATTERN, async (route) => {
    if (!firstSync) {
      await route.continue();
      return;
    }
    firstSync = false;
    await route.fetch();
    await route.abort('failed');
  });

  await context.setOffline(true);
  await page.getByLabel('Frequência cardíaca (bpm)').fill('83');
  await page.getByRole('button', { name: 'Confirmar registro' }).click();
  await expect.poll(async () => (await queueMetadata(page))[0]?.status).toBe('pending');

  await context.setOffline(false);
  await page.evaluate(() => window.dispatchEvent(new Event('online')));
  await expect.poll(async () => (await queueMetadata(page))[0]?.retry_count).toBe(1);
  await expect.poll(async () => (await queueMetadata(page))[0]?.status).toBe('pending');

  await page.unroute(SYNC_URL_PATTERN);
  await page.evaluate(() => window.dispatchEvent(new Event('online')));
  await expect.poll(async () => (await queueMetadata(page)).length).toBe(0);

  await page.goto(ENCOUNTER_URL);
  await expect(page.getByRole('row').filter({ hasText: '83 bpm' })).toHaveCount(1);
});

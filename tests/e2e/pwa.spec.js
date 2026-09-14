const { test, expect } = require('@playwright/test');

const SENSITIVE_CACHE_PREFIXES = [
  '/pacientes/',
  '/encontros/',
  '/evolucoes/',
  '/arquivos/',
  '/aegis-admin/',
  '/api/',
];

test('registers the PWA shell and serves only the generic offline fallback', async ({ page, context }) => {
  await page.goto('/');

  const manifest = page.locator('link[rel="manifest"]');
  await expect(manifest).toHaveAttribute('href', '/manifest.webmanifest');

  await page.evaluate(async () => {
    if (!('serviceWorker' in navigator)) throw new Error('Service Worker indisponível');
    await navigator.serviceWorker.ready;
  });

  await expect.poll(async () => page.evaluate(() => Boolean(navigator.serviceWorker.controller))).toBe(true);

  await context.setOffline(true);
  await page.goto('/sobre/?pwa-offline-ci=1');
  await expect(page.getByRole('heading', { name: 'Você está sem conexão' })).toBeVisible();
  await expect(page.getByText('Nenhum dado clínico identificável')).toBeVisible();
  await context.setOffline(false);

  const cachedPaths = await page.evaluate(async () => {
    const paths = [];
    for (const cacheName of await caches.keys()) {
      const cache = await caches.open(cacheName);
      for (const request of await cache.keys()) {
        paths.push(new URL(request.url).pathname);
      }
    }
    return paths;
  });

  for (const prefix of SENSITIVE_CACHE_PREFIXES) {
    expect(cachedPaths.some((path) => path.startsWith(prefix)), `${prefix} não pode estar no cache`).toBe(false);
  }
});

test('manifest exposes installable standalone metadata and both required icons', async ({ request }) => {
  const response = await request.get('/manifest.webmanifest');
  expect(response.ok()).toBe(true);

  const manifest = await response.json();
  expect(manifest.name).toBe('AegisShare HIS');
  expect(manifest.short_name).toBe('AegisShare');
  expect(manifest.start_url).toBe('/');
  expect(manifest.scope).toBe('/');
  expect(manifest.display).toBe('standalone');
  expect(manifest.orientation).toBe('portrait');
  expect(manifest.icons.map((icon) => icon.sizes)).toEqual(['192x192', '512x512']);

  for (const icon of manifest.icons) {
    const iconResponse = await request.get(icon.src);
    expect(iconResponse.ok()).toBe(true);
    expect(iconResponse.headers()['content-type']).toContain('image/png');
  }
});

test('offline queue stores only encrypted payloads and keeps the local key non-extractable', async ({ page }) => {
  await page.goto('/');
  await page.addScriptTag({ url: '/static/pwa/offline_queue.js' });

  const result = await page.evaluate(async () => {
    const sensitiveMarker = 'SYNTHETIC-PHI-MARKER-DO-NOT-PERSIST-IN-PLAINTEXT';
    const idempotencyKey = 'ci-pwa-encrypted-queue-001';
    const payload = {
      synthetic_patient_marker: sensitiveMarker,
      measurement: 123,
    };

    await window.AegisOfflineQueue.clear().catch(() => {});
    const envelope = await window.AegisOfflineQueue.enqueue({
      operationType: 'ci.synthetic.offline',
      userSessionFingerprint: 'ci-session-fingerprint',
      payload,
      idempotencyKey,
    });
    const decrypted = await window.AegisOfflineQueue.readPayload(idempotencyKey);
    const metadata = await window.AegisOfflineQueue.listMetadata({ status: 'pending' });

    const raw = await new Promise((resolve, reject) => {
      const openRequest = indexedDB.open(window.AegisOfflineQueue.databaseName, 1);
      openRequest.onerror = () => reject(openRequest.error);
      openRequest.onsuccess = () => {
        const db = openRequest.result;
        const transaction = db.transaction(['queue', 'keys'], 'readonly');
        const queueRequest = transaction.objectStore('queue').get(idempotencyKey);
        const keyRequest = transaction.objectStore('keys').get('payload-aes-gcm-v1');
        transaction.onerror = () => reject(transaction.error);
        transaction.oncomplete = () => {
          const rawRecord = queueRequest.result;
          const keyRecord = keyRequest.result;
          db.close();
          resolve({
            rawRecord,
            serializedRecord: JSON.stringify(rawRecord),
            keyExtractable: keyRecord.key.extractable,
          });
        };
      };
    });

    let duplicateRejected = false;
    try {
      await window.AegisOfflineQueue.enqueue({
        operationType: 'ci.synthetic.offline',
        userSessionFingerprint: 'ci-session-fingerprint',
        payload,
        idempotencyKey,
      });
    } catch (_error) {
      duplicateRejected = true;
    }

    await window.AegisOfflineQueue.clear();

    return {
      sensitiveMarker,
      envelope,
      decrypted,
      metadata,
      raw,
      duplicateRejected,
    };
  });

  expect(result.envelope.status).toBe('pending');
  expect(result.envelope.retry_count).toBe(0);
  expect(result.envelope.payload_ciphertext).toBeTruthy();
  expect(result.envelope.payload_iv).toBeTruthy();
  expect(result.raw.rawRecord.payload).toBeUndefined();
  expect(result.raw.serializedRecord).not.toContain(result.sensitiveMarker);
  expect(result.raw.keyExtractable).toBe(false);
  expect(result.decrypted.synthetic_patient_marker).toBe(result.sensitiveMarker);
  expect(result.metadata).toEqual([
    expect.objectContaining({
      idempotency_key: 'ci-pwa-encrypted-queue-001',
      operation_type: 'ci.synthetic.offline',
      status: 'pending',
      retry_count: 0,
      crypto_version: 1,
    }),
  ]);
  expect(result.duplicateRejected).toBe(true);
});
